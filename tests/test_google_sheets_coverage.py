from __future__ import annotations

import json


from metrixa_engine.db import Database
from metrixa_engine.telemetry.google_sheets_sync import GoogleSheetsSync


class _HttpResponse:
    status_code = 204

    def __init__(self, error=None, status=204):
        self.error = error
        self.status_code = status

    def raise_for_status(self):
        if self.error:
            raise self.error


class _HttpContext:
    response = _HttpResponse()
    posted = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def post(self, url, **kwargs):
        self.posted.append((url, kwargs))
        return self.response


def _gspread_fake(monkeypatch, service):
    import gspread

    monkeypatch.setattr(
        gspread, "service_account_from_dict", lambda credentials: service
    )
    monkeypatch.setattr(gspread, "service_account", lambda filename: service)
    return gspread


class _Worksheet:
    title = "Sheet"

    def __init__(self, fail_freeze=False):
        self.fail_freeze = fail_freeze
        self.updated = None

    def clear(self):
        return None

    def update(self, rows, value_input_option=None):
        self.updated = (rows, value_input_option)

    def freeze(self, rows=1):
        if self.fail_freeze:
            raise RuntimeError("freeze unavailable")


class _Spreadsheet:
    title = "Local Test Sheet"

    def __init__(self, missing=False, fail_add=False):
        self.missing = missing
        self.fail_add = fail_add
        self.tabs = {}

    def worksheets(self):
        return [_Worksheet()]

    def worksheet(self, name):
        if self.missing and name != "Qualified_Berlin_Leads":
            import gspread

            raise gspread.WorksheetNotFound(name)
        return self.tabs.setdefault(
            name, _Worksheet(fail_freeze=name == "Qualified_Berlin_Leads")
        )

    def add_worksheet(self, title, rows, cols):
        if self.fail_add:
            raise RuntimeError("cannot add tab")
        self.tabs[title] = _Worksheet()
        return self.tabs[title]


class _GClient:
    def __init__(self, sheet):
        self.sheet = sheet

    def open_by_key(self, key):
        return self.sheet


def _seed(db):
    with db.connect() as conn:
        company_id = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,legal_form,postal_code,website_url,canonical_domain,general_email,company_linkedin_url,is_vdiv_member,source_count,sources_csv,metrixa_lead_score,lead_tier,pipeline_stage,updated_at) VALUES ('alpha','Alpha GmbH','GmbH','10115','https://alpha.de','alpha.de','info@alpha.de','https://linkedin.com/company/alpha',1,2,'osm,11880',82,'Tier A (High Priority)','SCORED','2000-01-01T00:00:00+00:00')"
        ).lastrowid
        conn.execute(
            "INSERT INTO decision_makers (company_id,full_name,first_name,last_name,role,personal_email,email_status,mx_valid,mx_host,direct_phone,linkedin_url,source_url,evidence_quote,is_primary_contact) VALUES (?, 'Max Mustermann','Max','Mustermann','Director','max@alpha.de','PUBLIC_LISTED',1,'mx.alpha.de','030123','https://linkedin.com/in/max','https://alpha.de/impressum','Director Max Mustermann',1)",
            (company_id,),
        )
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,detected_erp_csv,detected_metering_csv,has_portal_link,crawled_at) VALUES (?,'homepage','https://alpha.de',200,'Casavi','Techem',1,'2026-11-10T09:00:00+00:00')",
            (company_id,),
        )
        conn.execute(
            "INSERT INTO kpi_extractions (company_id,units_evidence_quote,llm_provider_used,detected_erp_proptech,extracted_at) VALUES (?, '3200 units','deterministic','Casavi','2026-11-10T09:00:00+00:00')",
            (company_id,),
        )
        conn.execute(
            "INSERT INTO raw_listings (source_name,raw_company_name,scraped_at) VALUES ('osm','Alpha GmbH','now')"
        )
    return company_id


def test_extract_tabs_and_standby_connection(tmp_path, monkeypatch):
    import metrixa_engine.telemetry.google_sheets_sync as module

    db = Database(tmp_path / "tabs.db")
    _seed(db)
    sync = GoogleSheetsSync(db)
    tabs = sync.extract_all_tabs_data()
    assert len(tabs) == 4
    assert len(tabs["Qualified_Berlin_Leads"][1]) == 1
    assert tabs["Qualified_Berlin_Leads"][1][0][1] == "Alpha GmbH"
    assert (
        tabs["All_Decision_Makers_Contacts"][1][0][6]
        == "Publicly listed; mailbox not tested"
    )
    assert tabs["Evidence_And_Audit_Trail"][1][0][3] == "homepage"
    monkeypatch.setattr(module.settings, "google_sheet_id", "")
    assert sync.test_connection()["status"] == "READY_STANDBY"

    # Authenticated credentials without a target, and complete read access with a target.
    sheet = _Spreadsheet()
    service = _GClient(sheet)
    _gspread_fake(monkeypatch, service)
    assert (
        sync.test_connection(service_account_json='{"type":"service_account"}')[
            "status"
        ]
        == "AUTHENTICATED"
    )
    result = sync.test_connection(
        sheet_id="sheet-id", service_account_json='{"type":"service_account"}'
    )
    assert (
        result["status"] == "CONNECTED"
        and result["spreadsheet_title"] == "Local Test Sheet"
    )
    assert result["existing_worksheets"] == ["Sheet"]
    assert (
        sync.test_connection(service_account_file="creds.json")["status"]
        == "AUTHENTICATED"
    )
    assert (
        sync.test_connection(sheet_id="sheet-id", service_account_json="not json")[
            "status"
        ]
        == "ERROR"
    )


def test_webhook_sync_success_error_and_live_status_truth(tmp_path, monkeypatch):
    import metrixa_engine.telemetry.google_sheets_sync as module

    db = Database(tmp_path / "webhook.db")
    _seed(db)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    (export_dir / "metrixa_berlin_hausverwaltungen.xlsx").write_bytes(b"xlsx")
    (export_dir / "metrixa_berlin_leads_master.csv").write_text("csv")
    monkeypatch.setattr(module.settings, "export_dir", export_dir)
    monkeypatch.setattr(module.settings, "database_path", db.db_path)
    monkeypatch.setattr(
        module.settings, "google_sheets_webhook_url", "https://hook.example/receive"
    )
    monkeypatch.setattr(module.settings, "google_sheet_id", "")
    monkeypatch.setattr(module.settings, "google_service_account_file", "")
    monkeypatch.setattr(module.settings, "google_service_account_json", "")
    import httpx

    monkeypatch.setattr(httpx, "Client", _HttpContext)
    _HttpContext.response = _HttpResponse()
    _HttpContext.posted.clear()
    sync = GoogleSheetsSync(db)
    result = sync.sync_to_google_sheet()
    assert result["success"] and result["sync_mode"] == "apps_script_webhook"
    assert result["tabs_updated"] and len(_HttpContext.posted) == 1
    sent = _HttpContext.posted[0][1]["json"]
    assert all("headers" in item and "rows" in item for item in sent["tabs"].values())
    status = sync.get_live_deliverables_status()
    sheet_status = next(
        d for d in status["deliverables"] if d["id"] == "google_sheets_live"
    )
    assert sheet_status["status"] == "SYNCED" and sheet_status["records_count"] == 1
    assert {d["id"] for d in status["deliverables"]} >= {
        "excel_master",
        "csv_master",
        "sqlite_db",
    }

    _HttpContext.response = _HttpResponse(RuntimeError("webhook error"))
    failed = sync.sync_to_google_sheet()
    assert failed["sync_mode"] == "error" and "RuntimeError" in failed["error"]
    _HttpContext.response = _HttpResponse(status=205)
    unexpected_status = sync.sync_to_google_sheet()
    assert (
        unexpected_status["sync_mode"] == "error"
        and "RuntimeError" in unexpected_status["error"]
    )
    status = sync.get_live_deliverables_status()
    assert (
        next(d for d in status["deliverables"] if d["id"] == "google_sheets_live")[
            "status"
        ]
        == "ERROR"
    )


def test_google_api_sync_create_tabs_partial_and_connection_errors(
    tmp_path, monkeypatch
):
    import metrixa_engine.telemetry.google_sheets_sync as module

    db = Database(tmp_path / "gspread.db")
    _seed(db)
    monkeypatch.setattr(module.settings, "google_sheet_id", "sheet-id")
    monkeypatch.setattr(
        module.settings, "google_service_account_json", '{"type":"service_account"}'
    )
    monkeypatch.setattr(module.settings, "google_service_account_file", "")
    monkeypatch.setattr(module.settings, "google_sheets_webhook_url", "")

    sheet = _Spreadsheet(missing=True)
    _gspread_fake(monkeypatch, _GClient(sheet))
    result = GoogleSheetsSync(db).sync_to_google_sheet()
    assert result["success"] and result["sync_mode"] == "gspread_service_account"
    assert len(sheet.tabs) == 4
    with db.connect() as conn:
        log = conn.execute(
            "SELECT status,details_json FROM deliverables_sync_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert log["status"] == "SUCCESS"
    assert json.loads(log["details_json"])["target_fingerprint"]

    # Partial worksheet creation keeps the sync visibly incomplete.
    sheet = _Spreadsheet(missing=True, fail_add=True)
    _gspread_fake(monkeypatch, _GClient(sheet))
    partial = GoogleSheetsSync(db).sync_to_google_sheet()
    assert partial["success"] is False and partial["sync_mode"] == "partial"
    assert len(partial["tabs_updated"]) == 1

    # API credential failure is returned as an error, without leaking credentials.
    _gspread_fake(monkeypatch, _GClient(sheet))
    monkeypatch.setattr(module.settings, "google_service_account_json", "invalid json")
    error = GoogleSheetsSync(db).sync_to_google_sheet()
    assert error["sync_mode"] == "error" and "invalid json" not in error["error"]


def test_stale_status_invalid_log_and_sync_all_deliverables(tmp_path, monkeypatch):
    import metrixa_engine.telemetry.google_sheets_sync as module

    db = Database(tmp_path / "status.db")
    _seed(db)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    monkeypatch.setattr(module.settings, "export_dir", export_dir)
    monkeypatch.setattr(module.settings, "database_path", db.db_path)
    monkeypatch.setattr(module.settings, "google_sheet_id", "sheet-id")
    monkeypatch.setattr(module.settings, "google_service_account_file", "creds.json")
    monkeypatch.setattr(module.settings, "google_service_account_json", "")
    now = "2026-11-10T10:01:00+00:00"
    details = {
        "sync_mode": "gspread_service_account",
        "tabs_synced": [
            "Qualified_Berlin_Leads",
            "All_Decision_Makers_Contacts",
            "Evidence_And_Audit_Trail",
            "KPI_Methodology_And_Summary",
        ],
        "qualified_leads": 0,
        "target_fingerprint": __import__("hashlib").sha256(b"sheet-id").hexdigest(),
    }
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO deliverables_sync_log (deliverable_type,target_destination,status,records_count,duration_ms,details_json,created_at) VALUES ('google_sheets','https://docs.google.com/spreadsheets/d/sheet-id','SUCCESS',0,1,?,?)",
            (json.dumps(details), now),
        )
    status = GoogleSheetsSync(db).get_live_deliverables_status()
    sheet = next(d for d in status["deliverables"] if d["id"] == "google_sheets_live")
    assert sheet["status"] == "STALE"
    with db.connect() as conn:
        conn.execute(
            "UPDATE deliverables_sync_log SET details_json='bad json' WHERE id=(SELECT MAX(id) FROM deliverables_sync_log)"
        )
    assert (
        next(
            d
            for d in GoogleSheetsSync(db).get_live_deliverables_status()["deliverables"]
            if d["id"] == "google_sheets_live"
        )["status"]
        == "READY_STANDBY"
    )

    # A completed record parses and normalizes naive timestamps; malformed times are stale.
    with db.connect() as conn:
        conn.execute(
            "UPDATE deliverables_sync_log SET details_json=?,created_at=? WHERE id=(SELECT MAX(id) FROM deliverables_sync_log)",
            (json.dumps(details), "2026-11-10T10:01:00"),
        )
        conn.execute("UPDATE companies_golden SET updated_at='2026-11-10T10:02:00'")
    naive_status = GoogleSheetsSync(db).get_live_deliverables_status()
    assert (
        next(
            d for d in naive_status["deliverables"] if d["id"] == "google_sheets_live"
        )["status"]
        == "STALE"
    )
    with db.connect() as conn:
        conn.execute("UPDATE companies_golden SET updated_at='invalid timestamp'")
    invalid_time_status = GoogleSheetsSync(db).get_live_deliverables_status()
    assert (
        next(
            d
            for d in invalid_time_status["deliverables"]
            if d["id"] == "google_sheets_live"
        )["status"]
        == "STALE"
    )

    monkeypatch.setattr(
        GoogleSheetsSync,
        "sync_to_google_sheet",
        lambda self: {"success": False, "sync_mode": "dry_run"},
    )
    from metrixa_engine.telemetry.excel_exporter import ExcelExporter

    monkeypatch.setattr(
        ExcelExporter,
        "export_all",
        lambda self: {
            "xlsx_path": str(export_dir / "x.xlsx"),
            "csv_path": str(export_dir / "x.csv"),
        },
    )
    (export_dir / "x.xlsx").write_bytes(b"x")
    (export_dir / "x.csv").write_bytes(b"x")
    result = GoogleSheetsSync(db).sync_all_deliverables()
    assert result["local_exports_ready"] is True and result["success"] is False
