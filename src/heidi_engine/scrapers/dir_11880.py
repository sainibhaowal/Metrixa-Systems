"""
Scraper 2: 11880.com Berlin Property Management Directory Scraper.
Extracts structured JSON-LD (LocalBusiness) and HTML result cards across paginated Berlin queries.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional, Set
import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from heidi_engine.config import map_berlin_plz_to_district
from heidi_engine.entity_resolution.normalizer import (
    DIRECTORY_AND_SOCIAL_DOMAINS,
    FREEMAIL_DOMAINS,
    extract_canonical_domain,
)
from heidi_engine.models import RawListing
from heidi_engine.scrapers.base import BaseAsyncScraper

KEYWORDS_11880 = [
    "hausverwaltung",
    "immobilienverwaltung",
    "weg-verwaltung",
    "mietverwaltung",
    "grundstuecksverwaltung",
]

LOCATIONS_11880 = [
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
]


class Dir11880Scraper(BaseAsyncScraper):
    """Scrapes Berlin property management companies from 11880.com."""

    source_name = "11880"

    @staticmethod
    def decode_cloudflare_email(cf_href: str) -> Optional[str]:
        """
        Decode Cloudflare /cdn-cgi/l/email-protection#<hex> XOR-encoded email strings
        embedded on 11880.com listing cards.
        """
        if not cf_href or "email-protection#" not in cf_href:
            return None
        hex_part = cf_href.split("email-protection#", 1)[1].strip()
        if len(hex_part) < 6:
            return None
        try:
            key = int(hex_part[:2], 16)
            decoded_chars: List[str] = []
            for i in range(2, len(hex_part), 2):
                byte_val = int(hex_part[i : i + 2], 16) ^ key
                decoded_chars.append(chr(byte_val))
            decoded_str = "".join(decoded_chars)
            # Strip query params like ?subject=...
            email_clean = decoded_str.split("?", 1)[0].strip().lower()
            if "@" in email_clean and "." in email_clean.split("@", 1)[1]:
                return email_clean
        except Exception:
            pass
        return None

    def parse_page(self, html_text: str, page_url: str) -> List[RawListing]:
        listings: List[RawListing] = []
        if not html_text:
            return listings

        tree = HTMLParser(html_text)
        cards_by_name: dict[str, RawListing] = {}

        # 1. Parse HTML listing cards FIRST (contains Cloudflare email & phone buttons)
        for card in tree.css(
            "li.result-list-entry, article.result-list-entry, div.result-list-entry"
        ):
            title_el = card.css_first(
                "h2, .result-list-entry-title, a.result-list-entry-title__link"
            )
            name = self.clean_whitespace(title_el.text()) if title_el else None
            if not name:
                continue

            addr_el = card.css_first(".result-list-entry-address, address")
            addr_text = self.clean_whitespace(addr_el.text()) if addr_el else ""
            plz_match = re.search(r"\b(1[0-4]\d{3})\b", addr_text)
            plz = plz_match.group(1) if plz_match else None
            street = None
            if addr_text and plz:
                street = self.clean_whitespace(addr_text.split(plz)[0].rstrip(", "))

            phone_el = card.css_first("a[href^='tel:'], .result-list-entry-phone")
            phone = None
            if phone_el:
                href = phone_el.attributes.get("href", "")
                phone = (
                    href.replace("tel:", "").strip()
                    if href.startswith("tel:")
                    else self.clean_whitespace(phone_el.text())
                )

            # Decode Cloudflare protected email if present
            email = None
            cf_el = card.css_first("a.tracking-mail-to, a[href*='email-protection']")
            if cf_el:
                email = self.decode_cloudflare_email(cf_el.attributes.get("href", ""))

            web_el = card.css_first(
                "a.result-list-entry-website, a[data-action='website'], a[target='_blank'][rel*='noopener']"
            )
            website = None
            if web_el:
                href = web_el.attributes.get("href", "")
                if href.startswith("http") and "11880.com" not in href:
                    website = href

            # Derive corporate website URL from corporate email domain when not freemail
            if not website and email:
                corp_dom = extract_canonical_domain(None, email)
                if (
                    corp_dom
                    and corp_dom not in FREEMAIL_DOMAINS
                    and corp_dom not in DIRECTORY_AND_SOCIAL_DOMAINS
                ):
                    website = f"https://www.{corp_dom}"

            listing_obj = RawListing(
                source_name=self.source_name,
                raw_company_name=name,
                raw_street=street,
                raw_postal_code=plz,
                raw_city="Berlin",
                raw_district=map_berlin_plz_to_district(plz),
                raw_phone=phone,
                raw_email=email,
                raw_website=website,
                source_url=page_url,
                raw_payload={"raw_address": addr_text},
            )
            cards_by_name[name.lower()] = listing_obj
            listings.append(listing_obj)

        # 2. Enrich or append from JSON-LD structured business entries
        for script in tree.css("script[type='application/ld+json']"):
            raw_json = script.text()
            if not raw_json:
                continue
            try:
                data = json.loads(raw_json)
                candidates = []
                if isinstance(data, list):
                    candidates.extend(data)
                elif isinstance(data, dict):
                    if data.get("@type") == "ItemList" and "itemListElement" in data:
                        for el in data.get("itemListElement", []):
                            if isinstance(el, dict) and "item" in el:
                                candidates.append(el["item"])
                            elif isinstance(el, dict):
                                candidates.append(el)
                    else:
                        candidates.append(data)

                for item in candidates:
                    if not isinstance(item, dict):
                        continue
                    item_type = str(item.get("@type", ""))
                    if not any(
                        t in item_type
                        for t in (
                            "LocalBusiness",
                            "RealEstateAgent",
                            "Organization",
                            "ProfessionalService",
                        )
                    ):
                        continue
                    name = self.clean_whitespace(item.get("name"))
                    if not name or name.lower() == "11880.com":
                        continue

                    addr = item.get("address") or {}
                    if not isinstance(addr, dict):
                        addr = {}
                    plz = addr.get("postalCode")
                    street = addr.get("streetAddress")
                    phone = item.get("telephone")

                    if name.lower() in cards_by_name:
                        existing = cards_by_name[name.lower()]
                        if not existing.raw_postal_code and plz:
                            existing.raw_postal_code = plz
                            existing.raw_district = map_berlin_plz_to_district(plz)
                        if not existing.raw_street and street:
                            existing.raw_street = street
                        if not existing.raw_phone and phone:
                            existing.raw_phone = phone
                    else:
                        listings.append(
                            RawListing(
                                source_name=self.source_name,
                                raw_company_name=name,
                                raw_street=street,
                                raw_postal_code=plz,
                                raw_city="Berlin",
                                raw_district=map_berlin_plz_to_district(plz),
                                raw_phone=phone,
                                source_url=page_url,
                                raw_payload={"source_method": "json_ld"},
                            )
                        )
            except Exception:
                continue

        return listings

    async def scrape_berlin(self, max_pages: int = 8) -> List[RawListing]:
        all_listings: List[RawListing] = []
        seen_keys: Set[str] = set()

        async with httpx.AsyncClient(http2=True) as client:
            for kw in KEYWORDS_11880:
                for page_num in range(1, max_pages + 1):
                    url = (
                        f"https://www.11880.com/suche/{kw}/berlin"
                        if page_num == 1
                        else f"https://www.11880.com/suche/{kw}/berlin?page={page_num}"
                    )
                    html_text = await self.fetch_text(client, url)
                    if not html_text:
                        break
                    cards = self.parse_page(html_text, url)
                    if not cards:
                        break
                    new_on_page = 0
                    for item in cards:
                        key = f"{item.raw_company_name.lower()}_{item.raw_postal_code or ''}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_listings.append(item)
                            new_on_page += 1
                    if new_on_page == 0:
                        break

            # District sweep across Berlin Bezirke
            for loc in LOCATIONS_11880[1:]:
                url = f"https://www.11880.com/suche/hausverwaltung/{loc}"
                html_text = await self.fetch_text(client, url)
                if not html_text:
                    continue
                for item in self.parse_page(html_text, url):
                    key = (
                        f"{item.raw_company_name.lower()}_{item.raw_postal_code or ''}"
                    )
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_listings.append(item)

        return all_listings
