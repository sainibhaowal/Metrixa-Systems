"""
Stage 5b Deterministic Metrixa Lead Scoring & Tiering Engine (0-100 Score).
Implements the 5-Pillar Mathematical Qualification Formula specified in
04_TASK2_KPI_BLUEPRINT_CRAWLER_AND_SCORING_ENGINE.md:
  1. Portfolio Scale (Max 35 pts)
  2. Asset & Management Focus (Max 25 pts)
  3. Digital Maturity & PropTech ERP Stack (Max 20 pts)
  4. Professional Credibility & Stability (Max 10 pts)
  5. Decision-Maker & Personal Contact Reachability (Max 10 pts)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from heidi_engine.db import Database
from heidi_engine.models import LeadTier, UnitsSizeTier


def calculate_heidi_lead_score(
    exact_units: Optional[int],
    estimated_units_tier: Optional[str],
    employee_count: Optional[int],
    legal_form: Optional[str],
    has_website: bool,
    manages_weg: bool,
    manages_miet: bool,
    manages_gewerbe: bool,
    manages_sev: bool,
    detected_erp_proptech: Optional[str],
    has_customer_portal: bool,
    website_is_https: bool,
    is_vdiv_member: bool,
    has_hrb_or_established_year: bool,
    source_count: int,
    has_named_decision_maker: bool,
    has_personal_email: bool,
    has_linkedin_or_direct_phone: bool,
) -> Tuple[int, str]:
    """
    Compute deterministic 0-100 Heidi Lead Score and assign Qualification Tier (A / B / C).
    Returns (score_int, lead_tier_str).
    """
    # --- PILLAR 1: PORTFOLIO SCALE (Max 35 pts) ---
    s_scale = 6
    if (
        exact_units and exact_units >= 2500
    ) or estimated_units_tier == UnitsSizeTier.ENTERPRISE.value:
        s_scale = 35
    elif (
        exact_units and exact_units >= 1000
    ) or estimated_units_tier == UnitsSizeTier.LARGE.value:
        s_scale = 28
    elif (
        (exact_units and exact_units >= 300)
        or estimated_units_tier == UnitsSizeTier.MEDIUM.value
        or (employee_count and employee_count >= 5)
    ):
        s_scale = 20
    elif legal_form in ("GmbH", "AG", "GmbH & Co. KG", "SE", "eG") and has_website:
        s_scale = 16
    elif legal_form in ("GmbH", "UG (haftungsbeschränkt)", "GmbH & Co. KG"):
        s_scale = 12

    # --- PILLAR 2: ASSET & MANAGEMENT FOCUS (Max 25 pts) ---
    if manages_weg and manages_miet:
        s_focus = 25
    elif manages_weg or manages_miet:
        s_focus = 20
    elif manages_gewerbe:
        s_focus = 12
    elif manages_sev:
        s_focus = 4
    else:
        s_focus = 15

    # --- PILLAR 3: DIGITAL MATURITY & PROPTECH STACK (Max 20 pts) ---
    s_digital = 0
    if detected_erp_proptech and len(detected_erp_proptech.strip()) > 0:
        s_digital += 12
    if has_customer_portal:
        s_digital += 5
    if has_website and website_is_https:
        s_digital += 3
    elif has_website:
        s_digital += 1
    s_digital = min(20, s_digital)

    # --- PILLAR 4: CREDIBILITY & STABILITY (Max 10 pts) ---
    s_trust = 0
    if is_vdiv_member:
        s_trust += 5
    if has_hrb_or_established_year:
        s_trust += 3
    if source_count >= 2:
        s_trust += 2
    elif source_count == 1:
        s_trust += 1
    s_trust = min(10, s_trust)

    # --- PILLAR 5: DECISION-MAKER & PERSONAL CONTACT REACHABILITY (Max 10 pts) ---
    s_contact = 0
    if has_named_decision_maker:
        s_contact += 4
    if has_personal_email:
        s_contact += 4
    if has_linkedin_or_direct_phone:
        s_contact += 2
    s_contact = min(10, s_contact)

    total_score = min(100, max(0, s_scale + s_focus + s_digital + s_trust + s_contact))

    if total_score >= 70:
        tier = LeadTier.TIER_A.value
    elif total_score >= 45:
        tier = LeadTier.TIER_B.value
    else:
        tier = LeadTier.TIER_C.value

    return total_score, tier


class LeadScorer:
    """Scores and tiers all qualified companies in SQLite."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def score_all_companies(self) -> Dict[str, int]:
        now_iso = datetime.now(timezone.utc).isoformat()
        tier_counts = {
            LeadTier.TIER_A.value: 0,
            LeadTier.TIER_B.value: 0,
            LeadTier.TIER_C.value: 0,
        }

        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.company_id, c.legal_form, c.commercial_register_id,
                    c.website_url, c.phone_e164, c.company_linkedin_url,
                    c.is_vdiv_member, c.source_count, c.pipeline_stage,
                    k.founding_year, k.exact_units_managed, k.estimated_units_tier,
                    k.employee_count_est, k.manages_weg, k.manages_miet,
                    k.manages_gewerbe, k.manages_sev, k.has_customer_portal,
                    k.detected_erp_proptech
                FROM companies_golden c
                LEFT JOIN kpi_extractions k ON k.company_id = c.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                """
            ).fetchall()

            for r in rows:
                cid = r["company_id"]
                dms = conn.execute(
                    "SELECT full_name, personal_email, linkedin_url, direct_phone FROM decision_makers WHERE company_id = ?",
                    (cid,),
                ).fetchall()

                has_dm = len(dms) > 0
                has_pers_email = any(bool(d["personal_email"]) for d in dms)
                has_li_or_phone = bool(
                    r["company_linkedin_url"]
                    or r["phone_e164"]
                    or any(bool(d["linkedin_url"] or d["direct_phone"]) for d in dms)
                )

                web = r["website_url"] or ""
                has_hrb_or_yr = bool(
                    r["commercial_register_id"]
                    or (r["founding_year"] and r["founding_year"] <= 2020)
                )

                score, tier = calculate_heidi_lead_score(
                    exact_units=r["exact_units_managed"],
                    estimated_units_tier=r["estimated_units_tier"],
                    employee_count=r["employee_count_est"],
                    legal_form=r["legal_form"],
                    has_website=bool(web),
                    manages_weg=(
                        bool(r["manages_weg"]) if r["manages_weg"] is not None else True
                    ),
                    manages_miet=(
                        bool(r["manages_miet"])
                        if r["manages_miet"] is not None
                        else True
                    ),
                    manages_gewerbe=bool(r["manages_gewerbe"]),
                    manages_sev=bool(r["manages_sev"]),
                    detected_erp_proptech=r["detected_erp_proptech"],
                    has_customer_portal=bool(r["has_customer_portal"]),
                    website_is_https=web.startswith("https://"),
                    is_vdiv_member=bool(r["is_vdiv_member"]),
                    has_hrb_or_established_year=has_hrb_or_yr,
                    source_count=int(r["source_count"] or 1),
                    has_named_decision_maker=has_dm,
                    has_personal_email=has_pers_email,
                    has_linkedin_or_direct_phone=has_li_or_phone,
                )

                tier_counts[tier] = tier_counts.get(tier, 0) + 1
                conn.execute(
                    """
                    UPDATE companies_golden
                    SET metrixa_lead_score = ?,
                        heidi_lead_score = ?,
                        lead_tier = ?,
                        pipeline_stage = 'SCORED',
                        updated_at = ?
                    WHERE company_id = ?
                    """,
                    (score, score, tier, now_iso, cid),
                )

        return tier_counts


# Rebranded alias
calculate_metrixa_lead_score = calculate_heidi_lead_score
