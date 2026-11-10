"""
Stage 3 Asynchronous Website & German Impressum Crawler.
Crawls homepage + priority internal links (/impressum, /team, /ueber-uns, /leistungen, /referenzen),
detects DOM PropTech/ERP & Metering signatures, and extracts clean Markdown text.
"""

from __future__ import annotations

import asyncio
import ipaddress
import random
import re
import socket
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser
import trafilatura

from metrixa_engine.config import settings
from metrixa_engine.crawler.tech_detector import scan_html_for_tech_and_contacts
from metrixa_engine.db import Database
from metrixa_engine.scrapers.base import USER_AGENTS

SUBPAGE_PRIORITY_RULES: List[Tuple[str, List[str]]] = [
    (
        "impressum",
        [
            r"impressum",
            r"imprint",
            r"rechtliches",
            r"pflichtangaben",
        ],
    ),
    (
        "team",
        [
            r"\bteam\b",
            r"ansprechpartner",
            r"mitarbeiter",
            r"ueber[\-\s_]*uns",
            r"über[\-\s_]*uns",
            r"unternehmen",
            r"wir[\-\s_]*ueber",
            r"kontakt",
            r"geschaeftsfuehrung",
        ],
    ),
    (
        "leistungen",
        [
            r"leistung",
            r"verwaltung",
            r"weg[\-\s_]*verwaltung",
            r"mietverwaltung",
            r"zinshaus",
            r"gewerbeverwaltung",
            r"angebot",
            r"service",
        ],
    ),
    (
        "referenzen",
        [
            r"referenz",
            r"objekte",
            r"bestand",
            r"portfolio",
            r"immobilienbestand",
        ],
    ),
    (
        "portal",
        [
            r"kundenportal",
            r"eigentuemerportal",
            r"mieterportal",
            r"login",
            r"schadensmeldung",
        ],
    ),
]


class AsyncWebsiteCrawler:
    """Crawls Berlin property management websites and German Impressum pages concurrently."""

    def __init__(self, db: Database, concurrency: Optional[int] = None) -> None:
        self.db = db
        self.concurrency = concurrency or settings.max_concurrent_crawls
        self.semaphore = asyncio.Semaphore(self.concurrency)

    @staticmethod
    async def _is_safe_url(url: str) -> bool:
        """Reject non-web schemes and non-public destinations to reduce SSRF risk."""
        try:
            parsed = urllib.parse.urlsplit(url)
            host = parsed.hostname
            if (
                parsed.scheme.lower() not in ("http", "https")
                or not host
                or parsed.username
                or parsed.password
            ):
                return False
            if settings.allow_private_crawler_targets:
                return True

            try:
                addresses = {ipaddress.ip_address(host)}
            except ValueError:
                port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
                results = await asyncio.get_running_loop().getaddrinfo(
                    host, port, type=socket.SOCK_STREAM
                )
                addresses = {ipaddress.ip_address(result[4][0]) for result in results}
            return bool(addresses) and all(address.is_global for address in addresses)
        except (OSError, ValueError):
            return False

    @staticmethod
    def html_to_clean_markdown(raw_html: str, page_type: str = "homepage") -> str:
        """
        Convert raw HTML into compact, structured Markdown.
        For 'impressum' and 'team' pages, combines trafilatura with selectolax body text
        so short legal address/Geschäftsführer blocks are never stripped as boilerplate.
        """
        if not raw_html:
            return ""

        traf_md = ""
        try:
            extracted = trafilatura.extract(
                raw_html,
                include_links=False,
                include_tables=True,
                no_fallback=False,
            )
            if extracted:
                traf_md = extracted.strip()
        except Exception:
            pass

        # Always extract clean visible DOM text for impressum/team or when trafilatura is short
        if page_type in ("impressum", "team") or len(traf_md) < 400:
            try:
                tree = HTMLParser(raw_html)
                for tag in tree.css("script, style, noscript, svg, path"):
                    tag.decompose()
                body = tree.css_first("main, article, body")
                raw_text = (
                    body.text(separator="\n") if body else tree.text(separator="\n")
                )
                lines = [
                    re.sub(r"\s+", " ", line).strip() for line in raw_text.splitlines()
                ]
                lines = [ln for ln in lines if len(ln) > 1]
                dom_text = "\n".join(lines)
                if len(dom_text) > len(traf_md):
                    return dom_text[:10000]
            except Exception:
                pass

        return traf_md[:10000]

    @staticmethod
    def discover_priority_subpages(
        raw_html: str, base_url: str, max_subpages: int = 5
    ) -> List[Tuple[str, str]]:
        """Discover internal links for impressum, team, leistungen, referenzen, and portal."""
        if not raw_html:
            return []

        parsed_base = urllib.parse.urlparse(base_url)
        base_host = parsed_base.netloc.lower().lstrip("www.")
        tree = HTMLParser(raw_html)

        candidates: Dict[str, List[str]] = {k: [] for k, _ in SUBPAGE_PRIORITY_RULES}
        seen_urls: Set[str] = {base_url.rstrip("/")}

        for a_el in tree.css("a[href]"):
            href = (a_el.attributes.get("href") or "").strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            full_url = urllib.parse.urljoin(base_url, href).split("#")[0].rstrip("/")
            parsed = urllib.parse.urlparse(full_url)
            host = parsed.netloc.lower().lstrip("www.")

            if host != base_host:
                continue
            if any(
                full_url.lower().endswith(ext)
                for ext in (".pdf", ".jpg", ".jpeg", ".png", ".zip", ".doc", ".docx")
            ):
                continue
            if full_url in seen_urls:
                continue

            anchor_and_path = f"{parsed.path.lower()} {(a_el.text() or '').lower()}"
            for page_type, patterns in SUBPAGE_PRIORITY_RULES:
                if any(re.search(p, anchor_and_path) for p in patterns):
                    candidates[page_type].append(full_url)
                    seen_urls.add(full_url)
                    break

        selected: List[Tuple[str, str]] = []
        # Always pick at least 1 from each priority category first
        for page_type, _ in SUBPAGE_PRIORITY_RULES:
            if candidates[page_type] and len(selected) < max_subpages:
                selected.append((page_type, candidates[page_type][0]))

        # Fill remaining slots if available (especially second team/kontakt or leistungen page)
        for page_type, _ in SUBPAGE_PRIORITY_RULES:
            for extra_url in candidates[page_type][1:2]:
                if len(selected) < max_subpages:
                    selected.append((page_type, extra_url))

        # If no impressum link was found in DOM, proactively probe /impressum
        if (
            not any(pt == "impressum" for pt, _ in selected)
            and len(selected) < max_subpages
        ):
            root = f"{parsed_base.scheme}://{parsed_base.netloc}"
            selected.insert(0, ("impressum", f"{root}/impressum"))

        return selected[:max_subpages]

    async def _fetch_page(
        self, client: httpx.AsyncClient, url: str
    ) -> Tuple[int, str, str]:
        """Return (status_code, final_url, html_text)."""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
        current_url = url
        try:
            for _ in range(6):
                if not await self._is_safe_url(current_url):
                    return 0, current_url, ""
                resp = await client.get(
                    current_url,
                    headers=headers,
                    timeout=settings.http_timeout_seconds,
                    follow_redirects=False,
                )
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        return resp.status_code, str(resp.url), ""
                    current_url = urllib.parse.urljoin(current_url, location)
                    continue

                content_type = resp.headers.get("content-type", "").lower()
                if (
                    "text/html" in content_type
                    or "application/xhtml" in content_type
                    or not content_type
                ):
                    return resp.status_code, str(resp.url), resp.text
                return resp.status_code, str(resp.url), ""
            return 0, current_url, ""
        except Exception:
            return 0, current_url, ""

    async def crawl_single_company(
        self, client: httpx.AsyncClient, company_id: int, website_url: str
    ) -> Dict[str, Any]:
        async with self.semaphore:
            status, final_home_url, home_html = await self._fetch_page(
                client, website_url
            )
            now_iso = datetime.now(timezone.utc).isoformat()
            pages_to_save: List[Dict[str, Any]] = []

            if status == 200 and home_html:
                tech = scan_html_for_tech_and_contacts(home_html)
                clean_md = self.html_to_clean_markdown(home_html, "homepage")
                pages_to_save.append(
                    {
                        "company_id": company_id,
                        "page_type": "homepage",
                        "url": final_home_url,
                        "http_status": status,
                        "clean_markdown": clean_md,
                        "detected_erp_csv": ", ".join(tech["erp_list"]),
                        "detected_metering_csv": ", ".join(tech["metering_list"]),
                        "has_portal_link": 1 if tech["has_portal"] else 0,
                        "social_linkedin_csv": ", ".join(tech["linkedin_urls"]),
                        "extracted_emails_csv": ", ".join(tech["emails"]),
                        "crawled_at": now_iso,
                    }
                )

                subpages = self.discover_priority_subpages(
                    home_html,
                    final_home_url,
                    max_subpages=settings.max_subpages_per_company,
                )
                for page_type, sub_url in subpages:
                    s_code, s_final_url, s_html = await self._fetch_page(
                        client, sub_url
                    )
                    if s_code == 200 and s_html:
                        s_tech = scan_html_for_tech_and_contacts(s_html)
                        s_md = self.html_to_clean_markdown(s_html, page_type)
                        pages_to_save.append(
                            {
                                "company_id": company_id,
                                "page_type": page_type,
                                "url": s_final_url,
                                "http_status": s_code,
                                "clean_markdown": s_md,
                                "detected_erp_csv": ", ".join(s_tech["erp_list"]),
                                "detected_metering_csv": ", ".join(
                                    s_tech["metering_list"]
                                ),
                                "has_portal_link": 1 if s_tech["has_portal"] else 0,
                                "social_linkedin_csv": ", ".join(
                                    s_tech["linkedin_urls"]
                                ),
                                "extracted_emails_csv": ", ".join(s_tech["emails"]),
                                "crawled_at": now_iso,
                            }
                        )
            else:
                # Record unreachable attempt so state machine can still advance
                pages_to_save.append(
                    {
                        "company_id": company_id,
                        "page_type": "homepage",
                        "url": website_url,
                        "http_status": status,
                        "clean_markdown": "",
                        "detected_erp_csv": "",
                        "detected_metering_csv": "",
                        "has_portal_link": 0,
                        "social_linkedin_csv": "",
                        "extracted_emails_csv": "",
                        "crawled_at": now_iso,
                    }
                )

            with self.db.connect() as conn:
                conn.execute(
                    "DELETE FROM crawled_pages WHERE company_id = ?", (company_id,)
                )
                for p in pages_to_save:
                    conn.execute(
                        """
                        INSERT INTO crawled_pages (
                            company_id, page_type, url, http_status, clean_markdown,
                            detected_erp_csv, detected_metering_csv, has_portal_link,
                            social_linkedin_csv, extracted_emails_csv, crawled_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            p["company_id"],
                            p["page_type"],
                            p["url"],
                            p["http_status"],
                            p["clean_markdown"],
                            p["detected_erp_csv"],
                            p["detected_metering_csv"],
                            p["has_portal_link"],
                            p["social_linkedin_csv"],
                            p["extracted_emails_csv"],
                            p["crawled_at"],
                        ),
                    )
                conn.execute(
                    "UPDATE companies_golden SET pipeline_stage = 'CRAWLED', updated_at = ? WHERE company_id = ?",
                    (now_iso, company_id),
                )

            return {
                "company_id": company_id,
                "pages_crawled": len(
                    [p for p in pages_to_save if p["http_status"] == 200]
                ),
                "reachable": status == 200,
            }

    async def crawl_batch(
        self,
        limit: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, int]:
        with self.db.connect() as conn:
            query = """
                SELECT company_id, website_url
                FROM companies_golden
                WHERE pipeline_stage = 'DEDUPED'
                ORDER BY is_vdiv_member DESC, source_count DESC, company_id ASC
            """
            if limit:
                query += f" LIMIT {int(limit)}"
            rows = conn.execute(query).fetchall()

        total = len(rows)
        if total == 0:
            return {
                "companies_processed": 0,
                "reachable_websites": 0,
                "total_pages_saved": 0,
            }

        reachable = 0
        pages_saved = 0
        completed = 0

        async with httpx.AsyncClient(http2=True, trust_env=False) as client:
            # Mark companies without website as CRAWLED immediately so they proceed to extraction/scoring
            no_web_ids = [r["company_id"] for r in rows if not r["website_url"]]
            if no_web_ids:
                now_iso = datetime.now(timezone.utc).isoformat()
                with self.db.connect() as conn:
                    for cid in no_web_ids:
                        conn.execute(
                            "UPDATE companies_golden SET pipeline_stage = 'CRAWLED', updated_at = ? WHERE company_id = ?",
                            (now_iso, cid),
                        )
                        completed += 1
                        if progress_callback:
                            progress_callback(completed, total)

            web_rows = [r for r in rows if r["website_url"]]
            tasks = [
                self.crawl_single_company(client, r["company_id"], r["website_url"])
                for r in web_rows
            ]
            for coro in asyncio.as_completed(tasks):
                res = await coro
                completed += 1
                if res["reachable"]:
                    reachable += 1
                pages_saved += res["pages_crawled"]
                if progress_callback:
                    progress_callback(completed, total)

        return {
            "companies_processed": total,
            "reachable_websites": reachable,
            "total_pages_saved": pages_saved,
        }
