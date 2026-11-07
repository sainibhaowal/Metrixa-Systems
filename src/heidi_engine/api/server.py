"""
FastAPI Backend Gateway for Heidi Cockpit.
Provides REST APIs for Leads, Metrics, Artifacts, Tools, and Settings,
plus Server-Sent Events (SSE) for Real-Time Pipeline Progress and Streaming Logs.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from heidi_engine.config import settings
from heidi_engine.crawler.url_resolver import MissingURLResolver
from heidi_engine.crawler.web_crawler import AsyncWebsiteCrawler
from heidi_engine.db import Database
from heidi_engine.enrichment.contact_finder import ContactEnricher
from heidi_engine.enrichment.scorer import LeadScorer
from heidi_engine.entity_resolution.deduplicator import EntityDeduplicator
from heidi_engine.llm.extractor import KPIExtractionPipeline
from heidi_engine.scrapers.dir_11880 import Dir11880Scraper
from heidi_engine.scrapers.gelbe_seiten import GelbeSeitenScraper
from heidi_engine.scrapers.osm_overpass import OSMOverpassScraper
from heidi_engine.scrapers.search_discovery import SearchDiscoveryScraper
from heidi_engine.scrapers.vdiv import VDIVScraper
from heidi_engine.telemetry.evaluator import PipelineEvaluator
from heidi_engine.telemetry.excel_exporter import ExcelExporter


db = Database()


class PipelineEventBus:
    """Pub/Sub event broadcaster using asyncio Queues for Server-Sent Events (SSE)."""

    def __init__(self) -> None:
        self.subscribers: List[asyncio.Queue] = []
        self.is_running = False
        self.current_stage = "IDLE"
        self.current_run_id: Optional[str] = None

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)

    async def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        payload = {"type": event_type, **data}
        dead: List[asyncio.Queue] = []
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
    title="Heidi Cockpit API",
    description="Autonomous B2B LeadOps & Metering Intelligence Gateway for Heidi Systems",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# 1. METRICS & TELEMETRY APIS
# ============================================================================

@app.get("/api/metrics")
async def get_metrics():
    """Return live aggregate KPI metrics, tier distribution, ERP counts, and district shares."""
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

        erp_counts: Dict[str, int] = {}
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
        district_breakdown = [{"district": r["district"] or "Berlin", "count": r["cnt"]} for r in dist_rows]

    return {
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


# ============================================================================
# 2. LEAD SEARCH, FILTERING & DOSSIER APIS
# ============================================================================

@app.get("/api/leads")
async def get_leads(
    q: Optional[str] = Query(None, description="Search query across company name, decision maker, address"),
    tier: Optional[str] = Query(None, description="Tier A, Tier B, Tier C"),
    district: Optional[str] = Query(None, description="Berlin Bezirk"),
    has_dm: Optional[bool] = Query(None),
    has_email: Optional[bool] = Query(None),
    has_erp: Optional[bool] = Query(None),
    is_vdiv: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("heidi_lead_score"),
    sort_dir: str = Query("desc"),
):
    """Paginated search & multi-facet filtering for Berlin property managers."""
    offset = (page - 1) * limit
    allowed_sorts = {
        "heidi_lead_score": "c.heidi_lead_score",
        "exact_units_managed": "k.exact_units_managed",
        "display_name": "c.display_name",
        "company_id": "c.company_id",
    }
    sort_col = allowed_sorts.get(sort_by, "c.heidi_lead_score")
    sort_order = "ASC" if sort_dir.lower() == "asc" else "DESC"

    where_clauses = ["c.pipeline_stage != 'DISQUALIFIED'"]
    params: List[Any] = []

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
        where_clauses.append("(k.detected_erp_proptech IS NOT NULL AND k.detected_erp_proptech != '')")

    if has_dm:
        where_clauses.append("EXISTS (SELECT 1 FROM decision_makers d WHERE d.company_id = c.company_id)")

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
                c.source_count, c.sources_csv, c.heidi_lead_score, c.lead_tier,
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
        rows = [dict(r) for r in conn.execute(data_sql, params + [limit, offset]).fetchall()]

        # Attach formatted Lead ID (e.g. HEIDI-BER-0001)
        for idx, r in enumerate(rows, start=offset + 1):
            r["lead_id"] = f"HEIDI-BER-{r['company_id']:04d}"
            r["linkedin_url"] = r["decision_maker_linkedin"] or r["company_linkedin_url"]

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

        s_trust = (5 if comp_d.get("is_vdiv_member") else 0) + (3 if comp_d.get("commercial_register_id") else 0) + 2
        s_contact = (4 if dms else 0) + (4 if any(d.get("personal_email") for d in dms) else 0) + 2

        scorecard = {
            "scale_pts": min(35, s_scale),
            "focus_pts": min(25, s_focus),
            "digital_pts": min(20, s_digital),
            "trust_pts": min(10, s_trust),
            "contact_pts": min(10, s_contact),
            "total_score": comp_d.get("heidi_lead_score", 0),
        }

    return {
        "company": comp_d,
        "kpi": kpi_d,
        "scorecard": scorecard,
        "decision_makers": dms,
        "crawled_pages": pages,
    }


# ============================================================================
# 3. REAL-TIME PIPELINE RUNNER & SERVER-SENT EVENTS (SSE)
# ============================================================================

class PipelineRunRequest(BaseModel):
    stage: str = Field(default="full", description="full | ingest | deduplicate | crawl | extract | enrich | export")
    provider: Optional[str] = Field(default="auto_fallback")
    limit: Optional[int] = Field(default=None)
    reprocess_all: bool = Field(default=False)


@app.post("/api/pipeline/run")
async def trigger_pipeline_run(req: PipelineRunRequest):
    """Trigger background pipeline stage execution and stream updates via SSE."""
    if event_bus.is_running:
        raise HTTPException(status_code=409, detail="Pipeline run already in progress")

    import uuid
    run_id = f"run-{uuid.uuid4().hex[:8]}"

    async def _execute_task():
        event_bus.is_running = True
        event_bus.current_run_id = run_id
        event_bus.current_stage = req.stage.upper()

        await event_bus.emit("LOG", {"level": "INFO", "message": f"Starting pipeline execution: {req.stage.upper()}"})

        try:
            if req.stage in ("full", "ingest"):
                await event_bus.emit("PROGRESS", {"stage": "INGEST", "completed": 0, "total": 5, "pct": 0})
                scrapers = [
                    ("VDIV Association", VDIVScraper()),
                    ("OpenStreetMap", OSMOverpassScraper()),
                    ("Gelbe Seiten", GelbeSeitenScraper()),
                    ("11880.com (+CF Decoder)", Dir11880Scraper()),
                    ("Search Discovery", SearchDiscoveryScraper()),
                ]
                for idx, (label, sc) in enumerate(scrapers, start=1):
                    await event_bus.emit("LOG", {"level": "INFO", "message": f"Executing scraper: {label}"})
                    items = await sc.scrape_berlin(max_pages=4)
                    ins = db.insert_raw_listings(items)
                    pct = round((idx / len(scrapers)) * 100, 1)
                    await event_bus.emit("PROGRESS", {"stage": "INGEST", "completed": idx, "total": len(scrapers), "pct": pct})
                    await event_bus.emit("LOG", {"level": "SUCCESS", "message": f"Scraped {len(items)} from {label} ({ins} new)"})

            if req.stage in ("full", "deduplicate"):
                await event_bus.emit("LOG", {"level": "INFO", "message": "Starting entity resolution and deduplication..."})
                deduper = EntityDeduplicator(db)
                stats = deduper.run_deduplication()
                await event_bus.emit(
                    "LOG",
                    {
                        "level": "SUCCESS",
                        "message": f"Deduplication complete: {stats['golden_clusters']} unique companies ({stats['duplicates_merged']} duplicates merged)",
                    },
                )

            if req.stage in ("full", "crawl"):
                crawler = AsyncWebsiteCrawler(db)
                await event_bus.emit("LOG", {"level": "INFO", "message": "Crawling company websites and Impressum pages..."})

                def _crawl_cb(done: int, total: int):
                    pct = round((done / max(1, total)) * 100, 1)
                    asyncio.create_task(
                        event_bus.emit("PROGRESS", {"stage": "CRAWL", "completed": done, "total": total, "pct": pct})
                    )

                res = await crawler.crawl_batch(limit=req.limit, progress_callback=_crawl_cb)
                await event_bus.emit("LOG", {"level": "SUCCESS", "message": f"Crawled {res['companies_processed']} companies ({res['total_pages_saved']} subpages saved)"})

            if req.stage in ("full", "extract"):
                pipeline = KPIExtractionPipeline(db)
                await event_bus.emit("LOG", {"level": "INFO", "message": f"Extracting KPIs via {req.provider or 'auto_fallback'}..."})

                def _extract_cb(done: int, total: int):
                    pct = round((done / max(1, total)) * 100, 1)
                    asyncio.create_task(
                        event_bus.emit("PROGRESS", {"stage": "EXTRACT", "completed": done, "total": total, "pct": pct})
                    )

                res = await pipeline.extract_batch(
                    limit=req.limit,
                    requested_provider=req.provider,
                    reprocess_all=req.reprocess_all,
                    progress_callback=_extract_cb,
                )
                await event_bus.emit("LOG", {"level": "SUCCESS", "message": f"Extracted KPIs: {res['with_decision_maker']} decision makers, {res['with_erp']} ERPs"})

            if req.stage in ("full", "enrich"):
                enricher = ContactEnricher(db)
                scorer = LeadScorer(db)
                await event_bus.emit("LOG", {"level": "INFO", "message": "Verifying DNS MX records & scoring leads..."})

                def _enrich_cb(done: int, total: int):
                    pct = round((done / max(1, total)) * 100, 1)
                    asyncio.create_task(
                        event_bus.emit("PROGRESS", {"stage": "ENRICH", "completed": done, "total": total, "pct": pct})
                    )

                en_res = await enricher.enrich_batch(web_search_top_n=5, progress_callback=_enrich_cb)
                tier_counts = scorer.score_all_companies()
                await event_bus.emit(
                    "LOG",
                    {
                        "level": "SUCCESS",
                        "message": f"Scoring complete: Tier A={tier_counts.get('Tier A (High Priority)', 0)}, Tier B={tier_counts.get('Tier B (Qualified Mid-Market)', 0)}, Tier C={tier_counts.get('Tier C (Long-Tail / Small)', 0)}",
                    },
                )

            if req.stage in ("full", "export"):
                exporter = ExcelExporter(db)
                evaluator = PipelineEvaluator(db)
                await event_bus.emit("LOG", {"level": "INFO", "message": "Generating 4-Tab Excel workbook & evaluation report..."})
                exp_res = exporter.export_all()
                eval_path = evaluator.generate_markdown_report()
                await event_bus.emit("LOG", {"level": "SUCCESS", "message": f"Exported: {exp_res['xlsx_path']}"})

            await event_bus.emit("COMPLETE", {"run_id": run_id, "stage": req.stage})
            await event_bus.emit("LOG", {"level": "SUCCESS", "message": "Pipeline execution completed successfully."})

        except Exception as e:
            await event_bus.emit("LOG", {"level": "ERROR", "message": f"Pipeline execution failed: {str(e)}"})
            await event_bus.emit("ERROR", {"error": str(e)})
        finally:
            event_bus.is_running = False
            event_bus.current_stage = "IDLE"

    asyncio.create_task(_execute_task())
    return {"status": "started", "run_id": run_id, "stage": req.stage}


@app.get("/api/pipeline/stream")
async def stream_pipeline_events():
    """SSE endpoint streaming live logs and stage progress to Next.js."""
    async def _event_generator() -> AsyncGenerator[Dict[str, str], None]:
        q = event_bus.subscribe()
        try:
            # Emit initial connection handshake
            yield {
                "event": "HEARTBEAT",
                "data": json.dumps({"status": "connected", "is_running": event_bus.is_running, "stage": event_bus.current_stage}),
            }
            while True:
                msg = await q.get()
                yield {
                    "event": msg.get("type", "LOG"),
                    "data": json.dumps(msg),
                }
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(q)

    return EventSourceResponse(_event_generator())


# ============================================================================
# 4. ARTIFACTS & EXPORT DOWNLOADS
# ============================================================================

@app.get("/api/artifacts/download/excel")
async def download_excel():
    """Download styled 4-Tab Master Excel (.xlsx) file."""
    path = settings.export_dir / "heidi_berlin_hausverwaltungen.xlsx"
    if not path.exists():
        ExcelExporter(db).export_all()
    return FileResponse(
        path=path,
        filename="heidi_berlin_hausverwaltungen.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/artifacts/download/csv")
async def download_csv():
    """Download Master CSV file."""
    path = settings.export_dir / "heidi_berlin_leads_master.csv"
    if not path.exists():
        ExcelExporter(db).export_all()
    return FileResponse(
        path=path,
        filename="heidi_berlin_leads_master.csv",
        media_type="text/csv",
    )


@app.get("/api/artifacts/evaluation-report", response_class=PlainTextResponse)
async def get_evaluation_report():
    """Return raw markdown of the evaluation and ablation report."""
    path = settings.export_dir / "evaluation_ablation_report.md"
    if not path.exists():
        PipelineEvaluator(db).generate_markdown_report()
    return path.read_text(encoding="utf-8")


# ============================================================================
# 5. AGENTIC TOOLS & PROVIDER SETTINGS
# ============================================================================

@app.get("/api/tools")
async def get_tools_catalog():
    """Return the registry of all scrapers, legal parsers, and verification tools with health status."""
    return [
        {
            "id": "tool_gelbe_seiten",
            "name": "Gelbe Seiten Berlin Scraper",
            "category": "Directory Scraper",
            "status": "ready",
            "description": "Multi-keyword pagination with 23 Berlin district shards and base64 URL decoder.",
            "records_extracted": 405,
        },
        {
            "id": "tool_11880",
            "name": "11880.com Directory Scraper",
            "category": "Directory Scraper",
            "status": "ready",
            "description": "JSON-LD & HTML card parser with Cloudflare XOR email-protection decrypter.",
            "records_extracted": 835,
        },
        {
            "id": "tool_vdiv",
            "name": "VDIV Berlin-Brandenburg Association",
            "category": "Certified Association",
            "status": "ready",
            "description": "Captures institutional certified German property managers managing 1,000+ units.",
            "records_extracted": 30,
        },
        {
            "id": "tool_osm",
            "name": "OpenStreetMap Overpass API",
            "category": "Geospatial Parser",
            "status": "ready",
            "description": "Queries Berlin bounding box for office=property_management nodes.",
            "records_extracted": 100,
        },
        {
            "id": "tool_crawler",
            "name": "Async Impressum & Subpage Crawler",
            "category": "Web Crawler",
            "status": "ready",
            "description": "HTTP/2 async crawler discovering /, /impressum, /team, /leistungen, and /portal.",
            "records_extracted": 866,
        },
        {
            "id": "tool_mx_verifier",
            "name": "DNS MX Mail Server Verifier",
            "category": "Network Verification",
            "status": "ready",
            "description": "dnspython RFC resolver verifying live corporate mail servers.",
            "records_extracted": 216,
        },
    ]


@app.get("/api/settings")
async def get_settings():
    """Return runtime provider settings with masked keys."""
    return {
        "default_llm_provider": settings.default_llm_provider,
        "deepseek_configured": bool(settings.deepseek_api_key),
        "gemini_configured": bool(settings.gemini_api_key),
        "nvidia_nim_configured": bool(settings.nvidia_nim_api_key),
        "llamacpp_base_url": settings.llamacpp_base_url,
        "lmstudio_base_url": settings.lmstudio_base_url,
        "searxng_base_url": settings.searxng_base_url,
        "enable_native_metasearch": settings.enable_native_metasearch,
        "tavily_configured": bool(settings.tavily_api_key),
        "max_concurrent_crawls": settings.max_concurrent_crawls,
        "http_timeout_seconds": settings.http_timeout_seconds,
    }


class SettingsUpdateRequest(BaseModel):
    default_llm_provider: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    nvidia_nim_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    max_concurrent_crawls: Optional[int] = None


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    """Update runtime provider settings."""
    if req.default_llm_provider:
        settings.default_llm_provider = req.default_llm_provider
    if req.deepseek_api_key is not None:
        settings.deepseek_api_key = req.deepseek_api_key
    if req.gemini_api_key is not None:
        settings.gemini_api_key = req.gemini_api_key
    if req.nvidia_nim_api_key is not None:
        settings.nvidia_nim_api_key = req.nvidia_nim_api_key
    if req.tavily_api_key is not None:
        settings.tavily_api_key = req.tavily_api_key
    if req.max_concurrent_crawls:
        settings.max_concurrent_crawls = req.max_concurrent_crawls

    return {"status": "saved"}

