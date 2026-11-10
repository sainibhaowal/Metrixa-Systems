from __future__ import annotations

import base64
import json

import pytest

from metrixa_engine.crawler.url_resolver import MissingURLResolver
from metrixa_engine.enrichment.search_router import SearchResultItem
from metrixa_engine.scrapers.base import BaseAsyncScraper
from metrixa_engine.scrapers.dir_11880 import Dir11880Scraper
from metrixa_engine.scrapers.gelbe_seiten import GelbeSeitenScraper
from metrixa_engine.scrapers.osm_overpass import OSMOverpassScraper
from metrixa_engine.scrapers.search_discovery import SearchDiscoveryScraper
from metrixa_engine.scrapers.vdiv import VDIVScraper


class _Response:
    def __init__(self, status_code=200, text="ok", payload=None, headers=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}
        self.headers = headers or {}
        self.url = "https://example.org/page"

    def json(self):
        return self._payload


class _Context:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, *args):
        return None


@pytest.mark.asyncio
async def test_base_scraper_helpers_and_http_retry_paths(monkeypatch):
    import metrixa_engine.scrapers.base as module

    scraper = BaseAsyncScraper(delay_range=(0, 0))
    assert "Referer" not in scraper.get_headers()
    assert (
        scraper.get_headers("https://ref.example")["Referer"] == "https://ref.example"
    )
    assert scraper.decode_b64_url(None) is None
    assert scraper.decode_b64_url("https://direct.example") == "https://direct.example"
    encoded = base64.b64encode(b"https://decoded.example").decode().rstrip("=")
    assert scraper.decode_b64_url(encoded) == "https://decoded.example"
    assert scraper.decode_b64_url("not base64!") is None
    assert scraper.clean_whitespace(None) is None
    assert scraper.clean_whitespace("  a\n b  ") == "a b"
    assert scraper.clean_whitespace(" \n ") is None
    with pytest.raises(NotImplementedError):
        await scraper.scrape_berlin()

    sleeps = []
    monkeypatch.setattr(module.asyncio, "sleep", lambda n: _async_append(sleeps, n))

    class Client:
        def __init__(self, outcomes):
            self.outcomes = iter(outcomes)

        async def get(self, *args, **kwargs):
            value = next(self.outcomes)
            if isinstance(value, Exception):
                raise value
            return value

        async def post(self, *args, **kwargs):
            value = next(self.outcomes)
            if isinstance(value, Exception):
                raise value
            return value

    assert await scraper.fetch_text(Client([_Response()]), "https://x") == "ok"
    assert (
        await scraper.fetch_text(
            Client([_Response(503), _Response(200, "retried")]), "https://x"
        )
        == "retried"
    )
    assert (
        await scraper.fetch_text(
            Client([_Response(404), _Response(404), _Response(404)]), "https://x"
        )
        is None
    )
    assert (
        await scraper.fetch_text(
            Client([OSError(), _Response(200, "after exception")]), "https://x"
        )
        == "after exception"
    )
    assert (
        await scraper.fetch_text(
            Client([_Response(200, "posted")]),
            "https://x",
            method="POST",
            data={"a": "b"},
            referer="https://r",
        )
        == "posted"
    )
    assert sleeps  # both retry and exception waits were exercised


async def _async_append(target, value):
    target.append(value)


def test_11880_parses_cards_jsonld_and_invalid_payloads():
    scraper = Dir11880Scraper()
    assert scraper.parse_page("", "https://11880.example") == []
    assert scraper.decode_cloudflare_email("") is None
    assert scraper.decode_cloudflare_email("/cdn-cgi/l/email-protection#bad") is None
    assert scraper.decode_cloudflare_email("/cdn-cgi/l/email-protection#zzzzzz") is None
    email = "m.mueller@firma.de"
    key = 42
    encoded = f"{key:02x}" + "".join(f"{ord(ch)^key:02x}" for ch in email)
    assert (
        scraper.decode_cloudflare_email("/cdn-cgi/l/email-protection#" + encoded)
        == email
    )
    html = f"""<ul><li class="result-list-entry">
      <h2>Firma Hausverwaltung GmbH</h2><address>Uhlandstr. 1, 10719 Berlin</address>
      <a href="tel:+4930123">phone</a><a class="tracking-mail-to" href="/cdn-cgi/l/email-protection#{encoded}">email</a>
      </li><li class="result-list-entry"><h2>Freemail GmbH</h2><address>Berlin</address>
          <a class="tracking-mail-to" href="/cdn-cgi/l/email-protection#{(f'{key:02x}' + ''.join(f'{ord(ch)^key:02x}' for ch in 'm.mueller@gmail.com'))}">mail</a>
      <a class="result-list-entry-website" href="https://11880.com/out">out</a></li></ul>
      <script type="application/ld+json">{json.dumps([
        {"@type":"LocalBusiness","name":"Firma Hausverwaltung GmbH","address":{"postalCode":"10719","streetAddress":"Other St"},"telephone":"030 999"},
        {"@type":"RealEstateAgent","name":"JSON Firma GmbH","address":{"postalCode":"10115","streetAddress":"New St"},"telephone":"030 555"},
        {"@type":"Organization","name":"11880.com"}, {"@type":"Thing","name":"Ignored"}
      ])}</script>
      <script type="application/ld+json">{{bad json}}</script>"""
    rows = scraper.parse_page(html, "https://11880.example/page")
    assert len(rows) == 3
    assert rows[0].raw_phone == "+4930123"
    assert rows[0].raw_postal_code == "10719"
    assert rows[0].raw_website == "https://www.firma.de"
    assert rows[1].raw_website is None
    assert rows[2].raw_payload == {"source_method": "json_ld"}


@pytest.mark.asyncio
async def test_11880_scrape_breaks_and_deduplicates(monkeypatch):
    scraper = Dir11880Scraper()

    # one result on the first page, duplicate on subsequent keyword and district sweeps
    async def fetch(client, url, **kwargs):
        if "hausverwaltung" in url:
            return '<li class="result-list-entry"><h2>Unique GmbH</h2></li>'
        return ""

    monkeypatch.setattr(scraper, "fetch_text", fetch)
    result = await scraper.scrape_berlin(max_pages=1)
    assert len(result) == 1
    assert result[0].raw_company_name == "Unique GmbH"


def test_gelbe_seiten_parses_html_jsonld_and_invalid_json():
    scraper = GelbeSeitenScraper()
    assert scraper.parse_html_cards("", "https://gs.example") == []
    encoded = base64.b64encode(b"https://official.example").decode()
    html = f"""<article class="mod-Treffer" id="treffer_1">
      <h2 class="mod-Treffer__name">Alpha GmbH</h2><address>Street 1, 10719 Berlin (Charlottenburg)</address>
      <a class="mod-TelefonnummerKompakt__phoneNumber" href="tel:+4930">call</a><a data-webseitelink="{encoded}"></a>
      <a href="https://www.gelbeseiten.de/gsbiz/alpha">details</a></article>
      <article class="mod-Treffer"><h2>no postcode</h2><address>Berlin</address></article>
      <script type="application/ld+json">{json.dumps([
      {"@type":"LocalBusiness","name":"JSON One","address":{"postalCode":"10115","streetAddress":"Main"},"telephone":"030","url":"https://one.example"},
      {"@type":"Organization","name":"Directory","url":"https://gelbeseiten.de/x"}, {"@type":"Thing","name":"ignore"}, {"@type":"RealEstateAgent","name":"No Address","address":None}
      ])}</script><script type="application/ld+json">{{invalid}}</script>"""
    rows = scraper.parse_html_cards(html, "https://gs.example")
    assert len(rows) == 6
    assert rows[0].raw_website == "https://official.example"
    assert rows[0].raw_phone == "+4930"
    assert rows[0].source_url.endswith("/gsbiz/alpha")
    json_one = next(row for row in rows if row.raw_company_name == "JSON One")
    directory = next(row for row in rows if row.raw_company_name == "Directory")
    assert json_one.raw_website == "https://one.example"
    assert directory.raw_website is None


@pytest.mark.asyncio
async def test_gelbe_seiten_keyword_ajax_shapes_and_stop(monkeypatch):
    scraper = GelbeSeitenScraper()
    calls = []

    async def fetch(client, url, method="GET", **kwargs):
        calls.append((url, method, kwargs.get("data")))
        if method == "GET":
            return '<article class="mod-Treffer"><h2>Alpha GmbH</h2></article>'
        if len([c for c in calls if c[1] == "POST"]) == 1:
            return json.dumps(
                {"html": '<article class="mod-Treffer"><h2>Beta GmbH</h2></article>'}
            )
        return "<html></html>"

    monkeypatch.setattr(scraper, "fetch_text", fetch)
    rows = await scraper.scrape_keyword(None, "hausverwaltung", max_ajax_batches=4)
    assert [r.raw_company_name for r in rows] == ["Alpha GmbH", "Beta GmbH"]
    assert calls[1][1] == "POST" and calls[1][2]["position"] == "51"

    async def unavailable(*args, **kwargs):
        return None

    monkeypatch.setattr(scraper, "fetch_text", unavailable)
    assert await scraper.scrape_keyword(None, "x") == []


@pytest.mark.asyncio
async def test_osm_overpass_retries_endpoint_and_parses_tag_variants(monkeypatch):
    import metrixa_engine.scrapers.osm_overpass as module

    responses = iter(
        [
            OSError("primary Overpass endpoint unavailable"),
            _Response(
                payload={
                    "elements": [
                        {
                            "type": "node",
                            "id": 1,
                            "tags": {
                                "name": "Alpha Verwaltung GmbH",
                                "addr:street": "Main",
                                "addr:housenumber": "2",
                                "addr:postcode": "10115",
                                "contact:phone": "030",
                                "contact:email": "a@x.de",
                                "contact:website": "https://x.de",
                                "addr:suburb": "Mitte",
                            },
                        },
                        {"type": "node", "id": 1, "tags": {"name": "duplicate"}},
                        {
                            "type": "way",
                            "id": 2,
                            "tags": {
                                "operator": "Beta Verwaltung GmbH",
                                "addr:street": "Side",
                            },
                        },
                        {"type": "node", "id": 3, "tags": {"official_name": ""}},
                        {"type": "node", "id": 4, "tags": {}},
                    ]
                }
            ),
        ]
    )

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, *a, **kw):
            response = next(responses)
            if isinstance(response, Exception):
                raise response
            return response

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeClient)
    scraper = OSMOverpassScraper()
    rows = await scraper.scrape_berlin()
    assert len(rows) == 2
    assert scraper.last_diagnostic == (
        "Overpass returned 2 named Berlin company records via ovp.dresel.systems."
    )
    assert rows[0].raw_street == "Main 2"
    assert rows[0].raw_website == "https://x.de"
    assert rows[1].raw_company_name == "Beta Verwaltung GmbH"


@pytest.mark.asyncio
async def test_search_discovery_filters_deduplicates_and_falls_back_to_host(
    monkeypatch,
):
    import metrixa_engine.scrapers.search_discovery as module

    answers = [
        SearchResultItem(
            "Good Verwaltung GmbH | Home",
            "https://www.good.example/path",
            "Berlin 10719",
            "test",
        ),
        SearchResultItem(
            "duplicate", "https://good.example/other", "Berlin 10115", "test"
        ),
        SearchResultItem("directory", "https://gelbeseiten.de/x", "Berlin", "test"),
        SearchResultItem("x", "https://x.example", "no postcode", "test"),
        SearchResultItem("a", "https://short.example", "", "test"),
        SearchResultItem("x", "https://www.wwww.example/path", "", "test"),
    ]

    search_calls = []

    async def search(*args, **kwargs):
        search_calls.append((args, kwargs))
        return answers

    monkeypatch.setattr(module.search_router, "search", search)
    scraper = SearchDiscoveryScraper()
    rows = await scraper.scrape_berlin()
    assert len(rows) == 4
    assert "Accepted 4 unique company candidates" in scraper.last_diagnostic
    assert rows[0].raw_company_name == "Good Verwaltung GmbH"
    assert rows[0].raw_postal_code == "10719"
    assert rows[2].raw_company_name == "short.example"
    assert rows[3].raw_company_name == "wwww.example"
    assert search_calls and all(
        call[1]["allow_tavily_fallback"] is True for call in search_calls
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        ([], "provider chain returned no results"),
        (
            [SearchResultItem("Directory", "https://gelbeseiten.de/x", "", "test")],
            "no candidates remained",
        ),
    ],
)
async def test_search_discovery_reports_empty_and_excluded_results(
    monkeypatch, answers, expected
):
    import metrixa_engine.scrapers.search_discovery as module

    async def search(*args, **kwargs):
        return answers

    monkeypatch.setattr(module.search_router, "search", search)
    scraper = SearchDiscoveryScraper()

    assert await scraper.scrape_berlin() == []
    assert expected in scraper.last_diagnostic


def test_vdiv_parse_live_cards_filters_bad_cards():
    scraper = VDIVScraper()
    assert scraper.parse_vdiv_html("", "https://vdiv.example") == []
    html = """<article><h2>Alpha Verwaltung GmbH</h2><p>Uhlandstr. 1, 10719 Berlin</p>
      <a href="https://alpha.example">web</a><a href="mailto:a@alpha.example">mail</a><a href="tel:030123">phone</a></article>
      <article><h2>No PLZ GmbH</h2><p>Hamburg</p></article>
      <article><h2>Bad</h2><p>10719 Berlin</p></article>
      <article><h2>VDIV House GmbH</h2><p>10115 Berlin</p><a href="https://vdiv-bb.de/members">vdiv</a></article>"""
    rows = scraper.parse_vdiv_html(html, "https://vdiv.example")
    assert len(rows) == 2
    assert rows[0].raw_email == "a@alpha.example"
    assert rows[0].raw_phone == "030123"
    assert rows[1].raw_website is None


def test_vdiv_member_directory_parses_only_berlin_entries():
    scraper = VDIVScraper()
    html = """
    <div class="contact-list-contact-container">
      <span class="contact-list-contact-name">Alpha Hausverwaltung GmbH</span>
      <div class="contact-list-address">
        <span class="contact-list-address-line-1">Example Str. 1</span>
        <span class="contact-list-address-country-and-state">10115 Berlin</span>
      </div>
      <span class="contact-list-email"><a href="mailto:info@alpha.example?subject=test">mail</a></span>
      <span class="contact-list-phone"><a href="tel:+4930123456">phone</a></span>
      <div class="contact-list-custom-field-1">
        <span class="contact-list-custom-field-title">Internet</span>
        <span class="contact-list-custom-field-value"><a href="https://alpha.example">web</a></span>
      </div>
    </div>
    <div class="contact-list-contact-container">
      <span class="contact-list-contact-name">Beta Hausverwaltung GmbH</span>
      <div class="contact-list-address">
        <span class="contact-list-address-country-and-state">10719 Berlin</span>
      </div>
      <div class="contact-list-custom-field-1">
        <span class="contact-list-custom-field-title">Kontakt</span>
      </div>
      <div class="contact-list-custom-field-2">
        <span class="contact-list-custom-field-title">Internet</span>
        <span class="contact-list-custom-field-value"><a href="javascript:void(0)">invalid website</a></span>
      </div>
    </div>
    <div class="contact-list-contact-container">
      <span class="contact-list-contact-name">Brandenburg Hausverwaltung GmbH</span>
      <div class="contact-list-address"><span>14513 Teltow</span></div>
    </div>
    <div class="contact-list-contact-container">
      <div class="contact-list-address"><span>10115 Berlin</span></div>
    </div>
    """

    rows = scraper.parse_vdiv_html(html, scraper.members_directory_url)

    assert len(rows) == 2
    assert rows[0].raw_company_name == "Alpha Hausverwaltung GmbH"
    assert rows[0].raw_street == "Example Str. 1"
    assert rows[0].raw_postal_code == "10115"
    assert rows[0].raw_city == "Berlin"
    assert rows[0].raw_phone == "+4930123456"
    assert rows[0].raw_email == "info@alpha.example"
    assert rows[0].raw_website == "https://alpha.example"
    assert rows[0].is_vdiv_member is True
    assert rows[1].raw_website is None
    assert rows[1].raw_email is None
    assert rows[1].raw_phone is None


@pytest.mark.asyncio
async def test_missing_url_resolver_filters_and_persists(tmp_path, monkeypatch):
    from metrixa_engine.db import Database
    import metrixa_engine.crawler.url_resolver as module

    db = Database(tmp_path / "resolver.db")
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO companies_golden (canonical_name, display_name, postal_code, pipeline_stage, source_count, sources_csv, updated_at) VALUES ('alpha', 'Alpha Hausverwaltung GmbH', '10719', 'DEDUPED', 1, 'test', 'old')"
        )
        company_id = cur.lastrowid
    calls = []

    async def search(query, **kwargs):
        calls.append(query)
        return [
            SearchResultItem("Alpha", "https://gelbeseiten.de/alpha", "", "x"),
            SearchResultItem("Alpha", "mailto:a@alpha.example", "", "x"),
            SearchResultItem(
                "Alpha Hausverwaltung GmbH",
                "https://alpha-hausverwaltung.de/path",
                "",
                "x",
            ),
        ]

    monkeypatch.setattr(module.search_router, "search", search)
    resolver = MissingURLResolver(db)
    assert (
        await resolver.resolve_for_company("Alpha Hausverwaltung GmbH", "10719")
        == "https://alpha-hausverwaltung.de"
    )
    assert calls[-1].endswith("10719 Berlin")
    assert await resolver.resolve_missing_batch() == 1
    with db.connect() as conn:
        row = conn.execute(
            "SELECT website_url, canonical_domain FROM companies_golden WHERE company_id=?",
            (company_id,),
        ).fetchone()
    assert row["website_url"] == "https://alpha-hausverwaltung.de"
    assert row["canonical_domain"] == "alpha-hausverwaltung.de"

    async def no_results(*args, **kwargs):
        return []

    monkeypatch.setattr(module.search_router, "search", no_results)
    assert await resolver.resolve_for_company("No Match") is None
    assert await resolver.resolve_missing_batch() == 0
