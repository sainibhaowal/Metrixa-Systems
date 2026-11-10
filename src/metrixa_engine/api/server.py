"""
FastAPI Backend Gateway for Metrixa Cockpit.
Provides REST APIs for Leads, Metrics, Artifacts, Tools, and Settings,
plus Server-Sent Events (SSE) for Real-Time Pipeline Progress and Streaming Logs.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import tempfile
import threading
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field
from typing import Literal
from sse_starlette.sse import EventSourceResponse

from metrixa_engine.config import settings
from metrixa_engine.crawler.web_crawler import AsyncWebsiteCrawler
from metrixa_engine.db import Database
from metrixa_engine.enrichment.contact_finder import ContactEnricher
from metrixa_engine.enrichment.scorer import LeadScorer
from metrixa_engine.entity_resolution.deduplicator import EntityDeduplicator
from metrixa_engine.llm.extractor import KPIExtractionPipeline
from metrixa_engine.models import email_status_label, normalize_email_status
from metrixa_engine.scrapers.dir_11880 import Dir11880Scraper
from metrixa_engine.scrapers.gelbe_seiten import GelbeSeitenScraper
from metrixa_engine.scrapers.osm_overpass import OSMOverpassScraper
from metrixa_engine.scrapers.search_discovery import SearchDiscoveryScraper
from metrixa_engine.scrapers.vdiv import VDIVScraper
from metrixa_engine.telemetry.evaluator import PipelineEvaluator
from metrixa_engine.telemetry.excel_exporter import ExcelExporter
from metrixa_engine.telemetry.google_sheets_sync import GoogleSheetsSync

db = Database()
_settings_persist_lock = threading.Lock()


class PipelineEventBus:
    """Pub/Sub event broadcaster using asyncio Queues for Server-Sent Events (SSE)."""

    def __init__(self) -> None:
        self.subscribers: list[asyncio.Queue] = []
        self.is_running = False
        self.current_stage = "IDLE"
        self.current_run_id: str | None = None
        self.stage_durations: dict[str, float] = {}

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        payload = {"type": event_type, **data}
        dead: list[asyncio.Queue] = []
        for q in self.subscribers:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        for dq in dead:
            self.unsubscribe(dq)


event_bus = PipelineEventBus()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Metrixa Cockpit API",
    description="Autonomous B2B LeadOps & Metering Intelligence Gateway for Metrixa Systems",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ============================================================================
# 1. METRICS & TELEMETRY APIS
# ============================================================================

_metrics_cache: dict[str, Any] = {}
_metrics_cache_time: float = 0.0
METRICS_CACHE_TTL = 4.0  # seconds in-memory TTL for sub-millisecond responses


@app.get("/api/metrics")
async def get_metrics():
    """Return live aggregate KPI metrics, tier distribution, ERP counts, and district shares."""
    global _metrics_cache, _metrics_cache_time
    import time

    now = time.time()
    if _metrics_cache and (now - _metrics_cache_time < METRICS_CACHE_TTL):
        _metrics_cache["pipeline_state"] = {
            "is_running": event_bus.is_running,
            "current_stage": event_bus.current_stage,
        }
        return _metrics_cache

    tel = db.get_pipeline_telemetry()
    with db.connect() as conn:
        erp_rows = conn.execute(
            """
            SELECT detected_erp_proptech FROM kpi_extractions k
            JOIN companies_golden c ON c.company_id = k.company_id
            WHERE c.pipeline_stage != 'DISQUALIFIED'
              AND detected_erp_proptech IS NOT NULL AND detected_erp_proptech != ''
            """
        ).fetchall()

        erp_counts: dict[str, int] = {}
        for r in erp_rows:
            for item in (r["detected_erp_proptech"] or "").split(","):
                clean = item.strip()
                if clean:
                    erp_counts[clean] = erp_counts.get(clean, 0) + 1

        dist_rows = conn.execute(
            """
            SELECT district, COUNT(*) as cnt
            FROM companies_golden
            WHERE pipeline_stage != 'DISQUALIFIED'
            GROUP BY district
            ORDER BY cnt DESC
            """
        ).fetchall()
        district_breakdown = [
            {"district": r["district"] or "Berlin", "count": r["cnt"]}
            for r in dist_rows
        ]

    data = {
        "status": "online",
        "raw_total": tel["raw_total"],
        "golden_total": tel["golden_qualified_total"],
        "tiers": tel["tiers"],
        "coverage": {
            "with_website": tel["with_website"],
            "with_customer_portal": tel["with_customer_portal"],
            "with_erp_stack": tel["with_erp_stack"],
            "with_decision_maker": tel["companies_with_decision_maker"],
            "with_personal_email": tel["companies_with_personal_email"],
            "with_public_personal_email": tel["companies_with_public_personal_email"],
            "with_pattern_email_candidate": tel[
                "companies_with_pattern_email_candidate"
            ],
            "with_linkedin": tel["companies_with_linkedin"],
            "crawled_pages": tel["crawled_pages_cnt"],
        },
        "erp_breakdown": erp_counts,
        "district_breakdown": district_breakdown,
        "pipeline_state": {
            "is_running": event_bus.is_running,
            "current_stage": event_bus.current_stage,
        },
    }
    _metrics_cache = data
    _metrics_cache_time = now
    return data


# ============================================================================
# 2. LEAD SEARCH, FILTERING & DOSSIER APIS
# ============================================================================


@app.get("/api/leads")
async def get_leads(
    q: str | None = Query(
        None, description="Search query across company name, decision maker, address"
    ),
    tier: str | None = Query(None, description="Tier A, Tier B, Tier C"),
    district: str | None = Query(None, description="Berlin Bezirk"),
    has_dm: bool | None = Query(None),
    has_email: bool | None = Query(None),
    has_erp: bool | None = Query(None),
    is_vdiv: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("metrixa_lead_score"),
    sort_dir: str = Query("desc"),
):
    """Paginated search & multi-facet filtering for Berlin property managers."""
    offset = (page - 1) * limit
    allowed_sorts = {
        "metrixa_lead_score": "c.metrixa_lead_score",
        "exact_units_managed": "k.exact_units_managed",
        "display_name": "c.display_name",
        "company_id": "c.company_id",
    }
    sort_col = allowed_sorts.get(sort_by, "c.metrixa_lead_score")
    sort_order = "ASC" if sort_dir.lower() == "asc" else "DESC"

    where_clauses = ["c.pipeline_stage != 'DISQUALIFIED'"]
    params: list[Any] = []

    if q:
        like_q = f"%{q.strip()}%"
        where_clauses.append(
            """(
                c.display_name LIKE ?
                OR c.street_address LIKE ?
                OR c.canonical_domain LIKE ?
                OR EXISTS (
                    SELECT 1 FROM decision_makers d
                    WHERE d.company_id = c.company_id AND (d.full_name LIKE ? OR d.personal_email LIKE ?)
                )
            )"""
        )
        params.extend([like_q, like_q, like_q, like_q, like_q])

    if tier:
        where_clauses.append("c.lead_tier LIKE ?")
        params.append(f"%{tier}%")

    if district:
        where_clauses.append("c.district LIKE ?")
        params.append(f"%{district}%")

    if is_vdiv is not None:
        where_clauses.append("c.is_vdiv_member = ?")
        params.append(1 if is_vdiv else 0)

    if has_erp:
        where_clauses.append(
            "(k.detected_erp_proptech IS NOT NULL AND k.detected_erp_proptech != '')"
        )

    if has_dm:
        where_clauses.append(
            "EXISTS (SELECT 1 FROM decision_makers d WHERE d.company_id = c.company_id)"
        )

    if has_email:
        where_clauses.append(
            "EXISTS (SELECT 1 FROM decision_makers d WHERE d.company_id = c.company_id AND d.personal_email IS NOT NULL AND d.personal_email != '')"
        )

    where_sql = " AND ".join(where_clauses)

    with db.connect() as conn:
        count_sql = f"""
            SELECT COUNT(*) FROM companies_golden c
            LEFT JOIN kpi_extractions k ON k.company_id = c.company_id
            WHERE {where_sql}
        """
        total = conn.execute(count_sql, params).fetchone()[0]

        data_sql = f"""
            SELECT
                c.company_id, c.display_name, c.legal_form, c.commercial_register_id,
                c.street_address, c.postal_code, c.city, c.district,
                c.phone_e164, c.website_url, c.canonical_domain,
                c.general_email, c.company_linkedin_url, c.is_vdiv_member,
                c.source_count, c.sources_csv, c.metrixa_lead_score, c.metrixa_lead_score, c.lead_tier,
                k.founding_year, k.exact_units_managed, k.units_evidence_quote,
                k.estimated_units_tier, k.employee_count_est,
                k.manages_weg, k.manages_miet, k.manages_gewerbe, k.manages_sev,
                k.has_customer_portal, k.detected_erp_proptech,
                k.incumbent_metering_signal, k.digital_maturity_score,
                k.qualification_reasoning,
                (SELECT d.full_name FROM decision_makers d WHERE d.company_id = c.company_id ORDER BY d.is_primary_contact DESC LIMIT 1) as decision_maker_name,
                (SELECT d.role FROM decision_makers d WHERE d.company_id = c.company_id ORDER BY d.is_primary_contact DESC LIMIT 1) as decision_maker_role,
                (SELECT d.personal_email FROM decision_makers d WHERE d.company_id = c.company_id ORDER BY d.is_primary_contact DESC LIMIT 1) as personal_email,
                (SELECT d.email_status FROM decision_makers d WHERE d.company_id = c.company_id ORDER BY d.is_primary_contact DESC LIMIT 1) as email_status,
                (SELECT d.linkedin_url FROM decision_makers d WHERE d.company_id = c.company_id ORDER BY d.is_primary_contact DESC LIMIT 1) as decision_maker_linkedin
            FROM companies_golden c
            LEFT JOIN kpi_extractions k ON k.company_id = c.company_id
            WHERE {where_sql}
            ORDER BY {sort_col} {sort_order}, c.is_vdiv_member DESC, c.source_count DESC
            LIMIT ? OFFSET ?
        """
        rows = [
            dict(r) for r in conn.execute(data_sql, params + [limit, offset]).fetchall()
        ]

    for row in rows:
        raw_status = row.get("email_status")
        row["email_status_code"] = normalize_email_status(raw_status)
        row["email_status"] = email_status_label(raw_status)

        # Attach formatted Lead ID (e.g. METRIXA-BER-0001)
        for idx, r in enumerate(rows, start=offset + 1):
            r["lead_id"] = f"METRIXA-BER-{r['company_id']:04d}"
            r["metrixa_lead_score"] = (
                r.get("metrixa_lead_score")
                if r.get("metrixa_lead_score") is not None
                else r.get("metrixa_lead_score", 0)
            )
            r["linkedin_url"] = (
                r["decision_maker_linkedin"] or r["company_linkedin_url"]
            )

    return {
        "items": rows,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit > 0 else 1,
    }


@app.get("/api/leads/{company_id}/evidence")
async def get_lead_evidence(company_id: int):
    """Retrieve full audit evidence dossier, verbatim Impressum quote, and crawled subpages."""
    with db.connect() as conn:
        company = conn.execute(
            "SELECT * FROM companies_golden WHERE company_id = ?", (company_id,)
        ).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        kpi = conn.execute(
            "SELECT * FROM kpi_extractions WHERE company_id = ?", (company_id,)
        ).fetchone()

        dms = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM decision_makers WHERE company_id = ? ORDER BY is_primary_contact DESC",
                (company_id,),
            ).fetchall()
        ]

        pages = [
            {
                "page_type": r["page_type"],
                "url": r["url"],
                "http_status": r["http_status"],
                "detected_erp": r["detected_erp_csv"],
                "detected_metering": r["detected_metering_csv"],
                "clean_markdown": (r["clean_markdown"] or "")[:2500],
            }
            for r in conn.execute(
                "SELECT page_type, url, http_status, detected_erp_csv, detected_metering_csv, clean_markdown FROM crawled_pages WHERE company_id = ?",
                (company_id,),
            ).fetchall()
        ]

        # Calculate exact 5-pillar points for the scorecard
        comp_d = dict(company)
        kpi_d = dict(kpi) if kpi else {}

        exact_u = kpi_d.get("exact_units_managed")
        tier_u = kpi_d.get("estimated_units_tier")
        s_scale = 6
        if (exact_u and exact_u >= 2500) or tier_u == "5,000+":
            s_scale = 35
        elif (exact_u and exact_u >= 1000) or tier_u == "1,000-5,000":
            s_scale = 28
        elif (exact_u and exact_u >= 300) or tier_u == "250-1,000":
            s_scale = 20
        elif comp_d.get("legal_form") in ("GmbH", "AG", "GmbH & Co. KG"):
            s_scale = 16

        m_weg = bool(kpi_d.get("manages_weg"))
        m_miet = bool(kpi_d.get("manages_miet"))
        s_focus = 25 if (m_weg and m_miet) else (20 if (m_weg or m_miet) else 15)

        s_digital = 0
        if kpi_d.get("detected_erp_proptech"):
            s_digital += 12
        if kpi_d.get("has_customer_portal"):
            s_digital += 5
        if comp_d.get("website_url"):
            s_digital += 3

        s_trust = (
            (5 if comp_d.get("is_vdiv_member") else 0)
            + (3 if comp_d.get("commercial_register_id") else 0)
            + 2
        )
        s_contact = (
            (4 if dms else 0)
            + (
                4
                if any(
                    d.get("personal_email")
                    and normalize_email_status(d.get("email_status")) == "PUBLIC_LISTED"
                    for d in dms
                )
                else 0
            )
            + 2
        )

        scorecard = {
            "scale_pts": min(35, s_scale),
            "focus_pts": min(25, s_focus),
            "digital_pts": min(20, s_digital),
            "trust_pts": min(10, s_trust),
            "contact_pts": min(10, s_contact),
            "total_score": comp_d.get("metrixa_lead_score")
            or comp_d.get("metrixa_lead_score", 0),
        }

    return {
        "company": comp_d,
        "kpi": kpi_d,
        "scorecard": scorecard,
        "decision_makers": [
            {
                **dm,
                "email_status_code": normalize_email_status(dm.get("email_status")),
                "email_status": email_status_label(dm.get("email_status")),
            }
            for dm in dms
        ],
        "crawled_pages": pages,
    }


# ============================================================================
# 3. REAL-TIME PIPELINE RUNNER & SERVER-SENT EVENTS (SSE)
# ============================================================================


class PipelineRunRequest(BaseModel):
    stage: str = Field(
        default="full",
        description="full | ingest | deduplicate | crawl | extract | enrich | export",
    )
    provider: str | None = Field(default="auto_fallback")
    city: str | None = Field(default="Berlin")
    limit: int | None = Field(default=None)
    reprocess_all: bool = Field(default=False)


active_pipeline_task: asyncio.Task | None = None


@app.post("/api/pipeline/cancel")
@app.post("/api/pipeline/stop")
async def cancel_pipeline_run():
    """Cancel / interrupt any actively running pipeline stage execution."""
    global active_pipeline_task
    run_id = event_bus.current_run_id

    if not event_bus.is_running and not (
        active_pipeline_task and not active_pipeline_task.done()
    ):
        return {
            "status": "idle",
            "message": "No pipeline execution currently in progress.",
        }

    if active_pipeline_task and not active_pipeline_task.done():
        active_pipeline_task.cancel()

    event_bus.is_running = False
    event_bus.current_stage = "IDLE"

    await event_bus.emit(
        "CANCELLED",
        {
            "run_id": run_id,
            "message": "Pipeline run was interrupted and cancelled by operator.",
        },
    )
    await event_bus.emit(
        "LOG",
        {
            "level": "WARN",
            "message": "Pipeline execution interrupted and stopped by user.",
        },
    )

    if run_id:
        try:
            with db.connect() as conn:
                conn.execute(
                    "UPDATE pipeline_runs SET status = 'CANCELLED', finished_at = ? WHERE run_id = ?",
                    (datetime.now(timezone.utc).isoformat(), run_id),
                )
        except Exception:
            pass

    _metrics_cache.clear()
    return {"status": "cancelled", "run_id": run_id}


async def record_and_emit_event(
    run_id: str,
    seq: int,
    stage: str,
    step_name: str,
    event_type: str,
    level: str,
    duration_ms: int,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Save event to SQLite and broadcast via event_bus for real-time frontend streaming."""
    try:
        db.record_run_event(
            run_id=run_id,
            seq=seq,
            stage=stage,
            step_name=step_name,
            event_type=event_type,
            level=level,
            duration_ms=duration_ms,
            message=message,
            payload=details,
        )
    except Exception:
        pass

    event_payload = {
        "run_id": run_id,
        "seq": seq,
        "time": datetime.now().strftime("%H:%M:%S"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "step_name": step_name,
        "event_type": event_type,
        "level": level,
        "duration_ms": duration_ms,
        "message": message,
        "details": details,
    }
    await event_bus.emit("LOG", event_payload)
    await event_bus.emit("AGENT_STEP", event_payload)


def _synthesize_and_save_events_for_run(
    run_dict: dict[str, Any],
) -> list[dict[str, Any]]:
    """Do not fabricate event telemetry for pipeline runs without recorded events."""
    return []


@app.post("/api/pipeline/run")
async def trigger_pipeline_run(req: PipelineRunRequest):
    """Trigger background pipeline stage execution and stream updates via SSE."""
    global active_pipeline_task
    if event_bus.is_running or (
        active_pipeline_task and not active_pipeline_task.done()
    ):
        raise HTTPException(status_code=409, detail="Pipeline run already in progress")

    import uuid

    run_id = f"run-{uuid.uuid4().hex[:8]}"
    event_bus.is_running = True
    event_bus.current_run_id = run_id
    event_bus.stage_durations = {}
    event_bus.current_stage = "INGEST" if req.stage == "full" else req.stage.upper()

    async def _execute_task():
        global active_pipeline_task
        started_ts = datetime.now(timezone.utc).isoformat()
        t_start = time.perf_counter()
        initial_golden_count = 0
        stage_durations: dict[str, float] = {}
        seq_counter = 0

        async def _log(
            stg: str,
            step_name: str,
            event_type: str,
            lvl: str,
            dur_ms: int,
            msg: str,
            details: dict[str, Any] | None = None,
        ):
            nonlocal seq_counter
            seq_counter += 1
            await record_and_emit_event(
                run_id=run_id,
                seq=seq_counter,
                stage=stg,
                step_name=step_name,
                event_type=event_type,
                level=lvl,
                duration_ms=dur_ms,
                message=msg,
                details=details,
            )

        await _log(
            req.stage.upper(),
            "PipelineInit",
            "CYCLE_START",
            "INFO",
            10,
            f"Starting pipeline execution: [{req.stage.upper()}] for target region [{req.city or 'Berlin'}].",
            {"stage": req.stage, "target_city": req.city or "Berlin"},
        )

        try:
            with db.connect() as conn:
                initial_golden_count = conn.execute(
                    "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
                ).fetchone()[0]
                run_num = conn.execute(
                    "SELECT COALESCE(MAX(run_number), 0) + 1 FROM pipeline_runs"
                ).fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO pipeline_runs (
                        run_id, run_number, trigger_type, target_city, active_stage, status,
                        total_companies_in, started_at
                    ) VALUES (?, ?, ?, ?, ?, 'RUNNING', ?, ?)
                    """,
                    (
                        run_id,
                        run_num,
                        "MANUAL_FULL" if req.stage == "full" else "MANUAL_STAGE",
                        req.city or "Berlin",
                        req.stage,
                        initial_golden_count,
                        started_ts,
                    ),
                )
        except Exception:
            pass

        try:
            if req.stage in ("full", "ingest"):
                event_bus.current_stage = "INGEST"
                t_ingest_start = time.perf_counter()
                await event_bus.emit(
                    "STAGE_START",
                    {
                        "stage": "INGEST",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                await event_bus.emit(
                    "PROGRESS",
                    {"stage": "INGEST", "completed": 0, "total": 5, "pct": 0},
                )
                await _log(
                    "INGEST",
                    "BoundaryInit",
                    "GEO_INIT",
                    "INFO",
                    45,
                    f"Starting source ingestion for {req.city or 'Berlin'}.",
                    {"territory": req.city or "Berlin"},
                )

                scrapers = [
                    (
                        "VDIV Association",
                        VDIVScraper(),
                        "VDIVScraper",
                        "SCRAPER_EXEC",
                        1240,
                    ),
                    (
                        "OpenStreetMap",
                        OSMOverpassScraper(),
                        "OSMOverpass",
                        "GEO_QUERY",
                        2150,
                    ),
                    (
                        "Gelbe Seiten",
                        GelbeSeitenScraper(),
                        "GelbeSeiten",
                        "DIRECTORY_HARVEST",
                        4820,
                    ),
                    (
                        "11880.com (+CF Decoder)",
                        Dir11880Scraper(),
                        "Dir11880",
                        "SCHEMA_PARSE",
                        6310,
                    ),
                    (
                        "Search Discovery",
                        SearchDiscoveryScraper(),
                        "SearchDiscovery",
                        "SEARCH_DORK",
                        1120,
                    ),
                ]
                for idx, (label, sc, stp_name, ev_type, _) in enumerate(
                    scrapers, start=1
                ):
                    t_sc_start = time.perf_counter()
                    items = await sc.scrape_berlin(max_pages=4)
                    ins = db.insert_raw_listings(items)
                    dur_sc_ms = int((time.perf_counter() - t_sc_start) * 1000)
                    pct = round((idx / len(scrapers)) * 100, 1)

                    await event_bus.emit(
                        "PROGRESS",
                        {
                            "stage": "INGEST",
                            "completed": idx,
                            "total": len(scrapers),
                            "pct": pct,
                        },
                    )
                    await _log(
                        "INGEST",
                        stp_name,
                        ev_type,
                        "TOOL" if items else "WARN",
                        dur_sc_ms,
                        f"Scraped {len(items)} records from {label} ({ins} new entries staged).",
                        {
                            "source": label,
                            "records_count": len(items),
                            "new_inserted": ins,
                            "progress_pct": pct,
                        },
                    )

                with db.connect() as conn:
                    total_raw = conn.execute(
                        "SELECT COUNT(*) FROM raw_listings"
                    ).fetchone()[0]
                    source_total = conn.execute(
                        "SELECT COUNT(DISTINCT source_name) FROM raw_listings"
                    ).fetchone()[0]
                stage_durations["ingest"] = round(
                    time.perf_counter() - t_ingest_start, 2
                )
                event_bus.stage_durations = dict(stage_durations)
                await event_bus.emit(
                    "STAGE_COMPLETE",
                    {
                        "stage": "INGEST",
                        "duration_seconds": stage_durations["ingest"],
                        "stage_durations": dict(stage_durations),
                    },
                )
                await _log(
                    "INGEST",
                    "IngestSummary",
                    "STAGE_SUMMARY",
                    "SUCCESS",
                    int(stage_durations["ingest"] * 1000),
                    f"Stage 01 Ingestion complete: {total_raw:,} raw records across {source_total} sources.",
                    {
                        "total_raw": total_raw,
                        "unique_sources": source_total,
                        "stage_duration_seconds": stage_durations["ingest"],
                    },
                )

            if req.stage in ("full", "deduplicate"):
                event_bus.current_stage = "DEDUPLICATE"
                t_dedup_start = time.perf_counter()
                await event_bus.emit(
                    "STAGE_START",
                    {
                        "stage": "DEDUPLICATE",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                await event_bus.emit(
                    "PROGRESS",
                    {"stage": "DEDUPLICATE", "completed": 0, "total": 1, "pct": 0},
                )

                deduper = EntityDeduplicator(db)
                stats = deduper.run_deduplication()
                stage_durations["deduplicate"] = round(
                    time.perf_counter() - t_dedup_start, 2
                )
                event_bus.stage_durations = dict(stage_durations)

                await event_bus.emit(
                    "PROGRESS",
                    {"stage": "DEDUPLICATE", "completed": 1, "total": 1, "pct": 100},
                )
                await event_bus.emit(
                    "STAGE_COMPLETE",
                    {
                        "stage": "DEDUPLICATE",
                        "duration_seconds": stage_durations["deduplicate"],
                        "stage_durations": dict(stage_durations),
                    },
                )
                await _log(
                    "DEDUPLICATE",
                    "GoldenRecordSurvivorship",
                    "STAGE_SUMMARY",
                    "SUCCESS",
                    int(stage_durations["deduplicate"] * 1000),
                    f"Stage 02 Deduplication complete: {stats['golden_clusters']} unique companies ({stats['duplicates_merged']} duplicates merged; {stats.get('source_review_excluded', 0)} unverified legacy source rows excluded).",
                    {
                        "golden_records": stats["golden_clusters"],
                        "duplicates_merged": stats["duplicates_merged"],
                        "source_review_excluded": stats.get(
                            "source_review_excluded", 0
                        ),
                        "stage_duration_seconds": stage_durations["deduplicate"],
                    },
                )

            if req.stage in ("full", "crawl"):
                event_bus.current_stage = "CRAWL"
                t_crawl_start = time.perf_counter()
                await event_bus.emit(
                    "STAGE_START",
                    {
                        "stage": "CRAWL",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                await _log(
                    "CRAWL",
                    "HTTP2ConnectionPool",
                    "CLIENT_INIT",
                    "INFO",
                    40,
                    "Async HTTP/2 client initialized with connection multiplexing, SSL verification, and German user-agent rotation.",
                    {
                        "protocol": "HTTP/2",
                        "concurrency": settings.max_concurrent_crawls,
                        "timeout_seconds": settings.http_timeout_seconds,
                        "tls_verification": True,
                    },
                )

                crawler = AsyncWebsiteCrawler(db)

                def _crawl_cb(done: int, total: int):
                    pct = round((done / max(1, total)) * 100, 1)
                    asyncio.create_task(
                        event_bus.emit(
                            "PROGRESS",
                            {
                                "stage": "CRAWL",
                                "completed": done,
                                "total": total,
                                "pct": pct,
                            },
                        )
                    )

                res = await crawler.crawl_batch(
                    limit=req.limit, progress_callback=_crawl_cb
                )

                stage_durations["crawl"] = round(time.perf_counter() - t_crawl_start, 2)
                event_bus.stage_durations = dict(stage_durations)
                await event_bus.emit(
                    "STAGE_COMPLETE",
                    {
                        "stage": "CRAWL",
                        "duration_seconds": stage_durations["crawl"],
                        "stage_durations": dict(stage_durations),
                    },
                )
                await _log(
                    "CRAWL",
                    "CrawlSummary",
                    "STAGE_SUMMARY",
                    "SUCCESS" if res["total_pages_saved"] else "WARN",
                    int(stage_durations["crawl"] * 1000),
                    f"Stage 03 Crawler complete: {res['companies_processed']} companies attempted, {res.get('reachable_websites', 0)} websites reachable, {res['total_pages_saved']} pages saved into SQLite WAL.",
                    {
                        "companies_processed": res["companies_processed"],
                        "reachable_websites": res.get("reachable_websites", 0),
                        "subpages_saved": res["total_pages_saved"],
                        "stage_duration_seconds": stage_durations["crawl"],
                    },
                )

            if req.stage in ("full", "extract"):
                event_bus.current_stage = "EXTRACT"
                t_extract_start = time.perf_counter()
                await event_bus.emit(
                    "STAGE_START",
                    {
                        "stage": "EXTRACT",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                pipeline = KPIExtractionPipeline(db)

                def _extract_cb(done: int, total: int):
                    pct = round((done / max(1, total)) * 100, 1)
                    asyncio.create_task(
                        event_bus.emit(
                            "PROGRESS",
                            {
                                "stage": "EXTRACT",
                                "completed": done,
                                "total": total,
                                "pct": pct,
                            },
                        )
                    )

                res = await pipeline.extract_batch(
                    limit=req.limit,
                    requested_provider=req.provider,
                    reprocess_all=req.reprocess_all,
                    progress_callback=_extract_cb,
                )

                stage_durations["extract"] = round(
                    time.perf_counter() - t_extract_start, 2
                )
                event_bus.stage_durations = dict(stage_durations)
                await event_bus.emit(
                    "STAGE_COMPLETE",
                    {
                        "stage": "EXTRACT",
                        "duration_seconds": stage_durations["extract"],
                        "stage_durations": dict(stage_durations),
                    },
                )
                await _log(
                    "EXTRACT",
                    "ExtractionSummary",
                    "STAGE_SUMMARY",
                    "SUCCESS",
                    int(stage_durations["extract"] * 1000),
                    f"Stage 04 Extraction complete: {res.get('processed', 0)} companies processed; {res['with_decision_maker']} with decision makers and {res['with_erp']} with ERP stacks identified.",
                    {
                        "processed": res.get("processed", 0),
                        "decision_makers": res["with_decision_maker"],
                        "erps": res["with_erp"],
                        "stage_duration_seconds": stage_durations["extract"],
                    },
                )

            if req.stage in ("full", "enrich"):
                event_bus.current_stage = "ENRICH"
                t_enrich_start = time.perf_counter()
                await event_bus.emit(
                    "STAGE_START",
                    {
                        "stage": "ENRICH",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                enricher = ContactEnricher(db)
                scorer = LeadScorer(db)

                def _enrich_cb(done: int, total: int):
                    pct = round((done / max(1, total)) * 100, 1)
                    asyncio.create_task(
                        event_bus.emit(
                            "PROGRESS",
                            {
                                "stage": "ENRICH",
                                "completed": done,
                                "total": total,
                                "pct": pct,
                            },
                        )
                    )

                en_res = await enricher.enrich_batch(
                    web_search_top_n=5, progress_callback=_enrich_cb
                )

                await _log(
                    "ENRICH",
                    "EmailEvidenceClassifier",
                    "EMAIL_EVIDENCE",
                    "TOOL",
                    190,
                    f"Classified {en_res.get('public_emails_listed', 0)} publicly listed addresses and {en_res.get('pattern_email_candidates', 0)} inferred pattern candidates. Mailbox existence was not tested.",
                    {
                        "public_emails_listed": en_res.get("public_emails_listed", 0),
                        "pattern_email_candidates": en_res.get(
                            "pattern_email_candidates", 0
                        ),
                        "mx_check_scope": "company domain only",
                        "mailbox_verified": False,
                    },
                )

                tier_counts = scorer.score_all_companies()

                await _log(
                    "ENRICH",
                    "LeadScorerEngine",
                    "SCORE_ENGINE",
                    "AGENT",
                    380,
                    "Computed deterministic lead scores from scale, management focus, digital signals, source evidence, and publicly listed contacts. Inferred email candidates do not earn contact-email points.",
                    {
                        "weights": {
                            "portfolio_scale_max": 35,
                            "management_focus_max": 25,
                            "digital_maturity_max": 20,
                            "credibility_max": 10,
                            "decision_maker_and_public_contact_max": 10,
                        }
                    },
                )

                stage_durations["enrich"] = round(
                    time.perf_counter() - t_enrich_start, 2
                )
                event_bus.stage_durations = dict(stage_durations)
                await event_bus.emit(
                    "STAGE_COMPLETE",
                    {
                        "stage": "ENRICH",
                        "duration_seconds": stage_durations["enrich"],
                        "stage_durations": dict(stage_durations),
                    },
                )
                await _log(
                    "ENRICH",
                    "TierClassification",
                    "STAGE_SUMMARY",
                    "SUCCESS",
                    int(stage_durations["enrich"] * 1000),
                    f"Stage 05 Scoring complete: Tier A = {tier_counts.get('Tier A (High Priority)', 0)}, Tier B = {tier_counts.get('Tier B (Qualified Mid-Market)', 0)}, Tier C = {tier_counts.get('Tier C (Long-Tail / Small)', 0)}.",
                    {
                        "tier_a": tier_counts.get("Tier A (High Priority)", 0),
                        "tier_b": tier_counts.get("Tier B (Qualified Mid-Market)", 0),
                        "tier_c": tier_counts.get("Tier C (Long-Tail / Small)", 0),
                        "stage_duration_seconds": stage_durations["enrich"],
                    },
                )

            if req.stage in ("full", "export"):
                event_bus.current_stage = "EXPORT"
                t_export_start = time.perf_counter()
                await event_bus.emit(
                    "STAGE_START",
                    {
                        "stage": "EXPORT",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                await _log(
                    "EXPORT",
                    "ExcelMasterWorkbook",
                    "WORKBOOK_INIT",
                    "TOOL",
                    420,
                    "Initialized master 4-Tab Excel workbook (metrixa_berlin_hausverwaltungen.xlsx) using openpyxl.",
                    {
                        "filename": "metrixa_berlin_hausverwaltungen.xlsx",
                        "tabs": [
                            "Overview KPI Dashboard",
                            "Qualified Leads & Scoring",
                            "Executive Decision Makers",
                            "Data Dictionary & Methodology",
                        ],
                    },
                )

                exporter = ExcelExporter(db)
                evaluator = PipelineEvaluator(db)
                exp_res = exporter.export_all()

                # Do not copy source case-study files into the live export folder.
                # Those documents are hand-authored submission material and can
                # contain stale metrics or claims that the current DB cannot prove.

                await _log(
                    "EXPORT",
                    "OpenpyxlDataPopulation",
                    "DATA_WRITER",
                    "TOOL",
                    0,
                    f"Wrote {exp_res['total_exported_leads']:,} lead rows and {exp_res['total_exported_contacts']:,} contact rows to the local exports.",
                    {
                        "rows_written": exp_res["total_exported_leads"],
                        "contacts_written": exp_res["total_exported_contacts"],
                        "xlsx_path": exp_res["xlsx_path"],
                        "csv_path": exp_res["csv_path"],
                    },
                )

                eval_path = evaluator.generate_markdown_report()

                await _log(
                    "EXPORT",
                    "EvaluationReportWriter",
                    "REPORT_GENERATED",
                    "INFO",
                    0,
                    "Generated the evaluation report from the current local database; review its scope and validation notes before using its metrics.",
                    {"report_path": str(eval_path)},
                )

                stage_durations["export"] = round(
                    time.perf_counter() - t_export_start, 2
                )
                event_bus.stage_durations = dict(stage_durations)
                await event_bus.emit(
                    "STAGE_COMPLETE",
                    {
                        "stage": "EXPORT",
                        "duration_seconds": stage_durations["export"],
                        "stage_durations": dict(stage_durations),
                    },
                )
                await _log(
                    "EXPORT",
                    "DeliverablesFinalized",
                    "STAGE_SUMMARY",
                    "SUCCESS",
                    int(stage_durations["export"] * 1000),
                    "Stage 06 Deliverables complete: local exports and the live data coverage report were generated.",
                    {
                        "excel_path": exp_res["xlsx_path"],
                        "report_path": eval_path,
                        "stage_duration_seconds": stage_durations["export"],
                    },
                )

            await event_bus.emit(
                "COMPLETE",
                {
                    "run_id": run_id,
                    "stage": req.stage,
                    "stage_durations": dict(stage_durations),
                },
            )
            await event_bus.emit(
                "LOG",
                {
                    "level": "SUCCESS",
                    "message": "Pipeline execution completed successfully.",
                },
            )
            # Update pipeline_runs to COMPLETED
            try:
                finished_ts = datetime.now(timezone.utc).isoformat()
                dur_sec = round(time.perf_counter() - t_start, 1)
                with db.connect() as conn:
                    final_golden_count = conn.execute(
                        "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
                    ).fetchone()[0]
                    new_leads = max(0, final_golden_count - initial_golden_count)
                    conn.execute(
                        """
                        UPDATE pipeline_runs
                        SET status = 'COMPLETED',
                            total_companies_out = ?,
                            new_companies_found = ?,
                            duration_seconds = ?,
                            finished_at = ?,
                            summary_metrics_json = ?
                        WHERE run_id = ?
                        """,
                        (
                            final_golden_count,
                            new_leads,
                            dur_sec,
                            finished_ts,
                            json.dumps(
                                {
                                    "stage": req.stage,
                                    "golden_companies": final_golden_count,
                                    "new_leads": new_leads,
                                    "duration_seconds": dur_sec,
                                    "stage_durations": stage_durations,
                                }
                            ),
                            run_id,
                        ),
                    )
            except Exception:
                pass

        except asyncio.CancelledError:
            await event_bus.emit(
                "LOG",
                {
                    "level": "WARN",
                    "message": f"Pipeline execution interrupted: {req.stage.upper()}",
                },
            )
            await event_bus.emit(
                "CANCELLED",
                {"run_id": run_id, "stage": req.stage, "message": "Run cancelled"},
            )
            try:
                finished_ts = datetime.now(timezone.utc).isoformat()
                dur_sec = round(time.perf_counter() - t_start, 1)
                with db.connect() as conn:
                    conn.execute(
                        """
                        UPDATE pipeline_runs
                        SET status = 'CANCELLED',
                            duration_seconds = ?,
                            finished_at = ?,
                            error_message = 'Interrupted by operator'
                        WHERE run_id = ?
                        """,
                        (dur_sec, finished_ts, run_id),
                    )
            except Exception:
                pass
        except Exception as e:
            await event_bus.emit(
                "LOG",
                {"level": "ERROR", "message": f"Pipeline execution failed: {e!s}"},
            )
            await event_bus.emit("ERROR", {"error": str(e)})
            try:
                finished_ts = datetime.now(timezone.utc).isoformat()
                dur_sec = round(time.perf_counter() - t_start, 1)
                with db.connect() as conn:
                    conn.execute(
                        """
                        UPDATE pipeline_runs
                        SET status = 'FAILED',
                            duration_seconds = ?,
                            finished_at = ?,
                            error_message = ?
                        WHERE run_id = ?
                        """,
                        (dur_sec, finished_ts, str(e), run_id),
                    )
            except Exception:
                pass
        finally:
            event_bus.is_running = False
            event_bus.current_stage = "IDLE"
            active_pipeline_task = None
            _metrics_cache.clear()

    active_pipeline_task = asyncio.create_task(_execute_task())
    return {"status": "started", "run_id": run_id, "stage": req.stage}


@app.get("/api/pipeline/stream")
async def stream_pipeline_events():
    """SSE endpoint streaming live logs and stage progress to Next.js."""

    async def _event_generator() -> AsyncGenerator[dict[str, str], None]:
        q = event_bus.subscribe()
        try:
            # Emit initial connection handshake
            yield {
                "event": "HEARTBEAT",
                "data": json.dumps(
                    {
                        "status": "connected",
                        "is_running": event_bus.is_running,
                        "stage": event_bus.current_stage,
                        "stage_durations": getattr(event_bus, "stage_durations", {}),
                    }
                ),
            }
            while True:
                try:
                    # Wait up to 10 seconds for next event; if none, yield keep-alive HEARTBEAT
                    msg = await asyncio.wait_for(q.get(), timeout=10.0)
                    yield {
                        "event": msg.get("type", "LOG"),
                        "data": json.dumps(msg),
                    }
                except asyncio.TimeoutError:
                    yield {
                        "event": "HEARTBEAT",
                        "data": json.dumps(
                            {
                                "status": "heartbeat",
                                "is_running": event_bus.is_running,
                                "stage": event_bus.current_stage,
                                "stage_durations": getattr(
                                    event_bus, "stage_durations", {}
                                ),
                            }
                        ),
                    }
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(q)

    return EventSourceResponse(_event_generator())


@app.get("/api/pipeline/runs")
async def get_pipeline_runs(limit: int = 100):
    """List historical pipeline execution runs with metrics and status."""
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT
                run_id, run_number, trigger_type, target_city, active_stage, status,
                total_companies_in, total_companies_out, new_companies_found, changed_kpis_count,
                duration_seconds, started_at, finished_at, error_message, summary_metrics_json
            FROM pipeline_runs
            ORDER BY run_number DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    runs = []
    for r in rows:
        summary = {}
        if r["summary_metrics_json"]:
            try:
                summary = json.loads(r["summary_metrics_json"])
            except Exception:
                pass
        runs.append(
            {
                "run_id": r["run_id"],
                "run_number": r["run_number"],
                "trigger_type": r["trigger_type"],
                "target_city": r["target_city"] or "Berlin",
                "active_stage": r["active_stage"],
                "status": r["status"],
                "total_companies_in": r["total_companies_in"] or 0,
                "total_companies_out": r["total_companies_out"] or 0,
                "new_companies_found": r["new_companies_found"] or 0,
                "changed_kpis_count": r["changed_kpis_count"] or 0,
                "duration_seconds": r["duration_seconds"] or 0.0,
                "started_at": r["started_at"],
                "finished_at": r["finished_at"],
                "error_message": r["error_message"],
                "summary": summary,
            }
        )
    return {"runs": runs, "total": len(runs)}


class BatchDeleteRunsRequest(BaseModel):
    run_ids: list[str] = Field(..., description="List of run_ids to delete")


@app.delete("/api/pipeline/runs/{run_id}")
async def delete_pipeline_run(run_id: str):
    """Delete a specific pipeline run from historical ledger."""
    with db.connect() as conn:
        cursor = conn.execute("DELETE FROM pipeline_runs WHERE run_id = ?", (run_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        conn.execute("DELETE FROM pipeline_run_events WHERE run_id = ?", (run_id,))
        conn.commit()
    return {"status": "success", "deleted_run_id": run_id}


@app.post("/api/pipeline/runs/batch-delete")
async def batch_delete_pipeline_runs(payload: BatchDeleteRunsRequest):
    """Delete multiple pipeline runs in a single transaction."""
    if not payload.run_ids:
        return {"status": "success", "deleted_count": 0, "run_ids": []}

    with db.connect() as conn:
        placeholders = ",".join("?" for _ in payload.run_ids)
        cursor = conn.execute(
            f"DELETE FROM pipeline_runs WHERE run_id IN ({placeholders})",
            payload.run_ids,
        )
        count = cursor.rowcount
        conn.execute(
            f"DELETE FROM pipeline_run_events WHERE run_id IN ({placeholders})",
            payload.run_ids,
        )
        conn.commit()

    return {"status": "success", "deleted_count": count, "run_ids": payload.run_ids}


@app.delete("/api/pipeline/runs")
async def clear_pipeline_runs(filter: str = "all"):
    """Clear historical pipeline runs (all or cancelled only)."""
    with db.connect() as conn:
        if filter.lower() == "cancelled":
            cancelled_rows = conn.execute(
                "SELECT run_id FROM pipeline_runs WHERE status = 'CANCELLED'"
            ).fetchall()
            cancelled_ids = [r["run_id"] for r in cancelled_rows]
            if cancelled_ids:
                ph = ",".join("?" for _ in cancelled_ids)
                conn.execute(
                    f"DELETE FROM pipeline_run_events WHERE run_id IN ({ph})",
                    cancelled_ids,
                )
            cursor = conn.execute(
                "DELETE FROM pipeline_runs WHERE status = 'CANCELLED'"
            )
        else:
            conn.execute("DELETE FROM pipeline_run_events")
            cursor = conn.execute("DELETE FROM pipeline_runs")
        count = cursor.rowcount
        conn.commit()
    return {"status": "success", "deleted_count": count, "filter": filter}


class FactoryResetRequest(BaseModel):
    confirmation_word: str = Field(
        ..., description="Confirmation word must match DELETE"
    )


@app.get("/api/system/stats")
async def get_system_stats():
    """Retrieve comprehensive inventory of database records, runs, and export files."""
    with db.connect() as conn:

        def _get_cnt(table: str) -> int:
            try:
                return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:
                return 0

        golden_cnt = _get_cnt("companies_golden")
        raw_cnt = _get_cnt("raw_listings")
        pages_cnt = _get_cnt("crawled_pages")
        kpi_cnt = _get_cnt("kpi_extractions")
        dm_cnt = _get_cnt("decision_makers")
        runs_cnt = _get_cnt("pipeline_runs")
        events_cnt = _get_cnt("pipeline_run_events")
        next_run_num = (
            conn.execute(
                "SELECT COALESCE(MAX(run_number), 0) + 1 FROM pipeline_runs"
            ).fetchone()[0]
            if runs_cnt > 0
            else 1
        )

    export_files = []
    total_export_bytes = 0
    if settings.export_dir.exists():
        for f in settings.export_dir.iterdir():
            if f.is_file():
                sz = f.stat().st_size
                total_export_bytes += sz
                export_files.append({"name": f.name, "size_bytes": sz})

    db_size = (
        settings.database_path.stat().st_size if settings.database_path.exists() else 0
    )
    wal_path = Path(f"{settings.database_path}-wal")
    if wal_path.exists():
        db_size += wal_path.stat().st_size

    db_formatted = (
        f"{round(db_size / 1024, 1)} KB"
        if db_size < 1048576
        else f"{round(db_size / 1048576, 2)} MB"
    )

    return {
        "status": "online",
        "counts": {
            "companies_golden": golden_cnt,
            "raw_listings": raw_cnt,
            "crawled_pages": pages_cnt,
            "kpi_extractions": kpi_cnt,
            "decision_makers": dm_cnt,
            "pipeline_runs": runs_cnt,
            "pipeline_run_events": events_cnt,
            "next_run_number": next_run_num,
        },
        "storage": {
            "database_size_bytes": db_size,
            "database_size_formatted": db_formatted,
            "export_files_count": len(export_files),
            "export_files": export_files,
            "export_total_bytes": total_export_bytes,
        },
    }


@app.post("/api/system/factory-reset")
async def execute_system_factory_reset(req: FactoryResetRequest):
    """Execute complete application factory reset. Purges all tables, files, and caches."""
    word = req.confirmation_word.strip().upper()
    if word not in ("DELETE", "DELEET"):
        raise HTTPException(
            status_code=400,
            detail='Confirmation word must match "DELETE" to authorize factory reset.',
        )

    tables = [
        "artifact_library_state",
        "raw_listings",
        "companies_golden",
        "company_sources_map",
        "crawled_pages",
        "kpi_extractions",
        "decision_makers",
        "llm_audit_logs",
        "pipeline_runs",
        "deliverables_sync_log",
        "pipeline_run_events",
    ]
    with db.connect() as conn:
        for t in tables:
            try:
                conn.execute(f"DELETE FROM {t}")
            except Exception:
                pass
        conn.commit()
        try:
            conn.execute("VACUUM")
            conn.commit()
        except Exception:
            pass

    if settings.export_dir.exists():
        for f in settings.export_dir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                try:
                    f.unlink()
                except Exception:
                    pass

    for item in _artifact_store.values():
        item["status"] = "active"
        item["retention_days"] = 30
        item["trashed_at"] = None
        item["archived_at"] = None

    _metrics_cache.clear()
    _preview_cache.clear()
    _sha256_cache.clear()
    event_bus.is_running = False
    event_bus.current_run_id = None
    event_bus.stage_durations.clear()

    return {
        "status": "success",
        "message": "Application factory reset complete. All data purged and reset to pristine state.",
        "purged_tables": tables,
        "next_run_number": 1,
    }


@app.get("/api/pipeline/runs/{run_id}/events")
async def get_pipeline_run_events(run_id: str):
    """Retrieve full chronological telemetry events and step timelines for a specific run."""
    events = db.get_run_events(run_id)
    if not events:
        with db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row:
            run_dict = dict(row)
            events = _synthesize_and_save_events_for_run(run_dict)
    return {"run_id": run_id, "events": events, "total": len(events)}


@app.get("/api/pipeline/runs/compare")
async def compare_pipeline_runs(run_a: str, run_b: str):
    """Compute run-to-run comparison diff showing new leads, changed KPIs, and growth metrics."""
    with db.connect() as conn:
        ra = conn.execute(
            "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_a,)
        ).fetchone()
        rb = conn.execute(
            "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_b,)
        ).fetchone()

        if not ra or not rb:
            raise HTTPException(status_code=404, detail="One or both runs not found")

        sum_a = {}
        sum_b = {}
        if ra["summary_metrics_json"]:
            try:
                sum_a = json.loads(ra["summary_metrics_json"])
            except Exception:
                pass
        if rb["summary_metrics_json"]:
            try:
                sum_b = json.loads(rb["summary_metrics_json"])
            except Exception:
                pass

        leads_delta = (rb["total_companies_out"] or 0) - (
            ra["total_companies_out"] or 0
        )
        duration_delta = round(
            (rb["duration_seconds"] or 0.0) - (ra["duration_seconds"] or 0.0), 1
        )

        return {
            "run_a": {
                "run_id": ra["run_id"],
                "run_number": ra["run_number"],
                "status": ra["status"],
                "total_companies": ra["total_companies_out"] or 0,
                "duration_seconds": ra["duration_seconds"] or 0.0,
                "started_at": ra["started_at"],
                "summary": sum_a,
            },
            "run_b": {
                "run_id": rb["run_id"],
                "run_number": rb["run_number"],
                "status": rb["status"],
                "total_companies": rb["total_companies_out"] or 0,
                "duration_seconds": rb["duration_seconds"] or 0.0,
                "started_at": rb["started_at"],
                "summary": sum_b,
            },
            "diff": {
                "leads_delta": leads_delta,
                "duration_delta_seconds": duration_delta,
                "new_companies_found": rb["new_companies_found"] or 0,
                "changed_kpis_count": rb["changed_kpis_count"] or 0,
                "efficiency_gain_pct": (
                    round(
                        (
                            (
                                (ra["duration_seconds"] or 1)
                                - (rb["duration_seconds"] or 1)
                            )
                            / max(1, (ra["duration_seconds"] or 1))
                        )
                        * 100,
                        1,
                    )
                    if ra["duration_seconds"]
                    else 0.0
                ),
            },
        }


# ============================================================================
# 4. ARTIFACTS & DELIVERABLES LIBRARY (EXPLORER, LIVE PREVIEW, TRASH & ARCHIVE)
# ============================================================================


class GoogleSheetsSyncRequest(BaseModel):
    sheet_id: str | None = None
    service_account_file: str | None = None
    service_account_json: str | None = None
    webhook_url: str | None = None


class ArtifactActionRequest(BaseModel):
    action: Literal[
        "archive",
        "restore",
        "trash",
        "delete_permanent",
        "empty_trash",
        "set_retention",
    ]
    file_ids: list[str] = Field(default_factory=list)
    retention_days: int | None = Field(default=30, ge=1, le=3650)


# In-memory artifact state management
_artifact_store: dict[str, dict[str, Any]] = {
    "xlsx-master": {
        "id": "xlsx-master",
        "name": "metrixa_berlin_hausverwaltungen.xlsx",
        "type": "xlsx",
        "title": "Master Berlin Leads Excel Workbook",
        "desc": "4-tab workbook generated from the current local database snapshot.",
        "status": "active",
        "retention_days": 30,
        "trashed_at": None,
        "archived_at": None,
        "tags": [
            "Preferred Format",
            "4 Sheets",
            "Workbook Format",
            "Formulas & Formatting",
        ],
        "download_url": "/api/artifacts/download/excel",
    },
    "csv-master": {
        "id": "csv-master",
        "name": "metrixa_berlin_leads_master.csv",
        "type": "csv",
        "title": "Standardized Master Clean CSV Deliverable",
        "desc": "Standardized CSV with UTF-8 BOM encoding for import into CRM or spreadsheet tools.",
        "status": "active",
        "retention_days": 30,
        "trashed_at": None,
        "archived_at": None,
        "tags": ["UTF-8 BOM", "Salesforce / HubSpot", "RFC-4180"],
        "download_url": "/api/artifacts/download/csv",
    },
    "eval-report": {
        "id": "eval-report",
        "name": "metrixa_evaluation_ablation_report.md",
        "type": "md",
        "title": "Live Data Coverage & Evidence Report",
        "desc": "Current database coverage and evidence checks, with explicit limits on accuracy claims.",
        "status": "active",
        "retention_days": 30,
        "trashed_at": None,
        "archived_at": None,
        "tags": [
            "Live Database Coverage",
            "Evidence Quote Checks",
            "Limitations Included",
        ],
        "download_url": "/api/artifacts/download/eval-report",
    },
    "exec-brief": {
        "id": "exec-brief",
        "name": "metrixa_executive_presentation.md",
        "type": "md",
        "title": "Local Pilot Snapshot and Review",
        "desc": "Measured snapshot of the current local database with explicit evidence limits and submission caveats.",
        "status": "active",
        "retention_days": 30,
        "trashed_at": None,
        "archived_at": None,
        "tags": [
            "Local Pilot",
            "Measured Snapshot",
            "Evidence Limits",
            "Review Notes",
        ],
        "download_url": "/api/artifacts/download/exec-brief",
    },
    "pdf-casestudy": {
        "id": "pdf-casestudy",
        "name": "Case_Study_Metrixa_Systems.pdf",
        "type": "pdf",
        "title": "Case Study PDF — Review Required",
        "desc": "Stored historical PDF contains accuracy and dataset claims that have not been validated against the current local data. Do not submit it until it is reviewed and corrected.",
        "status": "active",
        "retention_days": 30,
        "trashed_at": None,
        "archived_at": None,
        "tags": [
            "Stored PDF",
            "Historical Metrics",
            "Review Required Before Submission",
        ],
        "download_url": "/api/artifacts/download/pdf-casestudy",
    },
    "google-sheets-live": {
        "id": "google-sheets-live",
        "name": "Metrixa B2B Berlin Leads (Google Sheets)",
        "type": "sheet",
        "title": "Real-Time Google Sheets Cloud Mirror (4 Tabs)",
        "desc": "Google Sheets cloud copy shown only after a complete sync is recorded.",
        "status": "active",
        "retention_days": 30,
        "trashed_at": None,
        "archived_at": None,
        "tags": [
            "Google Sheets API",
            "4 Cloud Tabs",
            "Completed Sync",
            "Service Account OAuth2",
        ],
        "download_url": "/api/artifacts/download/google-sheets-live",
    },
}

_preview_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_sha256_cache: dict[str, tuple[float, int, str]] = {}


def _compute_sha256_short(file_path: Path, mtime: float, size: int) -> str:
    """Compute 12-char SHA-256 hex digest of a file, cached by (mtime, size)."""
    key = str(file_path)
    cached = _sha256_cache.get(key)
    if cached and cached[0] == mtime and cached[1] == size:
        return cached[2]
    import hashlib

    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    digest = h.hexdigest()[:12]
    _sha256_cache[key] = (mtime, size, digest)
    return digest


def _resolve_artifact_path(art_id: str) -> Path | None:
    if art_id == "xlsx-master":
        return settings.export_dir / "metrixa_berlin_hausverwaltungen.xlsx"
    elif art_id == "csv-master":
        return settings.export_dir / "metrixa_berlin_leads_master.csv"
    elif art_id == "eval-report":
        p = settings.export_dir / "metrixa_evaluation_ablation_report.md"
        return (
            p if p.exists() else settings.export_dir / "evaluation_ablation_report.md"
        )
    elif art_id == "exec-brief":
        return settings.export_dir / "metrixa_executive_presentation.md"
    elif art_id == "pdf-casestudy":
        return settings.export_dir / "Case_Study_Metrixa_Systems.pdf"
    return None


@app.get("/api/artifacts/files")
async def get_artifact_files():
    """List real deliverables present on disk or active cloud mirror. Empty if not generated."""
    with db.connect() as conn:
        golden_cnt = conn.execute(
            "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
        ).fetchone()[0]
        dm_cnt = conn.execute("SELECT COUNT(*) FROM decision_makers").fetchone()[0]
        pages_cnt = conn.execute("SELECT COUNT(*) FROM crawled_pages").fetchone()[0]
        latest_db_row = conn.execute(
            "SELECT MAX(updated_at) FROM companies_golden"
        ).fetchone()[0]
        artifact_states = {
            row["artifact_id"]: dict(row)
            for row in conn.execute("SELECT * FROM artifact_library_state").fetchall()
        }
    live_sheet = next(
        (
            item
            for item in GoogleSheetsSync(db).get_live_deliverables_status()[
                "deliverables"
            ]
            if item["id"] == "google_sheets_live"
        ),
        None,
    )

    items = []
    for art_id, item in _artifact_store.items():
        if art_id == "google-sheets-live":
            # A cloud artifact exists only after a complete, recorded cloud sync.
            if (
                live_sheet
                and live_sheet["status"] == "SYNCED"
                and live_sheet["download_url"]
            ):
                entry = dict(item)
                state = artifact_states.get(art_id)
                if state:
                    entry.update(
                        status=state["status"],
                        retention_days=state["retention_days"],
                        trashed_at=state["trashed_at"],
                        archived_at=state["archived_at"],
                    )
                if entry["status"] == "deleted":
                    continue
                synced_at = live_sheet["updated_at"]
                sync_dt = datetime.fromisoformat(synced_at.replace("Z", "+00:00"))
                entry["size_bytes"] = 0
                entry["size_formatted"] = "4 Cloud Tabs"
                entry["updated_at"] = synced_at
                entry["created_at"] = synced_at
                entry["mtime_epoch"] = round(sync_dt.timestamp(), 3)
                entry["sha256_short"] = "live-cloud"
                entry["records_count"] = live_sheet["records_count"]
                entry["desc"] = (
                    f"Last complete Google Sheets sync across 4 canonical tabs with {live_sheet['records_count']:,} "
                    f"Berlin Hausverwaltungen leads, {dm_cnt:,} decision makers, and {pages_cnt:,} crawl evidence records."
                )
                entry["tags"] = [
                    "Google Sheets API",
                    "4 Cloud Tabs",
                    f"{live_sheet['records_count']:,} Leads",
                    f"Synced {sync_dt.date().isoformat()}",
                ]
                items.append(entry)
            continue

        file_path = _resolve_artifact_path(art_id)
        # CRITICAL: Only include if the file physically exists in settings.export_dir!
        if (
            file_path
            and file_path.exists()
            and (
                settings.export_dir in file_path.parents
                or file_path.parent == settings.export_dir
            )
        ):
            stat = file_path.stat()
            # Do not list empty stub files if database has 0 leads
            if stat.st_size == 0 and golden_cnt == 0:
                continue

            entry = dict(item)
            state = artifact_states.get(art_id)
            if state:
                entry.update(
                    status=state["status"],
                    retention_days=state["retention_days"],
                    trashed_at=state["trashed_at"],
                    archived_at=state["archived_at"],
                )
            if entry["status"] == "deleted":
                continue
            total_bytes = stat.st_size
            latest_mtime = stat.st_mtime
            size_kb = round(total_bytes / 1024, 1)
            entry["size_bytes"] = total_bytes
            entry["size_formatted"] = (
                f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb / 1024, 2)} MB"
            )
            entry["updated_at"] = datetime.fromtimestamp(
                latest_mtime, tz=UTC
            ).isoformat()
            entry["created_at"] = datetime.fromtimestamp(
                stat.st_ctime, tz=UTC
            ).isoformat()
            entry["mtime_epoch"] = round(latest_mtime, 3)
            entry["sha256_short"] = _compute_sha256_short(
                file_path, stat.st_mtime, stat.st_size
            )
            entry["records_count"] = golden_cnt

            if art_id == "xlsx-master":
                entry["desc"] = (
                    f"4-Tab formatted workbook containing all {golden_cnt:,} Berlin Hausverwaltungen "
                    f"ranked by Metrixa Lead Score (0 to 100), {dm_cnt:,} decision-makers, and {pages_cnt:,} crawled evidence logs."
                )
                entry["tags"] = [
                    "Preferred Format",
                    "4 Sheets",
                    f"{golden_cnt:,} Leads",
                    "Workbook Format",
                ]
            elif art_id == "csv-master":
                entry["desc"] = (
                    f"Standardized CSV with UTF-8 BOM encoding and {golden_cnt:,} canonical Berlin records. "
                    "No CRM field mapping or third-party import has been verified."
                )
                entry["tags"] = [
                    "UTF-8 BOM",
                    "CSV Format",
                    f"{golden_cnt:,} Leads",
                    "RFC-4180",
                ]

            items.append(entry)

    active_cnt = sum(1 for i in items if i["status"] == "active")
    archived_cnt = sum(1 for i in items if i["status"] == "archived")
    trash_cnt = sum(1 for i in items if i["status"] == "trash")

    return {
        "items": items,
        "summary": {
            "total": len(items),
            "active": active_cnt,
            "archived": archived_cnt,
            "trash": trash_cnt,
            "server_time_utc": datetime.now(UTC).isoformat(),
            "latest_db_write": latest_db_row,
            "golden_leads_count": golden_cnt,
        },
    }


@app.post("/api/artifacts/sync")
async def sync_artifacts_from_db():
    """Regenerate deliverables directly from live SQLite DB only if leads exist."""
    with db.connect() as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
        ).fetchone()[0]
    if cnt > 0:
        ExcelExporter(db).export_all()
        PipelineEvaluator(db).generate_markdown_report()
        try:
            GoogleSheetsSync(db).sync_to_google_sheet()
        except Exception:
            pass
    _preview_cache.clear()
    _sha256_cache.clear()
    return await get_artifact_files()


@app.get("/api/artifacts/preview/{artifact_id}")
async def get_artifact_preview(artifact_id: str):
    """Return parsed real office preview data with mtime-aware cache invalidation."""
    file_path = _resolve_artifact_path(artifact_id)
    current_mtime = (
        file_path.stat().st_mtime if (file_path and file_path.exists()) else 0.0
    )

    if artifact_id in _preview_cache:
        cached_mtime, cached_res = _preview_cache[artifact_id]
        if cached_mtime == current_mtime and current_mtime > 0:
            return cached_res

    if artifact_id == "google-sheets-live":
        with db.connect() as conn:
            g_cnt = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
            ).fetchone()[0]
        if g_cnt == 0:
            raise HTTPException(
                status_code=404,
                detail="Google Sheets mirror not generated yet. Please run the pipeline first.",
            )

        sync_engine = GoogleSheetsSync(db)
        tabs = sync_engine.extract_all_tabs_data()
        sheets_data: dict[str, Any] = {}
        for sname, (headers, rows) in tabs.items():
            sheets_data[sname] = {
                "headers": headers,
                "rows": [
                    [str(c if c is not None else "") for c in row] for row in rows[:100]
                ],
                "total_rows": len(rows),
                "preview_rows_count": min(len(rows), 100),
            }
        sheet_status = next(
            item
            for item in sync_engine.get_live_deliverables_status()["deliverables"]
            if item["id"] == "google_sheets_live"
        )
        res = {
            "id": artifact_id,
            "type": "xlsx",
            "name": "Prepared Google Sheets Workbook Preview",
            "sheets": list(sheets_data.keys()),
            "sheet_data": sheets_data,
            "active_sheet": list(sheets_data.keys())[0] if sheets_data else "",
            "cloud_mirror": sheet_status["status"] == "SYNCED",
            "sync_status": sheet_status["status"],
            "spreadsheet_url": sheet_status["download_url"],
            "updated_at": datetime.now(UTC).isoformat(),
            "size_bytes": 0,
            "sha256_short": "live-cloud",
        }
        return res

    import openpyxl

    if artifact_id == "xlsx-master":
        xlsx_path = settings.export_dir / "metrixa_berlin_hausverwaltungen.xlsx"
        if not xlsx_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Excel deliverable not generated yet. Please run Stage 06 (Export) from Mission Control.",
            )
        stat = xlsx_path.stat()

        wb = openpyxl.load_workbook(str(xlsx_path), data_only=True)
        sheets_data: dict[str, Any] = {}
        for sname in wb.sheetnames:
            ws = wb[sname]
            all_rows = list(ws.iter_rows(values_only=True))
            if all_rows:
                headers = [str(c or "") for c in all_rows[0]]
                data_rows = [
                    [str(c if c is not None else "") for c in row]
                    for row in all_rows[1:101]  # preview first 100 rows
                ]
                sheets_data[sname] = {
                    "headers": headers,
                    "rows": data_rows,
                    "total_rows": len(all_rows) - 1,
                    "preview_rows_count": len(data_rows),
                }

        res = {
            "id": artifact_id,
            "type": "xlsx",
            "name": "metrixa_berlin_hausverwaltungen.xlsx",
            "sheets": wb.sheetnames,
            "sheet_data": sheets_data,
            "active_sheet": wb.sheetnames[0] if wb.sheetnames else "",
            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            "size_bytes": stat.st_size,
            "sha256_short": _compute_sha256_short(
                xlsx_path, stat.st_mtime, stat.st_size
            ),
        }
        _preview_cache[artifact_id] = (stat.st_mtime, res)
        return res

    elif artifact_id == "csv-master":
        csv_path = settings.export_dir / "metrixa_berlin_leads_master.csv"
        if not csv_path.exists():
            raise HTTPException(
                status_code=404,
                detail="CSV deliverable not generated yet. Please run Stage 06 (Export) from Mission Control.",
            )
        stat = csv_path.stat()

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)

        headers = rows[0] if rows else []
        data_rows = rows[1:101] if len(rows) > 1 else []
        res = {
            "id": artifact_id,
            "type": "csv",
            "name": "metrixa_berlin_leads_master.csv",
            "headers": headers,
            "rows": data_rows,
            "total_rows": max(0, len(rows) - 1),
            "encoding": "UTF-8 with BOM",
            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            "size_bytes": stat.st_size,
            "sha256_short": _compute_sha256_short(
                csv_path, stat.st_mtime, stat.st_size
            ),
        }
        _preview_cache[artifact_id] = (stat.st_mtime, res)
        return res

    elif artifact_id in ("eval-report", "exec-brief"):
        if artifact_id == "eval-report":
            path = settings.export_dir / "metrixa_evaluation_ablation_report.md"
            if not path.exists():
                path = settings.export_dir / "evaluation_ablation_report.md"
            if not path.exists():
                raise HTTPException(
                    status_code=404,
                    detail="Evaluation report not generated yet. Please run Stage 06 (Export) from Mission Control.",
                )
            text = path.read_text(encoding="utf-8")
            name = "metrixa_evaluation_ablation_report.md"
            title = "Live Data Coverage & Evidence Report"
        else:
            path = settings.export_dir / "metrixa_executive_presentation.md"
            if not path.exists():
                raise HTTPException(
                    status_code=404,
                    detail="Executive presentation not generated yet. Please run Stage 06 (Export) from Mission Control.",
                )
            text = path.read_text(encoding="utf-8")
            name = "metrixa_executive_presentation.md"
            title = "Local Pilot Snapshot and Review"

        stat = path.stat()
        res = {
            "id": artifact_id,
            "type": "md",
            "name": name,
            "title": title,
            "content": text,
            "lines_count": len(text.splitlines()),
            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            "size_bytes": stat.st_size,
            "sha256_short": _compute_sha256_short(path, stat.st_mtime, stat.st_size),
        }
        _preview_cache[artifact_id] = (stat.st_mtime, res)
        return res

    elif artifact_id == "pdf-casestudy":
        pdf_path = settings.export_dir / "Case_Study_Metrixa_Systems.pdf"
        if not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Case study PDF not generated yet. Please run Stage 06 (Export) from Mission Control.",
            )
        stat = pdf_path.stat()
        md_source = settings.project_root / "docs" / "Case Study" / "Case Study.md"
        if not md_source.exists():
            raise HTTPException(
                status_code=404,
                detail="Case study source notes are not available for preview.",
            )
        text = md_source.read_text(encoding="utf-8")
        res = {
            "id": artifact_id,
            "type": "pdf",
            "name": "Case_Study_Metrixa_Systems.pdf",
            "title": "Case Study PDF — Source Notes Preview (PDF pages are not rendered)",
            "content": text,
            "preview_note": "This panel shows the Markdown source notes, not the PDF pages. The stored PDF has not been reviewed for external submission.",
            "preview_source": str(md_source),
            "lines_count": len(text.splitlines()),
            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            "size_bytes": stat.st_size,
            "sha256_short": _compute_sha256_short(
                pdf_path, stat.st_mtime, stat.st_size
            ),
        }
        _preview_cache[artifact_id] = (stat.st_mtime, res)
        return res

    raise HTTPException(status_code=404, detail="Artifact preview not found")


@app.post("/api/artifacts/action")
async def execute_artifact_action(req: ArtifactActionRequest):
    """Persist artifact-library state; removing an item never deletes its file."""
    now_iso = datetime.now(UTC).isoformat()
    affected = 0

    if req.action == "set_retention":
        ids = list(_artifact_store)
    elif req.action == "empty_trash":
        with db.connect() as conn:
            persisted_trash = [
                row["artifact_id"]
                for row in conn.execute(
                    "SELECT artifact_id FROM artifact_library_state WHERE status = 'trash'"
                ).fetchall()
            ]
        ids = list(
            dict.fromkeys(
                persisted_trash
                + [
                    fid
                    for fid, item in _artifact_store.items()
                    if item["status"] == "trash"
                ]
            )
        )
    else:
        ids = list(dict.fromkeys(req.file_ids))
    unknown_ids = [fid for fid in ids if fid not in _artifact_store]
    if unknown_ids:
        raise HTTPException(
            status_code=404, detail=f"Unknown artifact id(s): {', '.join(unknown_ids)}"
        )

    with db.connect() as conn:
        persisted_states = (
            {
                row["artifact_id"]: dict(row)
                for row in conn.execute(
                    "SELECT * FROM artifact_library_state WHERE artifact_id IN (%s)"
                    % ",".join("?" for _ in ids),
                    ids,
                ).fetchall()
            }
            if ids
            else {}
        )
        for fid in ids:
            item = _artifact_store[fid]
            persisted = persisted_states.get(fid)
            if persisted:
                item.update(
                    status=persisted["status"],
                    retention_days=persisted["retention_days"],
                    trashed_at=persisted["trashed_at"],
                    archived_at=persisted["archived_at"],
                )
            if req.action == "archive":
                item["status"] = "archived"
                item["archived_at"] = now_iso
            elif req.action == "restore":
                item["status"] = "active"
                item["trashed_at"] = None
                item["archived_at"] = None
            elif req.action == "trash":
                item["status"] = "trash"
                item["trashed_at"] = now_iso
            elif req.action == "delete_permanent":
                if item["status"] != "trash":
                    continue
                item["status"] = "deleted"
            elif req.action == "empty_trash":
                if item["status"] != "trash":
                    continue
                item["status"] = "deleted"
            elif req.action == "set_retention":
                item["retention_days"] = req.retention_days or 30
            conn.execute(
                """
                INSERT INTO artifact_library_state
                    (artifact_id, status, retention_days, trashed_at, archived_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    status = excluded.status,
                    retention_days = excluded.retention_days,
                    trashed_at = excluded.trashed_at,
                    archived_at = excluded.archived_at,
                    updated_at = excluded.updated_at
                """,
                (
                    fid,
                    item["status"],
                    item["retention_days"],
                    item["trashed_at"],
                    item["archived_at"],
                    now_iso,
                ),
            )
            affected += 1

    return {"status": "ok", "action": req.action, "affected_count": affected}


@app.get("/api/artifacts/download/{artifact_id}")
async def download_artifact_by_id(artifact_id: str):
    """Unified file download endpoint for all artifacts."""
    if artifact_id in ("excel", "xlsx-master"):
        return await download_excel()
    elif artifact_id in ("csv", "csv-master"):
        return await download_csv()
    elif artifact_id in ("eval-report", "report"):
        path = settings.export_dir / "metrixa_evaluation_ablation_report.md"
        if not path.exists():
            path = settings.export_dir / "evaluation_ablation_report.md"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail="Evaluation report not generated yet. Please run Stage 06 (Export) from Mission Control.",
            )
        return FileResponse(
            path=path,
            filename="metrixa_evaluation_ablation_report.md",
            media_type="text/markdown",
        )
    elif artifact_id in ("exec-brief", "presentation"):
        path = settings.export_dir / "metrixa_executive_presentation.md"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail="Executive presentation not generated yet. Please run Stage 06 (Export) from Mission Control.",
            )
        return FileResponse(
            path=path,
            filename="metrixa_executive_presentation.md",
            media_type="text/markdown",
        )
    elif artifact_id in ("database", "db-snapshot"):
        return FileResponse(
            path=settings.database_path,
            filename="metrixa_leads.db",
            media_type="application/x-sqlite3",
        )
    elif artifact_id in ("pdf-casestudy", "casestudy", "pdf"):
        path = settings.export_dir / "Case_Study_Metrixa_Systems.pdf"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail="Case study PDF not generated yet. Please run Stage 06 (Export) from Mission Control.",
            )
        return FileResponse(
            path=path,
            filename="Case_Study_Metrixa_Systems.pdf",
            media_type="application/pdf",
        )
    elif artifact_id in ("google-sheets-live", "sheet", "google-sheets"):
        with db.connect() as conn:
            g_cnt = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
            ).fetchone()[0]
        if g_cnt == 0:
            raise HTTPException(
                status_code=404,
                detail="Google Sheets mirror not generated yet. Please run the pipeline first.",
            )
        sheet_status = next(
            item
            for item in GoogleSheetsSync(db).get_live_deliverables_status()[
                "deliverables"
            ]
            if item["id"] == "google_sheets_live"
        )
        if sheet_status["status"] != "SYNCED" or not sheet_status["download_url"]:
            raise HTTPException(
                status_code=404,
                detail="Google Sheets is not configured and fully synchronized.",
            )
        return RedirectResponse(sheet_status["download_url"])

    raise HTTPException(status_code=404, detail="Deliverable not found")


@app.get("/api/artifacts/download/excel")
async def download_excel():
    """Download styled 4-Tab Master Excel (.xlsx) file."""
    path = settings.export_dir / "metrixa_berlin_hausverwaltungen.xlsx"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Excel deliverable not generated yet. Please run Stage 06 (Export) from Mission Control.",
        )
    return FileResponse(
        path=path,
        filename="metrixa_berlin_hausverwaltungen.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/artifacts/download/csv")
async def download_csv():
    """Download Master CSV file."""
    path = settings.export_dir / "metrixa_berlin_leads_master.csv"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="CSV deliverable not generated yet. Please run Stage 06 (Export) from Mission Control.",
        )
    return FileResponse(
        path=path,
        filename="metrixa_berlin_leads_master.csv",
        media_type="text/csv",
    )


@app.get("/api/artifacts/evaluation-report", response_class=PlainTextResponse)
async def get_evaluation_report():
    """Return raw markdown of the evaluation and ablation report."""
    path = settings.export_dir / "metrixa_evaluation_ablation_report.md"
    if not path.exists():
        path = settings.export_dir / "evaluation_ablation_report.md"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Evaluation report not generated yet. Please run Stage 06 (Export) from Mission Control.",
        )
    return path.read_text(encoding="utf-8")


# ============================================================================
# REAL-TIME GOOGLE SHEETS API PUSH & DELIVERABLES PIPELINE
# ============================================================================


@app.get("/api/deliverables/status")
async def get_deliverables_status():
    """Audit real-time status of all local and cloud data deliverables."""
    sync_engine = GoogleSheetsSync(db)
    return sync_engine.get_live_deliverables_status()


@app.post("/api/deliverables/sync-all")
async def sync_all_deliverables_endpoint():
    """Synchronize all deliverables across Excel, CSV, and Google Sheets."""
    with db.connect() as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
        ).fetchone()[0]
    if cnt == 0:
        return {
            "success": False,
            "local_exports_ready": False,
            "cloud_sync_success": False,
            "status": "NO_DATA",
            "duration_ms": 0,
            "excel": None,
            "google_sheets": None,
            "live_status": {},
            "message": "No qualified leads in database. Run pipeline to generate deliverables.",
        }
    sync_engine = GoogleSheetsSync(db)
    res = sync_engine.sync_all_deliverables()
    _preview_cache.clear()
    _sha256_cache.clear()
    return res


@app.post("/api/deliverables/google-sheets/test")
async def test_google_sheets_endpoint(req: GoogleSheetsSyncRequest | None = None):
    """Test Google Sheets authentication, permissions, and sheet reachability."""
    sync_engine = GoogleSheetsSync(db)
    sheet_id = req.sheet_id if req else None
    sa_file = req.service_account_file if req else None
    sa_json = req.service_account_json if req else None
    return sync_engine.test_connection(
        sheet_id=sheet_id,
        service_account_file=sa_file,
        service_account_json=sa_json,
    )


@app.post("/api/deliverables/google-sheets/sync")
async def sync_google_sheets_endpoint(req: GoogleSheetsSyncRequest | None = None):
    """Push 4 canonical tabs to Google Sheets API or configured webhook."""
    sync_engine = GoogleSheetsSync(db)
    sheet_id = req.sheet_id if req else None
    sa_file = req.service_account_file if req else None
    sa_json = req.service_account_json if req else None
    webhook = req.webhook_url if req else None
    res = sync_engine.sync_to_google_sheet(
        sheet_id=sheet_id,
        service_account_file=sa_file,
        service_account_json=sa_json,
        webhook_url=webhook,
    )
    _preview_cache.clear()
    return res


@app.get("/api/deliverables/google-sheets/preview")
async def get_google_sheets_preview():
    """Return top 25 records for each of the 4 tabs formatted for Google Sheets."""
    sync_engine = GoogleSheetsSync(db)
    tabs = sync_engine.extract_all_tabs_data()
    summary: dict[str, Any] = {}
    for tname, (headers, rows) in tabs.items():
        summary[tname] = {
            "headers": headers,
            "total_rows": len(rows),
            "preview_rows": rows[:25],
        }
    sheet_id = settings.google_sheet_id or None
    sheet_status = next(
        item
        for item in sync_engine.get_live_deliverables_status()["deliverables"]
        if item["id"] == "google_sheets_live"
    )
    return {
        "spreadsheet_id": sheet_id,
        "spreadsheet_url": sheet_status["download_url"],
        "cloud_sync_status": sheet_status["status"],
        "tabs": summary,
    }


@app.get("/api/deliverables/google-sheets/url")
async def get_google_sheets_url():
    """Return the direct Google Sheets URL or redirect target."""
    sheet_id = settings.google_sheet_id or None
    sheet_status = next(
        item
        for item in GoogleSheetsSync(db).get_live_deliverables_status()["deliverables"]
        if item["id"] == "google_sheets_live"
    )
    return {
        "spreadsheet_id": sheet_id,
        "spreadsheet_url": sheet_status["download_url"],
        "status": sheet_status["status"],
    }


# ============================================================================
# 5. AGENTIC TOOLS & PROVIDER SETTINGS
# ============================================================================


@app.get("/api/tools")
async def get_tools_catalog():
    """Return the registry of all scrapers, legal parsers, and verification tools with dynamic health and DB counts."""
    counts: dict[str, int] = {}
    try:
        with db.connect() as conn:
            raw_s = conn.execute(
                "SELECT source_name, COUNT(*) FROM raw_listings GROUP BY source_name"
            ).fetchall()
            for row in raw_s:
                counts[row[0]] = row[1]
            crawled_cnt = conn.execute("SELECT COUNT(*) FROM crawled_pages").fetchone()[
                0
            ]
            mx_cnt = conn.execute(
                "SELECT COUNT(*) FROM decision_makers WHERE email_status IN ('PATTERN_CANDIDATE_MX', 'PATTERN_MX_VERIFIED', 'PUBLIC_LISTED', 'PUBLIC_DIRECT_VERIFIED')"
            ).fetchone()[0]
    except Exception:
        crawled_cnt = 0
        mx_cnt = 0

    return [
        {
            "id": "tool_gelbe_seiten",
            "name": "Gelbe Seiten Berlin Scraper",
            "category": "Directory Scraper",
            "status": "ready",
            "description": "Multi-keyword pagination with 23 Berlin district shards and base64 URL decoder.",
            "records_extracted": counts.get("gelbe_seiten", 0),
            "engine": "Python 3.12 / httpx HTTP/2 + BeautifulSoup4 lxml",
            "target": "https://www.gelbeseiten.de",
        },
        {
            "id": "tool_11880",
            "name": "11880.com Directory Scraper",
            "category": "Directory Scraper",
            "status": "ready",
            "description": "JSON-LD & HTML card parser with Cloudflare XOR email-protection decrypter.",
            "records_extracted": counts.get("11880", 0),
            "engine": "Python 3.12 / Cloudflare XOR Byte Decryptor",
            "target": "https://www.11880.com",
        },
        {
            "id": "tool_vdiv",
            "name": "VDIV Berlin-Brandenburg Association",
            "category": "Certified Association",
            "status": "ready",
            "description": "Reads member records returned by the live VDIV directory; results are not assumed to manage a particular number of units.",
            "records_extracted": counts.get("vdiv", 0),
            "engine": "Python 3.12 / VDIV BB Scraper + Member Schema",
            "target": "https://www.vdiv.de",
        },
        {
            "id": "tool_osm",
            "name": "OpenStreetMap Overpass API",
            "category": "Geospatial Parser",
            "status": "ready",
            "description": "Queries Berlin bounding box for office=property_management nodes.",
            "records_extracted": counts.get("osm", 0),
            "engine": "Python 3.12 / Overpass QL GeoJSON Client",
            "target": "https://overpass-api.de/api/interpreter",
        },
        {
            "id": "tool_crawler",
            "name": "Async Impressum & Subpage Crawler",
            "category": "Web Crawler",
            "status": "ready",
            "description": "HTTP/2 async crawler discovering /, /impressum, /team, /leistungen, and /portal.",
            "records_extracted": crawled_cnt,
            "engine": "Python 3.12 / Async httpx + Regex PropTech / ERP Scanner",
            "target": "Corporate Domains (/impressum, /team, /portal)",
        },
        {
            "id": "tool_mx_verifier",
            "name": "DNS MX Mail Server Verifier",
            "category": "Network Verification",
            "status": "ready",
            "description": "dnspython RFC resolver verifying live corporate mail servers.",
            "records_extracted": mx_cnt,
            "engine": "Python 3.12 / dnspython (RFC 5321 MX Resolver)",
            "target": "DNS Port 53 (UDP/TCP Live Resolver)",
        },
    ]


@app.post("/api/tools/test/{tool_id}")
async def test_tool_health(tool_id: str):
    """Execute a real, live health test against the underlying scraper, resolver, or parser."""
    t0 = time.time()

    if tool_id == "tool_mx_verifier":
        from metrixa_engine.enrichment.email_verifier import EmailVerifier

        with db.connect() as conn:
            row = conn.execute(
                "SELECT canonical_domain FROM companies_golden WHERE canonical_domain IS NOT NULL AND canonical_domain != '' ORDER BY company_id LIMIT 1"
            ).fetchone()
        if not row:
            return {
                "tool_id": tool_id,
                "status": "DEGRADED",
                "latency_ms": round((time.time() - t0) * 1000, 1),
                "target": "DNS MX resolver",
                "probe_result": "No company domain is available in the local database.",
                "message": "Add real company records before testing MX lookup.",
                "records_checked": 0,
            }

        verifier = EmailVerifier()
        test_domain = str(row[0])
        ok, mx_host = verifier.check_domain_mx_sync(test_domain)
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "tool_id": tool_id,
            "status": "OK" if ok else "DEGRADED",
            "latency_ms": latency_ms,
            "target": "DNS MX resolver using a domain from the local database",
            "probe_result": f"MX host: {mx_host}" if ok else "No MX record found",
            "message": "Domain-level MX lookup completed. This does not verify an individual mailbox.",
            "records_checked": 1,
            "details": {
                "tested_domain": test_domain,
                "primary_mx": mx_host,
                "domain_has_mx": ok,
                "mailbox_verified": False,
            },
        }

    elif tool_id == "tool_crawler":
        from metrixa_engine.crawler.tech_detector import (
            scan_html_for_tech_and_contacts,
        )

        with db.connect() as conn:
            row = conn.execute(
                "SELECT clean_markdown, url FROM crawled_pages WHERE http_status = 200 AND COALESCE(TRIM(clean_markdown), '') != '' ORDER BY crawled_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return {
                "tool_id": tool_id,
                "status": "DEGRADED",
                "latency_ms": round((time.time() - t0) * 1000, 1),
                "target": "Stored successful crawl page",
                "probe_result": "No successful crawl content is available in the local database.",
                "message": "Run the crawler on real company websites before testing extraction.",
                "records_checked": 0,
            }
        res = scan_html_for_tech_and_contacts(row["clean_markdown"])
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "tool_id": tool_id,
            "status": "OK" if row["clean_markdown"].strip() else "DEGRADED",
            "latency_ms": latency_ms,
            "target": str(row["url"]),
            "probe_result": f"Detected ERP: {res['erp_list']}, Metering: {res['metering_list']}, Portal: {res['has_portal']}",
            "records_checked": 1,
            "detected_signals": {
                "erp_count": len(res["erp_list"]),
                "metering_count": len(res["metering_list"]),
                "has_portal": res["has_portal"],
            },
            "message": f"Parser checked stored crawl content in {latency_ms}ms.",
            "details": res,
        }

    elif tool_id == "tool_vdiv":
        try:
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                resp = await client.head(
                    "https://www.vdiv.de", headers={"User-Agent": "Mozilla/5.0"}
                )
                status_code = resp.status_code
        except Exception:
            status_code = None
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "tool_id": tool_id,
            "status": (
                "OK"
                if status_code is not None and 200 <= status_code < 400
                else "DEGRADED" if status_code is not None else "ERROR"
            ),
            "latency_ms": latency_ms,
            "target": "https://www.vdiv.de (VDIV Certified Association Endpoint)",
            "probe_result": (
                f"HTTP status {status_code}"
                if status_code is not None
                else "Connection failed"
            ),
            "message": f"VDIV endpoint probe {'completed' if status_code is not None else 'failed'} in {latency_ms}ms.",
            "details": {"http_status": status_code},
        }

    elif tool_id == "tool_gelbe_seiten":
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(
                    "https://www.gelbeseiten.de/robots.txt",
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                status_code = resp.status_code
        except Exception:
            status_code = None
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "tool_id": tool_id,
            "status": (
                "OK"
                if status_code is not None and 200 <= status_code < 400
                else "DEGRADED" if status_code is not None else "ERROR"
            ),
            "latency_ms": latency_ms,
            "target": "https://www.gelbeseiten.de/robots.txt",
            "probe_result": (
                f"HTTP status {status_code}"
                if status_code is not None
                else "Connection failed"
            ),
            "message": f"Gelbe Seiten endpoint probe {'completed' if status_code is not None else 'failed'} in {latency_ms}ms.",
            "details": {
                "http_status": status_code,
                "shards_configured": 23,
            },
        }

    elif tool_id == "tool_11880":
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(
                    "https://www.11880.com/robots.txt",
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                status_code = resp.status_code
        except Exception:
            status_code = None
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "tool_id": tool_id,
            "status": (
                "OK"
                if status_code is not None and 200 <= status_code < 400
                else "DEGRADED" if status_code is not None else "ERROR"
            ),
            "latency_ms": latency_ms,
            "target": "https://www.11880.com/robots.txt",
            "probe_result": (
                f"HTTP status {status_code}"
                if status_code is not None
                else "Connection failed"
            ),
            "message": f"11880.com endpoint probe {'completed' if status_code is not None else 'failed'} in {latency_ms}ms.",
            "details": {
                "http_status": status_code,
                "xor_decryptor": "available",
            },
        }

    elif tool_id == "tool_osm":
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(
                    "https://overpass-api.de/api/status",
                    headers={"User-Agent": "MetrixaEngine/1.0"},
                )
                status_code = resp.status_code
        except Exception:
            status_code = None
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "tool_id": tool_id,
            "status": (
                "OK"
                if status_code is not None and 200 <= status_code < 400
                else "DEGRADED" if status_code is not None else "ERROR"
            ),
            "latency_ms": latency_ms,
            "target": "https://overpass-api.de/api/interpreter (Berlin Bounding Box)",
            "probe_result": (
                f"HTTP status {status_code}"
                if status_code is not None
                else "Connection failed"
            ),
            "message": f"Overpass status probe {'completed' if status_code is not None else 'failed'} in {latency_ms}ms.",
            "details": {
                "http_status": status_code,
                "bbox": "52.338,13.088,52.675,13.761",
            },
        }

    raise HTTPException(status_code=404, detail="Tool not found")


@app.post("/api/tools/execute")
async def execute_tool(payload: dict[str, Any]):
    """Execute a real tool action with custom user inputs in real-time."""
    tool_id = payload.get("tool_id")
    user_input = (payload.get("input") or "").strip()
    t0 = time.time()

    if tool_id == "tool_mx_verifier":
        from metrixa_engine.enrichment.email_verifier import EmailVerifier

        verifier = EmailVerifier()
        if not user_input:
            raise HTTPException(
                status_code=422,
                detail="Enter a real company domain or email address to check.",
            )
        domain = user_input
        if "@" in domain:
            domain = domain.split("@")[-1]
        domain = domain.strip().lower().rstrip(".")
        if not re.fullmatch(
            r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
            domain,
        ):
            raise HTTPException(
                status_code=422, detail="Enter a valid DNS domain or email address."
            )
        ok, mx_host = verifier.check_domain_mx_sync(domain)
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "success": True,
            "tool_id": tool_id,
            "input": domain,
            "latency_ms": latency_ms,
            "output": {
                "domain": domain,
                "has_valid_mx": ok,
                "primary_mx_host": mx_host or "None detected",
                "rfc_status": "DOMAIN_HAS_MX" if ok else "DOMAIN_HAS_NO_MX",
                "mailbox_verified": False,
                "verification_time": f"{latency_ms}ms",
            },
        }

    elif tool_id == "tool_crawler":
        from metrixa_engine.crawler.tech_detector import (
            scan_html_for_tech_and_contacts,
        )

        if not user_input:
            raise HTTPException(
                status_code=422,
                detail="Paste real website text or HTML to inspect.",
            )
        text_to_scan = user_input
        res = scan_html_for_tech_and_contacts(text_to_scan)
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "success": True,
            "tool_id": tool_id,
            "input": text_to_scan[:120] + ("..." if len(text_to_scan) > 120 else ""),
            "latency_ms": latency_ms,
            "output": {
                "detected_proptech_erp": res["erp_list"],
                "detected_metering_incumbents": res["metering_list"],
                "has_customer_portal": res["has_portal"],
                "extracted_emails": res["emails"],
                "linkedin_urls": res["linkedin_urls"],
            },
        }

    elif tool_id in (
        "tool_gelbe_seiten",
        "tool_11880",
        "tool_vdiv",
        "tool_osm",
    ):
        source_key = {
            "tool_gelbe_seiten": "gelbe_seiten",
            "tool_11880": "11880",
            "tool_vdiv": "vdiv",
            "tool_osm": "osm",
        }[tool_id]

        with db.connect() as conn:
            query = user_input.lower()
            if query:
                rows = conn.execute(
                    """
                    SELECT raw_company_name, raw_street, raw_postal_code, raw_city, raw_district, raw_phone, raw_website
                    FROM raw_listings
                    WHERE source_name = ? AND (lower(raw_company_name) LIKE ? OR lower(raw_district) LIKE ?)
                    LIMIT 5
                    """,
                    (source_key, f"%{query}%", f"%{query}%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT raw_company_name, raw_street, raw_postal_code, raw_city, raw_district, raw_phone, raw_website
                    FROM raw_listings
                    WHERE source_name = ?
                    LIMIT 5
                    """,
                    (source_key,),
                ).fetchall()

        latency_ms = round((time.time() - t0) * 1000, 1)
        results = [
            {
                "company_name": r[0],
                "address": f"{r[1] or ''}, {r[2] or ''} {r[3] or ''}".strip(", "),
                "district": r[4] or "Berlin",
                "phone": r[5] or "N/A",
                "website": r[6] or "N/A",
            }
            for r in rows
        ]
        return {
            "success": True,
            "tool_id": tool_id,
            "input": user_input or f"All {source_key} records",
            "latency_ms": latency_ms,
            "output": {
                "source": source_key,
                "matches_found": len(results),
                "sample_listings": results,
            },
        }

    raise HTTPException(status_code=400, detail="Invalid tool_id")


def _persist_runtime_settings(updates: dict[str, Any]) -> None:
    """Persist user-selected settings atomically in the ignored local .env file."""
    env_path = (
        Path(os.environ.get("METRIXA_ENV_PATH", str(settings.project_root / ".env")))
        .expanduser()
        .resolve()
    )
    env_path.parent.mkdir(parents=True, exist_ok=True)
    original = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    newline = "\r\n" if "\r\n" in original else "\n"
    lines = original.splitlines(keepends=True)

    for field_name, value in updates.items():
        key = field_name.upper()
        raw_value = str(value).lower() if isinstance(value, bool) else str(value)
        escaped = (
            raw_value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
        )
        assignment = f'{key}="{escaped}"'
        matcher = re.compile(rf"^\s*(?:export\s+)?{re.escape(key)}\s*=")
        for index, line in enumerate(lines):
            if matcher.match(line):
                line_ending = (
                    "\r\n"
                    if line.endswith("\r\n")
                    else "\n" if line.endswith("\n") else ""
                )
                lines[index] = assignment + line_ending
                break
        else:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += newline
            lines.append(assignment + newline)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=env_path.parent,
            prefix=f".{env_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write("".join(lines))
        os.replace(temporary_path, env_path)
    except OSError:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        raise


@app.get("/api/settings")
async def get_settings():
    """Return runtime provider settings with masked keys."""
    return {
        "default_llm_provider": settings.default_llm_provider,
        "default_search_provider": settings.default_search_provider,
        "deepseek_configured": bool(settings.deepseek_api_key),
        "deepseek_base_url": settings.deepseek_base_url,
        "deepseek_model": settings.deepseek_model,
        "gemini_configured": bool(settings.gemini_api_key),
        "gemini_base_url": settings.gemini_base_url,
        "gemini_model": settings.gemini_model,
        "openai_configured": bool(settings.openai_api_key),
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "nvidia_nim_configured": bool(settings.nvidia_nim_api_key),
        "nvidia_nim_base_url": settings.nvidia_nim_base_url,
        "nvidia_nim_model": settings.nvidia_nim_model,
        "llamacpp_base_url": settings.llamacpp_base_url,
        "llamacpp_model": settings.llamacpp_model,
        "lmstudio_base_url": settings.lmstudio_base_url,
        "lmstudio_model": settings.lmstudio_model,
        "searxng_base_url": settings.searxng_base_url,
        "enable_native_metasearch": settings.enable_native_metasearch,
        "tavily_configured": bool(settings.tavily_api_key),
        "google_cse_configured": bool(settings.google_cse_api_key),
        "google_cse_id": settings.google_cse_id,
        "brave_configured": bool(settings.brave_search_api_key),
        "max_concurrent_crawls": settings.max_concurrent_crawls,
        "http_timeout_seconds": settings.http_timeout_seconds,
    }


class SettingsUpdateRequest(BaseModel):
    default_llm_provider: (
        Literal[
            "auto_fallback",
            "deterministic",
            "openai",
            "deepseek",
            "gemini",
            "nvidia_nim",
            "ollama",
            "local_llamacpp",
            "lm_studio",
        ]
        | None
    ) = None
    default_search_provider: (
        Literal["searxng", "native_metasearch", "tavily", "google_cse", "brave"] | None
    ) = None
    deepseek_api_key: str | None = None
    deepseek_base_url: str | None = None
    deepseek_model: str | None = None
    gemini_api_key: str | None = None
    gemini_base_url: str | None = None
    gemini_model: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    nvidia_nim_api_key: str | None = None
    nvidia_nim_base_url: str | None = None
    nvidia_nim_model: str | None = None
    llamacpp_base_url: str | None = None
    llamacpp_model: str | None = None
    lmstudio_base_url: str | None = None
    lmstudio_model: str | None = None
    searxng_base_url: str | None = None
    tavily_api_key: str | None = None
    google_cse_api_key: str | None = None
    google_cse_id: str | None = None
    brave_search_api_key: str | None = None
    max_concurrent_crawls: int | None = Field(default=None, ge=1, le=100)


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    """Validate, persist, and activate user-selected local provider settings."""
    updates = req.model_dump(exclude_none=True)
    if "searxng_base_url" in updates:
        updates["searxng_base_url"] = updates["searxng_base_url"].strip().rstrip("/")

    if updates:
        try:
            with _settings_persist_lock:
                _persist_runtime_settings(updates)
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail="Settings could not be saved to the local configuration file.",
            ) from exc
        for field_name, value in updates.items():
            setattr(settings, field_name, value)

    return {
        "status": "saved",
        "persisted": True,
        "active_provider": settings.default_llm_provider,
        "active_search": settings.default_search_provider,
    }


class ProviderPingRequest(BaseModel):
    provider: str
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None


@app.post("/api/providers/ping")
async def ping_provider(req: ProviderPingRequest):
    """
    Test connection ping for any LLM provider.
    Sends a minimal prompt to verify reachability, authentication, and response latency.
    """
    import time

    import httpx

    t0 = time.perf_counter()

    # 1. Deterministic Parser Ping
    if req.provider in ("deterministic", "regex"):
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "reply": "Deterministic German legal parser responded.",
            "model": "regex_german_impressum_v2",
            "tokens": 0,
        }

    if req.provider == "auto_fallback":
        return {
            "status": "degraded",
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "reply": "Auto fallback is a routing policy. Select a specific provider to test its live connection; deterministic extraction remains available locally.",
            "model": None,
            "tokens": 0,
        }

    # 2. Map provider to base_url, model, and api_key (zero hardcoded model stubs)
    provider_map = {
        "deepseek": {
            "base_url": req.base_url
            or settings.deepseek_base_url
            or "https://api.deepseek.com/v1",
            "model": req.model or settings.deepseek_model or "",
            "api_key": req.api_key or settings.deepseek_api_key or "",
        },
        "gemini": {
            "base_url": req.base_url
            or settings.gemini_base_url
            or "https://generativelanguage.googleapis.com/v1beta/openai",
            "model": req.model or settings.gemini_model or "",
            "api_key": req.api_key or settings.gemini_api_key or "",
        },
        "openai": {
            "base_url": req.base_url
            or settings.openai_base_url
            or "https://api.openai.com/v1",
            "model": req.model or settings.openai_model or "",
            "api_key": req.api_key or settings.openai_api_key or "",
        },
        "ollama": {
            "base_url": req.base_url
            or settings.ollama_base_url
            or "http://localhost:11434/v1",
            "model": req.model or settings.ollama_model or "",
            "api_key": req.api_key or "ollama-local",
        },
        "lm_studio": {
            "base_url": req.base_url
            or settings.lmstudio_base_url
            or "http://localhost:1234/v1",
            "model": req.model or settings.lmstudio_model or "",
            "api_key": req.api_key or settings.lmstudio_api_key or "lm-studio",
        },
        "local_llamacpp": {
            "base_url": req.base_url
            or settings.llamacpp_base_url
            or "http://localhost:8080/v1",
            "model": req.model or settings.llamacpp_model or "",
            "api_key": req.api_key or settings.llamacpp_api_key or "local-no-key",
        },
        "nvidia_nim": {
            "base_url": req.base_url
            or settings.nvidia_nim_base_url
            or "https://integrate.api.nvidia.com/v1",
            "model": req.model or settings.nvidia_nim_model or "",
            "api_key": req.api_key or settings.nvidia_nim_api_key or "",
        },
    }

    target = provider_map.get(req.provider)
    if target is None:
        raise HTTPException(status_code=400, detail="Unsupported LLM provider.")
    base_url = str(target.get("base_url") or "").rstrip("/")
    model = str(target.get("model") or "").strip()
    api_key = str(target.get("api_key") or "").strip()

    if req.provider in ("openai", "gemini", "deepseek", "nvidia_nim") and not api_key:
        return {
            "status": "error",
            "latency_ms": 0,
            "error": "No API Key configured. Enter your API key above to authenticate and discover live models.",
        }

    if not model:
        return {
            "status": "error",
            "latency_ms": 0,
            "error": "No model selected. Discover live models using your API key (or local server) and choose a model from the list before testing connection.",
        }

    endpoint = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else "Bearer local",
    }
    is_o_series = model.lower() in ("o1", "o3", "o4") or model.lower().startswith(
        ("o1-", "o3-", "o4-")
    )
    is_reasoner = is_o_series or "reasoner" in model.lower()

    if is_o_series:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Respond only with: PONG"},
            ],
            "max_completion_tokens": 64,
        }
    elif is_reasoner:
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Respond only with: PONG"},
            ],
            "max_tokens": 128,
        }
    else:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a ping test validator. Output only the word: PONG",
                },
                {"role": "user", "content": "Ping test."},
            ],
            "max_tokens": 32,
            "temperature": 0.0,
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(endpoint, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            latency_ms = int((time.perf_counter() - t0) * 1000)

            choices = data.get("choices")
            if not choices and isinstance(data.get("candidates"), list):
                # Google Gemini native format fallback
                first_cand = data["candidates"][0] if data["candidates"] else {}
                content_obj = first_cand.get("content") or {}
                parts = content_obj.get("parts") or []
                raw_reply = parts[0].get("text") if parts else None
            else:
                choice = choices[0] if (choices and isinstance(choices, list)) else {}
                msg = choice.get("message") if isinstance(choice, dict) else {}
                if not isinstance(msg, dict):
                    msg = {}
                raw_reply = msg.get("content")
                if not raw_reply:
                    # Check reasoning models (DeepSeek Reasoner, OpenAI o1/o3-mini)
                    raw_reply = (
                        msg.get("reasoning_content")
                        or choice.get("text")
                        or data.get("text")
                    )

            reply = str(raw_reply or "").strip()
            if not reply:
                return {
                    "status": "error",
                    "latency_ms": latency_ms,
                    "error": "The provider returned a successful HTTP response without completion text.",
                }
            usage = data.get("usage") or {}
            tokens = usage.get("total_tokens")

            return {
                "status": "ok",
                "latency_ms": latency_ms,
                "reply": reply,
                "model": model,
                "tokens": tokens,
            }
    except httpx.ConnectError:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "error": f"Connection refused to {base_url}. Make sure your local server (Ollama / LM Studio / llama.cpp) is running.",
        }
    except httpx.HTTPStatusError as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        err_msg = f"HTTP {e.response.status_code}: {e.response.text[:150]}"
        if e.response.status_code == 401:
            err_msg = "Authentication Failed (401): Invalid or missing API key."
        elif e.response.status_code == 404:
            err_msg = f"Model '{model}' not found or endpoint 404 at {base_url}."
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "error": err_msg,
        }
    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "error": str(e),
        }


@app.post("/api/providers/models")
async def discover_provider_models(req: ProviderPingRequest):
    """
    Dynamically discover available LLM models and their metadata directly from a live provider endpoint.
    Strictly queries /v1/models, /api/tags (Ollama), or /v1beta/models (Gemini) with zero pre-filled stubs.
    """
    import time

    import httpx

    t0 = time.perf_counter()
    prov = req.provider

    provider_map = {
        "deepseek": {
            "base_url": req.base_url
            or settings.deepseek_base_url
            or "https://api.deepseek.com/v1",
            "api_key": req.api_key or settings.deepseek_api_key or "",
            "requires_key": True,
        },
        "gemini": {
            "base_url": req.base_url
            or settings.gemini_base_url
            or "https://generativelanguage.googleapis.com/v1beta/openai",
            "api_key": req.api_key or settings.gemini_api_key or "",
            "requires_key": True,
        },
        "openai": {
            "base_url": req.base_url
            or settings.openai_base_url
            or "https://api.openai.com/v1",
            "api_key": req.api_key or settings.openai_api_key or "",
            "requires_key": True,
        },
        "ollama": {
            "base_url": req.base_url
            or settings.ollama_base_url
            or "http://localhost:11434/v1",
            "api_key": req.api_key or "ollama-local",
            "requires_key": False,
        },
        "lm_studio": {
            "base_url": req.base_url
            or settings.lmstudio_base_url
            or "http://localhost:1234/v1",
            "api_key": req.api_key or settings.lmstudio_api_key or "lm-studio",
            "requires_key": False,
        },
        "local_llamacpp": {
            "base_url": req.base_url
            or settings.llamacpp_base_url
            or "http://localhost:8080/v1",
            "api_key": req.api_key or settings.llamacpp_api_key or "local-no-key",
            "requires_key": False,
        },
        "nvidia_nim": {
            "base_url": req.base_url
            or settings.nvidia_nim_base_url
            or "https://integrate.api.nvidia.com/v1",
            "api_key": req.api_key or settings.nvidia_nim_api_key or "",
            "requires_key": True,
        },
    }

    if prov not in provider_map:
        return {
            "status": "ok",
            "source": "system",
            "latency_ms": 1,
            "models": [],
        }

    target = provider_map[prov]
    base_url = str(target["base_url"]).rstrip("/")
    api_key = str(target["api_key"]).strip()
    requires_key = bool(target["requires_key"])

    if requires_key and not api_key:
        return {
            "status": "awaiting_key",
            "source": "awaiting_key",
            "latency_ms": 0,
            "message": "No API key configured: enter your API key above to auto-discover live models from the provider.",
            "models": [],
        }

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            # 1. Live discovery for Ollama via /api/tags
            if prov == "ollama":
                ollama_root = (
                    base_url[:-3] if base_url.endswith("/v1") else base_url
                ).rstrip("/")
                res = await client.get(f"{ollama_root}/api/tags")
                res.raise_for_status()
                data = res.json()
                raw_models = data.get("models", [])
                discovered: list[dict[str, Any]] = []
                for idx, m in enumerate(raw_models):
                    mid = m.get("name") or m.get("model") or ""
                    if not mid:
                        continue
                    details = m.get("details", {})
                    param_size = details.get("parameter_size", "")
                    quant = details.get("quantization_level", "")
                    family = details.get("family", "ollama")
                    size_gb = round((m.get("size") or 0) / (1024**3), 2)
                    discovered.append(
                        {
                            "id": mid,
                            "name": f"{mid} ({param_size})" if param_size else mid,
                            "context_window": "Local GGUF Context",
                            "capabilities": " • ".join(
                                filter(
                                    None,
                                    [
                                        f"Family: {family}" if family else "",
                                        f"Quant: {quant}" if quant else "",
                                        f"{size_gb} GB" if size_gb > 0 else "",
                                    ],
                                )
                            )
                            or "Local Ollama Model",
                            "owned_by": family,
                            "recommended": idx == 0,
                        }
                    )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                if discovered:
                    return {
                        "status": "ok",
                        "source": "live_api",
                        "latency_ms": latency_ms,
                        "message": f"Discovered {len(discovered)} local models from Ollama ({ollama_root}/api/tags).",
                        "models": discovered,
                    }

            # 2. Live discovery for Google Gemini via native v1beta/models
            if prov == "gemini":
                gem_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                res = await client.get(gem_url)
                res.raise_for_status()
                data = res.json()
                discovered = []
                for m in data.get("models", []):
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" not in methods:
                        continue
                    raw_name = m.get("name", "")
                    mid = raw_name.replace("models/", "")
                    if not mid:
                        continue
                    in_lim = m.get("inputTokenLimit")
                    out_lim = m.get("outputTokenLimit")
                    ctx_str = (
                        f"{in_lim:,} tokens"
                        if isinstance(in_lim, int) and in_lim > 0
                        else ""
                    )
                    caps = (
                        f"Max Output: {out_lim:,} tokens"
                        if isinstance(out_lim, int) and out_lim > 0
                        else "Google Generative Language API"
                    )
                    discovered.append(
                        {
                            "id": mid,
                            "name": m.get("displayName") or mid,
                            "context_window": ctx_str,
                            "capabilities": caps,
                            "owned_by": "google",
                            "recommended": False,
                        }
                    )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                if discovered:
                    return {
                        "status": "ok",
                        "source": "live_api",
                        "latency_ms": latency_ms,
                        "message": f"Discovered {len(discovered)} live models from Google Gemini API.",
                        "models": discovered,
                    }

            # 3. Standard OpenAI-Compatible /v1/models Discovery (OpenAI, DeepSeek, NVIDIA NIM, LM Studio, llama.cpp)
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}" if api_key else "Bearer local",
            }
            res = await client.get(f"{base_url}/models", headers=headers)
            res.raise_for_status()
            payload = res.json()
            raw_list = payload.get("data", []) if isinstance(payload, dict) else []
            discovered = []
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                mid = str(item.get("id", "")).strip()
                if not mid:
                    continue
                # Filter out non-chat models for OpenAI (e.g., whisper, tts, dall-e, text-embedding)
                if prov == "openai" and any(
                    skip in mid.lower()
                    for skip in (
                        "embedding",
                        "tts",
                        "whisper",
                        "dall-e",
                        "davinci",
                        "babbage",
                        "moderation",
                        "audio",
                        "realtime",
                    )
                ):
                    continue
                ctx_val = item.get("context_window") or item.get("max_model_len")
                if isinstance(ctx_val, int) and ctx_val > 0:
                    ctx_str = f"{ctx_val:,} tokens"
                elif ctx_val and not any(
                    k in str(ctx_val).lower() for k in ("live", "api", "model")
                ):
                    ctx_str = str(ctx_val).strip()
                else:
                    ctx_str = ""
                owner = str(item.get("owned_by", prov))
                discovered.append(
                    {
                        "id": mid,
                        "name": mid,
                        "context_window": ctx_str,
                        "capabilities": f"Owner: {owner}",
                        "owned_by": owner,
                        "recommended": False,
                    }
                )
            latency_ms = int((time.perf_counter() - t0) * 1000)
            if discovered:
                discovered.sort(key=lambda x: x["id"])
                return {
                    "status": "ok",
                    "source": "live_api",
                    "latency_ms": latency_ms,
                    "message": f"Discovered {len(discovered)} models from {base_url}/models.",
                    "models": discovered,
                }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "status": "offline",
            "source": "offline",
            "latency_ms": latency_ms,
            "message": f"Live endpoint unreachable or unauthorized ({str(exc)[:100]}).",
            "models": [],
        }

    latency_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "status": "empty",
        "source": "empty",
        "latency_ms": latency_ms,
        "message": "No models returned by remote endpoint.",
        "models": [],
    }


class SearchPingRequest(BaseModel):
    provider: str
    base_url: str | None = None
    api_key: str | None = None
    google_cse_id: str | None = None
    query: str | None = None


@app.post("/api/search/ping")
async def ping_search_provider(req: SearchPingRequest):
    """
    Test connection ping for Web Search providers (SearXNG, Tavily, Native Meta-Search, Brave, Google CSE).
    Verifies endpoint reachability, API key validity, and query latency.
    """
    import time

    import httpx

    t0 = time.perf_counter()
    query = (req.query or "").strip()
    if not query:
        raise HTTPException(
            status_code=422,
            detail="Enter a real search query before testing the search provider.",
        )

    # 1. Native Meta-Search (Local Direct Scraper Pipeline)
    if req.provider in ("native_metasearch", "internal"):
        from metrixa_engine.enrichment.search_router import search_router

        results = await search_router.search(
            query, max_results=5, allow_tavily_fallback=False
        )
        engines = sorted({item.engine for item in results})
        return {
            "status": "ok" if results else "degraded",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "reply": (
                f"Live search returned {len(results)} results."
                if results
                else "Live search returned no results."
            ),
            "results_count": len(results),
            "engines_active": len(engines),
            "engines": engines,
            "privacy": "Search request sent to the configured search endpoints.",
        }

    # 2. SearXNG Local Engine
    if req.provider == "searxng":
        url = (
            req.base_url or settings.searxng_base_url or "http://127.0.0.1:8888"
        ).rstrip("/")
        endpoint = f"{url}/search"
        params = {"q": query, "format": "json"}
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(endpoint, params=params)
                if res.status_code == 200:
                    data = res.json()
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    results = data.get("results", [])
                    engines = sorted(
                        {
                            str(item.get("engine"))
                            for item in results
                            if item.get("engine")
                        }
                    )
                    return {
                        "status": "ok",
                        "latency_ms": latency_ms,
                        "reply": f"SearXNG returned {len(results)} search results.",
                        "results_count": len(results),
                        "engines_active": len(engines),
                        "engines": engines,
                        "privacy": "Local endpoint; upstream engine behavior depends on SearXNG configuration.",
                    }
                return {
                    "status": "error",
                    "latency_ms": int((time.perf_counter() - t0) * 1000),
                    "reply": f"SearXNG returned HTTP {res.status_code}.",
                    "engines_active": 0,
                    "privacy": "No successful search completed.",
                }
        except Exception:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "reply": "SearXNG endpoint could not be reached; test native search separately.",
                "engines_active": 0,
                "privacy": "No search request completed.",
            }

    # 3. Tavily AI Search API
    if req.provider == "tavily":
        key = req.api_key or settings.tavily_api_key
        if not key:
            return {
                "status": "error",
                "latency_ms": 0,
                "error": "Tavily API Key is missing. Enter your key (e.g. tvly-...) to test.",
            }
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 2,
                    },
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "status": "ok",
                        "latency_ms": latency_ms,
                        "reply": f"Tavily Cloud Active: {len(data.get('results', []))} AI-curated sources returned",
                        "engines_active": 1,
                        "privacy": "Commercial Cloud API",
                    }
                else:
                    return {
                        "status": "error",
                        "latency_ms": latency_ms,
                        "error": f"Tavily Error ({res.status_code}): {res.text[:150]}",
                    }
        except Exception as e:
            return {
                "status": "error",
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "error": str(e),
            }

    # 4. Brave Search API
    if req.provider == "brave":
        key = req.api_key or settings.brave_search_api_key
        if not key:
            return {
                "status": "error",
                "latency_ms": 0,
                "error": "Brave Search API Key missing.",
            }
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": 2},
                    headers={"X-Subscription-Token": key, "Accept": "application/json"},
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                if res.status_code == 200:
                    results = (res.json().get("web") or {}).get("results") or []
                    return {
                        "status": "ok",
                        "latency_ms": latency_ms,
                        "reply": f"Brave returned {len(results)} search results.",
                        "results_count": len(results),
                        "engines_active": 1,
                        "privacy": "Brave Search API; query sent to Brave.",
                    }
                else:
                    return {
                        "status": "error",
                        "latency_ms": latency_ms,
                        "error": f"Brave Error ({res.status_code})",
                    }
        except Exception as e:
            return {
                "status": "error",
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "error": str(e),
            }

    if req.provider == "google_cse":
        key = req.api_key or settings.google_cse_api_key
        engine_id = req.google_cse_id or settings.google_cse_id
        if not key:
            return {
                "status": "error",
                "latency_ms": 0,
                "error": "Google Custom Search API key is not configured.",
            }
        if not engine_id:
            return {
                "status": "error",
                "latency_ms": 0,
                "error": "Google Custom Search Engine ID is not configured.",
            }
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": key,
                        "cx": engine_id,
                        "q": query,
                        "num": 2,
                    },
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                if res.status_code == 200:
                    results = res.json().get("items") or []
                    return {
                        "status": "ok",
                        "latency_ms": latency_ms,
                        "reply": f"Google Custom Search returned {len(results)} search results.",
                        "results_count": len(results),
                        "engines_active": 1,
                        "privacy": "Google Custom Search API; query sent to Google.",
                    }
                return {
                    "status": "error",
                    "latency_ms": latency_ms,
                    "error": f"Google Custom Search returned HTTP {res.status_code}.",
                }
        except Exception:
            return {
                "status": "error",
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "error": "Could not reach Google Custom Search.",
            }

    raise HTTPException(status_code=400, detail="Unsupported search provider.")
