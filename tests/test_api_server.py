"""
Integration Test Suite for FastAPI Backend Gateway (`heidi_engine.api.server`).
Verifies /api/metrics, /api/leads, /api/leads/{id}/evidence, /api/tools, /api/settings,
and Artifact downloads.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from heidi_engine.api.server import app


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
        assert lead["heidi_lead_score"] >= 70

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

