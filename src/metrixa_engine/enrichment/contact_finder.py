"""
Stage 5 Decision-Maker LinkedIn & Email Candidate Enrichment Engine.
Checks corporate-domain DNS MX records, resolves LinkedIn URLs via search providers,
and labels generated address patterns as candidates rather than mailbox-verified emails.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from metrixa_engine.db import Database
from metrixa_engine.enrichment.email_verifier import email_verifier
from metrixa_engine.enrichment.search_router import search_router
from metrixa_engine.llm.router import clean_extracted_person_name


class ContactEnricher:
    """Enriches leads with sourced contacts and clearly labeled email candidates."""

    def __init__(self, db: Database, concurrency: int = 8) -> None:
        self.db = db
        self.semaphore = asyncio.Semaphore(concurrency)

    async def _search_linkedin_and_director(
        self,
        company_name: str,
        director_name: Optional[str] = None,
        enable_web_search: bool = False,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Return (personal_linkedin_url, company_linkedin_url, discovered_director_name).
        """
        if not enable_web_search:
            return None, None, None

        if director_name:
            query = f'site:linkedin.com "{director_name}" "{company_name}" Berlin'
        else:
            query = f'"{company_name}" Berlin Gesch\u00e4ftsf\u00fchrer'

        results = await search_router.search(
            query, max_results=5, allow_tavily_fallback=True
        )
        pers_li = None
        comp_li = None
        disc_director = None
        company_tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", company_name.casefold())
            if len(token) >= 4
            and token
            not in {
                "hausverwaltung",
                "verwaltung",
                "immobilien",
                "berlin",
                "gmbh",
                "gesellschaft",
                "aktiengesellschaft",
                "co",
                "kg",
            }
        ]

        for item in results:
            u_low = item.url.lower()
            result_text = f"{item.title} {item.snippet}".casefold()
            company_slug = u_low.split("linkedin.com/company/", 1)[-1].split("/", 1)[0]
            company_match = bool(company_tokens) and all(
                token in result_text or token in company_slug
                for token in company_tokens
            )
            if (
                "linkedin.com/in/" in u_low
                and director_name
                and not pers_li
                and all(
                    token in result_text
                    for token in re.findall(r"[a-z0-9]+", director_name.casefold())
                    if len(token) >= 2
                )
            ):
                pers_li = item.url.split("?")[0]
            if "linkedin.com/company/" in u_low and company_match and not comp_li:
                comp_li = item.url.split("?")[0]

            if not director_name and company_match and not disc_director:
                m = re.search(
                    r"(?:Gesch[aä]ftsf[uü]hrer(?:in)?|Inhaber(?:in)?)\s*[:\--]?\s*([A-ZÄÖÜ][a-zäöüß\-]+\s+[A-ZÄÖÜ][a-zäöüß\-]+)",
                    item.snippet + " " + item.title,
                )
                if m:
                    disc_director = clean_extracted_person_name(m.group(1))

        return pers_li, comp_li, disc_director

    async def enrich_single_company(
        self,
        company_row: Dict[str, Any],
        enable_web_search_for_missing: bool = False,
    ) -> Dict[str, Any]:
        async with self.semaphore:
            comp_id = company_row["company_id"]
            comp_name = company_row["display_name"]
            domain = company_row["canonical_domain"]
            comp_li = company_row["company_linkedin_url"]

            # 1. Verify DNS MX records for corporate domain
            mx_valid, mx_host = await email_verifier.check_domain_mx(domain)

            with self.db.connect() as conn:
                dms = [
                    dict(r)
                    for r in conn.execute(
                        """
                        SELECT d.*,
                            EXISTS (
                                SELECT 1 FROM crawled_pages p
                                WHERE p.company_id = d.company_id AND p.http_status = 200
                                  AND instr(
                                      lower(coalesce(p.clean_markdown, '') || ' ' || coalesce(p.extracted_emails_csv, '')),
                                      lower(coalesce(d.personal_email, ''))
                                  ) > 0
                            ) AS email_present_in_source
                        FROM decision_makers d
                        WHERE d.company_id = ?
                        ORDER BY d.is_primary_contact DESC, d.contact_id ASC
                        """,
                        (comp_id,),
                    ).fetchall()
                ]

            primary_dm_name = dms[0]["full_name"] if dms else None
            pers_li_found = dms[0]["linkedin_url"] if dms else None

            # 2. Optional web search for LinkedIn / missing decision maker on priority leads
            if enable_web_search_for_missing and (
                not primary_dm_name or not (pers_li_found or comp_li)
            ):
                s_pers_li, s_comp_li, s_dir_name = (
                    await self._search_linkedin_and_director(
                        comp_name, primary_dm_name, enable_web_search=True
                    )
                )
                if s_comp_li and not comp_li:
                    comp_li = s_comp_li
                if s_pers_li and not pers_li_found:
                    pers_li_found = s_pers_li
                # Search snippets are discovery hints, not primary-source evidence.
                # Do not create a decision-maker record from a snippet alone.

            # 3. Verify or infer personal emails for each Decision Maker
            has_public_email = False
            has_pattern_email_candidate = False
            now_iso = datetime.now(timezone.utc).isoformat()

            with self.db.connect() as conn:
                for idx, dm in enumerate(dms):
                    p_email = dm["personal_email"]
                    e_status = dm["email_status"]
                    li_url = dm["linkedin_url"] or (pers_li_found if idx == 0 else None)

                    if (
                        p_email
                        and email_verifier.is_personal_email(p_email)
                        and e_status in ("PUBLIC_DIRECT_VERIFIED", "PUBLIC_LISTED")
                        and dm["email_present_in_source"]
                    ):
                        e_status = "PUBLIC_LISTED"
                        has_public_email = True
                    elif mx_valid and domain:
                        inferred = email_verifier.generate_german_b2b_personal_email(
                            dm["full_name"], domain
                        )
                        if inferred:
                            p_email = inferred
                            e_status = "PATTERN_CANDIDATE_MX"
                            has_pattern_email_candidate = True
                    else:
                        p_email = None
                        e_status = (
                            "GENERIC_ONLY" if company_row["general_email"] else "NONE"
                        )

                    if dm.get("contact_id"):
                        conn.execute(
                            """
                            UPDATE decision_makers
                            SET personal_email = ?,
                                email_status = ?,
                                mx_valid = ?,
                                mx_host = ?,
                                linkedin_url = COALESCE(?, linkedin_url)
                            WHERE contact_id = ?
                            """,
                            (
                                p_email,
                                e_status,
                                1 if mx_valid else 0,
                                mx_host,
                                li_url,
                                dm["contact_id"],
                            ),
                        )
                conn.execute(
                    """
                    UPDATE companies_golden
                    SET company_linkedin_url = COALESCE(?, company_linkedin_url),
                        pipeline_stage = 'ENRICHED',
                        updated_at = ?
                    WHERE company_id = ?
                    """,
                    (comp_li, now_iso, comp_id),
                )

            return {
                "company_id": comp_id,
                "mx_valid": mx_valid,
                "has_public_email": has_public_email,
                "has_pattern_email_candidate": has_pattern_email_candidate,
                "has_linkedin": bool(pers_li_found or comp_li),
            }

    async def enrich_batch(
        self,
        limit: Optional[int] = None,
        web_search_top_n: int = 25,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, int]:
        with self.db.connect() as conn:
            query = """
                SELECT * FROM companies_golden
                WHERE pipeline_stage = 'EXTRACTED'
                ORDER BY is_vdiv_member DESC, source_count DESC, company_id ASC
            """
            if limit:
                query += f" LIMIT {int(limit)}"
            rows = [dict(r) for r in conn.execute(query).fetchall()]

        total = len(rows)
        if total == 0:
            return {
                "processed": 0,
                "mx_valid_domains": 0,
                "public_emails_listed": 0,
                "pattern_email_candidates": 0,
            }

        completed = 0
        mx_valid_cnt = 0
        public_email_cnt = 0
        pattern_email_candidate_cnt = 0

        tasks = [
            self.enrich_single_company(
                r, enable_web_search_for_missing=(idx < web_search_top_n)
            )
            for idx, r in enumerate(rows)
        ]
        for coro in asyncio.as_completed(tasks):
            res = await coro
            completed += 1
            if res["mx_valid"]:
                mx_valid_cnt += 1
            if res["has_public_email"]:
                public_email_cnt += 1
            if res["has_pattern_email_candidate"]:
                pattern_email_candidate_cnt += 1
            if progress_callback:
                progress_callback(completed, total)

        return {
            "processed": total,
            "mx_valid_domains": mx_valid_cnt,
            "public_emails_listed": public_email_cnt,
            "pattern_email_candidates": pattern_email_candidate_cnt,
        }
