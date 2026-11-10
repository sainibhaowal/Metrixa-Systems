"""Regression coverage for honest local and cloud deliverable state."""

from __future__ import annotations

from pathlib import Path

import gspread

from metrixa_engine.config import settings
from metrixa_engine.db import Database
from metrixa_engine.telemetry.google_sheets_sync import GoogleSheetsSync


def _seed_company(db: Database) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO companies_golden (
                canonical_name, display_name, sources_csv, pipeline_stage, updated_at
            ) VALUES ('Example Hausverwaltung GmbH', 'Example Hausverwaltung GmbH', 'test', 'SCORED', ?)
            """,
            ("2026-11-10T00:00:00+00:00",),
        )


class _FakeWorksheet:
    def clear(self) -> None:
        pass

    def update(self, values, value_input_option=None) -> None:
        assert values
        assert value_input_option == "RAW"

    def freeze(self, rows=1) -> None:
        assert rows == 1


class _FakeSpreadsheet:
    title = "Test Sheet"

    def worksheet(self, name: str) -> _FakeWorksheet:
        return _FakeWorksheet()

    def worksheets(self) -> list[_FakeWorksheet]:
        return [_FakeWorksheet()]


class _FakeGoogleClient:
    def open_by_key(self, sheet_id: str) -> _FakeSpreadsheet:
        assert sheet_id == "test-sheet-id"
        return _FakeSpreadsheet()


def test_google_sheets_reports_synced_only_after_all_tabs_succeed(
    tmp_path: Path, monkeypatch
) -> None:
    db = Database(tmp_path / "sheet_sync.db")
    _seed_company(db)
    monkeypatch.setattr(settings, "google_sheet_id", "test-sheet-id")
    monkeypatch.setattr(
        settings, "google_service_account_json", '{"type":"service_account"}'
    )
    monkeypatch.setattr(settings, "google_service_account_file", "")
    monkeypatch.setattr(settings, "google_sheets_webhook_url", "")
    monkeypatch.setattr(
        gspread, "service_account_from_dict", lambda credentials: _FakeGoogleClient()
    )

    sync = GoogleSheetsSync(db)
    result = sync.sync_to_google_sheet()
    status = sync.get_live_deliverables_status()
    google_status = next(
        item for item in status["deliverables"] if item["id"] == "google_sheets_live"
    )

    assert result["success"] is True
    assert len(result["tabs_updated"]) == 4
    assert result["qualified_leads_synced"] == 1
    assert google_status["status"] == "SYNCED"
    assert google_status["records_count"] == 1

    with db.connect() as conn:
        conn.execute(
            "UPDATE companies_golden SET updated_at = ?",
            ("2027-01-01T00:00:00+00:00",),
        )
    stale_status = sync.get_live_deliverables_status()
    stale_sheet = next(
        item
        for item in stale_status["deliverables"]
        if item["id"] == "google_sheets_live"
    )
    assert stale_sheet["status"] == "STALE"
    assert stale_sheet["records_count"] == 1


def test_unconfigured_google_sheets_is_never_reported_online(
    tmp_path: Path, monkeypatch
) -> None:
    db = Database(tmp_path / "unconfigured.db")
    _seed_company(db)
    monkeypatch.setattr(settings, "google_sheet_id", "")
    monkeypatch.setattr(settings, "google_service_account_json", "")
    monkeypatch.setattr(settings, "google_service_account_file", "")
    monkeypatch.setattr(settings, "google_sheets_webhook_url", "")

    status = GoogleSheetsSync(db).get_live_deliverables_status()
    google_status = next(
        item for item in status["deliverables"] if item["id"] == "google_sheets_live"
    )

    assert google_status["status"] == "NOT_CONFIGURED"
    assert google_status["records_count"] == 0
    assert google_status["prepared_records_count"] == 1
    assert google_status["download_url"] is None
    pdf_status = next(
        item for item in status["deliverables"] if item["id"] == "research_pdf"
    )
    assert pdf_status["status"] == "REVIEW_REQUIRED"
    assert "not been validated" in pdf_status["quality_note"]
