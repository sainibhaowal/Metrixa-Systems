from __future__ import annotations

import asyncio
import socket

import pytest

from metrixa_engine.crawler.tech_detector import scan_html_for_tech_and_contacts
from metrixa_engine.crawler.web_crawler import AsyncWebsiteCrawler
from metrixa_engine.db import Database


def test_tech_detector_empty_and_filters_non_contact_artifacts():
    assert scan_html_for_tech_and_contacts("") == {
        "erp_list": [],
        "metering_list": [],
        "has_portal": False,
        "linkedin_urls": [],
        "emails": [],
    }
    result = scan_html_for_tech_and_contacts(
        "info@company.de logo.png logo@company.png app.js@company.js "
        "private@sentry.io user@example.com wix@wixpress.com wp@wordpress.org"
    )
    assert result["emails"] == ["info@company.de"]


@pytest.mark.asyncio
async def test_crawler_public_dns_dom_parse_failure_priority_fill_and_404(
    monkeypatch, tmp_path
):
    import metrixa_engine.crawler.web_crawler as module

    loop = asyncio.get_running_loop()

    async def public_dns(host, port, **kwargs):
        assert host == "public.example" and port == 443
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(loop, "getaddrinfo", public_dns, raising=False)
    monkeypatch.setattr(module.settings, "allow_private_crawler_targets", False)
    assert await AsyncWebsiteCrawler._is_safe_url("https://public.example/path") is True

    db = Database(tmp_path / "dom-exception.db")
    monkeypatch.setattr(module.trafilatura, "extract", lambda *a, **k: None)
    parser = module.HTMLParser
    monkeypatch.setattr(
        module, "HTMLParser", lambda html: (_ for _ in ()).throw(RuntimeError("parser"))
    )
    assert AsyncWebsiteCrawler.html_to_clean_markdown("<main>text</main>", "team") == ""
    monkeypatch.setattr(module, "HTMLParser", parser)

    links = AsyncWebsiteCrawler.discover_priority_subpages(
        "<a href='/team'>Team</a><a href='/kontakt'>Contact</a>",
        "https://public.example",
        max_subpages=3,
    )
    assert links == [
        ("impressum", "https://public.example/impressum"),
        ("team", "https://public.example/team"),
        ("team", "https://public.example/kontakt"),
    ]

    crawler = AsyncWebsiteCrawler(db)

    class NotFound:
        async def get(self, *args, **kwargs):
            return type(
                "Resp",
                (),
                {
                    "status_code": 404,
                    "url": "https://public.example/missing",
                    "headers": {"content-type": "image/png"},
                    "text": "binary",
                },
            )()

    monkeypatch.setattr(crawler, "_is_safe_url", lambda url: _true())
    assert await crawler._fetch_page(NotFound(), "https://public.example/missing") == (
        404,
        "https://public.example/missing",
        "",
    )

    class RedirectLoop:
        async def get(self, url, **kwargs):
            from urllib.parse import urlparse

            path = urlparse(url).path
            return type(
                "Resp",
                (),
                {
                    "status_code": 302,
                    "url": url,
                    "headers": {"location": f"{path}/next"},
                    "text": "",
                },
            )()

    assert await crawler._fetch_page(
        RedirectLoop(), "https://public.example/start"
    ) == (0, "https://public.example/start/next/next/next/next/next/next", "")


async def _true():
    return True
