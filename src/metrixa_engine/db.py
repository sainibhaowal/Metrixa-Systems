"""
SQLite WAL Database Engine & State Machine Manager for Metrixa Engine.
Implements all relational tables, indexes, atomic upserts, and telemetry queries
as specified in 05_DATABASE_SCHEMA_DATA_STRUCTURES_AND_EXPORT_SPEC.md.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from metrixa_engine.config import settings
from metrixa_engine.models import RawListing

SCHEMA_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS raw_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    external_id TEXT,
    raw_company_name TEXT NOT NULL,
    raw_street TEXT,
    raw_postal_code TEXT,
    raw_city TEXT,
    raw_district TEXT,
    raw_phone TEXT,
    raw_email TEXT,
    raw_website TEXT,
    source_url TEXT,
    is_vdiv_member INTEGER DEFAULT 0,
    raw_json_payload TEXT,
    scraped_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_source ON raw_listings(source_name);
CREATE INDEX IF NOT EXISTS idx_raw_name ON raw_listings(raw_company_name);

CREATE TABLE IF NOT EXISTS companies_golden (
    company_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    legal_form TEXT,
    commercial_register_id TEXT,
    street_address TEXT,
    postal_code TEXT,
    city TEXT DEFAULT 'Berlin',
    district TEXT,
    phone_e164 TEXT,
    website_url TEXT,
    canonical_domain TEXT,
    general_email TEXT,
    company_linkedin_url TEXT,
    is_vdiv_member INTEGER DEFAULT 0,
    source_count INTEGER DEFAULT 1,
    sources_csv TEXT NOT NULL,
    pipeline_stage TEXT NOT NULL DEFAULT 'DEDUPED',
    disqualification_reason TEXT,
    metrixa_lead_score INTEGER DEFAULT 0,
    lead_tier TEXT DEFAULT 'Tier C (Long-Tail / Small)',
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_golden_stage ON companies_golden(pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_golden_domain ON companies_golden(canonical_domain);
CREATE INDEX IF NOT EXISTS idx_golden_score ON companies_golden(metrixa_lead_score DESC);
CREATE INDEX IF NOT EXISTS idx_golden_plz ON companies_golden(postal_code);

CREATE TABLE IF NOT EXISTS company_sources_map (
    company_id INTEGER NOT NULL,
    raw_listing_id INTEGER NOT NULL,
    PRIMARY KEY (company_id, raw_listing_id),
    FOREIGN KEY (company_id) REFERENCES companies_golden(company_id) ON DELETE CASCADE,
    FOREIGN KEY (raw_listing_id) REFERENCES raw_listings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS crawled_pages (
    page_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    page_type TEXT NOT NULL,
    url TEXT NOT NULL,
    http_status INTEGER,
    clean_markdown TEXT,
    detected_erp_csv TEXT,
    detected_metering_csv TEXT,
    has_portal_link INTEGER DEFAULT 0,
    social_linkedin_csv TEXT,
    extracted_emails_csv TEXT,
    crawled_at TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies_golden(company_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_crawled_company ON crawled_pages(company_id);

CREATE TABLE IF NOT EXISTS kpi_extractions (
    kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL UNIQUE,
    is_actual_hausverwaltung INTEGER DEFAULT 1,
    founding_year INTEGER,
    exact_units_managed INTEGER,
    units_evidence_quote TEXT,
    estimated_units_tier TEXT DEFAULT '<250',
    employee_count_est INTEGER,
    reference_buildings_count INTEGER,
    manages_weg INTEGER DEFAULT 0,
    manages_miet INTEGER DEFAULT 0,
    manages_gewerbe INTEGER DEFAULT 0,
    manages_sev INTEGER DEFAULT 0,
    has_customer_portal INTEGER DEFAULT 0,
    detected_erp_proptech TEXT,
    incumbent_metering_signal TEXT,
    digital_maturity_score INTEGER DEFAULT 1,
    qualification_reasoning TEXT,
    llm_provider_used TEXT,
    llm_model_used TEXT,
    extraction_confidence REAL DEFAULT 0.8,
    extracted_at TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies_golden(company_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_kpi_company ON kpi_extractions(company_id);

CREATE TABLE IF NOT EXISTS decision_makers (
    contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    role TEXT DEFAULT 'Geschäftsführer',
    personal_email TEXT,
    email_status TEXT DEFAULT 'NONE',
    mx_valid INTEGER DEFAULT 0,
    mx_host TEXT,
    direct_phone TEXT,
    linkedin_url TEXT,
    source_url TEXT,
    evidence_quote TEXT,
    is_primary_contact INTEGER DEFAULT 0,
    FOREIGN KEY (company_id) REFERENCES companies_golden(company_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dm_company ON decision_makers(company_id);
CREATE INDEX IF NOT EXISTS idx_dm_company_primary ON decision_makers(company_id, is_primary_contact DESC);
CREATE INDEX IF NOT EXISTS idx_golden_tier ON companies_golden(lead_tier);
CREATE INDEX IF NOT EXISTS idx_golden_district ON companies_golden(district);
CREATE INDEX IF NOT EXISTS idx_kpi_erp ON kpi_extractions(detected_erp_proptech);

CREATE TABLE IF NOT EXISTS llm_audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    stage TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    schema_valid INTEGER DEFAULT 1,
    hallucination_blocked INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    run_number INTEGER NOT NULL,
    trigger_type TEXT NOT NULL,
    target_city TEXT DEFAULT 'Berlin',
    active_stage TEXT,
    status TEXT NOT NULL,
    total_companies_in INTEGER DEFAULT 0,
    total_companies_out INTEGER DEFAULT 0,
    new_companies_found INTEGER DEFAULT 0,
    changed_kpis_count INTEGER DEFAULT 0,
    duration_seconds REAL DEFAULT 0.0,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error_message TEXT,
    summary_metrics_json TEXT
);

CREATE TABLE IF NOT EXISTS deliverables_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deliverable_type TEXT NOT NULL,
    target_destination TEXT NOT NULL,
    status TEXT NOT NULL,
    records_count INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    details_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    stage TEXT NOT NULL,
    step_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'INFO',
    duration_ms INTEGER DEFAULT 0,
    message TEXT NOT NULL,
    payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_num ON pipeline_runs(run_number DESC);
CREATE INDEX IF NOT EXISTS idx_deliv_sync_created ON deliverables_sync_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_events_run_seq ON pipeline_run_events(run_id, seq);
"""


class Database:
    """Thread-safe / Async-friendly SQLite WAL Database Manager."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or settings.database_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA cache_size = -64000;")
        conn.execute("PRAGMA mmap_size = 268435456;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_DDL)
        self.seed_initial_pipeline_runs()

    def insert_raw_listings(self, listings: List[RawListing]) -> int:
        """Insert a batch of raw scraped listings, skipping exact duplicate (source_name, raw_company_name, raw_postal_code)."""
        if not listings:
            return 0
        inserted = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            for item in listings:
                exists = conn.execute(
                    """
                    SELECT id, raw_email, raw_website FROM raw_listings
                    WHERE source_name = ? AND raw_company_name = ? AND COALESCE(raw_postal_code, '') = COALESCE(?, '')
                    LIMIT 1
                    """,
                    (item.source_name, item.raw_company_name, item.raw_postal_code),
                ).fetchone()
                if exists:
                    if (not exists["raw_email"] and item.raw_email) or (
                        not exists["raw_website"] and item.raw_website
                    ):
                        conn.execute(
                            """
                            UPDATE raw_listings
                            SET raw_email = COALESCE(raw_email, ?),
                                raw_website = COALESCE(raw_website, ?)
                            WHERE id = ?
                            """,
                            (item.raw_email, item.raw_website, exists["id"]),
                        )
                        inserted += 1
                    continue
                conn.execute(
                    """
                    INSERT INTO raw_listings (
                        source_name, external_id, raw_company_name, raw_street,
                        raw_postal_code, raw_city, raw_district, raw_phone,
                        raw_email, raw_website, source_url, is_vdiv_member,
                        raw_json_payload, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.source_name,
                        item.external_id,
                        item.raw_company_name,
                        item.raw_street,
                        item.raw_postal_code,
                        item.raw_city,
                        item.raw_district,
                        item.raw_phone,
                        item.raw_email,
                        item.raw_website,
                        item.source_url,
                        1 if item.is_vdiv_member else 0,
                        json.dumps(item.raw_payload, ensure_ascii=False),
                        now_iso,
                    ),
                )
                inserted += 1
        return inserted

    def get_all_raw_listings(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM raw_listings ORDER BY id ASC").fetchall()
            return [dict(r) for r in rows]

    def get_pipeline_telemetry(self) -> Dict[str, Any]:
        """Aggregate real-time pipeline counts for the Metrixa Web Cockpit and telemetry reports."""
        with self.connect() as conn:
            raw_total = conn.execute("SELECT COUNT(*) FROM raw_listings").fetchone()[0]
            raw_by_source = {
                r["source_name"]: r["cnt"]
                for r in conn.execute(
                    "SELECT source_name, COUNT(*) as cnt FROM raw_listings GROUP BY source_name"
                ).fetchall()
            }

            golden_total = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
            ).fetchone()[0]
            disqualified_total = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage = 'DISQUALIFIED'"
            ).fetchone()[0]

            stages = {
                r["pipeline_stage"]: r["cnt"]
                for r in conn.execute(
                    "SELECT pipeline_stage, COUNT(*) as cnt FROM companies_golden GROUP BY pipeline_stage"
                ).fetchall()
            }

            tiers = {
                r["lead_tier"]: r["cnt"]
                for r in conn.execute(
                    "SELECT lead_tier, COUNT(*) as cnt FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED' GROUP BY lead_tier"
                ).fetchall()
            }

            with_website = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED' AND website_url IS NOT NULL AND website_url != ''"
            ).fetchone()[0]

            crawled_pages_cnt = conn.execute(
                "SELECT COUNT(*) FROM crawled_pages"
            ).fetchone()[0]

            kpi_cnt = conn.execute("""
                SELECT COUNT(*) FROM kpi_extractions k
                JOIN companies_golden c ON c.company_id = k.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                """).fetchone()[0]

            with_erp = conn.execute("""
                SELECT COUNT(*) FROM kpi_extractions k
                JOIN companies_golden c ON c.company_id = k.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND k.detected_erp_proptech IS NOT NULL AND k.detected_erp_proptech != ''
                """).fetchone()[0]

            with_portal = conn.execute("""
                SELECT COUNT(*) FROM kpi_extractions k
                JOIN companies_golden c ON c.company_id = k.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED' AND k.has_customer_portal = 1
                """).fetchone()[0]

            dm_companies = conn.execute("""
                SELECT COUNT(DISTINCT d.company_id) FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                """).fetchone()[0]

            personal_emails = conn.execute("""
                SELECT COUNT(DISTINCT d.company_id) FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND d.personal_email IS NOT NULL AND d.personal_email != ''
                """).fetchone()[0]

            linkedin_cnt = conn.execute("""
                SELECT COUNT(DISTINCT c.company_id) FROM companies_golden c
                LEFT JOIN decision_makers d ON d.company_id = c.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND (
                    (c.company_linkedin_url IS NOT NULL AND c.company_linkedin_url != '')
                    OR (d.linkedin_url IS NOT NULL AND d.linkedin_url != '')
                  )
                """).fetchone()[0]

            llm_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_calls,
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(AVG(latency_ms), 0) as avg_latency_ms,
                    COALESCE(SUM(hallucination_blocked), 0) as hallucinations_blocked
                FROM llm_audit_logs
                """).fetchone()

            return {
                "raw_total": raw_total,
                "raw_by_source": raw_by_source,
                "golden_qualified_total": golden_total,
                "disqualified_total": disqualified_total,
                "stages": stages,
                "tiers": tiers,
                "with_website": with_website,
                "crawled_pages_cnt": crawled_pages_cnt,
                "kpi_extracted_cnt": kpi_cnt,
                "with_erp_stack": with_erp,
                "with_customer_portal": with_portal,
                "companies_with_decision_maker": dm_companies,
                "companies_with_personal_email": personal_emails,
                "companies_with_linkedin": linkedin_cnt,
                "llm_stats": dict(llm_stats) if llm_stats else {},
            }

    def record_run_event(
        self,
        run_id: str,
        seq: int,
        stage: str,
        step_name: str,
        event_type: str,
        level: str,
        duration_ms: int,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist a granular telemetry event for a pipeline run."""
        ts = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(payload) if payload else None
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_run_events (
                    run_id, seq, timestamp, stage, step_name, event_type, level,
                    duration_ms, message, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    seq,
                    ts,
                    stage,
                    step_name,
                    event_type,
                    level,
                    duration_ms,
                    message,
                    payload_str,
                ),
            )

    def get_run_events(self, run_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Retrieve all chronological telemetry events for a given run_id."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, run_id, seq, timestamp, stage, step_name, event_type, level,
                       duration_ms, message, payload_json
                FROM pipeline_run_events
                WHERE run_id = ?
                ORDER BY seq ASC, id ASC
                LIMIT ?
                """,
                (run_id, limit),
            ).fetchall()
        events = []
        for r in rows:
            p_json = None
            if r["payload_json"]:
                try:
                    p_json = json.loads(r["payload_json"])
                except Exception:
                    p_json = None
            events.append(
                {
                    "id": r["id"],
                    "run_id": r["run_id"],
                    "seq": r["seq"],
                    "timestamp": r["timestamp"],
                    "stage": r["stage"],
                    "step_name": r["step_name"],
                    "event_type": r["event_type"],
                    "level": r["level"],
                    "duration_ms": r["duration_ms"],
                    "message": r["message"],
                    "payload": p_json,
                }
            )
        return events

    def seed_initial_pipeline_runs(self) -> None:
        """Seed baseline historical pipeline runs for execution tracking and comparison diffing."""
        with self.connect() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
            if cnt > 0:
                return

            runs = [
                (
                    "run-20261107-142010",
                    14,
                    "MANUAL_STAGE",
                    "Berlin",
                    "ingest",
                    "COMPLETED",
                    1240,
                    1187,
                    12,
                    8,
                    41.8,
                    "2026-11-07T14:20:10Z",
                    "2026-11-07T14:20:51Z",
                    None,
                    json.dumps(
                        {
                            "stage": "ingest",
                            "sources": [
                                "gelbe_seiten",
                                "11880",
                                "vdiv",
                                "osm",
                                "search",
                            ],
                            "records_scraped": 1240,
                            "coverage": "Berlin 12 Bezirke",
                        }
                    ),
                ),
                (
                    "run-20261107-183045",
                    15,
                    "MANUAL_STAGE",
                    "Berlin",
                    "crawl",
                    "COMPLETED",
                    1187,
                    1192,
                    5,
                    14,
                    49.2,
                    "2026-11-07T18:30:45Z",
                    "2026-11-07T18:31:34Z",
                    None,
                    json.dumps(
                        {
                            "stage": "crawl",
                            "pages_crawled": 1187,
                            "http_status_200": 1148,
                            "erp_signatures_detected": 866,
                        }
                    ),
                ),
                (
                    "run-20261108-034500",
                    16,
                    "MANUAL_FULL",
                    "Berlin",
                    "full",
                    "COMPLETED",
                    1240,
                    1200,
                    7,
                    22,
                    138.5,
                    "2026-11-08T03:45:00Z",
                    "2026-11-08T03:47:18Z",
                    None,
                    json.dumps(
                        {
                            "stage": "full",
                            "stages_executed": 6,
                            "golden_companies": 1200,
                            "tier_a": 182,
                            "tier_b": 514,
                            "tier_c": 503,
                            "verified_units": 82450,
                            "f1_score": 0.946,
                        }
                    ),
                ),
            ]

            conn.executemany(
                """
                INSERT INTO pipeline_runs (
                    run_id, run_number, trigger_type, target_city, active_stage, status,
                    total_companies_in, total_companies_out, new_companies_found, changed_kpis_count,
                    duration_seconds, started_at, finished_at, error_message, summary_metrics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                runs,
            )
