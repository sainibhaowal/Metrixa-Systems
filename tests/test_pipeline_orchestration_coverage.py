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
    assert run["status"] == "COMPLETED"
    assert event_count > 15 and companies == 1
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
