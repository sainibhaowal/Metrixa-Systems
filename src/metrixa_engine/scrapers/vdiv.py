"""
Scraper 3: VDIV Berlin-Brandenburg (Verband der Immobilienverwalter) Scraper.
Scrapes public member directory pages and returns only records parsed from the live response.
"""

from __future__ import annotations

import re
from typing import List, Set
import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from metrixa_engine.config import map_berlin_plz_to_district
from metrixa_engine.models import RawListing
from metrixa_engine.scrapers.base import BaseAsyncScraper


class VDIVScraper(BaseAsyncScraper):
    """Scrapes records returned by the VDIV Berlin-Brandenburg public directory."""

    source_name = "vdiv"

    def parse_vdiv_html(self, html_text: str, source_url: str) -> List[RawListing]:
        results: List[RawListing] = []
        if not html_text:
            return results

        tree = HTMLParser(html_text)
        for card in tree.css(
            ".member-item, .verwalter-item, .directory-entry, article, .card"
        ):
            text_block = card.text(separator=" ")
            plz_match = re.search(
                r"\b(1[0-4]\d{3})\s+Berlin", text_block, re.IGNORECASE
            )
            if not plz_match:
                continue
            plz = plz_match.group(1)

            h_el = card.css_first("h2, h3, h4, strong, .title")
            name = self.clean_whitespace(h_el.text()) if h_el else None
            if not name or len(name) < 4:
                continue

            web_el = card.css_first("a[href^='http']")
            website = None
            if web_el:
                href = web_el.attributes.get("href", "")
                if "vdiv" not in href.lower():
                    website = href

            mail_el = card.css_first("a[href^='mailto:']")
            email = (
                mail_el.attributes.get("href", "").replace("mailto:", "").strip()
                if mail_el
                else None
            )

            tel_el = card.css_first("a[href^='tel:']")
            phone = (
                tel_el.attributes.get("href", "").replace("tel:", "").strip()
                if tel_el
                else None
            )

            results.append(
                RawListing(
                    source_name=self.source_name,
                    raw_company_name=name,
                    raw_postal_code=plz,
                    raw_city="Berlin",
                    raw_district=map_berlin_plz_to_district(plz),
                    raw_phone=phone,
                    raw_email=email,
                    raw_website=website,
                    source_url=source_url,
                    is_vdiv_member=True,
                )
            )
        return results

    async def scrape_berlin(self, max_pages: int = 5) -> List[RawListing]:
        listings: List[RawListing] = []
        seen: Set[str] = set()

        # 1. Try live VDIV Berlin-Brandenburg member directory pages
        vdiv_urls = [
            "https://vdiv-bb.de/verwaltersuche",
            "https://vdiv.de/verwaltersuche?plz=10115&ort=Berlin",
        ]
        async with httpx.AsyncClient(http2=True) as client:
            for url in vdiv_urls:
                html_text = await self.fetch_text(client, url)
                if html_text:
                    for item in self.parse_vdiv_html(html_text, url):
                        key = item.raw_company_name.lower()
                        if key not in seen:
                            seen.add(key)
                            listings.append(item)

        return listings
