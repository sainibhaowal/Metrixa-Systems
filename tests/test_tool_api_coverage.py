from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from metrixa_engine.api import server
from metrixa_engine.db import Database


class _Response:
    def __init__(self, status=200):
        self.status_code = status


class _HttpClient:
    status = 204
    error = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def head(self, *args, **kwargs):
        if self.error:
            raise self.error
        return _Response(self.status)

    async def get(self, *args, **kwargs):
        if self.error:
            raise self.error
        return _Response(self.status)


@pytest.fixture
def client():
    return TestClient(server.app)


def test_tool_health_database_branches_and_unknown(client, monkeypatch, tmp_path):
    import metrixa_engine.enrichment.email_verifier as email_module
    import metrixa_engine.api.server as api

    isolated = Database(tmp_path / "tool-health.db")
    monkeypatch.setattr(api, "db", isolated)
    # Empty database produces honest degraded states for MX and crawler tools.
    mx = client.post("/api/tools/test/tool_mx_verifier").json()
    crawler = client.post("/api/tools/test/tool_crawler").json()
    assert mx["status"] == "DEGRADED" and mx["records_checked"] == 0
    assert crawler["status"] == "DEGRADED" and crawler["records_checked"] == 0

    with isolated.connect() as conn:
        cur = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,canonical_domain,sources_csv,pipeline_stage,updated_at) VALUES ('x','Alpha GmbH','alpha.de','test','DEDUPED','now')"
        )
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,clean_markdown,crawled_at) VALUES (?,'homepage','https://alpha.de',200,'Casavi info@alpha.de','now')",
            (cur.lastrowid,),
        )
    monkeypatch.setattr(
        email_module.EmailVerifier,
        "check_domain_mx_sync",
        lambda self, domain: (True, "mx.alpha.de"),
    )
    assert client.post("/api/tools/test/tool_mx_verifier").json()["status"] == "OK"
    stored = client.post("/api/tools/test/tool_crawler").json()
    assert stored["records_checked"] == 1 and stored["target"] == "https://alpha.de"

    monkeypatch.setattr(api.httpx, "AsyncClient", _HttpClient)
    for tool_id in ("tool_vdiv", "tool_gelbe_seiten", "tool_11880", "tool_osm"):
        assert client.post(f"/api/tools/test/{tool_id}").json()["status"] == "OK"
    _HttpClient.status = 503
    assert client.post("/api/tools/test/tool_vdiv").json()["status"] == "DEGRADED"
    _HttpClient.error = OSError("offline")
    assert client.post("/api/tools/test/tool_gelbe_seiten").json()["status"] == "ERROR"
    assert client.post("/api/tools/test/not-a-tool").status_code == 404
    _HttpClient.status, _HttpClient.error = 204, None


def test_execute_tool_validates_inputs_and_returns_real_local_results(
    client, monkeypatch, tmp_path
):
    import metrixa_engine.api.server as api
    import metrixa_engine.enrichment.email_verifier as email_module

    isolated = Database(tmp_path / "tool-exec.db")
    monkeypatch.setattr(api, "db", isolated)
    with isolated.connect() as conn:
        conn.execute(
            "INSERT INTO raw_listings (source_name,raw_company_name,raw_street,raw_postal_code,raw_city,raw_district,raw_phone,raw_website,scraped_at) VALUES ('gelbe_seiten','Alpha Hausverwaltung GmbH','Main St','10115','Berlin','Mitte','030123','https://alpha.de','now')"
        )
        conn.execute(
            "INSERT INTO raw_listings (source_name,raw_company_name,scraped_at) VALUES ('11880','Beta Hausverwaltung GmbH','now')"
        )
    assert (
        client.post(
            "/api/tools/execute", json={"tool_id": "invalid", "input": ""}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/tools/execute", json={"tool_id": "tool_mx_verifier", "input": ""}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/tools/execute",
            json={"tool_id": "tool_mx_verifier", "input": "not a domain"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/tools/execute", json={"tool_id": "tool_crawler", "input": ""}
        ).status_code
        == 422
    )
    monkeypatch.setattr(
        email_module.EmailVerifier,
        "check_domain_mx_sync",
        lambda self, domain: (False, None),
    )
    mx = client.post(
        "/api/tools/execute",
        json={"tool_id": "tool_mx_verifier", "input": "Owner@Alpha.DE."},
    ).json()
    assert (
        mx["output"]["domain"] == "alpha.de"
        and mx["output"]["mailbox_verified"] is False
    )
    text = (
        "Kundenportal Casavi info@alpha.de LinkedIn https://linkedin.com/company/alpha"
    )
    crawl = client.post(
        "/api/tools/execute", json={"tool_id": "tool_crawler", "input": text}
    ).json()
    assert crawl["output"]["detected_proptech_erp"] == ["Casavi"]
    assert crawl["output"]["extracted_emails"] == ["info@alpha.de"]
    assert len(crawl["input"]) == len(text)
    long_text = "x" * 121
    assert (
        client.post(
            "/api/tools/execute", json={"tool_id": "tool_crawler", "input": long_text}
        )
        .json()["input"]
        .endswith("...")
    )

    # Directory tool IDs map to source names; query and all-record modes return DB-backed data only.
    for tool_id in ("tool_gelbe_seiten", "tool_11880", "tool_vdiv", "tool_osm"):
        all_rows = client.post(
            "/api/tools/execute", json={"tool_id": tool_id, "input": ""}
        ).json()
        assert all_rows["success"] and "All " in all_rows["input"]
        queried = client.post(
            "/api/tools/execute", json={"tool_id": tool_id, "input": "alpha"}
        ).json()
        expected = 1 if tool_id == "tool_gelbe_seiten" else 0
        assert queried["output"]["matches_found"] == expected
    sample = client.post(
        "/api/tools/execute", json={"tool_id": "tool_gelbe_seiten", "input": "alpha"}
    ).json()["output"]["sample_listings"][0]
    assert sample["address"] == "Main St, 10115 Berlin" and sample["phone"] == "030123"


def test_health_probe_connection_errors_are_reported(client, monkeypatch):
    import metrixa_engine.api.server as api

    monkeypatch.setattr(api.httpx, "AsyncClient", _HttpClient)
    _HttpClient.error = OSError("offline")
    for tool_id in ("tool_vdiv", "tool_gelbe_seiten", "tool_11880", "tool_osm"):
        assert client.post(f"/api/tools/test/{tool_id}").json()["status"] == "ERROR"
    _HttpClient.error = None
