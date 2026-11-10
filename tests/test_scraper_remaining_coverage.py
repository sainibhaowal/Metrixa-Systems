from __future__ import annotations

import base64

import pytest

from metrixa_engine.models import RawListing
from metrixa_engine.scrapers.dir_11880 import Dir11880Scraper
from metrixa_engine.scrapers.gelbe_seiten import GelbeSeitenScraper
from metrixa_engine.scrapers.vdiv import VDIVScraper


class _HttpContext:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


def test_11880_jsonld_shapes_and_card_enrichment():
    scraper = Dir11880Scraper()
    html = """
      <li class="result-list-entry"><h2>Incomplete GmbH</h2><address>Street Berlin</address></li>
      <li class="result-list-entry"><h2></h2></li>
      <li class="result-list-entry"><h2>Direct Site GmbH</h2><a class="result-list-entry-website" href="https://direct.invalid"></a></li>
      <script type="application/ld+json"></script>
      <script type="application/ld+json">["not an object"]</script>
      <script type="application/ld+json">{"@type":"ItemList","itemListElement":[
        {"item":{"@type":"LocalBusiness","name":"Incomplete GmbH","address":{"postalCode":"10115","streetAddress":"Added Street"},"telephone":"030 555"}},
        {"@type":"ProfessionalService","name":"Listed from ItemList","address":"invalid"},
        "not an object"]}</script>
      <script type="application/ld+json">{"@type":"Organization","name":"Direct JSON","address":{"postalCode":"10719"}}</script>
    """
    rows = scraper.parse_page(html, "https://directory.invalid/results")
    incomplete = next(row for row in rows if row.raw_company_name == "Incomplete GmbH")
    assert incomplete.raw_postal_code == "10115"
    assert incomplete.raw_street == "Added Street"
    assert incomplete.raw_phone == "030 555"
    direct = next(row for row in rows if row.raw_company_name == "Direct Site GmbH")
    assert direct.raw_website == "https://direct.invalid"
    assert {row.raw_company_name for row in rows} == {
        "Incomplete GmbH",
        "Direct Site GmbH",
        "Listed from ItemList",
        "Direct JSON",
    }


@pytest.mark.asyncio
async def test_11880_scrape_berlin_page_and_district_dedup_branches(monkeypatch):
    import metrixa_engine.scrapers.dir_11880 as module

    scraper = Dir11880Scraper()
    monkeypatch.setattr(module.httpx, "AsyncClient", _HttpContext)
    city_html = '<li class="result-list-entry"><h2>City GmbH</h2></li>'
    district_html = '<li class="result-list-entry"><h2>District GmbH</h2></li>'

    async def fetch(_client, url, **kwargs):
        if "/suche/hausverwaltung/berlin?" in url or url.endswith(
            "/suche/hausverwaltung/berlin"
        ):
            return city_html
        if "/suche/hausverwaltung/berlin?page=2" in url:
            return city_html  # duplicate page ends this keyword sweep
        if "/suche/immobilienverwaltung/berlin" in url:
            return "<html></html>"  # no cards stops the keyword
        if "berlin-charlottenburg" in url:
            return district_html
        if "/suche/hausverwaltung/berlin-" in url:
            return None
        return ""

    monkeypatch.setattr(scraper, "fetch_text", fetch)
    result = await scraper.scrape_berlin(max_pages=2)
    assert [row.raw_company_name for row in result] == ["City GmbH", "District GmbH"]


def test_gelbe_seiten_website_phone_and_jsonld_fallbacks():
    scraper = GelbeSeitenScraper()
    encoded = base64.b64encode(b"https://encoded.example").decode()
    html = f"""
      <article class="mod-Treffer"><h2>Direct Site GmbH</h2>
        <span class="mod-TelefonnummerKompakt__phoneNumber">030 111</span>
        <a class="mod-WebseiteKompakt__text" href="https://direct.example"></a></article>
      <article class="mod-Treffer"><h2>Nested Site GmbH</h2>
        <a class="contains-icon-homepage"><span data-webseitelink="{encoded}"></span></a></article>
      <article class="mod-Treffer" data-realid="fallback-id"><h2>Fallback ID GmbH</h2></article>
      <article class="mod-Treffer" data-webseitelink="%%%"><h2>Broken Site GmbH</h2></article>
      <article class="mod-Treffer"><h2></h2></article>
      <script type="application/ld+json"></script>
      <script type="application/ld+json">[null, {{"@type":"Organization"}},
        {{"@type":"LocalBusiness","name":""}},
        {{"@type":"RealEstateAgent","name":"Directory URL","url":"https://gelbeseiten.de/x","address":[]}}]</script>
    """
    rows = scraper.parse_html_cards(html, "https://gelbe.invalid/search")
    direct = next(row for row in rows if row.raw_company_name == "Direct Site GmbH")
    nested = next(row for row in rows if row.raw_company_name == "Nested Site GmbH")
    fallback = next(row for row in rows if row.raw_company_name == "Fallback ID GmbH")
    ld = next(row for row in rows if row.raw_company_name == "Directory URL")
    assert (
        direct.raw_phone == "030 111" and direct.raw_website == "https://direct.example"
    )
    assert nested.raw_website == "https://encoded.example"
    assert fallback.external_id == "fallback-id"
    assert ld.raw_website is None


@pytest.mark.asyncio
async def test_gelbe_seiten_scrape_keyword_unparseable_ajax_and_district_dedup(
    monkeypatch,
):
    import metrixa_engine.scrapers.gelbe_seiten as module

    scraper = GelbeSeitenScraper()
    calls = []

    async def fetch(_client, url, method="GET", **kwargs):
        calls.append((url, method))
        if method == "GET":
            return '<article class="mod-Treffer"><h2>Base GmbH</h2></article>'
        if len([call for call in calls if call[1] == "POST"]) == 1:
            return '<article class="mod-Treffer"><h2>Ajax GmbH</h2></article>'
        return "<html></html>"

    monkeypatch.setattr(scraper, "fetch_text", fetch)
    rows = await scraper.scrape_keyword(None, "hausverwaltung", max_ajax_batches=2)
    assert [row.raw_company_name for row in rows] == ["Base GmbH", "Ajax GmbH"]

    monkeypatch.setattr(module.httpx, "AsyncClient", _HttpContext)

    async def shard(_client, keyword, location="berlin", max_ajax_batches=8):
        name = (
            "Same GmbH"
            if location == "berlin" or location.endswith("charlottenburg")
            else f"{location} GmbH"
        )
        return [
            RawListing(
                source_name="gelbe_seiten",
                raw_company_name=name,
                raw_postal_code="10115",
            )
        ]

    monkeypatch.setattr(scraper, "scrape_keyword", shard)
    results = await scraper.scrape_berlin(max_pages=1)
    assert len(results) == len(module.BERLIN_DISTRICT_SHARDS) - 1

    calls.clear()
    scraper = GelbeSeitenScraper()

    async def empty_ajax(_client, url, method="GET", **kwargs):
        return (
            '<article class="mod-Treffer"><h2>One GmbH</h2></article>'
            if method == "GET"
            else None
        )

    monkeypatch.setattr(scraper, "fetch_text", empty_ajax)
    assert [
        r.raw_company_name
        for r in await scraper.scrape_keyword(None, "x", max_ajax_batches=1)
    ] == ["One GmbH"]


def test_module_cli_invokes_configured_uvicorn(monkeypatch):
    import runpy
    import uvicorn
    from metrixa_engine.config import settings

    calls = []
    monkeypatch.setattr(
        uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    runpy.run_module("metrixa_engine.__main__", run_name="__main__")
    assert calls == [
        (
            ("metrixa_engine.api.server:app",),
            {"host": settings.api_host, "port": settings.api_port, "reload": False},
        )
    ]


@pytest.mark.asyncio
async def test_vdiv_live_scrape_deduplicates_between_directory_pages(monkeypatch):
    import metrixa_engine.scrapers.vdiv as module

    scraper = VDIVScraper()
    monkeypatch.setattr(module.httpx, "AsyncClient", _HttpContext)
    first = "<article><h2>Alpha Verwaltung GmbH</h2><p>10115 Berlin</p></article>"
    second = "<article><h2>Alpha Verwaltung GmbH</h2><p>10115 Berlin</p></article><article><h2>Beta Verwaltung GmbH</h2><p>10719 Berlin</p></article>"

    async def fetch(client, url):
        return first if "vdiv-bb" in url else second

    monkeypatch.setattr(scraper, "fetch_text", fetch)
    rows = await scraper.scrape_berlin()
    assert [row.raw_company_name for row in rows] == [
        "Alpha Verwaltung GmbH",
        "Beta Verwaltung GmbH",
    ]


@pytest.mark.asyncio
async def test_overpass_skips_non_success_http_responses(monkeypatch):
    import metrixa_engine.scrapers.osm_overpass as module
    from metrixa_engine.scrapers.osm_overpass import OSMOverpassScraper

    class Response:
        status_code = 503

    class ClientContext:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(module.httpx, "AsyncClient", ClientContext)
    assert await OSMOverpassScraper().scrape_berlin() == []
