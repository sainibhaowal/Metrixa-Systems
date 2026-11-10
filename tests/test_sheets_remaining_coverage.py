from __future__ import annotations

from metrixa_engine.db import Database
from metrixa_engine.telemetry.google_sheets_sync import (
    GoogleSheetsSync,
    _sheet_cell_value,
)


def test_google_sheet_cell_values_keep_booleans_distinct():
    assert _sheet_cell_value(True) == "TRUE"
    assert _sheet_cell_value(False) == "FALSE"
    assert _sheet_cell_value(4) == 4
    assert _sheet_cell_value(1.5) == 1.5
    assert _sheet_cell_value(None) == ""
    assert _sheet_cell_value("data") == "data"


def test_sync_uses_service_account_file_branch(tmp_path, monkeypatch):
    import gspread
    import metrixa_engine.telemetry.google_sheets_sync as module

    db = Database(tmp_path / "file-credential.db")
    monkeypatch.setattr(module.settings, "google_sheet_id", "sheet-id")
    monkeypatch.setattr(
        module.settings, "google_service_account_file", "isolated-creds.json"
    )
    monkeypatch.setattr(module.settings, "google_service_account_json", "")
    monkeypatch.setattr(module.settings, "google_sheets_webhook_url", "")

    class Worksheet:
        def clear(self):
            pass

        def update(self, *args, **kwargs):
            pass

        def freeze(self, rows=1):
            pass

    class Spreadsheet:
        def worksheet(self, name):
            raise gspread.WorksheetNotFound(name)

        def add_worksheet(self, title, rows, cols):
            return Worksheet()

    class Service:
        def open_by_key(self, key):
            assert key == "sheet-id"
            return Spreadsheet()

    calls = []
    monkeypatch.setattr(
        gspread,
        "service_account",
        lambda filename: (calls.append(filename), Service())[1],
    )
    result = GoogleSheetsSync(db).sync_to_google_sheet()
    assert result["sync_mode"] == "gspread_service_account"
    assert calls == ["isolated-creds.json"]
