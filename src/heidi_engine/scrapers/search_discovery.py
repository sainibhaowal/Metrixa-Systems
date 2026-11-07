"""
Scraper 5: Search Discovery Agent (Local SearXNG + Native Meta-Search + Tavily).
Discovers digital-first Berlin property management companies (WEG/Mietverwaltung)
via targeted German search dorks.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import List, Set

from heidi_engine.config import map_berlin_plz_to_district
from heidi_engine.enrichment.search_router import search_router
from heidi_engine.models import RawListing
from heidi_engine.scrapers.base import BaseAsyncScraper


BERLIN_SEARCH_DORKS = [
    '"Hausverwaltung" "Berlin" "Impressum" "GmbH"',
    '"WEG-Verwaltung" "Berlin" "Wohneinheiten" "GmbH"',
    '"Mietverwaltung" "Berlin" "Kundenportal" "Hausverwaltung"',
    '"Immobilienverwaltung" "Berlin" "Geschäftsführer" "HRB"',
    '"Hausverwaltung" "Berlin" ("Casavi" OR "etg24" OR "Domus")',
]

EXCLUDED_SEARCH_DOMAINS = {
    "gelbeseiten.de",
    "11880.com",
    "dasoertliche.de",
    "immobilienscout24.de",
    "immowelt.de",
    "kleinanzeigen.de",
    "wikipedia.org",
    "linkedin.com",
    "xing.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "northdata.de",
    "companyhouse.de",
    "kununu.com",
    "stepstone.de",
    "indeed.com",
    "anwalt.de",
    "berlin.de",
}


class SearchDiscoveryScraper(BaseAsyncScraper):
    """Discovers Berlin property managers via SearXNG / Meta-Search / Tavily dorks."""

    source_name = "searxng_discovery"

    async def scrape_berlin(self, max_pages: int = 1) -> List[RawListing]:
        listings: List[RawListing] = []
        seen_domains: Set[str] = set()

        for query in BERLIN_SEARCH_DORKS:
            results = await search_router.search(
                query, max_results=10, allow_tavily_fallback=False
            )
            for item in results:
                parsed = urllib.parse.urlparse(item.url)
                host = parsed.netloc.lower().lstrip("www.")
                if not host or any(excl in host for excl in EXCLUDED_SEARCH_DOMAINS):
                    continue
                if host in seen_domains:
                    continue
                seen_domains.add(host)

                # Clean title to extract company name
                raw_title = item.title.split("|")[0].split("–")[0].split(" - ")[0].strip()
                if len(raw_title) < 4 or len(raw_title) > 110:
                    raw_title = host

                # Look for Berlin PLZ in snippet
                plz_match = re.search(r"\b(1[0-4]\d{3})\b", item.snippet)
                plz = plz_match.group(1) if plz_match else None

                root_url = f"{parsed.scheme}://{parsed.netloc}"
                listings.append(
                    RawListing(
                        source_name=self.source_name,
                        raw_company_name=raw_title,
                        raw_postal_code=plz,
                        raw_city="Berlin",
                        raw_district=map_berlin_plz_to_district(plz),
                        raw_website=root_url,
                        source_url=item.url,
                        raw_payload={"snippet": item.snippet, "engine": item.engine},
                    )
                )

        return listings

