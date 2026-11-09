"""
Missing Website URL Resolver for Golden Companies.
Uses the Unified Search Router (Local SearXNG -> Native Meta-Search -> Tavily Fallback)
to find official corporate websites for Berlin property managers missing a URL.
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone
from typing import Optional
from rapidfuzz import fuzz

from metrixa_engine.db import Database
from metrixa_engine.enrichment.search_router import search_router
from metrixa_engine.entity_resolution.normalizer import (
    DIRECTORY_AND_SOCIAL_DOMAINS,
    FREEMAIL_DOMAINS,
    canonicalize_company_name,
    extract_canonical_domain,
)
from metrixa_engine.scrapers.search_discovery import EXCLUDED_SEARCH_DOMAINS


class MissingURLResolver:
    """Resolves missing corporate website URLs for deduplicated Berlin companies."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def resolve_for_company(
        self, company_name: str, postal_code: Optional[str] = None
    ) -> Optional[str]:
        query = f'"{company_name}" Berlin Hausverwaltung'
        if postal_code:
            query = f'"{company_name}" {postal_code} Berlin'

        results = await search_router.search(
            query, max_results=5, allow_tavily_fallback=False
        )
        norm_target = canonicalize_company_name(company_name)

        for item in results:
            parsed = urllib.parse.urlparse(item.url)
            host = parsed.netloc.lower().lstrip("www.")
            if (
                not host
                or any(d in host for d in DIRECTORY_AND_SOCIAL_DOMAINS)
                or any(d in host for d in EXCLUDED_SEARCH_DOMAINS)
                or any(d in host for d in FREEMAIL_DOMAINS)
            ):
                continue

            domain_root = host.split(".")[0].replace("-", " ")
            title_norm = canonicalize_company_name(item.title)
            if (
                fuzz.partial_ratio(norm_target, domain_root) >= 65
                or fuzz.token_set_ratio(norm_target, title_norm) >= 70
            ):
                return f"{parsed.scheme}://{parsed.netloc}"

        return None

    async def resolve_missing_batch(self, limit: int = 40) -> int:
        """Resolve missing URLs for up to `limit` companies in SQLite."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT company_id, display_name, postal_code
                FROM companies_golden
                WHERE (website_url IS NULL OR website_url = '')
                  AND pipeline_stage != 'DISQUALIFIED'
                ORDER BY is_vdiv_member DESC, source_count DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        resolved_count = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        for r in rows:
            url = await self.resolve_for_company(r["display_name"], r["postal_code"])
            if url:
                dom = extract_canonical_domain(url)
                with self.db.connect() as conn:
                    conn.execute(
                        """
                        UPDATE companies_golden
                        SET website_url = ?, canonical_domain = COALESCE(canonical_domain, ?), updated_at = ?
                        WHERE company_id = ?
                        """,
                        (url, dom, now_iso, r["company_id"]),
                    )
                resolved_count += 1
        return resolved_count
