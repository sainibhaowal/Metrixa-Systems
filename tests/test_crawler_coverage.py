from __future__ import annotations

import asyncio

import pytest

from metrixa_engine.crawler.web_crawler import AsyncWebsiteCrawler
from metrixa_engine.db import Database


class _Response:
    def __init__(
        self,
        status=200,
        url="https://public.example/",
        text="<main>Page content is long enough to inspect.</main>",
        headers=None,
    ):
        self.status_code = status
        self.url = url
        self.text = text
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}


class _Client:
    def __init__(self, responses=None, error=None):
        self.responses = iter(responses or [])
        self.error = error
        self.requested = []

    async def get(self, url, **kwargs):
        self.requested.append((url, kwargs))
        if self.error:
            raise self.error
        return next(self.responses)


def test_crawler_markdown_and_priority_link_discovery(monkeypatch):
    import metrixa_engine.crawler.web_crawler as module

    html = """<html><head><script>SECRET</script><style>.x{}</style></head><body>
      <main><h1>Visible company</h1><p>Executive director details and registered address 10719 Berlin.</p>
      <a href="/impressum">Legal</a><a href="/team">Team</a><a href="/team/contact">More team</a>
      <a href="/leistungen">Services</a><a href="/referenzen">References</a><a href="/kundenportal">Portal</a>
      <a href="https://outside.example/impressum">external</a><a href="/file.pdf">pdf</a>
      <a href="#anchor">anchor</a><a href="mailto:x@example.org">mail</a><a href="/">home</a></main></body></html>"""
    assert AsyncWebsiteCrawler.html_to_clean_markdown("") == ""
    text = AsyncWebsiteCrawler.html_to_clean_markdown(html, "impressum")
    assert "Visible company" in text and "SECRET" not in text
    monkeypatch.setattr(module.trafilatura, "extract", lambda *a, **k: "A" * 450)
    assert (
        AsyncWebsiteCrawler.html_to_clean_markdown("<body>short</body>", "homepage")
        == "A" * 450
    )
    monkeypatch.setattr(module.trafilatura, "extract", lambda *a, **k: None)
    assert "short" in AsyncWebsiteCrawler.html_to_clean_markdown(
        "<body>short text</body>"
    )
    monkeypatch.setattr(
        module.trafilatura,
        "extract",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError()),
    )
    assert "short" in AsyncWebsiteCrawler.html_to_clean_markdown(
        "<body>short text</body>", "team"
    )

    links = AsyncWebsiteCrawler.discover_priority_subpages(
        html, "https://www.public.example/", max_subpages=5
    )
    assert [kind for kind, _ in links] == [
        "impressum",
        "team",
        "leistungen",
        "referenzen",
        "portal",
    ]
    assert (
        len(
            AsyncWebsiteCrawler.discover_priority_subpages(
                "<body></body>", "https://x.example", 2
            )
        )
        == 1
    )
    assert AsyncWebsiteCrawler.discover_priority_subpages("", "https://x.example") == []


@pytest.mark.asyncio
async def test_fetch_page_redirect_validation_content_types_and_errors(
    monkeypatch, tmp_path
):
    db = Database(tmp_path / "crawl.db")
    crawler = AsyncWebsiteCrawler(db)
    safe = iter([True, True, False])
    monkeypatch.setattr(crawler, "_is_safe_url", lambda url: _next_async(safe))
    client = _Client(
        [
            _Response(302, "https://public.example/", headers={"location": "/next"}),
            _Response(200, "https://public.example/next", "<html>ok</html>"),
        ]
    )
    result = await crawler._fetch_page(client, "https://public.example/")
    assert result == (200, "https://public.example/next", "<html>ok</html>")
    monkeypatch.setattr(crawler, "_is_safe_url", lambda url: _async_true())
    client = _Client([_Response(302, headers={})])
    result = await crawler._fetch_page(client, "https://public.example/")
    assert result[0] == 302 and result[2] == ""
    client = _Client([_Response(200, headers={"content-type": "image/png"})])
    result = await crawler._fetch_page(client, "https://public.example/file")
    assert result[0] == 200 and result[2] == ""
    client = _Client(error=OSError("offline"))
    result = await crawler._fetch_page(client, "https://public.example/")
    assert result[0] == 0 and result[2] == ""
    monkeypatch.setattr(crawler, "_is_safe_url", lambda url: _async_false())
    assert (await crawler._fetch_page(_Client(), "http://127.0.0.1"))[0] == 0


async def _next_async(iterator):
    return next(iterator)


async def _async_false():
    return False


async def _async_true():
    return True


def _company(db: Database, name: str, website: str | None, stage="DEDUPED") -> int:
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO companies_golden (canonical_name, display_name, website_url, pipeline_stage, sources_csv, updated_at) VALUES (?, ?, ?, ?, 'test', 'old')",
            (name.lower(), name, website, stage),
        )
        return int(cur.lastrowid)


@pytest.mark.asyncio
async def test_crawl_single_company_persists_success_and_failure(tmp_path, monkeypatch):
    db = Database(tmp_path / "single-crawl.db")
    cid = _company(db, "Alpha Hausverwaltung GmbH", "https://alpha.example")
    crawler = AsyncWebsiteCrawler(db)
    home = """<html><body><main><h1>Alpha Verwaltung</h1><p>info@alpha.example</p>
       <a href="/impressum">Impressum</a><a href="https://alpha.example/login">Kundenportal</a>
       </main></body></html>"""

    async def fetch(client, url):
        if url.endswith("/impressum"):
            return 200, url, "<main>Impressum address and management</main>"
        return 200, url, home

    monkeypatch.setattr(crawler, "_fetch_page", fetch)
    result = await crawler.crawl_single_company(_Client(), cid, "https://alpha.example")
    assert result == {"company_id": cid, "pages_crawled": 3, "reachable": True}
    with db.connect() as conn:
        pages = conn.execute(
            "SELECT page_type, http_status FROM crawled_pages WHERE company_id=? ORDER BY page_id",
            (cid,),
        ).fetchall()
        stage = conn.execute(
            "SELECT pipeline_stage FROM companies_golden WHERE company_id=?", (cid,)
        ).fetchone()[0]
    assert [p["page_type"] for p in pages] == ["homepage", "impressum", "portal"]
    assert stage == "CRAWLED"

    async def failed(client, url):
        return 0, url, ""

    monkeypatch.setattr(crawler, "_fetch_page", failed)
    result = await crawler.crawl_single_company(_Client(), cid, "https://alpha.example")
    assert result["reachable"] is False and result["pages_crawled"] == 0
    with db.connect() as conn:
        row = conn.execute(
            "SELECT http_status, clean_markdown FROM crawled_pages WHERE company_id=?",
            (cid,),
        ).fetchone()
    assert row["http_status"] == 0 and row["clean_markdown"] == ""


@pytest.mark.asyncio
async def test_crawl_batch_empty_missing_url_and_callback(tmp_path, monkeypatch):
    import metrixa_engine.crawler.web_crawler as module

    db = Database(tmp_path / "batch-crawl.db")
    crawler = AsyncWebsiteCrawler(db)
    assert await crawler.crawl_batch() == {
        "companies_processed": 0,
        "reachable_websites": 0,
        "total_pages_saved": 0,
    }
    missing_id = _company(db, "Missing URL GmbH", None)
    with db.connect() as conn:
        conn.execute(
            "UPDATE companies_golden SET source_count=2 WHERE company_id=?",
            (missing_id,),
        )
        conn.execute(
            "INSERT INTO companies_golden (canonical_name, display_name, website_url, pipeline_stage, sources_csv, updated_at) VALUES ('online', 'Online GmbH', 'https://online.example', 'DEDUPED', 'test', 'old')"
        )
    progress = []

    async def fake_single(client, company_id, website_url):
        return {"company_id": company_id, "reachable": True, "pages_crawled": 1}

    monkeypatch.setattr(crawler, "crawl_single_company", fake_single)

    class FakeClientContext:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return _Client()

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeClientContext)
    result = await crawler.crawl_batch(
        progress_callback=lambda n, total: progress.append((n, total))
    )
    assert result == {
        "companies_processed": 2,
        "reachable_websites": 1,
        "total_pages_saved": 1,
    }
    assert progress == [(1, 2), (2, 2)]
    with db.connect() as conn:
        stage = conn.execute(
            "SELECT pipeline_stage FROM companies_golden WHERE company_id=?",
            (missing_id,),
        ).fetchone()[0]
    assert stage == "CRAWLED"


@pytest.mark.asyncio
async def test_crawler_safe_url_rejects_private_non_http_and_dns_failures(
    monkeypatch, tmp_path
):
    import metrixa_engine.crawler.web_crawler as module

    Database(tmp_path / "safe.db")
    monkeypatch.setattr(module.settings, "allow_private_crawler_targets", False)
    assert await AsyncWebsiteCrawler._is_safe_url("file:///etc/passwd") is False
    assert (
        await AsyncWebsiteCrawler._is_safe_url("http://user:pass@example.com") is False
    )
    assert await AsyncWebsiteCrawler._is_safe_url("http://127.0.0.1") is False

    async def bad_dns(*args, **kwargs):
        raise OSError("DNS unavailable")

    monkeypatch.setattr(
        asyncio.get_running_loop(), "getaddrinfo", bad_dns, raising=False
    )
    assert await AsyncWebsiteCrawler._is_safe_url("https://bad.example") is False
    monkeypatch.setattr(module.settings, "allow_private_crawler_targets", True)
    assert await AsyncWebsiteCrawler._is_safe_url("http://127.0.0.1") is True
