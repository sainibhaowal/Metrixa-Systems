"""
Integration Test Suite for FastAPI Backend Gateway (`metrixa_engine.api.server`).
Verifies /api/metrics, /api/leads, /api/leads/{id}/evidence, /api/tools, /api/settings,
and Artifact downloads.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from metrixa_engine.api.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_metrics(client: TestClient) -> None:
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert data["golden_total"] >= 0
    assert isinstance(data["tiers"], dict)
    assert isinstance(data["district_breakdown"], list)


def test_api_leads_search_and_filters(client: TestClient) -> None:
    # 1. Test tier filter
    resp = client.get("/api/leads?tier=Tier+A&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["items"], list)
    for lead in data["items"]:
        assert "Tier A" in lead["lead_tier"]
        assert lead["metrixa_lead_score"] >= 70

    # 2. Test search query
    resp_q = client.get("/api/leads?q=BVBI")
    assert resp_q.status_code == 200
    data_q = resp_q.json()
    assert isinstance(data_q["items"], list)


def test_api_lead_evidence_dossier(client: TestClient) -> None:
    # Fetch lead list
    resp = client.get("/api/leads?limit=1")
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    if items:
        first_id = items[0]["company_id"]
        ev_resp = client.get(f"/api/leads/{first_id}/evidence")
        assert ev_resp.status_code == 200
        ev_data = ev_resp.json()
        assert "scorecard" in ev_data
        assert "scale_pts" in ev_data["scorecard"]
        assert "total_score" in ev_data["scorecard"]
        assert isinstance(ev_data["decision_makers"], list)
        assert isinstance(ev_data["crawled_pages"], list)
    else:
        # 404 for non-existent lead when DB is clean
        ev_resp = client.get("/api/leads/999999/evidence")
        assert ev_resp.status_code == 404


def test_api_tools_catalog(client: TestClient) -> None:
    resp = client.get("/api/tools")
    assert resp.status_code == 200
    tools = resp.json()
    assert len(tools) >= 5
    tool_ids = [t["id"] for t in tools]
    assert "tool_gelbe_seiten" in tool_ids
    assert "tool_11880" in tool_ids
    assert "tool_mx_verifier" in tool_ids


def test_api_settings(client: TestClient) -> None:
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    settings_data = resp.json()
    assert "default_llm_provider" in settings_data
    assert "max_concurrent_crawls" in settings_data


def test_api_provider_ping(client: TestClient) -> None:
    resp = client.post("/api/providers/ping", json={"provider": "deterministic"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "PONG" in data["reply"]
    assert data["latency_ms"] >= 0

    # Test ping with unconfigured provider returns clean validation error
    unconf_resp = client.post(
        "/api/providers/ping",
        json={"provider": "openai", "api_key": None, "model": None},
    )
    assert unconf_resp.status_code == 200
    unconf_data = unconf_resp.json()
    assert unconf_data["status"] == "error"
    assert "No API Key configured" in unconf_data["error"]

    # Test ping with key but no model returns clean model selection prompt
    no_model_resp = client.post(
        "/api/providers/ping",
        json={"provider": "openai", "api_key": "sk-mock-key", "model": None},
    )
    assert no_model_resp.status_code == 200
    no_model_data = no_model_resp.json()
    assert no_model_data["status"] == "error"
    assert "No model selected" in no_model_data["error"]

    for prov in ("gemini", "openai", "deepseek"):
        disc_resp = client.post("/api/providers/models", json={"provider": prov})
        assert disc_resp.status_code == 200
        disc_data = disc_resp.json()
        assert disc_data["status"] in ("awaiting_key", "offline", "ok")
        assert isinstance(disc_data["models"], list)
        if disc_data["status"] == "awaiting_key":
            assert disc_data["models"] == []


def test_api_artifacts_library_and_preview(client: TestClient) -> None:
    from metrixa_engine.api.server import db
    from metrixa_engine.telemetry.evaluator import PipelineEvaluator
    from metrixa_engine.telemetry.excel_exporter import ExcelExporter

    resp = client.get("/api/artifacts/files")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data

    # If empty (clean factory state), generate test deliverables for verification
    if len(data["items"]) == 0:
        ExcelExporter(db).export_all()
        PipelineEvaluator(db).generate_markdown_report()
        resp = client.get("/api/artifacts/files")
        assert resp.status_code == 200
        data = resp.json()

    assert len(data["items"]) >= 2
    file_ids = [item["id"] for item in data["items"]]
    assert "xlsx-master" in file_ids
    assert "csv-master" in file_ids

    # Test preview endpoint for Excel
    prev_resp = client.get("/api/artifacts/preview/xlsx-master")
    assert prev_resp.status_code == 200
    prev_data = prev_resp.json()
    assert prev_data["type"] == "xlsx"
    assert "sheets" in prev_data
    assert len(prev_data["sheets"]) >= 1

    # Test preview endpoint for CSV
    csv_prev = client.get("/api/artifacts/preview/csv-master")
    assert csv_prev.status_code == 200
    assert csv_prev.json()["type"] == "csv"

    # Test artifact action (archive and restore)
    act_resp = client.post(
        "/api/artifacts/action",
        json={"action": "archive", "file_ids": ["xlsx-master"]},
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["affected_count"] == 1

    restore_resp = client.post(
        "/api/artifacts/action",
        json={"action": "restore", "file_ids": ["xlsx-master"]},
    )
    assert restore_resp.status_code == 200


def test_api_pipeline_runs_and_comparison(client: TestClient) -> None:
    from metrixa_engine.api.server import db

    # Ensure at least 2 runs exist with events for comparison diff testing
    with db.connect() as conn:
        cnt = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
        if cnt < 2:
            conn.execute(
                """
                INSERT INTO pipeline_runs (
                    run_id, run_number, trigger_type, target_city, active_stage, status,
                    started_at, finished_at, duration_seconds, total_companies_in, total_companies_out
                ) VALUES
                ('test-seed-run-1', 1, 'MANUAL_STAGE', 'Berlin', 'ingest', 'COMPLETED', '2026-11-09T00:00:00Z', '2026-11-09T00:00:10Z', 10.0, 100, 95),
                ('test-seed-run-2', 2, 'MANUAL_FULL', 'Berlin', 'full', 'COMPLETED', '2026-11-09T01:00:00Z', '2026-11-09T01:00:20Z', 20.0, 100, 98)
            """
            )
            conn.execute(
                """
                INSERT INTO pipeline_run_events (
                    run_id, seq, stage, step_name, event_type, level, duration_ms, message, timestamp
                ) VALUES
                ('test-seed-run-2', 1, 'export', 'exporter', 'STEP_COMPLETED', 'INFO', 250, 'Excel export written', '2026-11-09T01:00:15Z')
            """
            )
            conn.commit()

    resp = client.get("/api/pipeline/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    assert len(data["runs"]) >= 2
    run_latest = data["runs"][0]
    run_prev = data["runs"][1]
    assert run_latest["status"] in ["COMPLETED", "RUNNING", "CANCELLED"]

    # Test run-to-run comparison diff endpoint
    cmp_resp = client.get(
        f"/api/pipeline/runs/compare?run_a={run_prev['run_id']}&run_b={run_latest['run_id']}"
    )
    assert cmp_resp.status_code == 200
    cmp_data = cmp_resp.json()
    assert "run_a" in cmp_data
    assert "run_b" in cmp_data
    assert "diff" in cmp_data
    assert "leads_delta" in cmp_data["diff"]
    assert "duration_delta_seconds" in cmp_data["diff"]

    # Test run events retrieval
    ev_resp = client.get(f"/api/pipeline/runs/{run_latest['run_id']}/events")
    assert ev_resp.status_code == 200
    ev_data = ev_resp.json()
    assert "events" in ev_data

    # Test single run deletion
    # Insert a temporary test run to safely delete
    from metrixa_engine.api.server import db

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, run_number, trigger_type, target_city, active_stage, status,
                started_at, duration_seconds
            ) VALUES ('test-run-del-1', 9999, 'MANUAL_STAGE', 'Berlin', 'ingest', 'CANCELLED', '2026-11-09T00:00:00Z', 1.0)
            """
        )
        conn.commit()

    del_resp = client.delete("/api/pipeline/runs/test-run-del-1")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted_run_id"] == "test-run-del-1"

    # Test clear cancelled filter
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, run_number, trigger_type, target_city, active_stage, status,
                started_at, duration_seconds
            ) VALUES ('test-run-del-2', 9998, 'MANUAL_STAGE', 'Berlin', 'ingest', 'CANCELLED', '2026-11-09T00:00:00Z', 1.0)
            """
        )
        conn.commit()

    clear_resp = client.delete("/api/pipeline/runs?filter=cancelled")
    assert clear_resp.status_code == 200
    assert clear_resp.json()["status"] == "success"

    # Test batch deletion endpoint
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, run_number, trigger_type, target_city, active_stage, status,
                started_at, duration_seconds
            ) VALUES
                ('test-run-batch-1', 9997, 'MANUAL_STAGE', 'Berlin', 'ingest', 'COMPLETED', '2026-11-09T00:00:00Z', 1.0),
                ('test-run-batch-2', 9996, 'MANUAL_STAGE', 'Berlin', 'ingest', 'COMPLETED', '2026-11-09T00:00:00Z', 1.0)
            """
        )
        conn.commit()

    batch_resp = client.post(
        "/api/pipeline/runs/batch-delete",
        json={"run_ids": ["test-run-batch-1", "test-run-batch-2"]},
    )
    assert batch_resp.status_code == 200
    assert batch_resp.json()["deleted_count"] == 2

    # Clean up test seed runs so database stays pristine
    with db.connect() as conn:
        conn.execute(
            "DELETE FROM pipeline_run_events WHERE run_id LIKE 'test-seed-run%'"
        )
        conn.execute("DELETE FROM pipeline_runs WHERE run_id LIKE 'test-seed-run%'")
        conn.commit()


def test_api_deliverables_and_google_sheets_sync(client: TestClient) -> None:
    # 1. Test deliverables status endpoint
    status_resp = client.get("/api/deliverables/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["canonical_leads"] >= 0
    assert status_data["deliverables_count"] >= 5
    deliv_ids = [d["id"] for d in status_data["deliverables"]]
    assert "excel_master" in deliv_ids
    assert "csv_master" in deliv_ids
    assert "sqlite_db" in deliv_ids
    assert "google_sheets_live" in deliv_ids

    # 2. Test Google Sheets connectivity test endpoint
    test_conn = client.post("/api/deliverables/google-sheets/test", json={})
    assert test_conn.status_code == 200
    conn_data = test_conn.json()
    assert conn_data["status"] in ("READY_STANDBY", "CONNECTED", "AUTHENTICATED")
    assert conn_data["prepared_rows_count"] >= 0

    # 3. Test Google Sheets sync endpoint
    sync_resp = client.post("/api/deliverables/google-sheets/sync", json={})
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["success"] is True
    assert sync_data["qualified_leads_synced"] >= 0
    assert len(sync_data["tabs_updated"]) == 4

    # 4. Test Google Sheets preview endpoint
    preview_resp = client.get("/api/deliverables/google-sheets/preview")
    assert preview_resp.status_code == 200
    preview_data = preview_resp.json()
    assert "tabs" in preview_data
    assert "Qualified_Berlin_Leads" in preview_data["tabs"]
    assert preview_data["tabs"]["Qualified_Berlin_Leads"]["total_rows"] >= 0

    # 5. Test Google Sheets URL endpoint
    url_resp = client.get("/api/deliverables/google-sheets/url")
    assert url_resp.status_code == 200
    assert "spreadsheet_url" in url_resp.json()

    # 6. Test artifacts preview for google-sheets-live
    art_prev = client.get("/api/artifacts/preview/google-sheets-live")
    assert art_prev.status_code in (200, 404)
    if art_prev.status_code == 200:
        art_data = art_prev.json()
        assert art_data["type"] == "xlsx"
        assert len(art_data["sheets"]) == 4
        assert "Qualified_Berlin_Leads" in art_data["sheets"]

    # 7. Test sync all deliverables endpoint
    sync_all = client.post("/api/deliverables/sync-all")
    assert sync_all.status_code == 200
    assert sync_all.json()["success"] is True


def test_api_system_stats_and_factory_reset(client: TestClient) -> None:
    # 1. Test system stats endpoint
    stats_resp = client.get("/api/system/stats")
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()
    assert stats_data["status"] == "online"
    assert "counts" in stats_data
    assert "storage" in stats_data
    assert stats_data["counts"]["next_run_number"] >= 1

    # 2. Test factory reset with invalid word (must return 400)
    bad_reset = client.post(
        "/api/system/factory-reset",
        json={"confirmation_word": "WRONG_WORD"},
    )
    assert bad_reset.status_code == 400

    # 3. Test factory reset with correct word "DELETE"
    ok_reset = client.post(
        "/api/system/factory-reset",
        json={"confirmation_word": "DELETE"},
    )
    assert ok_reset.status_code == 200
    reset_data = ok_reset.json()
    assert reset_data["status"] == "success"
    assert reset_data["next_run_number"] == 1

    # 4. Verify system stats reflect clean state
    post_stats = client.get("/api/system/stats")
    assert post_stats.status_code == 200
    p_data = post_stats.json()
    assert p_data["counts"]["companies_golden"] == 0
    assert p_data["counts"]["pipeline_runs"] == 0
    assert p_data["counts"]["next_run_number"] == 1

    # 5. Verify artifacts file list is empty after factory reset
    art_resp = client.get("/api/artifacts/files")
    assert art_resp.status_code == 200
    assert art_resp.json()["items"] == []
