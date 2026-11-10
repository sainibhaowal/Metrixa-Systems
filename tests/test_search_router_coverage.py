from __future__ import annotations

import pytest

from metrixa_engine.enrichment.search_router import SearchResultItem, SearchRouter


class Response:
    def __init__(self, status=200, data=None, text=""):
        self.status_code, self._data, self.text = status, data or {}, text

    def json(self):
        return self._data


class Client:
    def __init__(self, get_responses=(), post_responses=(), error=None):
        self.get_responses, self.post_responses = iter(get_responses), iter(
            post_responses
        )
        self.error = error
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if self.error:
            raise self.error
        return next(self.get_responses)

    async def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if self.error:
            raise self.error
        return next(self.post_responses)


def test_search_item_serialization_and_local_searxng_variants():
    item = SearchResultItem("title", "https://x.de", "excerpt", "engine")
    assert item.to_dict() == {
        "title": "title",
        "url": "https://x.de",
        "snippet": "excerpt",
        "engine": "engine",
    }
    router = SearchRouter()
    assert (
        router._query_local_searxng
    )  # method is exercised asynchronously in the next test


@pytest.mark.asyncio
async def test_searxng_success_unavailable_and_exception(monkeypatch):
    router = SearchRouter()
    response = Response(
        data={
            "results": [
                {"title": "First", "url": "https://one.de", "content": "Text"},
                {"title": "bad", "url": "ftp://invalid", "content": ""},
                {"title": "Second", "url": "https://two.de"},
            ]
        }
    )
    rows = await router._query_local_searxng(Client([response]), "query", 3)
    assert router.searxng_available is True and len(rows) == 2
    assert rows[0].engine == "local_searxng" and rows[1].snippet == ""
    assert await router._query_local_searxng(Client(), "skip") == []
    assert (
        await router._query_local_searxng(Client([Response(503)]), "bad status") == []
    )
    other = SearchRouter()
    assert await other._query_local_searxng(Client(error=OSError()), "error") == []
    assert other.searxng_available is False


@pytest.mark.asyncio
async def test_native_metasearch_disabled_ddg_success_and_brave_fallback(monkeypatch):
    import metrixa_engine.enrichment.search_router as module

    router = SearchRouter()
    monkeypatch.setattr(module.settings, "enable_native_metasearch", False)
    assert await router._query_native_metasearch(Client(), "x") == []
    monkeypatch.setattr(module.settings, "enable_native_metasearch", True)
    ddg = """<div class="result"><a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fone.de%2F">One</a><a class="result__snippet">Snippet</a></div>
      <div class="result"><a class="result__a" href="https://two.de">Two</a></div>
      <div class="result"><a class="result__a" href="https://duckduckgo.com/">bad host</a></div>
      <div class="result"><div class="result__snippet">no title</div></div>"""
    rows = await router._query_native_metasearch(
        Client(post_responses=[Response(text=ddg)]), "query", 1
    )
    assert (
        len(rows) == 1
        and rows[0].url == "https://one.de/"
        and rows[0].engine == "native_ddg_de"
    )
    brave = """<div class="snippet"><a href="https://brave.com/">bad</a></div>
      <div class="snippet"><a href="https://three.de">Three</a><p>Brave snippet</p></div>"""
    rows = await router._query_native_metasearch(
        Client(post_responses=[Response(503)], get_responses=[Response(text=brave)]),
        "query",
    )
    assert (
        len(rows) == 1
        and rows[0].url == "https://three.de"
        and rows[0].engine == "native_brave_de"
    )
    assert await router._query_native_metasearch(Client(error=OSError()), "query") == []
    monkeypatch.setattr(module.settings, "enable_native_metasearch", False)
    assert await router._query_native_metasearch(Client(), "query") == []


@pytest.mark.asyncio
async def test_search_provider_helpers_and_limits(monkeypatch):
    import metrixa_engine.enrichment.search_router as module

    router = SearchRouter()
    settings = module.settings
    monkeypatch.setattr(settings, "tavily_api_key", "")
    assert await router._query_tavily_fallback(Client(), "q") == []
    monkeypatch.setattr(settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(settings, "tavily_max_calls_per_run", 1)
    client = Client(
        post_responses=[
            Response(
                data={
                    "results": [{"title": "T", "url": "https://t.de", "content": "C"}]
                }
            )
        ]
    )
    rows = await router._query_tavily_fallback(client, "q", 2)
    assert len(rows) == 1 and rows[0].engine == "tavily_api"
    assert router.tavily_calls_used == 1
    assert await router._query_tavily_fallback(Client(), "q") == []
    assert (
        await SearchRouter()._query_tavily_fallback(Client(error=OSError()), "q") == []
    )
    assert (
        await SearchRouter()._query_tavily_fallback(
            Client(post_responses=[Response(503)]), "q"
        )
        == []
    )

    monkeypatch.setattr(settings, "brave_search_api_key", "")
    assert await router._query_brave_api(Client(), "q") == []
    monkeypatch.setattr(settings, "brave_search_api_key", "brave-key")
    brave_data = {
        "web": {
            "results": [
                {"title": "B", "url": "https://b.de", "description": "D"},
                {"url": "bad"},
            ]
        }
    }
    rows = await router._query_brave_api(
        Client(get_responses=[Response(data=brave_data)]), "q", 1
    )
    assert len(rows) == 1 and rows[0].engine == "brave_api"
    assert (
        await router._query_brave_api(Client(get_responses=[Response(503)]), "q") == []
    )
    assert await router._query_brave_api(Client(error=OSError()), "q") == []

    monkeypatch.setattr(settings, "google_cse_api_key", "")
    assert await router._query_google_cse(Client(), "q") == []
    monkeypatch.setattr(settings, "google_cse_api_key", "google-key")
    monkeypatch.setattr(settings, "google_cse_id", "engine-id")
    google_data = {
        "items": [
            {"title": "G", "link": "https://g.de", "snippet": "S"},
            {"link": "mailto:x"},
        ]
    }
    rows = await router._query_google_cse(
        Client(get_responses=[Response(data=google_data)]), "q", 1
    )
    assert len(rows) == 1 and rows[0].engine == "google_cse"
    assert (
        await router._query_google_cse(Client(get_responses=[Response(500)]), "q") == []
    )
    assert await router._query_google_cse(Client(error=OSError()), "q") == []


@pytest.mark.asyncio
async def test_search_provider_order_fallback_and_tavily_flag(monkeypatch):
    import metrixa_engine.enrichment.search_router as module

    router = SearchRouter()
    calls = []

    async def empty(*args):
        calls.append("searxng")
        return []

    async def native(*args):
        calls.append("native")
        return []

    async def brave(*args):
        calls.append("brave")
        return [SearchResultItem("B", "https://b.de", "", "brave")]

    async def google(*args):
        calls.append("google")
        return []

    async def tavily(*args):
        calls.append("tavily")
        return []

    monkeypatch.setattr(router, "_query_local_searxng", empty)
    monkeypatch.setattr(router, "_query_native_metasearch", native)
    monkeypatch.setattr(router, "_query_brave_api", brave)
    monkeypatch.setattr(router, "_query_google_cse", google)
    monkeypatch.setattr(router, "_query_tavily_fallback", tavily)
    monkeypatch.setattr(module.settings, "default_search_provider", "brave")

    async def no_sleep(*args):
        return None

    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)
    result = await router.search("q")
    assert result[0].engine == "brave" and calls == ["brave"]

    calls.clear()
    monkeypatch.setattr(module.settings, "default_search_provider", "native_metasearch")
    await router.search("q", allow_tavily_fallback=False)
    assert calls == ["native", "searxng"]

    calls.clear()
    monkeypatch.setattr(module.settings, "default_search_provider", "google_cse")
    monkeypatch.setattr(router, "_query_google_cse", google)
    await router.search("q")
    assert calls == ["google", "searxng", "native", "tavily"]

    calls.clear()
    monkeypatch.setattr(module.settings, "default_search_provider", "unrecognized")
    monkeypatch.setattr(
        router, "_query_local_searxng", lambda *args: _result("searxng", calls)
    )
    await router.search("q", allow_tavily_fallback=False)
    assert calls == ["searxng"]


async def _result(name, calls):
    calls.append(name)
    return [SearchResultItem(name, "https://x.de", "", name)]
