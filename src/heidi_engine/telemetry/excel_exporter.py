"""
Stage 6 Multi-Tab Excel (.xlsx) & CSV Exporter for Metrixa Systems.
Builds a 4-Tab Workbook ready for direct upload to Google Sheets or Excel attachment:
  Tab 1: Qualified_Berlin_Leads (31 KPI & Contact columns, sorted by Metrixa Lead Score)
  Tab 2: All_Decision_Makers_Contacts (Bonus Task deep-dive with MX & Evidence verification)
  Tab 3: Evidence_And_Audit_Trail (Anti-Hallucination URLs, HTTP codes & verbatim quotes)
  Tab 4: KPI_Methodology_And_Summary (Executive KPI rationale, scoring formula & live stats)
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from heidi_engine.config import settings
from heidi_engine.db import Database

HEADER_FILL = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Calibri", size=10, color="111111")
LINK_FONT = Font(name="Calibri", size=10, color="0563C1", underline="single")

TIER_A_FILL = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")
TIER_B_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
TIER_C_FILL = PatternFill(start_color="F3F3F3", end_color="F3F3F3", fill_type="solid")

THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)


class ExcelExporter:
    """Exports the SQLite Golden Dataset into a styled 4-Tab Excel workbook and CSV."""

    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _style_worksheet(ws: Any, col_widths: Dict[int, int]) -> None:
        ws.freeze_panes = "A2"
        if ws.max_row >= 1 and ws.max_column >= 1:
            last_col = get_column_letter(ws.max_column)
            ws.auto_filter.ref = f"A1:{last_col}{ws.max_row}"

        for col_idx in range(1, ws.max_column + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(
                horizontal="center", vertical="center", wrap_text=True
            )
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = col_widths.get(col_idx, 20)

        ws.row_dimensions[1].height = 28

    def export_all(
        self,
        xlsx_path: Optional[Path] = None,
        csv_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        settings.ensure_dirs()
        out_xlsx = xlsx_path or (
            settings.export_dir / "metrixa_berlin_hausverwaltungen.xlsx"
        )
        out_csv = csv_path or (settings.export_dir / "metrixa_berlin_leads_master.csv")

        with self.db.connect() as conn:
            master_rows = conn.execute(
                """
                SELECT
                    c.company_id, c.display_name, c.legal_form, c.commercial_register_id,
                    c.street_address, c.postal_code, c.city, c.district,
                    c.phone_e164, c.website_url, c.canonical_domain,
                    c.general_email, c.company_linkedin_url, c.is_vdiv_member,
                    c.source_count, c.sources_csv, c.heidi_lead_score, c.lead_tier,
                    k.founding_year, k.exact_units_managed, k.units_evidence_quote,
                    k.estimated_units_tier, k.employee_count_est, k.reference_buildings_count,
                    k.manages_weg, k.manages_miet, k.manages_gewerbe, k.manages_sev,
                    k.has_customer_portal, k.detected_erp_proptech,
                    k.incumbent_metering_signal, k.digital_maturity_score,
                    k.qualification_reasoning, k.llm_provider_used
                FROM companies_golden c
                LEFT JOIN kpi_extractions k ON k.company_id = c.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                ORDER BY c.heidi_lead_score DESC, c.is_vdiv_member DESC, c.source_count DESC, c.display_name ASC
                """
            ).fetchall()

            dm_rows = conn.execute(
                """
                SELECT
                    d.*, c.display_name as company_name, c.lead_tier, c.heidi_lead_score, c.website_url
                FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                ORDER BY c.heidi_lead_score DESC, d.is_primary_contact DESC, d.contact_id ASC
                """
            ).fetchall()

            audit_rows = conn.execute(
                """
                SELECT
                    c.company_id, c.display_name, c.heidi_lead_score, c.lead_tier,
                    p.page_type, p.url, p.http_status, p.detected_erp_csv,
                    p.detected_metering_csv, p.has_portal_link,
                    k.units_evidence_quote, k.llm_provider_used
                FROM crawled_pages p
                JOIN companies_golden c ON c.company_id = p.company_id
                LEFT JOIN kpi_extractions k ON k.company_id = c.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                ORDER BY c.heidi_lead_score DESC, c.company_id ASC
                """
            ).fetchall()

        # Index primary decision maker per company_id
        primary_dm_by_comp: Dict[int, Dict[str, Any]] = {}
        for dm in dm_rows:
            cid = dm["company_id"]
            if cid not in primary_dm_by_comp:
                primary_dm_by_comp[cid] = dict(dm)

        wb = openpyxl.Workbook()

        # ====================================================================
        # TAB 1: Qualified_Berlin_Leads (31 Columns A -> AE)
        # ====================================================================
        ws1 = wb.active
        ws1.title = "Qualified_Berlin_Leads"

        headers_tab1 = [
            "Lead ID",
            "Lead Tier",
            "Metrixa Lead Score (0-100)",
            "Company Name",
            "Legal Form",
            "Berlin District (Bezirk)",
            "Postal Code (PLZ)",
            "Street Address",
            "Website URL",
            "Reported Units (Wohneinheiten)",
            "Estimated Portfolio Size Tier",
            "Est. Team Size (Employees)",
            "Manages WEG (Condos)",
            "Manages Mietverwaltung (Rentals)",
            "Manages Commercial (Gewerbe)",
            "Has Online Customer Portal",
            "Detected ERP / PropTech Stack",
            "Incumbent Metering Signal",
            "Digital Maturity Score (1-5)",
            "VDIV Certified Member",
            "Commercial Register (HRB)",
            "Founding Year",
            "Primary Decision Maker Name",
            "Decision Maker Role",
            "Personal / Direct Email (Bonus)",
            "Email Verification Status",
            "Decision Maker / Company LinkedIn",
            "General Company Email",
            "Company Phone",
            "AI Qualification Summary",
            "Data Sources Matched",
        ]
        ws1.append(headers_tab1)

        csv_rows_out: List[List[Any]] = [headers_tab1]

        for idx, r in enumerate(master_rows, start=1):
            cid = r["company_id"]
            lead_id = f"METRIXA-BER-{idx:04d}"
            pdm = primary_dm_by_comp.get(cid, {})

            li_url = pdm.get("linkedin_url") or r["company_linkedin_url"] or ""
            pers_email = pdm.get("personal_email") or ""
            email_status = pdm.get("email_status") or (
                "GENERIC_ONLY" if r["general_email"] else "NONE"
            )

            row_vals = [
                lead_id,
                r["lead_tier"],
                r["heidi_lead_score"],
                r["display_name"],
                r["legal_form"] or "N/A",
                r["district"] or "Berlin",
                r["postal_code"] or "",
                r["street_address"] or "",
                r["website_url"] or "",
                r["exact_units_managed"] if r["exact_units_managed"] else "",
                r["estimated_units_tier"] or "<250",
                r["employee_count_est"] if r["employee_count_est"] else "",
                "Yes" if r["manages_weg"] else "No",
                "Yes" if r["manages_miet"] else "No",
                "Yes" if r["manages_gewerbe"] else "No",
                "Yes" if r["has_customer_portal"] else "No",
                r["detected_erp_proptech"] or "",
                r["incumbent_metering_signal"] or "",
                r["digital_maturity_score"] or 1,
                "Yes" if r["is_vdiv_member"] else "No",
                r["commercial_register_id"] or "",
                r["founding_year"] if r["founding_year"] else "",
                pdm.get("full_name") or "",
                pdm.get("role") or "",
                pers_email,
                email_status,
                li_url,
                r["general_email"] or "",
                r["phone_e164"] or "",
                r["qualification_reasoning"] or "",
                r["sources_csv"] or "",
            ]
            ws1.append(row_vals)
            csv_rows_out.append(row_vals)

            row_num = idx + 1
            tier_str = str(r["lead_tier"] or "")
            tier_fill = (
                TIER_A_FILL
                if "Tier A" in tier_str
                else (TIER_B_FILL if "Tier B" in tier_str else TIER_C_FILL)
            )

            for c_i in range(1, len(row_vals) + 1):
                cell = ws1.cell(row=row_num, column=c_i)
                cell.font = BODY_FONT
                cell.border = THIN_BORDER
                if c_i in (2, 3):
                    cell.fill = tier_fill
                if c_i in (9, 27) and cell.value and str(cell.value).startswith("http"):
                    cell.hyperlink = str(cell.value)
                    cell.font = LINK_FONT

        col_widths_tab1 = {
            1: 16,
            2: 26,
            3: 14,
            4: 38,
            5: 14,
            6: 24,
            7: 12,
            8: 26,
            9: 30,
            10: 16,
            11: 18,
            12: 14,
            13: 14,
            14: 16,
            15: 16,
            16: 16,
            17: 24,
            18: 18,
            19: 14,
            20: 14,
            21: 16,
            22: 12,
            23: 24,
            24: 18,
            25: 28,
            26: 24,
            27: 30,
            28: 26,
            29: 18,
            30: 48,
            31: 24,
        }
        self._style_worksheet(ws1, col_widths_tab1)

        # ====================================================================
        # TAB 2: All_Decision_Makers_Contacts (Bonus Task Deep-Dive)
        # ====================================================================
        ws2 = wb.create_sheet(title="All_Decision_Makers_Contacts")
        headers_tab2 = [
            "Company Name",
            "Lead Tier",
            "Heidi Score",
            "Decision Maker Full Name",
            "Role / Title",
            "Personal / Direct Email",
            "Email Verification Status",
            "DNS MX Valid",
            "DNS MX Server Host",
            "Direct Phone",
            "LinkedIn URL",
            "Source Page URL",
            "Verbatim Impressum / Team Evidence Quote",
        ]
        ws2.append(headers_tab2)

        for r_idx, dm in enumerate(dm_rows, start=2):
            ws2.append(
                [
                    dm["company_name"],
                    dm["lead_tier"],
                    dm["heidi_lead_score"],
                    dm["full_name"],
                    dm["role"],
                    dm["personal_email"] or "",
                    dm["email_status"],
                    "Yes" if dm["mx_valid"] else "No",
                    dm["mx_host"] or "",
                    dm["direct_phone"] or "",
                    dm["linkedin_url"] or "",
                    dm["source_url"] or "",
                    dm["evidence_quote"] or "",
                ]
            )
            for c_i in range(1, len(headers_tab2) + 1):
                cell = ws2.cell(row=r_idx, column=c_i)
                cell.font = BODY_FONT
                cell.border = THIN_BORDER

        self._style_worksheet(
            ws2,
            {
                1: 36,
                2: 24,
                3: 12,
                4: 24,
                5: 18,
                6: 28,
                7: 24,
                8: 12,
                9: 24,
                10: 18,
                11: 30,
                12: 32,
                13: 50,
            },
        )

        # ====================================================================
        # TAB 3: Evidence_And_Audit_Trail (Anti-Hallucination Proof)
        # ====================================================================
        ws3 = wb.create_sheet(title="Evidence_And_Audit_Trail")
        headers_tab3 = [
            "Company Name",
            "Lead Tier",
            "Heidi Score",
            "Crawled Page Type",
            "Crawled URL",
            "HTTP Status",
            "DOM Detected ERP / PropTech",
            "DOM Detected Metering Incumbent",
            "Customer Portal Detected",
            "Verbatim Units Evidence Quote",
            "Extraction Engine Used",
        ]
        ws3.append(headers_tab3)

        for r_idx, ar in enumerate(audit_rows, start=2):
            ws3.append(
                [
                    ar["display_name"],
                    ar["lead_tier"],
                    ar["heidi_lead_score"],
                    ar["page_type"],
                    ar["url"],
                    ar["http_status"],
                    ar["detected_erp_csv"] or "",
                    ar["detected_metering_csv"] or "",
                    "Yes" if ar["has_portal_link"] else "No",
                    ar["units_evidence_quote"] or "",
                    ar["llm_provider_used"] or "deterministic_german_nlp",
                ]
            )
            for c_i in range(1, len(headers_tab3) + 1):
                cell = ws3.cell(row=r_idx, column=c_i)
                cell.font = BODY_FONT
                cell.border = THIN_BORDER

        self._style_worksheet(
            ws3,
            {
                1: 34,
                2: 24,
                3: 12,
                4: 16,
                5: 38,
                6: 12,
                7: 24,
                8: 24,
                9: 18,
                10: 42,
                11: 24,
            },
        )

        # ====================================================================
        # TAB 4: KPI_Methodology_And_Summary (Executive Overview)
        # ====================================================================
        ws4 = wb.create_sheet(title="KPI_Methodology_And_Summary")
        tel = self.db.get_pipeline_telemetry()

        ws4.append(
            [
                "Section / Metric",
                "Value / Specification",
                "Business Rationale for Metrixa Systems (Submetering)",
            ]
        )
        summary_rows = [
            (
                "Total Raw Scraped Listings (Stage 1)",
                str(tel["raw_total"]),
                "Aggregated across Gelbe Seiten, 11880.com, VDIV Berlin-Brandenburg, OpenStreetMap Overpass, and SearXNG Discovery.",
            ),
            (
                "Deduplicated Qualified Berlin Hausverwaltungen (Stage 2)",
                str(tel["golden_qualified_total"]),
                "Cleaned via Canonical Domain + E.164 Phone + RapidFuzz Token Sort Ratio + Union-Find Graph Clustering.",
            ),
            (
                "Tier A — High-Priority Target Leads (Score 70-100)",
                str(tel["tiers"].get("Tier A (High Priority)", 0)),
                "Large/Mid-sized WEG & Mietverwaltung firms with high digital maturity or VDIV certification and direct decision-maker contact.",
            ),
            (
                "Tier B — Qualified Mid-Market Leads (Score 45-69)",
                str(tel["tiers"].get("Tier B (Qualified Mid-Market)", 0)),
                "Established Berlin residential property managers ideal for structured outbound sequences.",
            ),
            (
                "Tier C — Long-Tail / Small Portfolio Leads (Score <45)",
                str(tel["tiers"].get("Tier C (Long-Tail / Small)", 0)),
                "Smaller local managers or firms with limited digital footprint.",
            ),
            (
                "Companies with Named Decision Maker (Geschäftsführer/Inhaber)",
                str(tel["companies_with_decision_maker"]),
                "Extracted from legally mandated German § 5 DDG Impressum and Team pages.",
            ),
            (
                "Companies with Verified / MX-Valid Personal Email (Non-info@)",
                str(tel["companies_with_personal_email"]),
                "Strictly separates generic info@ inboxes from personal executive emails verified against live DNS MX servers.",
            ),
            (
                "KPI Pillar 1: Portfolio Scale (Max 35 pts)",
                "Reported Units (Wohneinheiten), Size Tier, Employee Count, Legal Form",
                "Submetering hardware & annual billing revenue scale directly with the number of managed apartment units.",
            ),
            (
                "KPI Pillar 2: Asset Focus (Max 25 pts)",
                "WEG-Verwaltung & Mietverwaltung vs. Commercial/SEV",
                "Multi-family residential buildings (WEG & Miet) require mandatory annual Heizkostenabrechnung under HeizkV.",
            ),
            (
                "KPI Pillar 3: Digital Maturity & ERP Stack (Max 20 pts)",
                "Casavi, Domus, Wodis, Haufe, Immoware24, etg24, Customer Portal",
                "Property managers already using cloud portals/ERPs are tech-forward buyers ready to adopt smart submetering.",
            ),
            (
                "KPI Pillar 4: Credibility & Stability (Max 10 pts)",
                "VDIV Membership, HRB Commercial Register, Founding Year",
                "VDIV members manage institutional portfolios with strict EED monthly consumption compliance requirements.",
            ),
            (
                "KPI Pillar 5: Contact Reachability (Max 10 pts)",
                "Decision Maker Name, Personal Email (MX Valid), LinkedIn URL",
                "Enables Metrixa Systems Account Executives to bypass info@ gatekeepers and reach the contract signer.",
            ),
        ]
        for sr_idx, sr in enumerate(summary_rows, start=2):
            ws4.append(list(sr))
            for c_i in range(1, 4):
                cell = ws4.cell(row=sr_idx, column=c_i)
                cell.font = BODY_FONT
                cell.border = THIN_BORDER

        self._style_worksheet(ws4, {1: 44, 2: 42, 3: 75})

        wb.save(str(out_xlsx))

        # Write clean Master CSV
        with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerows(csv_rows_out)

        return {
            "xlsx_path": str(out_xlsx),
            "csv_path": str(out_csv),
            "total_exported_leads": len(master_rows),
            "total_exported_contacts": len(dm_rows),
        }
