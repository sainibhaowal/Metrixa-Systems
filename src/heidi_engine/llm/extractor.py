"""
Stage 4 Batch KPI & Decision-Maker Extraction Engine.
Combines crawled pages per company, calls LLMRouter + Deterministic Guard,
infers Portfolio Size Tiers and Digital Maturity Scores, and persists to SQLite.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from heidi_engine.db import Database
from heidi_engine.llm.router import llm_router
from heidi_engine.models import UnitsSizeTier


def infer_portfolio_units_tier(
    exact_units: Optional[int],
    employee_count: Optional[int],
    legal_form: Optional[str],
    is_vdiv_member: bool,
    has_erp_or_portal: bool,
) -> str:
    """
    Deterministically assign Portfolio Size Tier (<250, 250-1,000, 1,000-5,000, 5,000+)
    using explicit units when available, or industry ratios (~350 units per employee in Germany).
    """
    if exact_units is not None:
        if exact_units >= 5000:
            return UnitsSizeTier.ENTERPRISE.value
        if exact_units >= 1000:
            return UnitsSizeTier.LARGE.value
        if exact_units >= 250:
            return UnitsSizeTier.MEDIUM.value
        return UnitsSizeTier.SMALL.value

    if employee_count is not None:
        if employee_count >= 15:
            return UnitsSizeTier.ENTERPRISE.value
        if employee_count >= 5:
            return UnitsSizeTier.LARGE.value
        if employee_count >= 2:
            return UnitsSizeTier.MEDIUM.value

    if is_vdiv_member:
        return UnitsSizeTier.LARGE.value

    if legal_form in ("AG", "GmbH & Co. KG", "SE"):
        return UnitsSizeTier.LARGE.value

    if legal_form == "GmbH":
        return UnitsSizeTier.LARGE.value if has_erp_or_portal else UnitsSizeTier.MEDIUM.value

    return UnitsSizeTier.SMALL.value


def compute_digital_maturity_score(
    has_website: bool,
    website_is_https: bool,
    has_portal: bool,
    erp_list: List[str],
    has_linkedin: bool,
) -> int:
    """Compute Digital Maturity Score from 1 (offline/legacy) to 5 (cloud PropTech leader)."""
    if not has_website:
        return 1
    score = 2
    if website_is_https:
        score += 1
    if has_portal or erp_list:
        score += 1
    if len(erp_list) >= 1 and (has_portal or has_linkedin):
        score += 1
    return min(5, score)


class KPIExtractionPipeline:
    """Runs Stage 4 KPI & Decision-Maker extraction across crawled Berlin companies."""

    def __init__(self, db: Database, concurrency: int = 8) -> None:
        self.db = db
        self.semaphore = asyncio.Semaphore(concurrency)

    async def extract_single_company(
        self, company_row: Dict[str, Any], requested_provider: Optional[str] = None
    ) -> Dict[str, Any]:
        async with self.semaphore:
            comp_id = company_row["company_id"]
            comp_name = company_row["display_name"]
            website_url = company_row["website_url"] or ""
            is_vdiv = bool(company_row["is_vdiv_member"])

            with self.db.connect() as conn:
                pages = conn.execute(
                    """
                    SELECT page_type, url, http_status, clean_markdown,
                           detected_erp_csv, detected_metering_csv, has_portal_link,
                           social_linkedin_csv, extracted_emails_csv
                    FROM crawled_pages
                    WHERE company_id = ? AND http_status = 200
                    ORDER BY CASE page_type
                        WHEN 'impressum' THEN 1
                        WHEN 'team' THEN 2
                        WHEN 'leistungen' THEN 3
                        WHEN 'referenzen' THEN 4
                        WHEN 'homepage' THEN 5
                        ELSE 6
                    END
                    """,
                    (comp_id,),
                ).fetchall()

            combined_parts: List[str] = []
            erp_set: set[str] = set()
            metering_set: set[str] = set()
            emails_set: set[str] = set()
            linkedin_set: set[str] = set()
            has_portal = False
            impressum_url = website_url

            for p in pages:
                pt = p["page_type"]
                if pt == "impressum":
                    impressum_url = p["url"]
                md = (p["clean_markdown"] or "").strip()
                if md:
                    combined_parts.append(f"=== PAGE [{pt.upper()}] ({p['url']}) ===\n{md[:3500]}")
                for item in (p["detected_erp_csv"] or "").split(","):
                    if item.strip():
                        erp_set.add(item.strip())
                for item in (p["detected_metering_csv"] or "").split(","):
                    if item.strip():
                        metering_set.add(item.strip())
                for item in (p["extracted_emails_csv"] or "").split(","):
                    if item.strip():
                        emails_set.add(item.strip())
                for item in (p["social_linkedin_csv"] or "").split(","):
                    if item.strip():
                        linkedin_set.add(item.strip())
                if p["has_portal_link"]:
                    has_portal = True

            combined_markdown = "\n\n".join(combined_parts)
            erp_list = sorted(erp_set)
            metering_list = sorted(metering_set)
            emails_list = sorted(emails_set)
            linkedin_list = sorted(linkedin_set)

            extraction, audit_meta = await llm_router.extract_kpis_with_llm_and_deterministic_guard(
                company_name=comp_name,
                website_url=website_url,
                combined_markdown=combined_markdown,
                dom_erp_list=erp_list,
                dom_metering_list=metering_list,
                dom_has_portal=has_portal,
                dom_emails=emails_list,
                dom_linkedin_urls=linkedin_list,
                requested_provider=requested_provider,
            )

            final_legal_form = extraction.legal_form or company_row["legal_form"]
            final_has_portal = extraction.has_online_portal or has_portal
            final_erp_str = ", ".join(sorted(set(erp_list)))
            final_metering_str = ", ".join(sorted(set(metering_list)))

            est_tier = infer_portfolio_units_tier(
                exact_units=extraction.exact_units_managed,
                employee_count=extraction.employee_count_mentioned,
                legal_form=final_legal_form,
                is_vdiv_member=is_vdiv,
                has_erp_or_portal=bool(erp_list or final_has_portal),
            )

            dig_score = compute_digital_maturity_score(
                has_website=bool(website_url and pages),
                website_is_https=website_url.startswith("https://"),
                has_portal=final_has_portal,
                erp_list=erp_list,
                has_linkedin=bool(linkedin_list),
            )

            company_li_url = next(
                (u for u in linkedin_list if "/company/" in u.lower()),
                linkedin_list[0] if linkedin_list else None,
            )
            gen_email = (
                extraction.general_emails[0]
                if extraction.general_emails
                else company_row["general_email"]
            )

            now_iso = datetime.now(timezone.utc).isoformat()
            next_stage = "EXTRACTED" if extraction.is_actual_hausverwaltung else "DISQUALIFIED"

            with self.db.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO kpi_extractions (
                        company_id, is_actual_hausverwaltung, founding_year,
                        exact_units_managed, units_evidence_quote, estimated_units_tier,
                        employee_count_est, reference_buildings_count,
                        manages_weg, manages_miet, manages_gewerbe, manages_sev,
                        has_customer_portal, detected_erp_proptech, incumbent_metering_signal,
                        digital_maturity_score, qualification_reasoning,
                        llm_provider_used, llm_model_used, extraction_confidence, extracted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_id) DO UPDATE SET
                        is_actual_hausverwaltung = excluded.is_actual_hausverwaltung,
                        founding_year = excluded.founding_year,
                        exact_units_managed = excluded.exact_units_managed,
                        units_evidence_quote = excluded.units_evidence_quote,
                        estimated_units_tier = excluded.estimated_units_tier,
                        employee_count_est = excluded.employee_count_est,
                        reference_buildings_count = excluded.reference_buildings_count,
                        manages_weg = excluded.manages_weg,
                        manages_miet = excluded.manages_miet,
                        manages_gewerbe = excluded.manages_gewerbe,
                        manages_sev = excluded.manages_sev,
                        has_customer_portal = excluded.has_customer_portal,
                        detected_erp_proptech = excluded.detected_erp_proptech,
                        incumbent_metering_signal = excluded.incumbent_metering_signal,
                        digital_maturity_score = excluded.digital_maturity_score,
                        qualification_reasoning = excluded.qualification_reasoning,
                        llm_provider_used = excluded.llm_provider_used,
                        llm_model_used = excluded.llm_model_used,
                        extracted_at = excluded.extracted_at
                    """,
                    (
                        comp_id,
                        1 if extraction.is_actual_hausverwaltung else 0,
                        extraction.founding_year,
                        extraction.exact_units_managed,
                        extraction.units_evidence_quote,
                        est_tier,
                        extraction.employee_count_mentioned,
                        extraction.reference_buildings_count,
                        1 if extraction.manages_weg else 0,
                        1 if extraction.manages_miet else 0,
                        1 if extraction.manages_gewerbe else 0,
                        1 if extraction.manages_sev else 0,
                        1 if final_has_portal else 0,
                        final_erp_str or None,
                        final_metering_str or None,
                        dig_score,
                        extraction.qualification_reasoning,
                        audit_meta["provider"],
                        audit_meta["model_name"],
                        0.92 if pages else 0.65,
                        now_iso,
                    ),
                )

                # Save extracted Decision Makers
                conn.execute("DELETE FROM decision_makers WHERE company_id = ?", (comp_id,))
                for idx, dm in enumerate(extraction.decision_makers):
                    parts = dm.full_name.split()
                    first_name = parts[0] if parts else ""
                    last_name = parts[-1] if len(parts) > 1 else ""
                    email_stat = "PUBLIC_DIRECT_VERIFIED" if dm.direct_email else "NONE"
                    conn.execute(
                        """
                        INSERT INTO decision_makers (
                            company_id, full_name, first_name, last_name, role,
                            personal_email, email_status, direct_phone, linkedin_url,
                            source_url, evidence_quote, is_primary_contact
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            comp_id,
                            dm.full_name,
                            first_name,
                            last_name,
                            dm.role,
                            dm.direct_email,
                            email_stat,
                            dm.direct_phone,
                            dm.linkedin_url,
                            impressum_url,
                            dm.source_quote,
                            1 if idx == 0 else 0,
                        ),
                    )

                # Update Golden Company metadata
                conn.execute(
                    """
                    UPDATE companies_golden
                    SET legal_form = COALESCE(?, legal_form),
                        commercial_register_id = COALESCE(?, commercial_register_id),
                        general_email = COALESCE(?, general_email),
                        company_linkedin_url = COALESCE(?, company_linkedin_url),
                        pipeline_stage = ?,
                        updated_at = ?
                    WHERE company_id = ?
                    """,
                    (
                        final_legal_form,
                        extraction.commercial_register_id,
                        gen_email,
                        company_li_url,
                        next_stage,
                        now_iso,
                        comp_id,
                    ),
                )

                # Log LLM call audit
                conn.execute(
                    """
                    INSERT INTO llm_audit_logs (
                        company_id, stage, provider, model_name, prompt_tokens,
                        completion_tokens, latency_ms, schema_valid, hallucination_blocked, created_at
                    ) VALUES (?, 'kpi_extraction', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        comp_id,
                        audit_meta["provider"],
                        audit_meta["model_name"],
                        audit_meta["prompt_tokens"],
                        audit_meta["completion_tokens"],
                        audit_meta["latency_ms"],
                        1 if audit_meta["schema_valid"] else 0,
                        1 if audit_meta["hallucination_blocked"] else 0,
                        now_iso,
                    ),
                )

            return {
                "company_id": comp_id,
                "provider": audit_meta["provider"],
                "dms_found": len(extraction.decision_makers),
                "has_erp": bool(final_erp_str),
            }

    async def extract_batch(
        self,
        limit: Optional[int] = None,
        requested_provider: Optional[str] = None,
        reprocess_all: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, int]:
        with self.db.connect() as conn:
            stage_filter = (
                "pipeline_stage != 'DISQUALIFIED'"
                if reprocess_all
                else "pipeline_stage = 'CRAWLED'"
            )
            query = f"""
                SELECT * FROM companies_golden
                WHERE {stage_filter}
                ORDER BY is_vdiv_member DESC, source_count DESC, company_id ASC
            """
            if limit:
                query += f" LIMIT {int(limit)}"
            rows = [dict(r) for r in conn.execute(query).fetchall()]

        total = len(rows)
        if total == 0:
            return {"processed": 0, "with_decision_maker": 0, "with_erp": 0}

        completed = 0
        with_dm = 0
        with_erp = 0

        tasks = [
            self.extract_single_company(r, requested_provider=requested_provider)
            for r in rows
        ]
        for coro in asyncio.as_completed(tasks):
            res = await coro
            completed += 1
            if res["dms_found"] > 0:
                with_dm += 1
            if res["has_erp"]:
                with_erp += 1
            if progress_callback:
                progress_callback(completed, total)

        return {
            "processed": total,
            "with_decision_maker": with_dm,
            "with_erp": with_erp,
        }
