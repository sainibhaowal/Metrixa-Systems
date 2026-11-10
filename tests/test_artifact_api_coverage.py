from __future__ import annotations


from fastapi.testclient import TestClient

from metrixa_engine.api import server


def test_artifact_files_preview_actions_and_download_variants(tmp_path, monkeypatch):
    client = TestClient(server.app)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    monkeypatch.setattr(server.settings, "export_dir", export_dir)
    monkeypatch.setattr(server.settings, "project_root", tmp_path)
    (tmp_path / "docs" / "Case Study").mkdir(parents=True)
    (tmp_path / "docs" / "Case Study" / "Case Study.md").write_text(
        "case notes", encoding="utf-8"
    )
    # Real parsers consume the supported formats; these are isolated test artifacts.
    import openpyxl

    book = openpyxl.Workbook()
    book.active.append(["Lead", "Value"])
    book.active.append(["Alpha", 1])
    book.save(export_dir / "metrixa_berlin_hausverwaltungen.xlsx")
    (export_dir / "metrixa_berlin_leads_master.csv").write_text(
        "Lead,Value\nAlpha,1\n", encoding="utf-8-sig"
    )
    (export_dir / "evaluation_ablation_report.md").write_text(
        "# Evaluation", encoding="utf-8"
    )
    (export_dir / "metrixa_executive_presentation.md").write_text(
        "# Brief", encoding="utf-8"
    )
    (export_dir / "Case_Study_Metrixa_Systems.pdf").write_bytes(b"%PDF isolated")

    orig = {k: dict(v) for k, v in server._artifact_store.items()}
    try:
        # Unknown and all supported resolver aliases.
        assert server._resolve_artifact_path("unknown") is None
        for artifact_id in (
            "xlsx-master",
            "csv-master",
            "eval-report",
            "exec-brief",
            "pdf-casestudy",
        ):
            assert server._resolve_artifact_path(artifact_id) is not None
        response = client.get("/api/artifacts/files")
        assert response.status_code == 200
        listed = {row["id"]: row for row in response.json()["items"]}
        assert "xlsx-master" in listed and "csv-master" in listed
        assert "google-sheets-live" not in listed  # no complete sheet sync
        assert listed["xlsx-master"]["sha256_short"]
        # Hash helper returns its cached value for identical mtime and size.
        xlsx = export_dir / "metrixa_berlin_hausverwaltungen.xlsx"
        stat = xlsx.stat()
        assert (
            server._compute_sha256_short(xlsx, stat.st_mtime, stat.st_size)
            == listed["xlsx-master"]["sha256_short"]
        )

        assert client.get("/api/artifacts/preview/xlsx-master").json()["sheet_data"][
            "Sheet"
        ]["rows"] == [["Alpha", "1"]]
        assert (
            client.get("/api/artifacts/preview/xlsx-master").status_code == 200
        )  # mtime cache
        assert client.get("/api/artifacts/preview/csv-master").json()["total_rows"] == 1
        assert (
            client.get("/api/artifacts/preview/eval-report").json()["content"]
            == "# Evaluation"
        )
        assert (
            client.get("/api/artifacts/preview/exec-brief").json()["content"]
            == "# Brief"
        )
        assert (
            client.get("/api/artifacts/preview/pdf-casestudy").json()["content"]
            == "case notes"
        )
        assert client.get("/api/artifacts/preview/unknown").status_code == 404

        # Retention and trash lifecycle persist metadata and leave the files intact.
        set_retention = client.post(
            "/api/artifacts/action",
            json={"action": "set_retention", "retention_days": 60},
        )
        assert set_retention.json()["affected_count"] == len(server._artifact_store)
        assert all(
            item["retention_days"] == 60 for item in server._artifact_store.values()
        )
        assert (
            client.post(
                "/api/artifacts/action",
                json={"action": "trash", "file_ids": ["xlsx-master"]},
            ).json()["affected_count"]
            == 1
        )
        assert (
            client.post("/api/artifacts/action", json={"action": "empty_trash"}).json()[
                "affected_count"
            ]
            == 1
        )
        assert server._artifact_store["xlsx-master"]["status"] == "deleted"
        assert (
            client.post(
                "/api/artifacts/action",
                json={"action": "delete_permanent", "file_ids": ["csv-master"]},
            ).json()["affected_count"]
            == 0
        )
        client.post(
            "/api/artifacts/action",
            json={"action": "trash", "file_ids": ["csv-master"]},
        )
        assert (
            client.post(
                "/api/artifacts/action",
                json={"action": "delete_permanent", "file_ids": ["csv-master"]},
            ).json()["affected_count"]
            == 1
        )
        assert server._artifact_store["csv-master"]["status"] == "deleted"
        assert (
            client.post(
                "/api/artifacts/action",
                json={"action": "restore", "file_ids": ["xlsx-master"]},
            ).json()["affected_count"]
            == 1
        )
        assert server._artifact_store["xlsx-master"]["status"] == "active"

        # Downloads use actual temporary artifacts/database snapshot only.
        for artifact in (
            "xlsx-master",
            "excel",
            "csv-master",
            "csv",
            "eval-report",
            "report",
            "exec-brief",
            "presentation",
            "database",
            "db-snapshot",
            "pdf-casestudy",
            "casestudy",
            "pdf",
        ):
            assert client.get(f"/api/artifacts/download/{artifact}").status_code == 200
        for endpoint in (
            "/api/artifacts/download/excel",
            "/api/artifacts/download/csv",
        ):
            assert client.get(endpoint).status_code == 200
        assert client.get("/api/artifacts/evaluation-report").status_code == 200

        # Fallback report filename works when canonical filename is absent.
        (export_dir / "metrixa_evaluation_ablation_report.md").unlink(missing_ok=True)
        assert client.get("/api/artifacts/download/eval-report").status_code == 200
    finally:
        server._artifact_store.clear()
        server._artifact_store.update({k: dict(v) for k, v in orig.items()})
        server._preview_cache.clear()
        server._sha256_cache.clear()


def test_artifact_missing_files_empty_database_and_cloud_preview(tmp_path, monkeypatch):
    client = TestClient(server.app)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    monkeypatch.setattr(server.settings, "export_dir", export_dir)
    monkeypatch.setattr(server.settings, "project_root", tmp_path)
    for url in (
        "/api/artifacts/preview/xlsx-master",
        "/api/artifacts/preview/csv-master",
        "/api/artifacts/preview/eval-report",
        "/api/artifacts/preview/exec-brief",
        "/api/artifacts/preview/pdf-casestudy",
        "/api/artifacts/download/xlsx-master",
        "/api/artifacts/download/csv-master",
        "/api/artifacts/download/eval-report",
        "/api/artifacts/download/exec-brief",
        "/api/artifacts/download/pdf-casestudy",
        "/api/artifacts/download/google-sheets-live",
    ):
        assert client.get(url).status_code == 404
    assert client.get("/api/artifacts/evaluation-report").status_code == 404
    assert client.get("/api/artifacts/download/not-found").status_code == 404
    assert client.post("/api/artifacts/sync").status_code == 200

    # A zero-byte artifact is hidden when there are no canonical leads.
    (export_dir / "metrixa_berlin_leads_master.csv").write_bytes(b"")
    assert all(
        row["id"] != "csv-master"
        for row in client.get("/api/artifacts/files").json()["items"]
    )


def test_artifact_cloud_sync_preview_and_status_metadata(monkeypatch):
    client = TestClient(server.app)
    import metrixa_engine.api.server as module

    original = module.GoogleSheetsSync.get_live_deliverables_status
    monkeypatch.setattr(
        module.GoogleSheetsSync,
        "get_live_deliverables_status",
        lambda self: {
            "deliverables": [
                {
                    "id": "google_sheets_live",
                    "status": "SYNCED",
                    "download_url": "https://docs.google.com/spreadsheets/d/test",
                    "updated_at": "2026-11-10T10:00:00+00:00",
                    "records_count": 12,
                }
            ]
        },
    )
    orig = {k: dict(v) for k, v in module._artifact_store.items()}
    try:
        with module.db.connect() as conn:
            conn.execute(
                "INSERT INTO companies_golden (canonical_name, display_name, sources_csv, pipeline_stage, updated_at) VALUES ('cloud','Cloud GmbH','test','EXTRACTED','now')"
            )
        preview = client.get("/api/artifacts/preview/google-sheets-live")
        assert preview.status_code == 200 and preview.json()["cloud_mirror"] is True
        redirect = client.get(
            "/api/artifacts/download/google-sheets-live", follow_redirects=False
        )
        assert redirect.status_code == 307 and redirect.headers["location"].startswith(
            "https://docs.google.com"
        )
        files = client.get("/api/artifacts/files").json()
        cloud = next(row for row in files["items"] if row["id"] == "google-sheets-live")
        assert (
            cloud["records_count"] == 12 and cloud["size_formatted"] == "4 Cloud Tabs"
        )
        # Deleting state suppresses a cloud artifact from the library.
        client.post(
            "/api/artifacts/action",
            json={"action": "trash", "file_ids": ["google-sheets-live"]},
        )
        client.post(
            "/api/artifacts/action",
            json={"action": "delete_permanent", "file_ids": ["google-sheets-live"]},
        )
        assert all(
            row["id"] != "google-sheets-live"
            for row in client.get("/api/artifacts/files").json()["items"]
        )
    finally:
        module._artifact_store.clear()
        module._artifact_store.update({k: dict(v) for k, v in orig.items()})
        monkeypatch.setattr(
            module.GoogleSheetsSync, "get_live_deliverables_status", original
        )
