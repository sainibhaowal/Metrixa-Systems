"""
Scraper 5: Search Discovery Agent (Local SearXNG + Native Meta-Search + Tavily).
Discovers digital-first Berlin property management companies (WEG/Mietverwaltung)
via targeted German search dorks.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import List, Set

from metrixa_engine.config import map_berlin_plz_to_district
from metrixa_engine.enrichment.search_router import search_router
from metrixa_engine.models import RawListing
from metrixa_engine.scrapers.base import BaseAsyncScraper

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
        search_results_count = 0
        rejected_candidates = 0

        for query in BERLIN_SEARCH_DORKS:
            results = await search_router.search(
                query, max_results=10, allow_tavily_fallback=True
            )
            search_results_count += len(results)
            for item in results:
                parsed = urllib.parse.urlparse(item.url)
                host = (parsed.hostname or "").lower()
                if host.startswith("www."):
                    host = host[4:]
                if not host or any(
                    host == excluded or host.endswith(f".{excluded}")
                    for excluded in EXCLUDED_SEARCH_DOMAINS
                ):
                    rejected_candidates += 1
                    continue
                if host in seen_domains:
                    rejected_candidates += 1
                    continue
                seen_domains.add(host)

                # Clean title to extract company name
                raw_title = (
                    item.title.split("|")[0].split("-")[0].split(" - ")[0].strip()
                )
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

        if listings:
            self.last_diagnostic = (
                f"Accepted {len(listings)} unique company candidates from "
                f"{search_results_count} search results."
            )
        elif search_results_count:
            self.last_diagnostic = (
                f"Received {search_results_count} search results; "
                f"{rejected_candidates} were excluded or duplicated, and no candidates remained."
            )
        else:
            self.last_diagnostic = "The configured search provider chain returned no results for the targeted queries."
        return listings
