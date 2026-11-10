"""
Stage 6 live database coverage and evidence-check reporting.
Does not claim labeled Gold-Set precision/recall or hallucination rates unless those
metrics have actually been measured against suitable labeled data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from metrixa_engine.config import settings
from metrixa_engine.db import Database


class PipelineEvaluator:
    """Computes live database coverage and evidence metrics for operational reporting."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def compute_live_ablation_metrics(self) -> Dict[str, Any]:
        """
        Compute exact Stage 1 -> Stage 5 progression metrics directly from SQLite `metrixa_leads.db`.
        """
        with self.db.connect() as conn:
            # Baseline A: Gelbe Seiten only raw count
            gs_raw = conn.execute(
                "SELECT COUNT(*) FROM raw_listings WHERE source_name = 'gelbe_seiten'"
            ).fetchone()[0]
            gs_with_web = conn.execute(
                "SELECT COUNT(*) FROM raw_listings WHERE source_name = 'gelbe_seiten' AND raw_website IS NOT NULL AND raw_website != ''"
            ).fetchone()[0]

            # Stage 1: All 5 sources raw count
            all_raw = conn.execute("SELECT COUNT(*) FROM raw_listings").fetchone()[0]

            # Stage 2: Deduplicated Golden Berlin Leads
            golden_total = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
            ).fetchone()[0]
            golden_with_web = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED' AND website_url IS NOT NULL AND website_url != ''"
            ).fetchone()[0]
            vdiv_cnt = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED' AND is_vdiv_member = 1"
            ).fetchone()[0]

            # Stage 3: Crawled Websites & DOM Tech Detection
            crawled_companies = conn.execute(
                "SELECT COUNT(DISTINCT company_id) FROM crawled_pages WHERE http_status = 200"
            ).fetchone()[0]
            dom_portal_or_erp = conn.execute(
                """
                SELECT COUNT(DISTINCT company_id) FROM crawled_pages
                WHERE http_status = 200 AND (has_portal_link = 1 OR (detected_erp_csv IS NOT NULL AND detected_erp_csv != ''))
                """
            ).fetchone()[0]

            # Stage 4: KPI & Impressum Extraction
            kpi_populated = conn.execute(
                """
                SELECT COUNT(*) FROM kpi_extractions k
                JOIN companies_golden c ON c.company_id = k.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                """
            ).fetchone()[0]
            dm_extracted = conn.execute(
                """
                SELECT COUNT(DISTINCT d.company_id) FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                """
            ).fetchone()[0]
            public_direct_emails = conn.execute(
                """
                SELECT COUNT(DISTINCT d.company_id) FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED' AND d.email_status = 'PUBLIC_DIRECT_VERIFIED'
                """
            ).fetchone()[0]

            # Stage 5: Enrichment (source-listed contacts, email candidates, MX-domain checks, and scoring)
            total_pers_emails = conn.execute(
                """
                SELECT COUNT(DISTINCT d.company_id) FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND d.personal_email IS NOT NULL AND d.personal_email != ''
                """
            ).fetchone()[0]
            mx_verified_domains = conn.execute(
                """
                SELECT COUNT(DISTINCT d.company_id) FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED' AND d.mx_valid = 1
                """
            ).fetchone()[0]

            denom = max(1, golden_total)
            return {
                "gs_raw": gs_raw,
                "gs_web_pct": round(100.0 * gs_with_web / max(1, gs_raw), 1),
                "all_raw": all_raw,
                "golden_total": golden_total,
                "duplicates_removed": max(0, all_raw - golden_total),
                "golden_web_pct": round(100.0 * golden_with_web / denom, 1),
                "vdiv_pct": round(100.0 * vdiv_cnt / denom, 1),
                "crawled_companies": crawled_companies,
                "dom_portal_or_erp_cnt": dom_portal_or_erp,
                "dom_portal_or_erp_pct": round(100.0 * dom_portal_or_erp / denom, 1),
                "kpi_populated_cnt": kpi_populated,
                "kpi_populated_pct": round(100.0 * kpi_populated / denom, 1),
                "dm_extracted_cnt": dm_extracted,
                "dm_extracted_pct": round(100.0 * dm_extracted / denom, 1),
                "public_direct_emails_cnt": public_direct_emails,
                "public_direct_emails_pct": round(
                    100.0 * public_direct_emails / denom, 1
                ),
                "total_pers_emails_cnt": total_pers_emails,
                "total_pers_emails_pct": round(100.0 * total_pers_emails / denom, 1),
                "mx_verified_domains": mx_verified_domains,
            }

    def evaluate_validation_metrics(self) -> Dict[str, Any]:
        """Measure data coverage and exact stored quote matches; avoid unsupported accuracy claims."""
        with self.db.connect() as conn:
            total_gold = conn.execute(
                "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
            ).fetchone()[0]

            valid_berlin_plz = conn.execute(
                """
                SELECT COUNT(*) FROM companies_golden
                WHERE pipeline_stage != 'DISQUALIFIED'
                  AND CAST(postal_code AS INTEGER) BETWEEN 10115 AND 14199
                """
            ).fetchone()[0]

            units_rows = conn.execute(
                """
                SELECT k.company_id, k.units_evidence_quote,
                    (SELECT GROUP_CONCAT(p.clean_markdown, char(10))
                     FROM crawled_pages p
                     WHERE p.company_id = k.company_id AND p.http_status = 200) AS page_text
                FROM kpi_extractions k
                JOIN companies_golden c ON c.company_id = k.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND k.exact_units_managed IS NOT NULL
                """
            ).fetchall()

            def _normalized_text(value: str | None) -> str:
                return " ".join((value or "").split()).casefold()

            grounded_units = sum(
                1
                for row in units_rows
                if _normalized_text(row["units_evidence_quote"])
                and _normalized_text(row["units_evidence_quote"])
                in _normalized_text(row["page_text"])
            )

            pers_emails = conn.execute(
                """
                SELECT d.personal_email FROM decision_makers d
                JOIN companies_golden c ON c.company_id = d.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND d.personal_email IS NOT NULL AND d.personal_email != ''
                """
            ).fetchall()
            non_info_emails = sum(
                1
                for r in pers_emails
                if not r["personal_email"]
                .lower()
                .startswith(("info@", "kontakt@", "office@", "mail@", "service@"))
            )

            blocked_hallucinations = conn.execute(
                "SELECT COALESCE(SUM(hallucination_blocked), 0) FROM llm_audit_logs"
            ).fetchone()[0]
            legacy_vdiv_registry_rows = conn.execute(
                """
                SELECT COUNT(*) FROM raw_listings
                WHERE source_name = 'vdiv'
                  AND raw_json_payload LIKE '%legacy_curated_vdiv_registry_requires_review%'
                """
            ).fetchone()[0]

        return {
            "total_evaluated_leads": total_gold,
            "eligible_leads_with_berlin_plz_pct": (
                round(100.0 * valid_berlin_plz / total_gold, 1) if total_gold else None
            ),
            "explicit_units_extracted": len(units_rows),
            "units_evidence_grounded_pct": (
                round(100.0 * grounded_units / max(1, len(units_rows)), 1)
                if units_rows
                else None
            ),
            "personal_emails_total": len(pers_emails),
            "personal_email_non_generic_rate_pct": (
                round(100.0 * non_info_emails / max(1, len(pers_emails)), 1)
                if pers_emails
                else None
            ),
            "hallucinations_blocked_by_gate": blocked_hallucinations,
            "legacy_vdiv_registry_rows": legacy_vdiv_registry_rows,
            "final_hallucination_rate_pct": None,
        }

    def generate_markdown_report(self, output_path: Optional[Path] = None) -> Path:
        settings.ensure_dirs()
        out_file = output_path or (
            settings.export_dir / "evaluation_ablation_report.md"
        )
        tel = self.db.get_pipeline_telemetry()
        abl = self.compute_live_ablation_metrics()
        val = self.evaluate_validation_metrics()
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        plz_rate = (
            f"{val['eligible_leads_with_berlin_plz_pct']:.1f}%"
            if val["eligible_leads_with_berlin_plz_pct"] is not None
            else "Not measured (no eligible leads)"
        )
        quote_rate = (
            f"{val['units_evidence_grounded_pct']:.1f}%"
            if val["units_evidence_grounded_pct"] is not None
            else "Not measured (no explicit unit claims)"
        )
        email_rate = (
            f"{val['personal_email_non_generic_rate_pct']:.1f}%"
            if val["personal_email_non_generic_rate_pct"] is not None
            else "Not measured (no personal emails)"
        )
        report_md = f"""# Metrixa Engine: Live Data Coverage and Evidence Report

**Generated at:** `{now_str}`
**Database:** `{settings.database_path}`
**Primary Excel deliverable:** `{settings.export_dir / 'metrixa_berlin_hausverwaltungen.xlsx'}`

This report describes the current local database snapshot. It is not a labeled Gold-Set benchmark or a controlled ablation experiment. Coverage rates below describe stored records and must not be interpreted as model accuracy, sales conversion, or verified truth.

## Current dataset

| Metric | Current value |
| --- | ---: |
| Raw source records | {tel['raw_total']:,} |
| Eligible canonical companies | {tel['golden_qualified_total']:,} |
| Tier A companies | {tel['tiers'].get('Tier A (High Priority)', 0):,} |
| Tier B companies | {tel['tiers'].get('Tier B (Qualified Mid-Market)', 0):,} |
| Tier C companies | {tel['tiers'].get('Tier C (Long-Tail / Small)', 0):,} |
| Companies with a website | {tel['with_website']:,} ({abl['golden_web_pct']:.1f}% of eligible companies) |
| Stored crawled pages | {tel['crawled_pages_cnt']:,} |
| Companies with portal/ERP signals | {tel['with_customer_portal']:,} ({abl['dom_portal_or_erp_pct']:.1f}%) |
| Companies with a named decision maker | {tel['companies_with_decision_maker']:,} ({abl['dm_extracted_pct']:.1f}%) |
| Companies with a personal email | {tel['companies_with_personal_email']:,} ({abl['total_pers_emails_pct']:.1f}%) |

## Pipeline coverage

These are counts currently present in the database, not a controlled ablation study.

| Stage output | Count / rate |
| --- | ---: |
| Gelbe Seiten raw records | {abl['gs_raw']:,} |
| Eligible canonical companies with a website | {abl['golden_total']:,} / {abl['golden_web_pct']:.1f}% |
| Companies with a successful crawl page | {abl['crawled_companies']:,} |
| Companies with a KPI extraction | {abl['kpi_populated_cnt']:,} / {abl['kpi_populated_pct']:.1f}% |
| Companies with a decision maker | {abl['dm_extracted_cnt']:,} / {abl['dm_extracted_pct']:.1f}% |
| Companies with a personal email | {abl['total_pers_emails_cnt']:,} / {abl['total_pers_emails_pct']:.1f}% |

## Evidence and data checks

| Check | Result | Scope |
| --- | ---: | --- |
| Eligible records with a Berlin-range postal code | {plz_rate} | Range coverage only; not independently verified postal accuracy |
| Explicit unit claims whose stored quote appears in a successful crawled page | {quote_rate} | Exact normalized text presence; not a full claim correctness audit |
| Stored personal emails that do not use common generic prefixes | {email_rate} | Prefix check only; not proof of identity, consent, or deliverability |
| Legacy VDIV registry rows requiring live-source review | {val['legacy_vdiv_registry_rows']:,} | Preserved from an older embedded registry; excluded from verified VDIV membership scoring |
| Audit rows marked as blocked by the gate | {val['hallucinations_blocked_by_gate']:,} | Count of blocked events only |
| Overall hallucination rate | Not measured | Requires a labeled review of all extracted claims |

## Limits

The application does not calculate Gold-Set precision, recall, or F1 from the current dataset. A non-empty evidence quote or a blocked-event count alone cannot establish a hallucination rate. Validate a representative, independently labeled sample before using accuracy claims in external materials.
"""
        out_file.write_text(report_md, encoding="utf-8")
        if output_path is None:
            # Keep the artifact-library filename in sync with the canonical report.
            (settings.export_dir / "metrixa_evaluation_ablation_report.md").write_text(
                report_md, encoding="utf-8"
            )
        return out_file
