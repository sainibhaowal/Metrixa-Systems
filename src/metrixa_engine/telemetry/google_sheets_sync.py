"""
Real-Time Google Sheets API Synchronizer & Data Deliverables Engine.
Synchronizes canonical SQLite golden records directly into a 4-tab live Google Sheet:
  Tab 1: Qualified_Berlin_Leads (31 columns, sorted by Metrixa Lead Score)
  Tab 2: All_Decision_Makers_Contacts (Decision-makers with MX deliverability)
  Tab 3: Evidence_And_Audit_Trail (Verbatim statutory Impressum evidence)
  Tab 4: KPI_Methodology_And_Summary (Executive KPI rationale and live telemetry)

Supports direct Google Sheets API v4 via Service Account JSON, OAuth2,
or Webhook push, with automatic fallback diagnostics and dry-run validation.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from metrixa_engine.config import settings
from metrixa_engine.db import Database
from metrixa_engine.models import email_status_label


def _sheet_cell_value(value: Any) -> Any:
    """Keep booleans legible in Google Sheets while preserving numeric values."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return value
    return str(value)


class GoogleSheetsSync:
    """Manages real-time Google Sheets API push and live deliverable exports."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database()

    def extract_all_tabs_data(self) -> Dict[str, Tuple[List[str], List[List[Any]]]]:
        """Extracts the 4 canonical tabs matching the master Excel export schema."""
        with self.db.connect() as conn:
            # Tab 1: Qualified Berlin Leads
            q1 = """
                SELECT
                    c.company_id, c.display_name, c.legal_form, c.commercial_register_id,
                    c.street_address, c.postal_code, c.city, c.district,
                    c.phone_e164, c.website_url, c.canonical_domain,
                    c.general_email, c.company_linkedin_url, c.is_vdiv_member,
                    c.source_count, c.sources_csv, c.metrixa_lead_score, c.lead_tier,
                    k.founding_year, k.exact_units_managed, k.units_evidence_quote,
                    k.estimated_units_tier, k.employee_count_est, k.reference_buildings_count,
                    k.manages_weg, k.manages_miet, k.manages_gewerbe, k.manages_sev,
                    k.has_customer_portal, k.detected_erp_proptech,
                    k.incumbent_metering_signal, k.digital_maturity_score,
                    k.qualification_reasoning, k.llm_provider_used
                FROM companies_golden c
                LEFT JOIN kpi_extractions k ON k.company_id = c.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                ORDER BY c.metrixa_lead_score DESC, c.is_vdiv_member DESC, c.source_count DESC, c.display_name ASC
            """
            master_rows = conn.execute(q1).fetchall()

            h1 = [
                "Company ID",
                "Company Name",
                "Legal Form",
                "Register ID (HRB)",
                "Street Address",
                "PLZ (Postal Code)",
                "City",
                "Berlin District",
                "Phone (E.164)",
                "Website URL",
                "Canonical Domain",
                "General Email",
                "Company LinkedIn",
                "VDIV Member",
                "Source Count",
                "Ingestion Sources",
                "Metrixa Lead Score (0-100)",
                "Lead Tier",
                "Founding Year",
                "Exact Units Managed",
                "Units Evidence Quote",
                "Estimated Units Tier",
                "Employee Count Est",
                "Reference Buildings",
                "WEG Management",
                "Rental Management",
                "Commercial Management",
                "SEV Management",
                "Customer Portal",
                "Detected PropTech ERP",
                "Incumbent Metering",
                "Digital Maturity (1-5)",
                "Qualification Reasoning",
                "LLM Provider Used",
            ]
            d1: List[List[Any]] = []
            for r in master_rows:
                row_vals = [_sheet_cell_value(val) for val in r]
                d1.append(row_vals)

            # Tab 2: Decision Makers
            q2 = """
                SELECT
                    c.display_name as company_name, c.lead_tier, c.metrixa_lead_score,
                    d.full_name, d.role, d.personal_email, d.email_status,
                    d.mx_valid, d.mx_host, d.direct_phone, d.linkedin_url,
                    d.source_url, d.evidence_quote
                FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                ORDER BY c.metrixa_lead_score DESC, d.is_primary_contact DESC, d.contact_id ASC
            """
            dm_rows = conn.execute(q2).fetchall()
            h2 = [
                "Company Name",
                "Lead Tier",
                "Metrixa Score",
                "Decision Maker Full Name",
                "Role / Title",
                "Email Address / Candidate",
                "Email Evidence Status",
                "DNS MX Valid",
                "DNS MX Server Host",
                "Direct Phone",
                "LinkedIn URL",
                "Source Page URL",
                "Verbatim Impressum / Team Evidence Quote",
            ]
            d2: List[List[Any]] = []
            for r in dm_rows:
                d2.append(
                    [
                        r["company_name"] or "",
                        r["lead_tier"] or "",
                        r["metrixa_lead_score"] or 0,
                        r["full_name"] or "",
                        r["role"] or "",
                        r["personal_email"] or "",
                        email_status_label(r["email_status"]),
                        "Yes" if r["mx_valid"] else "No",
                        r["mx_host"] or "",
                        r["direct_phone"] or "",
                        r["linkedin_url"] or "",
                        r["source_url"] or "",
                        r["evidence_quote"] or "",
                    ]
                )

            # Tab 3: Evidence and Audit Trail
            q3 = """
                SELECT
                    c.display_name, c.lead_tier, c.metrixa_lead_score,
                    p.page_type, p.url, p.http_status, p.detected_erp_csv,
                    p.detected_metering_csv, p.has_portal_link,
                    k.units_evidence_quote, k.llm_provider_used
                FROM crawled_pages p
                JOIN companies_golden c ON c.company_id = p.company_id
                LEFT JOIN kpi_extractions k ON k.company_id = c.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                ORDER BY c.metrixa_lead_score DESC, c.company_id ASC
            """
            crawl_rows = conn.execute(q3).fetchall()
            raw_total = conn.execute("SELECT COUNT(*) FROM raw_listings").fetchone()[0]
            source_counts = conn.execute(
                "SELECT source_name, COUNT(*) AS total FROM raw_listings GROUP BY source_name ORDER BY source_name"
            ).fetchall()
            qualified_total = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
            ).fetchone()[0]
            tier_counts = {
                row["tier"]: row["total"]
                for row in conn.execute(
                    """
                    SELECT CASE
                        WHEN lead_tier LIKE 'Tier A%' THEN 'Tier A'
                        WHEN lead_tier LIKE 'Tier B%' THEN 'Tier B'
                        ELSE 'Tier C'
                    END AS tier, COUNT(*) AS total
                    FROM companies_golden
                    WHERE pipeline_stage != 'DISQUALIFIED'
                    GROUP BY tier
                    """
                ).fetchall()
            }
            decision_maker_total = conn.execute(
                """
                SELECT COUNT(*) FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                """
            ).fetchone()[0]
            public_email_total = conn.execute(
                """
                SELECT COUNT(*) FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND d.email_status IN ('PUBLIC_LISTED', 'PUBLIC_DIRECT_VERIFIED')
                """
            ).fetchone()[0]
            email_candidate_total = conn.execute(
                """
                SELECT COUNT(*) FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND d.email_status IN ('PATTERN_CANDIDATE_MX', 'PATTERN_MX_VERIFIED')
                """
            ).fetchone()[0]
            erp_total = conn.execute(
                """
                SELECT COUNT(*) FROM kpi_extractions k
                JOIN companies_golden c ON c.company_id = k.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND COALESCE(TRIM(k.detected_erp_proptech), '') != ''
                """
            ).fetchone()[0]
            quote_total = conn.execute(
                """
                SELECT COUNT(*) FROM kpi_extractions k
                JOIN companies_golden c ON c.company_id = k.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND COALESCE(TRIM(k.units_evidence_quote), '') != ''
                """
            ).fetchone()[0]
            h3 = [
                "Company Name",
                "Lead Tier",
                "Metrixa Score",
                "Crawled Page Type",
                "Crawled URL",
                "HTTP Status",
                "DOM Detected ERP / PropTech",
                "DOM Detected Metering Incumbent",
                "Customer Portal Detected",
                "Verbatim Units Evidence Quote",
                "Extraction Engine Used",
            ]
            d3: List[List[Any]] = []
            for r in crawl_rows:
                d3.append(
                    [
                        r["display_name"] or "",
                        r["lead_tier"] or "",
                        r["metrixa_lead_score"] or 0,
                        r["page_type"] or "",
                        r["url"] or "",
                        r["http_status"] or 200,
                        r["detected_erp_csv"] or "",
                        r["detected_metering_csv"] or "",
                        "Yes" if r["has_portal_link"] else "No",
                        r["units_evidence_quote"] or "",
                        r["llm_provider_used"] or "deterministic_german_nlp",
                    ]
                )

            # Tab 4: KPI Methodology & Summary Telemetry
            h4 = [
                "Metric / Parameter",
                "Value",
                "Business Rationale for Metrixa Systems",
            ]
            source_summary = (
                ", ".join(
                    f"{row['source_name']} ({row['total']:,})" for row in source_counts
                )
                or "No source records yet"
            )
            d4 = [
                [
                    "Total Raw Directory Records Harvested",
                    f"{raw_total:,}",
                    f"Current raw-listing records by source: {source_summary}",
                ],
                [
                    "Canonical Deduplicated Berlin Leads",
                    f"{qualified_total:,}",
                    "Current eligible company records in the canonical database.",
                ],
                [
                    "Tier A: High Priority Institutional Leads",
                    f"{tier_counts.get('Tier A', 0):,}",
                    "Current eligible companies assigned Tier A.",
                ],
                [
                    "Tier B: Qualified Mid-Market Leads",
                    f"{tier_counts.get('Tier B', 0):,}",
                    "Current eligible companies assigned Tier B.",
                ],
                [
                    "Tier C: Long-Tail Property Managers",
                    f"{tier_counts.get('Tier C', 0):,}",
                    "Current eligible companies assigned Tier C.",
                ],
                [
                    "Named Executive Decision Makers",
                    f"{decision_maker_total:,}",
                    "Current decision-maker records linked to eligible companies.",
                ],
                [
                    "Publicly listed decision-maker email addresses (mailbox not tested)",
                    f"{public_email_total:,}",
                    "Addresses found in source content; mailbox existence and deliverability are not checked.",
                ],
                [
                    "Inferred email pattern candidates (domain MX only)",
                    f"{email_candidate_total:,}",
                    "Candidate patterns only; an MX record does not verify that an individual mailbox exists.",
                ],
                [
                    "DOM PropTech ERP Deployments Detected",
                    f"{erp_total:,}",
                    "Current KPI records with a detected ERP or PropTech value.",
                ],
                [
                    "Crawled Web Subpages",
                    f"{len(crawl_rows):,}",
                    "Current crawled evidence pages linked to eligible companies.",
                ],
                [
                    "KPI Extractions with Stored Unit Evidence",
                    f"{quote_total:,}",
                    "Current KPI records that include a non-empty units evidence quote.",
                ],
            ]

        return {
            "Qualified_Berlin_Leads": (h1, d1),
            "All_Decision_Makers_Contacts": (h2, d2),
            "Evidence_And_Audit_Trail": (h3, d3),
            "KPI_Methodology_And_Summary": (h4, d4),
        }

    def test_connection(
        self,
        sheet_id: Optional[str] = None,
        service_account_file: Optional[str] = None,
        service_account_json: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tests Google Sheets API authentication, permissions, and spreadsheet reachability."""
        start_time = time.time()
        target_sheet_id = (sheet_id or settings.google_sheet_id).strip()
        creds_file = (
            service_account_file or settings.google_service_account_file
        ).strip()
        creds_json = (
            service_account_json or settings.google_service_account_json
        ).strip()

        tabs_data = self.extract_all_tabs_data()
        total_prepared_rows = sum(len(rows) for _, (_, rows) in tabs_data.items())

        # If live credentials are provided, test actual Google Sheets API connectivity
        if creds_file or creds_json:
            try:
                import gspread

                if creds_json:
                    creds_dict = json.loads(creds_json)
                    gc = gspread.service_account_from_dict(creds_dict)
                else:
                    gc = gspread.service_account(filename=creds_file)

                if target_sheet_id:
                    sh = gc.open_by_key(target_sheet_id)
                    title = sh.title
                    worksheets = [ws.title for ws in sh.worksheets()]
                    latency_ms = int((time.time() - start_time) * 1000)
                    return {
                        "status": "CONNECTED",
                        "auth_mode": "service_account",
                        "latency_ms": latency_ms,
                        "spreadsheet_id": target_sheet_id,
                        "spreadsheet_title": title,
                        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{target_sheet_id}",
                        "existing_worksheets": worksheets,
                        "prepared_rows_count": total_prepared_rows,
                        "message": f"Authenticated and opened '{title}'. Run a sync to verify write access.",
                    }
                else:
                    latency_ms = int((time.time() - start_time) * 1000)
                    return {
                        "status": "AUTHENTICATED",
                        "auth_mode": "service_account",
                        "latency_ms": latency_ms,
                        "spreadsheet_id": "",
                        "prepared_rows_count": total_prepared_rows,
                        "message": "Service account authenticated successfully. Specify target Spreadsheet ID to execute live sync.",
                    }
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                return {
                    "status": "ERROR",
                    "auth_mode": "service_account",
                    "latency_ms": latency_ms,
                    "error": str(e),
                    "message": f"Authentication test failed: {e}",
                }

        # Otherwise, report dry-run readiness with full schema validation
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "READY_STANDBY",
            "auth_mode": "dry_run_ready",
            "latency_ms": latency_ms,
            "spreadsheet_id": target_sheet_id,
            "prepared_rows_count": total_prepared_rows,
            "tabs_ready": list(tabs_data.keys()),
            "message": (
                f"Prepared {len(tabs_data['Qualified_Berlin_Leads'][1]):,} qualified leads "
                f"across {len(tabs_data)} tabs locally. Configure a spreadsheet ID and "
                "service-account credentials or a webhook to enable cloud sync."
            ),
        }

    def sync_to_google_sheet(
        self,
        sheet_id: Optional[str] = None,
        service_account_file: Optional[str] = None,
        service_account_json: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pushes canonical leads to Google Sheets via API or Webhook, with local fallback."""
        start_time = time.time()
        target_sheet_id = (sheet_id or settings.google_sheet_id).strip()
        creds_file = (
            service_account_file or settings.google_service_account_file
        ).strip()
        creds_json = (
            service_account_json or settings.google_service_account_json
        ).strip()
        target_webhook = (webhook_url or settings.google_sheets_webhook_url).strip()

        tabs_data = self.extract_all_tabs_data()
        tabs_synced: List[str] = []
        total_rows_synced = 0
        sync_mode = "dry_run"
        sync_error: Optional[str] = None
        final_url = ""
        qualified_leads = len(tabs_data["Qualified_Berlin_Leads"][1])
        prepared_rows = sum(len(rows) for _, rows in tabs_data.values())

        # Strategy 1: Direct Google Sheets API with service-account credentials.
        if (creds_file or creds_json) and target_sheet_id:
            try:
                import gspread

                if creds_json:
                    gc = gspread.service_account_from_dict(json.loads(creds_json))
                else:
                    gc = gspread.service_account(filename=creds_file)

                spreadsheet = gc.open_by_key(target_sheet_id)
                final_url = f"https://docs.google.com/spreadsheets/d/{target_sheet_id}"
                for tab_name, (headers, rows) in tabs_data.items():
                    try:
                        worksheet = spreadsheet.worksheet(tab_name)
                    except gspread.WorksheetNotFound:
                        worksheet = spreadsheet.add_worksheet(
                            title=tab_name,
                            rows=max(len(rows) + 1, 100),
                            cols=len(headers),
                        )
                    worksheet.clear()
                    worksheet.update([headers] + rows, value_input_option="RAW")
                    try:
                        worksheet.freeze(rows=1)
                    except Exception:
                        pass
                    tabs_synced.append(tab_name)
                    total_rows_synced += len(rows)
                sync_mode = "gspread_service_account"
            except Exception as exc:
                sync_error = f"Google Sheets API sync failed ({type(exc).__name__})."

        # Strategy 2: A configured webhook receives the actual tab data, not only row counts.
        if not tabs_synced and target_webhook:
            try:
                import httpx

                payload = {
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                    "total_leads": qualified_leads,
                    "tabs": {
                        name: {"headers": headers, "rows": rows, "row_count": len(rows)}
                        for name, (headers, rows) in tabs_data.items()
                    },
                }
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(target_webhook, json=payload)
                    response.raise_for_status()
                if response.status_code not in (200, 201, 202, 204):
                    raise RuntimeError(f"Webhook returned HTTP {response.status_code}")
                sync_mode = "apps_script_webhook"
                final_url = "configured_webhook"
                tabs_synced = list(tabs_data)
                total_rows_synced = prepared_rows
                sync_error = None
            except Exception as exc:
                sync_error = (
                    f"Google Sheets webhook sync failed ({type(exc).__name__})."
                )

        if tabs_synced and len(tabs_synced) != len(tabs_data):
            sync_mode = "partial"
        elif not tabs_synced and sync_error:
            sync_mode = "error"

        success = len(tabs_synced) == len(tabs_data) and sync_mode in {
            "gspread_service_account",
            "apps_script_webhook",
        }
        duration_ms = int((time.time() - start_time) * 1000)
        log_status = (
            "SUCCESS"
            if success
            else "PARTIAL" if tabs_synced else "ERROR" if sync_error else "DRY_RUN"
        )
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO deliverables_sync_log
                    (deliverable_type, target_destination, status, records_count, duration_ms, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "google_sheets",
                    final_url,
                    log_status,
                    total_rows_synced,
                    duration_ms,
                    json.dumps(
                        {
                            "sync_mode": sync_mode,
                            "tabs_synced": tabs_synced,
                            "qualified_leads": qualified_leads if success else 0,
                            "prepared_leads": qualified_leads,
                            "prepared_rows": prepared_rows,
                            "error": sync_error,
                            "target_fingerprint": (
                                hashlib.sha256(
                                    (
                                        target_sheet_id
                                        if sync_mode == "gspread_service_account"
                                        else target_webhook
                                    ).encode()
                                ).hexdigest()
                                if success
                                else None
                            ),
                        }
                    ),
                ),
            )

        message = (
            f"Synchronized {total_rows_synced:,} records across {len(tabs_synced)} tabs."
            if success
            else f"Prepared {prepared_rows:,} local rows; no complete cloud sync was performed."
        )
        return {
            "success": success,
            "sync_mode": sync_mode,
            "spreadsheet_url": (
                final_url if sync_mode == "gspread_service_account" else None
            ),
            "spreadsheet_id": target_sheet_id or None,
            "tabs_updated": tabs_synced,
            "total_rows_synced": total_rows_synced,
            "qualified_leads_synced": qualified_leads if success else 0,
            "qualified_leads_prepared": qualified_leads,
            "prepared_rows_count": prepared_rows,
            "error": sync_error,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"{message} ({duration_ms}ms)",
        }

    def get_live_deliverables_status(self) -> Dict[str, Any]:
        """Audits all real-time data deliverables across disk, database, and cloud destinations."""
        deliverables = []
        with self.db.connect() as conn:
            canonical_count = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
            ).fetchone()[0]
            latest_company_update = conn.execute(
                "SELECT MAX(updated_at) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
            ).fetchone()[0]
            raw_count = conn.execute("SELECT COUNT(*) FROM raw_listings").fetchone()[0]
            latest_sync = conn.execute(
                """
                SELECT status, target_destination, records_count, details_json, created_at
                FROM deliverables_sync_log
                WHERE deliverable_type = 'google_sheets'
                ORDER BY id DESC LIMIT 1
                """
            ).fetchone()

        sync_details: Dict[str, Any] = {}
        if latest_sync and latest_sync["details_json"]:
            try:
                sync_details = json.loads(latest_sync["details_json"])
            except (TypeError, json.JSONDecodeError):
                sync_details = {}
        target_sheet_id = settings.google_sheet_id.strip()
        target_webhook = settings.google_sheets_webhook_url.strip()
        has_sheet_credentials = bool(
            settings.google_service_account_file or settings.google_service_account_json
        )
        configured = bool(target_webhook or (target_sheet_id and has_sheet_credentials))
        sync_mode = sync_details.get("sync_mode")
        expected_tabs = {
            "Qualified_Berlin_Leads",
            "All_Decision_Makers_Contacts",
            "Evidence_And_Audit_Trail",
            "KPI_Methodology_And_Summary",
        }
        logged_tabs = set(sync_details.get("tabs_synced", []))
        expected_destination = (
            f"https://docs.google.com/spreadsheets/d/{target_sheet_id}"
            if sync_mode == "gspread_service_account"
            else "configured_webhook"
        )
        target_identity = (
            target_sheet_id
            if sync_mode == "gspread_service_account"
            else target_webhook if sync_mode == "apps_script_webhook" else ""
        )
        expected_fingerprint = hashlib.sha256(target_identity.encode()).hexdigest()
        complete_sync_recorded = bool(
            configured
            and latest_sync
            and latest_sync["status"] == "SUCCESS"
            and sync_mode in ("gspread_service_account", "apps_script_webhook")
            and logged_tabs == expected_tabs
            and latest_sync["target_destination"] == expected_destination
            and sync_details.get("target_fingerprint") == expected_fingerprint
        )
        synced_count = int(sync_details.get("qualified_leads", 0))
        stale = complete_sync_recorded and synced_count != canonical_count
        if complete_sync_recorded and latest_company_update and latest_sync:
            try:
                company_update = datetime.fromisoformat(
                    str(latest_company_update).replace("Z", "+00:00")
                )
                sync_time = datetime.fromisoformat(
                    str(latest_sync["created_at"]).replace("Z", "+00:00")
                )
                if company_update.tzinfo is None:
                    company_update = company_update.replace(tzinfo=timezone.utc)
                if sync_time.tzinfo is None:
                    sync_time = sync_time.replace(tzinfo=timezone.utc)
                stale = stale or company_update > sync_time
            except ValueError:
                stale = True
        synced = complete_sync_recorded and not stale
        if synced:
            sheet_status = "SYNCED"
        elif stale:
            sheet_status = "STALE"
        elif not configured:
            sheet_status = "NOT_CONFIGURED"
            synced_count = 0
        elif latest_sync and latest_sync["status"] in ("ERROR", "PARTIAL"):
            sheet_status = "ERROR"
            synced_count = 0
        else:
            sheet_status = "READY_STANDBY"
            synced_count = 0

        # 1. Excel Master Workbook (.xlsx)
        xlsx_file = settings.export_dir / "metrixa_berlin_hausverwaltungen.xlsx"
        if xlsx_file.exists():
            stat = xlsx_file.stat()
            deliverables.append(
                {
                    "id": "excel_master",
                    "name": "metrixa_berlin_hausverwaltungen.xlsx",
                    "title": "4-Tab Master Excel Deliverable",
                    "format": "XLSX",
                    "status": "READY",
                    "records_count": canonical_count,
                    "size_bytes": stat.st_size,
                    "size_formatted": f"{stat.st_size / 1024:.1f} KB",
                    "updated_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "download_url": "/api/artifacts/download/excel",
                    "cloud_sync_ready": False,
                }
            )

        # 2. Master Clean CSV
        csv_file = settings.export_dir / "metrixa_berlin_leads_master.csv"
        if csv_file.exists():
            stat = csv_file.stat()
            deliverables.append(
                {
                    "id": "csv_master",
                    "name": "metrixa_berlin_leads_master.csv",
                    "title": "Standardized Master Clean CSV",
                    "format": "CSV",
                    "status": "READY",
                    "records_count": canonical_count,
                    "size_bytes": stat.st_size,
                    "size_formatted": f"{stat.st_size / 1024:.1f} KB",
                    "updated_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "download_url": "/api/artifacts/download/csv",
                    "cloud_sync_ready": False,
                }
            )

        # 3. Canonical SQLite WAL Database
        db_file = settings.database_path
        if db_file.exists():
            stat = db_file.stat()
            deliverables.append(
                {
                    "id": "sqlite_db",
                    "name": "metrixa_leads.db",
                    "title": "Live Relational SQLite Ledger (WAL)",
                    "format": "SQLITE",
                    "status": "READY",
                    "records_count": canonical_count,
                    "size_bytes": stat.st_size,
                    "size_formatted": f"{stat.st_size / (1024 * 1024):.2f} MB",
                    "updated_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "download_url": "/api/artifacts/download/db",
                    "cloud_sync_ready": False,
                }
            )

        # 4. Existing PDF file. Presence on disk does not mean its claims were validated.
        pdf_file = (
            settings.project_root
            / "docs"
            / "Case Study"
            / "Case_Study_Metrixa_Systems.pdf"
        )
        if pdf_file.exists():
            stat = pdf_file.stat()
            deliverables.append(
                {
                    "id": "research_pdf",
                    "name": "Case_Study_Metrixa_Systems.pdf",
                    "title": "Case Study PDF (review required before submission)",
                    "format": "PDF",
                    "status": "REVIEW_REQUIRED",
                    "quality_note": "Historical metrics and accuracy claims have not been validated against the current local dataset.",
                    "records_count": None,
                    "size_bytes": stat.st_size,
                    "size_formatted": f"{stat.st_size / 1024:.1f} KB",
                    "updated_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "download_url": "/api/artifacts/download/pdf",
                    "cloud_sync_ready": False,
                }
            )

        # 5. Google Sheets is online only after a complete, recorded cloud sync.
        sheet_url = (
            f"https://docs.google.com/spreadsheets/d/{target_sheet_id}"
            if target_sheet_id and has_sheet_credentials
            else None
        )
        deliverables.append(
            {
                "id": "google_sheets_live",
                "name": (
                    f"Google Sheets ({target_sheet_id})"
                    if target_sheet_id
                    else "Google Sheets"
                ),
                "title": "Google Sheets Cloud Mirror (4 Tabs)",
                "format": "GOOGLE_SHEET",
                "status": sheet_status,
                "records_count": synced_count,
                "prepared_records_count": canonical_count,
                "size_bytes": 0,
                "size_formatted": (
                    f"{synced_count:,} synced leads" if synced else "Not synced"
                ),
                "updated_at": (
                    latest_sync["created_at"] if synced and latest_sync else None
                ),
                "last_sync_mode": sync_mode,
                "download_url": sheet_url,
                "cloud_sync_ready": configured,
            }
        )

        return {
            "deliverables_count": len(deliverables),
            "canonical_leads": canonical_count,
            "raw_listings": raw_count,
            "deliverables": deliverables,
            "last_audited_at": datetime.now(timezone.utc).isoformat(),
        }

    def sync_all_deliverables(self) -> Dict[str, Any]:
        """Refreshes Excel, CSV, Google Sheets, and updates deliverables state."""
        start_time = time.time()
        from metrixa_engine.telemetry.excel_exporter import ExcelExporter

        # 1. Regenerate Excel and CSV
        exporter = ExcelExporter(self.db)
        export_res = exporter.export_all()

        # 2. Push to Google Sheets
        sheets_res = self.sync_to_google_sheet()

        # 3. Compile live status
        status_res = self.get_live_deliverables_status()

        duration_ms = int((time.time() - start_time) * 1000)
        local_exports_ready = (
            Path(export_res["xlsx_path"]).is_file()
            and Path(export_res["csv_path"]).is_file()
        )
        return {
            "success": local_exports_ready and sheets_res["success"],
            "local_exports_ready": local_exports_ready,
            "cloud_sync_success": sheets_res["success"],
            "duration_ms": duration_ms,
            "excel": export_res,
            "google_sheets": sheets_res,
            "live_status": status_res,
            "message": (
                f"Local exports are ready; Google Sheets sync {'completed' if sheets_res['success'] else 'is not connected'} "
                f"({duration_ms}ms)."
            ),
        }
