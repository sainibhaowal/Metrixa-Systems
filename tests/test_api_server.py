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
    assert data["golden_total"] >= 1100
    assert "Tier A (High Priority)" in data["tiers"]
    assert len(data["district_breakdown"]) >= 5


def test_api_leads_search_and_filters(client: TestClient) -> None:
    # 1. Test tier filter
    resp = client.get("/api/leads?tier=Tier+A&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) > 0
    for lead in data["items"]:
        assert "Tier A" in lead["lead_tier"]
        assert lead["metrixa_lead_score"] >= 70

    # 2. Test search query
    resp_q = client.get("/api/leads?q=BVBI")
    assert resp_q.status_code == 200
    data_q = resp_q.json()
    assert any("BVBI" in item["display_name"] for item in data_q["items"])


def test_api_lead_evidence_dossier(client: TestClient) -> None:
    # Fetch lead list to grab first company id
    resp = client.get("/api/leads?limit=1")
    assert resp.status_code == 200
    first_id = resp.json()["items"][0]["company_id"]

    ev_resp = client.get(f"/api/leads/{first_id}/evidence")
    assert ev_resp.status_code == 200
    ev_data = ev_resp.json()

    assert "scorecard" in ev_data
    assert "scale_pts" in ev_data["scorecard"]
    assert "total_score" in ev_data["scorecard"]
    assert isinstance(ev_data["decision_makers"], list)
    assert isinstance(ev_data["crawled_pages"], list)


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

    for prov in ("gemini", "openai", "deepseek"):
        disc_resp = client.post("/api/providers/models", json={"provider": prov})
        assert disc_resp.status_code == 200
        disc_data = disc_resp.json()
        assert disc_data["status"] in ("awaiting_key", "offline", "ok")
        assert isinstance(disc_data["models"], list)
        if disc_data["status"] == "awaiting_key":
            assert disc_data["models"] == []


def test_api_artifacts_library_and_preview(client: TestClient) -> None:
    resp = client.get("/api/artifacts/files")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 4
    file_ids = [item["id"] for item in data["items"]]
    assert "xlsx-master" in file_ids
    assert "csv-master" in file_ids
    assert "eval-report" in file_ids

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
        json={"action": "archive", "file_ids": ["eval-report"]},
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["affected_count"] == 1

    restore_resp = client.post(
        "/api/artifacts/action",
        json={"action": "restore", "file_ids": ["eval-report"]},
    )
    assert restore_resp.status_code == 200


def test_api_pipeline_runs_and_comparison(client: TestClient) -> None:
    resp = client.get("/api/pipeline/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    assert len(data["runs"]) >= 3
    run_16 = data["runs"][0]
    run_15 = data["runs"][1]
    assert run_16["run_number"] >= 16
    assert run_16["status"] == "COMPLETED"

    # Test run-to-run comparison diff endpoint
    cmp_resp = client.get(
        f"/api/pipeline/runs/compare?run_a={run_15['run_id']}&run_b={run_16['run_id']}"
    )
    assert cmp_resp.status_code == 200
    cmp_data = cmp_resp.json()
    assert "run_a" in cmp_data
    assert "run_b" in cmp_data
    assert "diff" in cmp_data
    assert "leads_delta" in cmp_data["diff"]
    assert "duration_delta_seconds" in cmp_data["diff"]


def test_api_deliverables_and_google_sheets_sync(client: TestClient) -> None:
    # 1. Test deliverables status endpoint
    status_resp = client.get("/api/deliverables/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["canonical_leads"] == 1200
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
    assert conn_data["prepared_rows_count"] >= 1200

    # 3. Test Google Sheets sync endpoint
    sync_resp = client.post("/api/deliverables/google-sheets/sync", json={})
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["success"] is True
    assert sync_data["qualified_leads_synced"] == 1200
    assert len(sync_data["tabs_updated"]) == 4

    # 4. Test Google Sheets preview endpoint
    preview_resp = client.get("/api/deliverables/google-sheets/preview")
    assert preview_resp.status_code == 200
    preview_data = preview_resp.json()
    assert "tabs" in preview_data
    assert "Qualified_Berlin_Leads" in preview_data["tabs"]
    assert preview_data["tabs"]["Qualified_Berlin_Leads"]["total_rows"] == 1200

    # 5. Test Google Sheets URL endpoint
    url_resp = client.get("/api/deliverables/google-sheets/url")
    assert url_resp.status_code == 200
    assert "spreadsheet_url" in url_resp.json()

    # 6. Test artifacts preview for google-sheets-live
    art_prev = client.get("/api/artifacts/preview/google-sheets-live")
    assert art_prev.status_code == 200
    art_data = art_prev.json()
    assert art_data["type"] == "xlsx"
    assert len(art_data["sheets"]) == 4
    assert "Qualified_Berlin_Leads" in art_data["sheets"]

    # 7. Test sync all deliverables endpoint
    sync_all = client.post("/api/deliverables/sync-all")
    assert sync_all.status_code == 200
    assert sync_all.json()["success"] is True
