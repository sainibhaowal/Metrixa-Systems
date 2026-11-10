from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metrixa_engine.api import server
from metrixa_engine.db import Database


@pytest.fixture
def isolated_api(monkeypatch, tmp_path):
    db = Database(tmp_path / "api-residual.db")
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.settings, "database_path", db.db_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    monkeypatch.setattr(server.settings, "export_dir", export_dir)
    server._metrics_cache.clear()
    server._preview_cache.clear()
    server._sha256_cache.clear()
    return TestClient(server.app), db, export_dir


def _insert_run(
    db, run_id, number, *, status="COMPLETED", summary=None, out=1, duration=1.0
):
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO pipeline_runs (run_id,run_number,trigger_type,target_city,active_stage,status,total_companies_out,duration_seconds,started_at,summary_metrics_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                number,
                "MANUAL_STAGE",
                None,
                "full",
                status,
                out,
                duration,
                "now",
                summary,
            ),
        )


def test_metrics_include_trimmed_erp_counts_and_cache(isolated_api):
    client, db, _ = isolated_api
    with db.connect() as conn:
        company = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,pipeline_stage,updated_at,district) VALUES ('a','Alpha','test','SCORED','now',NULL)"
        ).lastrowid
        conn.execute(
            "INSERT INTO kpi_extractions (company_id,detected_erp_proptech,extracted_at) VALUES (?,?,'now')",
            (company, " Casavi, , Domus "),
        )
    first = client.get("/api/metrics").json()
    assert first["erp_breakdown"] == {"Casavi": 1, "Domus": 1}
    assert first["district_breakdown"] == [{"district": "Berlin", "count": 1}]
    server.event_bus.current_stage = "TEST_CACHE"
    second = client.get("/api/metrics").json()
    assert second["pipeline_state"]["current_stage"] == "TEST_CACHE"
    server.event_bus.current_stage = "IDLE"


def test_scorecard_scale_and_contact_variants(isolated_api):
    client, db, _ = isolated_api
    expected = [
        (2500, None, 35),
        (1000, None, 28),
        (300, None, 20),
        (None, None, 16),
        (None, None, 6),
    ]
    ids = []
    with db.connect() as conn:
        for index, (units, tier, _) in enumerate(expected):
            company_id = conn.execute(
                "INSERT INTO companies_golden (canonical_name,display_name,legal_form,sources_csv,pipeline_stage,updated_at,website_url,is_vdiv_member) VALUES (?,?,?,?,?,?,?,?)",
                (
                    f"c{index}",
                    f"Company {index}",
                    "GmbH" if index == 3 else None,
                    "test",
                    "SCORED",
                    "now",
                    "https://example.invalid" if index == 0 else None,
                    1 if index == 0 else 0,
                ),
            ).lastrowid
            ids.append(company_id)
            conn.execute(
                "INSERT INTO kpi_extractions (company_id,exact_units_managed,estimated_units_tier,manages_weg,manages_miet,has_customer_portal,detected_erp_proptech,extracted_at) VALUES (?,?,?,?,?,?,?,'now')",
                (
                    company_id,
                    units,
                    tier,
                    index == 0,
                    index < 2,
                    index == 0,
                    "Casavi" if index == 0 else None,
                ),
            )
            if index == 0:
                conn.execute(
                    "INSERT INTO decision_makers (company_id,full_name,personal_email,email_status) VALUES (?, 'Max Mustermann','max@example.invalid','PUBLIC_LISTED')",
                    (company_id,),
                )
    for company_id, (_, _, scale) in zip(ids, expected):
        response = client.get(f"/api/leads/{company_id}/evidence")
        assert response.status_code == 200
        assert response.json()["scorecard"]["scale_pts"] == scale
    assert (
        client.get(f"/api/leads/{ids[0]}/evidence").json()["scorecard"]["focus_pts"]
        == 25
    )
    assert (
        client.get(f"/api/leads/{ids[2]}/evidence").json()["scorecard"]["focus_pts"]
        == 15
    )


def test_pipeline_run_json_fallback_delete_clear_events_and_compare(isolated_api):
    client, db, _ = isolated_api
    _insert_run(db, "valid", 1, summary='{"count": 2}', out=2, duration=4)
    _insert_run(db, "invalid", 2, summary="not-json", out=4, duration=7)
    listing = client.get("/api/pipeline/runs").json()["runs"]
    assert listing[0]["summary"] == {} and listing[1]["summary"] == {"count": 2}
    assert client.get("/api/pipeline/runs/valid/events").json()["events"] == []
    assert client.get("/api/pipeline/runs/absent/events").json()["events"] == []
    assert (
        client.get("/api/pipeline/runs/compare?run_a=missing&run_b=valid").status_code
        == 404
    )
    assert (
        client.get("/api/pipeline/runs/compare?run_a=valid&run_b=invalid").status_code
        == 200
    )
    assert (
        client.get("/api/pipeline/runs/compare?run_a=invalid&run_b=valid").status_code
        == 200
    )
    assert client.delete("/api/pipeline/runs/missing").status_code == 404
    assert (
        client.post("/api/pipeline/runs/batch-delete", json={"run_ids": []}).json()[
            "deleted_count"
        ]
        == 0
    )

    _insert_run(db, "cancelled", 3, status="CANCELLED")
    _insert_run(db, "keep", 4)
    cancelled = client.delete("/api/pipeline/runs?filter=cancelled").json()
    assert cancelled["filter"] == "cancelled" and cancelled["deleted_count"] == 1
    all_runs = client.delete("/api/pipeline/runs?filter=all").json()
    assert all_runs["deleted_count"] == 3


def test_cancel_pipeline_idle_and_active(isolated_api, monkeypatch):
    client, db, _ = isolated_api
    assert client.post("/api/pipeline/cancel").json()["status"] == "idle"
    _insert_run(db, "running-test", 1, status="RUNNING")

    class Task:
        cancelled = False

        def done(self):
            return False

        def cancel(self):
            self.cancelled = True

    task = Task()
    monkeypatch.setattr(server, "active_pipeline_task", task)
    server.event_bus.is_running = True
    server.event_bus.current_run_id = "running-test"
    result = client.post("/api/pipeline/cancel").json()
    assert result == {"status": "cancelled", "run_id": "running-test"}
    assert task.cancelled
    with db.connect() as conn:
        assert (
            conn.execute(
                "SELECT status FROM pipeline_runs WHERE run_id='running-test'"
            ).fetchone()[0]
            == "CANCELLED"
        )
    server.event_bus.current_run_id = None
    server.event_bus.is_running = False


def test_sse_stream_first_message_heartbeat_and_event(monkeypatch):
    async def run():
        response = await server.stream_pipeline_events()
        iterator = response.body_iterator
        first = await anext(iterator)
        assert (
            first["event"] == "HEARTBEAT" and '"status": "connected"' in first["data"]
        )

        original_wait_for = asyncio.wait_for
        calls = 0

        async def first_timeout(awaitable, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                awaitable.close()
                raise asyncio.TimeoutError
            return await original_wait_for(awaitable, timeout)

        monkeypatch.setattr(asyncio, "wait_for", first_timeout)
        heartbeat = await anext(iterator)
        assert heartbeat["event"] == "HEARTBEAT"
        await server.event_bus.emit("LOG", {"message": "queued"})
        queued = await anext(iterator)
        assert queued["event"] == "LOG"
        await iterator.aclose()

    asyncio.run(run())


def test_stats_wal_and_large_database_format(isolated_api, monkeypatch, tmp_path):
    client, db, export_dir = isolated_api
    (export_dir / "visible.csv").write_text("a", encoding="utf-8")
    db_file = tmp_path / "large.db"
    db_file.write_bytes(b"x" * (1024 * 1024 + 10))
    Path(f"{db_file}-wal").write_bytes(b"wal")
    monkeypatch.setattr(server.settings, "database_path", db_file)
    data = client.get("/api/system/stats").json()
    assert data["storage"]["database_size_bytes"] == 1024 * 1024 + 13
    assert data["storage"]["database_size_formatted"].endswith("MB")
    assert data["storage"]["export_files_count"] == 1


def test_tools_catalog_degrades_when_database_unavailable(isolated_api, monkeypatch):
    client, _, _ = isolated_api

    class BrokenDb:
        def connect(self):
            raise OSError("offline")

    monkeypatch.setattr(server, "db", BrokenDb())
    tools = {item["id"]: item for item in client.get("/api/tools").json()}
    assert tools["tool_crawler"]["records_extracted"] == 0
    assert tools["tool_mx_verifier"]["records_extracted"] == 0


def test_atomic_env_write_cleans_temp_on_replace_failure(monkeypatch, tmp_path):
    target = tmp_path / "settings.env"
    target.write_text("OLD=value\n", encoding="utf-8")
    monkeypatch.setenv("METRIXA_ENV_PATH", str(target))

    def fail_replace(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(server.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk full"):
        server._persist_runtime_settings({"OPENAI_API_KEY": "new-value"})
    assert target.read_text(encoding="utf-8") == "OLD=value\n"
    assert list(tmp_path.glob(".settings.env.*.tmp")) == []


def test_application_lifespan_yields_cleanly():
    async def run():
        async with server.lifespan(server.app):
            assert server.app.title == "Metrixa Cockpit API"

    asyncio.run(run())
