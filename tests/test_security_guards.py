"""Regression tests for outbound crawler destination checks."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from metrixa_engine.crawler.web_crawler import AsyncWebsiteCrawler
from metrixa_engine.db import Database


def test_crawler_rejects_private_and_non_http_targets(tmp_path) -> None:
    async def check() -> tuple[bool, bool, bool]:
        return (
            await AsyncWebsiteCrawler._is_safe_url("http://127.0.0.1/admin"),
            await AsyncWebsiteCrawler._is_safe_url(
                "http://169.254.169.254/latest/meta-data"
            ),
            await AsyncWebsiteCrawler._is_safe_url("file:///etc/passwd"),
        )

    assert asyncio.run(check()) == (False, False, False)


def test_crawler_validates_each_redirect_target(tmp_path, monkeypatch) -> None:
    crawler = AsyncWebsiteCrawler(Database(tmp_path / "crawler.db"))
    checked_urls: list[str] = []

    async def safe_url(url: str) -> bool:
        checked_urls.append(url)
        return url == "https://public.example/"

    monkeypatch.setattr(crawler, "_is_safe_url", safe_url)

    class FakeClient:
        calls = 0

        async def get(self, url, **kwargs):
            self.calls += 1
            return SimpleNamespace(
                status_code=302,
                headers={"location": "http://127.0.0.1/admin"},
                url=url,
                text="",
            )

    client = FakeClient()
    result = asyncio.run(crawler._fetch_page(client, "https://public.example/"))

    assert result == (0, "http://127.0.0.1/admin", "")
    assert checked_urls == ["https://public.example/", "http://127.0.0.1/admin"]
    assert client.calls == 1
