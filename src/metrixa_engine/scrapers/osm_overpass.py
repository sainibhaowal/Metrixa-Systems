"""
Scraper 4: OpenStreetMap Overpass API Berlin Property Management Scraper.
Queries Berlin geospatial bounding box (52.338,13.088,52.675,13.761) for
office=property_management and Hausverwaltung/Immobilienverwaltung nodes & ways.
"""

from __future__ import annotations

from typing import List, Set
import httpx

from metrixa_engine.config import map_berlin_plz_to_district
from metrixa_engine.models import RawListing
from metrixa_engine.scrapers.base import BaseAsyncScraper

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    # Europe extract, updated daily; fallback for primary public-server load shedding.
    "https://ovp.dresel.systems/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

BERLIN_OVERPASS_QUERY = """
[out:json][timeout:45];
(
  node["office"="property_management"](52.338,13.088,52.675,13.761);
  way["office"="property_management"](52.338,13.088,52.675,13.761);
  node["name"~"Hausverwaltung|Immobilienverwaltung|WEG-Verwaltung|Mietverwaltung|Grundstücksverwaltung",i](52.338,13.088,52.675,13.761);
  way["name"~"Hausverwaltung|Immobilienverwaltung|WEG-Verwaltung|Mietverwaltung|Grundstücksverwaltung",i](52.338,13.088,52.675,13.761);
);
out center tags;
"""


class OSMOverpassScraper(BaseAsyncScraper):
    """Queries OpenStreetMap Overpass API for property management companies in Berlin."""

    source_name = "osm"

    async def scrape_berlin(self, max_pages: int = 1) -> List[RawListing]:
        listings: List[RawListing] = []
        seen_ids: Set[str] = set()
        endpoint_results: List[str] = []
        successful_responses = 0
        successful_endpoint = None

        async with httpx.AsyncClient(timeout=45.0) as client:
            for endpoint in OVERPASS_ENDPOINTS:
                host = endpoint.split("/")[2]
                try:
                    resp = await client.post(
                        endpoint,
                        data={"data": BERLIN_OVERPASS_QUERY},
                        headers={"User-Agent": "MetrixaEngine-BerlinResearch/1.0"},
                    )
                    if resp.status_code != 200:
                        endpoint_results.append(
                            f"{host} returned HTTP {resp.status_code}"
                        )
                        continue
                    payload = resp.json()
                    elements = payload.get("elements", [])
                    successful_responses += 1
                    endpoint_results.append(
                        f"{host} returned {len(elements)} map elements"
                    )
                    for el in elements:
                        osm_id = f"{el.get('type', 'node')}_{el.get('id')}"
                        if osm_id in seen_ids:
                            continue
                        seen_ids.add(osm_id)

                        tags = el.get("tags") or {}
                        name = self.clean_whitespace(
                            tags.get("name")
                            or tags.get("operator")
                            or tags.get("official_name")
                        )
                        if not name:
                            continue

                        street = tags.get("addr:street")
                        housenumber = tags.get("addr:housenumber")
                        full_street = (
                            f"{street} {housenumber}".strip()
                            if street and housenumber
                            else street
                        )
                        plz = tags.get("addr:postcode")
                        city = tags.get("addr:city", "Berlin")
                        suburb = tags.get("addr:suburb") or tags.get("addr:borough")

                        phone = (
                            tags.get("contact:phone")
                            or tags.get("phone")
                            or tags.get("contact:mobile")
                        )
                        email = tags.get("contact:email") or tags.get("email")
                        website = (
                            tags.get("contact:website")
                            or tags.get("website")
                            or tags.get("url")
                        )

                        listings.append(
                            RawListing(
                                source_name=self.source_name,
                                external_id=osm_id,
                                raw_company_name=name,
                                raw_street=full_street,
                                raw_postal_code=plz,
                                raw_city=city,
                                raw_district=map_berlin_plz_to_district(plz, suburb),
                                raw_phone=phone,
                                raw_email=email,
                                raw_website=website,
                                source_url=f"https://www.openstreetmap.org/{el.get('type', 'node')}/{el.get('id')}",
                                raw_payload={"tags": tags},
                            )
                        )
                    if listings:
                        successful_endpoint = host
                        break
                except Exception as exc:
                    endpoint_results.append(
                        f"{host} request failed ({type(exc).__name__})"
                    )
                    continue

        if listings:
            self.last_diagnostic = f"Overpass returned {len(listings)} named Berlin company records via {successful_endpoint}."
        elif successful_responses:
            self.last_diagnostic = (
                "Overpass responded, but no matching named company records were found. "
                + "; ".join(endpoint_results)
            )
        else:
            self.last_diagnostic = (
                "No Overpass endpoint returned a usable response. "
                + "; ".join(endpoint_results)
            )
        return listings
