from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import asyncio
import pytest
from fastapi.testclient import TestClient

from metrixa_engine.api import server
from metrixa_engine.db import Database


class _FailingConnection:
    def __init__(self, conn, fail):
        self._conn = conn
        self._fail = fail

    def execute(self, sql, *args, **kwargs):
        if self._fail(sql):
            raise OSError("injected database failure")
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _DatabaseProxy:
    def __init__(self, db, fail):
        self._db = db
        self._fail = fail
        self.db_path = db.db_path

    @contextmanager
    def connect(self):
        with self._db.connect() as conn:
            yield _FailingConnection(conn, self._fail)

    def __getattr__(self, name):
        return getattr(self._db, name)


@pytest.fixture
def app_db(monkeypatch, tmp_path):
    db = Database(tmp_path / "server-rem.db")
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.settings, "database_path", db.db_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    monkeypatch.setattr(server.settings, "export_dir", export_dir)
    return TestClient(server.app), db, export_dir


def test_stats_count_query_failure_defaults_to_zero(app_db, monkeypatch):
    client, db, _ = app_db
    proxy = _DatabaseProxy(db, lambda sql: sql == "SELECT COUNT(*) FROM raw_listings")
    monkeypatch.setattr(server, "db", proxy)
    assert client.get("/api/system/stats").json()["counts"]["raw_listings"] == 0


def test_factory_reset_handles_table_vacuum_and_file_failures(app_db, monkeypatch):
    client, db, export_dir = app_db
    doomed = export_dir / "keep-on-unlink-error.csv"
    doomed.write_text("local test", encoding="utf-8")
    hidden = export_dir / ".hidden"
    hidden.write_text("preserved", encoding="utf-8")

    def fail(sql):
        return sql == "DELETE FROM artifact_library_state" or sql == "VACUUM"

    monkeypatch.setattr(server, "db", _DatabaseProxy(db, fail))
    original_unlink = Path.unlink

    def selective_unlink(path, *args, **kwargs):
        if path == doomed:
            raise OSError("locked file")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", selective_unlink)
    result = client.post(
        "/api/system/factory-reset", json={"confirmation_word": "DELETE"}
    )
    assert result.status_code == 200
    assert doomed.exists() and hidden.exists()


def test_artifact_sync_deleted_filter_and_case_study_missing_source(
    app_db, monkeypatch
):
    client, db, export_dir = app_db
    monkeypatch.setattr(server.settings, "project_root", export_dir.parent)
    xlsx = export_dir / "metrixa_berlin_hausverwaltungen.xlsx"
    xlsx.write_bytes(b"test workbook")
    pdf = export_dir / "Case_Study_Metrixa_Systems.pdf"
    pdf.write_bytes(b"test pdf")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO artifact_library_state (artifact_id,status,retention_days,updated_at) VALUES ('xlsx-master','deleted',30,'now')"
        )
        conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,pipeline_stage,updated_at) VALUES ('alpha','Alpha GmbH','test','SCORED','now')"
        )
    files = client.get("/api/artifacts/files").json()["items"]
    assert all(item["id"] != "xlsx-master" for item in files)
    assert client.get("/api/artifacts/preview/pdf-casestudy").status_code == 404

    calls = []
    monkeypatch.setattr(
        server.ExcelExporter, "export_all", lambda self: calls.append("excel")
    )
    monkeypatch.setattr(
        server.PipelineEvaluator,
        "generate_markdown_report",
        lambda self: calls.append("report"),
    )
    monkeypatch.setattr(
        server.GoogleSheetsSync,
        "sync_to_google_sheet",
        lambda self: (_ for _ in ()).throw(RuntimeError("cloud unavailable")),
    )
    assert client.post("/api/artifacts/sync").status_code == 200
    assert calls == ["excel", "report"]


def test_artifact_action_skip_non_trash_and_google_download_error(app_db, monkeypatch):
    client, db, _ = app_db
    original = {key: dict(item) for key, item in server._artifact_store.items()}
    try:
        server._artifact_store["xlsx-master"]["status"] = "trash"
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO artifact_library_state (artifact_id,status,retention_days,updated_at) VALUES ('xlsx-master','active',30,'now')"
            )
        response = client.post(
            "/api/artifacts/action",
            json={"action": "empty_trash", "file_ids": ["xlsx-master"]},
        )
        assert response.status_code == 200 and response.json()["affected_count"] == 0
    finally:
        server._artifact_store.clear()
        server._artifact_store.update(original)

    with db.connect() as conn:
        conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,pipeline_stage,updated_at) VALUES ('alpha','Alpha GmbH','test','SCORED','now')"
        )
    monkeypatch.setattr(
        server.GoogleSheetsSync,
        "get_live_deliverables_status",
        lambda self: {
            "deliverables": [
                {"id": "google_sheets_live", "status": "ERROR", "download_url": None}
            ]
        },
    )
    assert client.get("/api/artifacts/download/google-sheets-live").status_code == 404


def test_sync_all_deliverables_with_records_and_tool_catalog_counts(
    app_db, monkeypatch
):
    client, db, _ = app_db
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,pipeline_stage,updated_at) VALUES ('alpha','Alpha GmbH','test','SCORED','now')"
        )
        conn.execute(
            "INSERT INTO raw_listings (source_name,raw_company_name,scraped_at) VALUES ('test-source','Alpha GmbH','now')"
        )
    monkeypatch.setattr(
        server.GoogleSheetsSync,
        "sync_all_deliverables",
        lambda self: {"success": True, "status": "SYNCED"},
    )
    result = client.post("/api/deliverables/sync-all").json()
    assert result == {"success": True, "status": "SYNCED"}
    tools = {item["id"]: item for item in client.get("/api/tools").json()}
    assert tools["tool_gelbe_seiten"]["records_extracted"] == 0


def test_cancel_pipeline_db_failure_is_swallowed(app_db, monkeypatch):
    client, db, _ = app_db
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO pipeline_runs (run_id,run_number,trigger_type,status,started_at) VALUES ('cancel-error',1,'MANUAL_STAGE','RUNNING','now')"
        )

    class Task:
        def done(self):
            return False

        def cancel(self):
            return True

    monkeypatch.setattr(server, "active_pipeline_task", Task())
    server.event_bus.is_running = True
    server.event_bus.current_run_id = "cancel-error"
    monkeypatch.setattr(
        server,
        "db",
        _DatabaseProxy(
            db, lambda sql: "UPDATE pipeline_runs SET status = 'CANCELLED'" in sql
        ),
    )
    assert client.post("/api/pipeline/cancel").json()["status"] == "cancelled"
    server.event_bus.current_run_id = None
    server.event_bus.is_running = False
    server.active_pipeline_task = None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure_sql,stage,patch_name",
    [
        ("INSERT INTO pipeline_runs", "crawl", None),
        ("SET status = 'COMPLETED'", "crawl", None),
        ("SET status = 'CANCELLED'", "crawl", "cancel"),
        ("SET status = 'FAILED'", "export", "fail"),
    ],
)
async def test_pipeline_handles_ledger_write_failures(
    tmp_path, monkeypatch, failure_sql, stage, patch_name
):
    db = Database(tmp_path / f"pipeline-{patch_name or 'complete'}.db")
    monkeypatch.setattr(
        server, "db", _DatabaseProxy(db, lambda sql: failure_sql in sql)
    )
    monkeypatch.setattr(server.settings, "export_dir", tmp_path / "exports")
    monkeypatch.setattr(server.settings, "database_path", db.db_path)
    server.event_bus.is_running = False
    server.event_bus.current_stage = "IDLE"
    server.event_bus.current_run_id = None
    server.active_pipeline_task = None

    if patch_name == "cancel":

        async def cancelled(self, **kwargs):
            raise asyncio.CancelledError

        monkeypatch.setattr(server.AsyncWebsiteCrawler, "crawl_batch", cancelled)
    elif patch_name == "fail":
        monkeypatch.setattr(
            server.ExcelExporter,
            "export_all",
            lambda self: (_ for _ in ()).throw(RuntimeError("export fails")),
        )

    started = await server.trigger_pipeline_run(
        server.PipelineRunRequest(stage=stage, city="Berlin")
    )
    task = server.active_pipeline_task
    assert started["status"] == "started" and task is not None
    await task
    assert server.event_bus.is_running is False and server.active_pipeline_task is None
