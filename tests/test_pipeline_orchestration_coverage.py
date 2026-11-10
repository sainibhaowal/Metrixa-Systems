from __future__ import annotations

import asyncio

import pytest

from metrixa_engine.api import server
from metrixa_engine.db import Database
from metrixa_engine.models import RawListing


@pytest.mark.asyncio
async def test_event_bus_cleans_dead_queues_and_record_event_is_resilient(
    tmp_path, monkeypatch
):
    queue = server.PipelineEventBus()
    live = queue.subscribe()
    queue.subscribers.append(_BrokenQueue())
    await queue.emit("PROGRESS", {"pct": 100})
    assert await live.get() == {"type": "PROGRESS", "pct": 100}
    assert queue.subscribers == [live]
    queue.unsubscribe(live)
    queue.unsubscribe(live)
    assert queue.subscribers == []

    isolated = Database(tmp_path / "event.db")
    monkeypatch.setattr(server, "db", isolated)
    original_emit = server.event_bus.emit
    observed = []

    async def emit(event_type, data):
        observed.append(event_type)

    monkeypatch.setattr(server.event_bus, "emit", emit)
    await server.record_and_emit_event(
        "run", 1, "test", "step", "EVENT", "INFO", 1, "message"
    )
    assert observed == ["LOG", "AGENT_STEP"]
    with isolated.connect() as conn:
        assert (
            conn.execute("SELECT COUNT(*) FROM pipeline_run_events").fetchone()[0] == 1
        )
    monkeypatch.setattr(
        isolated,
        "record_run_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
    )
    await server.record_and_emit_event(
        "run", 2, "test", "step", "EVENT", "INFO", 1, "message"
    )
    assert observed == ["LOG", "AGENT_STEP", "LOG", "AGENT_STEP"]
    monkeypatch.setattr(server.event_bus, "emit", original_emit)


class _BrokenQueue:
    def put_nowait(self, item):
        raise RuntimeError("closed subscriber")


def _reset_bus():
    server.event_bus.is_running = False
    server.event_bus.current_stage = "IDLE"
    server.event_bus.current_run_id = None
    server.event_bus.stage_durations = {}
    server.active_pipeline_task = None


@pytest.mark.asyncio
async def test_full_pipeline_stage_orchestration_is_local_and_recorded(
    tmp_path, monkeypatch
):
    isolated = Database(tmp_path / "pipeline.db")
    monkeypatch.setattr(server, "db", isolated)
    monkeypatch.setattr(server.settings, "export_dir", tmp_path / "exports")
    monkeypatch.setattr(server.settings, "database_path", isolated.db_path)
    _reset_bus()

    async def scrape(self, max_pages=10):
        return [
            RawListing(
                source_name=self.source_name,
                raw_company_name="Alpha Berlin Hausverwaltung GmbH",
                raw_postal_code="10115",
                raw_city="Berlin",
                raw_website=None,
            )
        ]

    for scraper in (
        server.VDIVScraper,
        server.OSMOverpassScraper,
        server.GelbeSeitenScraper,
        server.Dir11880Scraper,
        server.SearchDiscoveryScraper,
    ):
        monkeypatch.setattr(scraper, "scrape_berlin", scrape)

    async def empty_vdiv(self, max_pages=10):
        self.last_diagnostic = "test source returned no candidates"
        return []

    monkeypatch.setattr(server.VDIVScraper, "scrape_berlin", empty_vdiv)

    async def crawl(self, limit=None, progress_callback=None, reprocess_all=False):
        with isolated.connect() as conn:
            company_id = conn.execute(
                "SELECT company_id FROM companies_golden LIMIT 1"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO crawled_pages (company_id,page_type,url,http_status,clean_markdown,crawled_at) VALUES (?, 'homepage','https://alpha.example/',200,'Alpha official source page content for grounded extraction','now')",
                (company_id,),
            )
            conn.execute(
                "UPDATE companies_golden SET pipeline_stage='CRAWLED' WHERE company_id=?",
                (company_id,),
            )
        if progress_callback:
            progress_callback(1, 1)
        return {
            "companies_processed": 1,
            "reachable_websites": 0,
            "total_pages_saved": 1,
            "previous_evidence_preserved": 0,
        }

    monkeypatch.setattr(server.AsyncWebsiteCrawler, "crawl_batch", crawl)

    extraction_providers = []

    async def failed_extraction(self, row, requested_provider=None):
        extraction_providers.append(requested_provider)
        raise RuntimeError("simulated extraction failure")

    monkeypatch.setattr(
        server.KPIExtractionPipeline, "extract_single_company", failed_extraction
    )

    async def enrich(self, limit=None, web_search_top_n=25, progress_callback=None):
        if progress_callback:
            progress_callback(1, 1)
        return {
            "processed": 1,
            "mx_valid_domains": 0,
            "public_emails_listed": 0,
            "pattern_email_candidates": 0,
        }

    monkeypatch.setattr(server.ContactEnricher, "enrich_batch", enrich)

    started = await server.trigger_pipeline_run(
        server.PipelineRunRequest(stage="full", city="Berlin", limit=4)
    )
    task = server.active_pipeline_task
    assert started["status"] == "started" and task is not None
    await task
    assert (
        server.event_bus.is_running is False
        and server.event_bus.current_stage == "IDLE"
    )
    with isolated.connect() as conn:
        run = conn.execute(
            "SELECT * FROM pipeline_runs WHERE run_id=?", (started["run_id"],)
        ).fetchone()
        event_count = conn.execute(
            "SELECT COUNT(*) FROM pipeline_run_events WHERE run_id=?",
            (started["run_id"],),
        ).fetchone()[0]
        companies = conn.execute(
            "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
        ).fetchone()[0]
    assert run["status"] == "COMPLETED_WITH_WARNINGS"
    assert "INGEST_EMPTY:VDIVScraper" in run["summary_metrics_json"]
    assert "CRAWL_PARTIAL_UNREACHABLE" in run["summary_metrics_json"]
    assert "EXTRACTION_FAILURES" in run["summary_metrics_json"]
    assert event_count > 15 and companies == 1
    assert extraction_providers == ["deterministic"]
    extraction_event = next(
        event
        for event in isolated.get_run_events(started["run_id"])
        if event["step_name"] == "ExtractionSummary"
    )
    empty_source_event = next(
        event
        for event in isolated.get_run_events(started["run_id"])
        if event["step_name"] == "VDIVScraper"
    )
    assert (
        empty_source_event["payload"]["diagnostic"]
        == "test source returned no candidates"
    )
    assert (
        "Diagnostic: test source returned no candidates"
        in empty_source_event["message"]
    )
    assert extraction_event["payload"]["factual_extraction_provider"] == "deterministic"
    assert extraction_event["payload"]["llm_used_for_factual_extraction"] is False
    assert (tmp_path / "exports" / "metrixa_berlin_hausverwaltungen.xlsx").exists()
    assert (tmp_path / "exports" / "metrixa_evaluation_ablation_report.md").exists()


@pytest.mark.asyncio
async def test_pipeline_cancelled_and_failed_runs_update_status(tmp_path, monkeypatch):
    isolated = Database(tmp_path / "pipeline-errors.db")
    monkeypatch.setattr(server, "db", isolated)
    _reset_bus()

    async def cancelled(self, max_pages=10):
        raise asyncio.CancelledError()

    monkeypatch.setattr(server.VDIVScraper, "scrape_berlin", cancelled)
    started = await server.trigger_pipeline_run(
        server.PipelineRunRequest(stage="ingest")
    )
    task = server.active_pipeline_task
    await task
    with isolated.connect() as conn:
        status = conn.execute(
            "SELECT status,error_message FROM pipeline_runs WHERE run_id=?",
            (started["run_id"],),
        ).fetchone()
    assert (
        status["status"] == "CANCELLED"
        and status["error_message"] == "Interrupted by operator"
    )
    _reset_bus()

    async def empty(self, max_pages=10):
        return []

    for scraper in (
        server.VDIVScraper,
        server.OSMOverpassScraper,
        server.GelbeSeitenScraper,
        server.Dir11880Scraper,
        server.SearchDiscoveryScraper,
    ):
        monkeypatch.setattr(scraper, "scrape_berlin", empty)
    monkeypatch.setattr(
        server.ExcelExporter,
        "export_all",
        lambda self: (_ for _ in ()).throw(RuntimeError("export failed")),
    )
    monkeypatch.setattr(server.settings, "export_dir", tmp_path / "error-exports")
    started = await server.trigger_pipeline_run(
        server.PipelineRunRequest(stage="export")
    )
    task = server.active_pipeline_task
    await task
    with isolated.connect() as conn:
        status = conn.execute(
            "SELECT status,error_message FROM pipeline_runs WHERE run_id=?",
            (started["run_id"],),
        ).fetchone()
    assert status["status"] == "FAILED" and status["error_message"] == "export failed"
    _reset_bus()


@pytest.mark.asyncio
async def test_pipeline_does_not_emit_complete_when_run_status_save_fails(
    tmp_path, monkeypatch
):
    isolated = Database(tmp_path / "pipeline-status-save.db")
    monkeypatch.setattr(server, "db", isolated)
    monkeypatch.setattr(server.settings, "export_dir", tmp_path / "exports-status")
    monkeypatch.setattr(server.settings, "database_path", isolated.db_path)
    _reset_bus()
    with isolated.connect() as conn:
        conn.execute(
            """
            CREATE TRIGGER fail_completed_pipeline_status
            BEFORE UPDATE OF status ON pipeline_runs
            WHEN NEW.status = 'COMPLETED'
            BEGIN
                SELECT RAISE(ABORT, 'status persistence failed');
            END
            """
        )

    started = await server.trigger_pipeline_run(
        server.PipelineRunRequest(stage="export")
    )
    await server.active_pipeline_task

    with isolated.connect() as conn:
        run = conn.execute(
            "SELECT status,error_message FROM pipeline_runs WHERE run_id=?",
            (started["run_id"],),
        ).fetchone()
        complete_events = conn.execute(
            "SELECT COUNT(*) FROM pipeline_run_events WHERE run_id=? AND event_type='COMPLETE'",
            (started["run_id"],),
        ).fetchone()[0]
    assert run["status"] == "FAILED"
    assert "status persistence failed" in run["error_message"]
    assert complete_events == 0


@pytest.mark.asyncio
async def test_final_report_refresh_failure_emits_warning(tmp_path, monkeypatch):
    isolated = Database(tmp_path / "report-refresh.db")
    monkeypatch.setattr(server, "db", isolated)
    monkeypatch.setattr(server.settings, "export_dir", tmp_path / "exports")
    monkeypatch.setattr(server.settings, "database_path", isolated.db_path)
    _reset_bus()
    original = server.PipelineEvaluator.generate_markdown_report
    calls = 0
    messages = []

    def fail_on_final_refresh(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("final report write failed")
        return original(self, *args, **kwargs)

    async def capture(event_type, data):
        messages.append((event_type, data))

    monkeypatch.setattr(
        server.PipelineEvaluator, "generate_markdown_report", fail_on_final_refresh
    )
    monkeypatch.setattr(server.event_bus, "emit", capture)
    started = await server.trigger_pipeline_run(
        server.PipelineRunRequest(stage="export")
    )
    await server.active_pipeline_task
    with isolated.connect() as conn:
        status = conn.execute(
            "SELECT status FROM pipeline_runs WHERE run_id=?", (started["run_id"],)
        ).fetchone()[0]
    assert status == "COMPLETED"
    assert calls == 2
    assert any(
        "Could not refresh final evaluation report" in data.get("message", "")
        for _, data in messages
    )
    _reset_bus()
