"""
Scraper 1: Gelbe Seiten (gelbeseiten.de) Berlin Property Management Scraper.
Supports multi-keyword sharding, HTML card extraction (selectolax),
base64 website link decoding, JSON-LD parsing, and AJAX pagination (/ajaxsuche).
"""

from __future__ import annotations

import json
import re
from typing import List, Set
import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from heidi_engine.config import map_berlin_plz_to_district
from heidi_engine.models import RawListing
from heidi_engine.scrapers.base import BaseAsyncScraper

GELBE_SEITEN_KEYWORDS = [
    "hausverwaltung",
    "immobilienverwaltung",
    "weg-verwaltung",
    "mietverwaltung",
    "grundstuecksverwaltung",
]

BERLIN_DISTRICT_SHARDS = [
    "berlin",
    "berlin-charlottenburg",
    "berlin-wilmersdorf",
    "berlin-mitte",
    "berlin-pankow",
    "berlin-prenzlauer-berg",
    "berlin-friedrichshain",
    "berlin-kreuzberg",
    "berlin-steglitz",
    "berlin-zehlendorf",
    "berlin-schoeneberg",
    "berlin-tempelhof",
    "berlin-neukoelln",
    "berlin-spandau",
    "berlin-koepenick",
    "berlin-lichtenberg",
    "berlin-reinickendorf",
    "berlin-treptow",
    "berlin-tiergarten",
    "berlin-wedding",
    "berlin-halensee",
    "berlin-grunewald",
    "berlin-friedenau",
    "berlin-lichterfelde",
]


class GelbeSeitenScraper(BaseAsyncScraper):
    """Scrapes Berlin property management companies from GelbeSeiten.de."""

    source_name = "gelbe_seiten"

    def parse_html_cards(self, html_text: str, source_url: str) -> List[RawListing]:
        listings: List[RawListing] = []
        if not html_text:
            return listings

        tree = HTMLParser(html_text)

        # 1. Parse <article class="mod mod-Treffer"> cards
        for article in tree.css("article.mod-Treffer, article[id^='treffer_']"):
            ext_id = article.attributes.get("id") or article.attributes.get(
                "data-realid"
            )

            # Company Name
            h2 = article.css_first(
                "h2.mod-Treffer__name, h2[data-wipe-name='Titel'], h2"
            )
            name = self.clean_whitespace(h2.text()) if h2 else None
            if not name:
                continue

            # Address & PLZ
            addr_node = article.css_first(
                "div.mod-AdresseKompakt__adress-text, address, [data-wipe-name='Adresse']"
            )
            addr_text = self.clean_whitespace(addr_node.text()) if addr_node else ""
            plz_match = re.search(r"\b(1[0-4]\d{3})\b", addr_text)
            plz = plz_match.group(1) if plz_match else None

            street = None
            district = None
            if addr_text and plz:
                parts = addr_text.split(plz)
                street = self.clean_whitespace(parts[0].rstrip(", "))
                after_plz = parts[1] if len(parts) > 1 else ""
                dist_match = re.search(r"\(([^)]+)\)", after_plz)
                if dist_match:
                    district = self.clean_whitespace(dist_match.group(1))

            # Phone
            phone_node = article.css_first(
                "a.mod-TelefonnummerKompakt__phoneNumber, [data-wipe-name='Kontaktdaten'] a[href^='tel:'], span.mod-TelefonnummerKompakt__phoneNumber"
            )
            phone = None
            if phone_node:
                href = phone_node.attributes.get("href", "")
                if href.startswith("tel:"):
                    phone = href.replace("tel:", "").strip()
                else:
                    phone = self.clean_whitespace(phone_node.text())

            # Website URL (Direct or Base64 encoded in data-webseitelink / data-parameters)
            website = None
            web_node = article.css_first(
                "[data-webseitelink], a.mod-WebseiteKompakt__text, a.contains-icon-homepage, a.contains-icon-website"
            )
            if web_node:
                b64_attr = web_node.attributes.get("data-webseitelink")
                href_attr = web_node.attributes.get("href")
                if b64_attr:
                    website = self.decode_b64_url(b64_attr)
                elif (
                    href_attr
                    and href_attr.startswith("http")
                    and "gelbeseiten.de" not in href_attr
                ):
                    website = href_attr
                else:
                    # Sometimes base64 is in span[data-webseitelink]
                    inner_b64 = web_node.css_first("[data-webseitelink]")
                    if inner_b64:
                        website = self.decode_b64_url(
                            inner_b64.attributes.get("data-webseitelink")
                        )

            if not website:
                # Check any element inside article with data-webseitelink
                any_b64 = article.css_first("[data-webseitelink]")
                if any_b64:
                    website = self.decode_b64_url(
                        any_b64.attributes.get("data-webseitelink")
                    )

            # Detail URL
            detail_link = article.css_first("a[href*='gelbeseiten.de/gsbiz/']")
            detail_url = (
                detail_link.attributes.get("href") if detail_link else source_url
            )

            listings.append(
                RawListing(
                    source_name=self.source_name,
                    external_id=ext_id,
                    raw_company_name=name,
                    raw_street=street,
                    raw_postal_code=plz,
                    raw_city="Berlin",
                    raw_district=map_berlin_plz_to_district(plz, district),
                    raw_phone=phone,
                    raw_website=website,
                    source_url=detail_url,
                    raw_payload={"raw_address": addr_text},
                )
            )

        # 2. Also extract any JSON-LD LocalBusiness items embedded in page
        for script in tree.css("script[type='application/ld+json']"):
            raw_json = script.text()
            if not raw_json:
                continue
            try:
                data = json.loads(raw_json)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("@type") in (
                        "LocalBusiness",
                        "RealEstateAgent",
                        "Organization",
                    ):
                        name = self.clean_whitespace(item.get("name"))
                        if not name:
                            continue
                        addr = item.get("address") or {}
                        plz = addr.get("postalCode")
                        street = addr.get("streetAddress")
                        phone = item.get("telephone")
                        url = item.get("url")
                        if url and "gelbeseiten.de" in url:
                            url = None
                        listings.append(
                            RawListing(
                                source_name=self.source_name,
                                raw_company_name=name,
                                raw_street=street,
                                raw_postal_code=plz,
                                raw_city="Berlin",
                                raw_district=map_berlin_plz_to_district(plz),
                                raw_phone=phone,
                                raw_website=url,
                                source_url=source_url,
                                raw_payload={"ld_json": True},
                            )
                        )
            except Exception:
                continue

        return listings

    async def scrape_keyword(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        location: str = "berlin",
        max_ajax_batches: int = 8,
    ) -> List[RawListing]:
        results: List[RawListing] = []
        base_url = f"https://www.gelbeseiten.de/suche/{keyword}/{location}"
        html_text = await self.fetch_text(client, base_url)
        if not html_text:
            return results

        results.extend(self.parse_html_cards(html_text, base_url))

        # AJAX load-more batches (/ajaxsuche)
        position = 51
        for _ in range(max_ajax_batches):
            ajax_data = {
                "umkreis": "-1",
                "WAS": keyword,
                "WO": location,
                "position": str(position),
                "anzahl": "50",
                "sortierung": "relevanz",
            }
            resp_text = await self.fetch_text(
                client,
                "https://www.gelbeseiten.de/ajaxsuche",
                method="POST",
                data=ajax_data,
                referer=base_url,
            )
            if not resp_text:
                break
            html_chunk = resp_text
            try:
                parsed_json = json.loads(resp_text)
                if isinstance(parsed_json, dict) and "html" in parsed_json:
                    html_chunk = parsed_json["html"]
            except Exception:
                pass

            batch_cards = self.parse_html_cards(html_chunk, base_url)
            if not batch_cards:
                break
            results.extend(batch_cards)
            position += 50

        return results

    async def scrape_berlin(self, max_pages: int = 6) -> List[RawListing]:
        all_listings: List[RawListing] = []
        seen_keys: Set[str] = set()

        async with httpx.AsyncClient(http2=True) as client:
            # 1. City-wide multi-keyword sweep
            for kw in GELBE_SEITEN_KEYWORDS:
                kw_listings = await self.scrape_keyword(
                    client, kw, location="berlin", max_ajax_batches=max_pages
                )
                for item in kw_listings:
                    key = (
                        f"{item.raw_company_name.lower()}_{item.raw_postal_code or ''}"
                    )
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_listings.append(item)

            # 2. District-sharded sweep across all 23 Berlin Bezirke/Ortsteile
            district_tasks = [
                self.scrape_keyword(
                    client, "hausverwaltung", location=loc, max_ajax_batches=2
                )
                for loc in BERLIN_DISTRICT_SHARDS[1:]
            ]
            import asyncio

            for batch in await asyncio.gather(*district_tasks):
                for item in batch:
                    key = (
                        f"{item.raw_company_name.lower()}_{item.raw_postal_code or ''}"
                    )
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_listings.append(item)

        return all_listings
