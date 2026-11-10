from __future__ import annotations

import pytest

from metrixa_engine.enrichment.search_router import SearchRouter


class _Response:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text


class _Client:
    def __init__(self, post, get):
        self.post_response = post
        self.get_response = get

    async def post(self, *args, **kwargs):
        return self.post_response

    async def get(self, *args, **kwargs):
        return self.get_response


@pytest.mark.asyncio
async def test_native_search_skips_bad_cards_and_stops_at_max(monkeypatch):
    import metrixa_engine.enrichment.search_router as module

    monkeypatch.setattr(module.settings, "enable_native_metasearch", True)
    ddg = _Response(
        200,
        """
      <div class="result"><span>No anchor selector here</span></div>
    """,
    )
    brave = _Response(
        200,
        """
      <div class="snippet"><span>No link here</span></div>
      <div class="snippet"><a href="https://search.brave.com/internal">Internal</a></div>
      <div class="snippet"><a href="https://source.example/a">First source</a><p>Useful</p></div>
      <div class="snippet"><a href="https://source.example/b">Second source</a></div>
    """,
    )
    results = await SearchRouter()._query_native_metasearch(
        _Client(ddg, brave), "query", max_results=1
    )
    assert len(results) == 1 and results[0].url == "https://source.example/a"
