"""
Unified 3-Tier Search Router for Metrixa Engine:
  Tier 1: Local Self-Hosted SearXNG (http://127.0.0.1:8888/search?format=json)
  Tier 2: Built-in Native Python Async Meta-Search (DuckDuckGo Lite / Brave HTML)
  Tier 3: Tavily AI Search API Fallback (https://api.tavily.com/search)
"""

from __future__ import annotations

import asyncio
import random
import urllib.parse
from typing import Dict, List, Optional
import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from metrixa_engine.config import settings
from metrixa_engine.scrapers.base import USER_AGENTS


class SearchResultItem:
    def __init__(self, title: str, url: str, snippet: str, engine: str) -> None:
        self.title = title
        self.url = url
        self.snippet = snippet
        self.engine = engine

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "engine": self.engine,
        }


class SearchRouter:
    """Routes web & LinkedIn search queries across Local SearXNG, Native Meta-Search, and Tavily."""

    def __init__(self) -> None:
        self.tavily_calls_used = 0
        self.searxng_available: Optional[bool] = None
        self._semaphore = asyncio.Semaphore(4)

    async def _query_local_searxng(
        self, client: httpx.AsyncClient, query: str, max_results: int = 8
    ) -> List[SearchResultItem]:
        if self.searxng_available is False:
            return []
        try:
            url = f"{settings.searxng_base_url}/search"
            resp = await client.get(
                url,
                params={"q": query, "format": "json", "language": "de-DE"},
                timeout=6.0,
            )
            if resp.status_code == 200:
                self.searxng_available = True
                data = resp.json()
                results: List[SearchResultItem] = []
                for r in data.get("results", [])[:max_results]:
                    r_url = r.get("url", "")
                    if not r_url.startswith("http"):
                        continue
                    results.append(
                        SearchResultItem(
                            title=str(r.get("title", "")).strip(),
                            url=r_url,
                            snippet=str(r.get("content", "")).strip(),
                            engine="local_searxng",
                        )
                    )
                return results
        except Exception:
            self.searxng_available = False
        return []

    async def _query_native_metasearch(
        self, client: httpx.AsyncClient, query: str, max_results: int = 8
    ) -> List[SearchResultItem]:
        """Zero-Docker native Python meta-search across DuckDuckGo HTML & Brave Search."""
        if not settings.enable_native_metasearch:
            return []

        results: List[SearchResultItem] = []
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }

        # 1. DuckDuckGo HTML endpoint
        try:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "kl": "de-de"},
                headers=headers,
                timeout=10.0,
            )
            if resp.status_code == 200:
                tree = HTMLParser(resp.text)
                for node in tree.css("div.result, div.web-result"):
                    a_el = node.css_first("a.result__a")
                    snip_el = node.css_first("a.result__snippet, div.result__snippet")
                    if not a_el:
                        continue
                    href = a_el.attributes.get("href", "")
                    if "uddg=" in href:
                        parsed_qs = urllib.parse.parse_qs(
                            urllib.parse.urlparse(href).query
                        )
                        if "uddg" in parsed_qs:
                            href = parsed_qs["uddg"][0]
                    if href.startswith("http") and "duckduckgo.com" not in href:
                        results.append(
                            SearchResultItem(
                                title=a_el.text().strip(),
                                url=href,
                                snippet=snip_el.text().strip() if snip_el else "",
                                engine="native_ddg_de",
                            )
                        )
                        if len(results) >= max_results:
                            return results
        except Exception:
            pass

        # 2. Brave Search HTML fallback if needed
        if not results:
            try:
                resp = await client.get(
                    "https://search.brave.com/search",
                    params={"q": query, "country": "de"},
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    tree = HTMLParser(resp.text)
                    for node in tree.css("div.snippet"):
                        a_el = node.css_first("a[href^='http']")
                        snip_el = node.css_first("div.snippet-description, p")
                        if not a_el:
                            continue
                        href = a_el.attributes.get("href", "")
                        if "brave.com" not in href:
                            results.append(
                                SearchResultItem(
                                    title=a_el.text().strip(),
                                    url=href,
                                    snippet=snip_el.text().strip() if snip_el else "",
                                    engine="native_brave_de",
                                )
                            )
                            if len(results) >= max_results:
                                break
            except Exception:
                pass

        return results

    async def _query_tavily_fallback(
        self, client: httpx.AsyncClient, query: str, max_results: int = 5
    ) -> List[SearchResultItem]:
        """Tier 3: Tavily AI Search API (Reserved for fallback when API key is configured)."""
        if (
            not settings.tavily_api_key
            or self.tavily_calls_used >= settings.tavily_max_calls_per_run
        ):
            return []
        try:
            self.tavily_calls_used += 1
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                },
                timeout=12.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                results: List[SearchResultItem] = []
                for r in data.get("results", []):
                    results.append(
                        SearchResultItem(
                            title=str(r.get("title", "")).strip(),
                            url=str(r.get("url", "")).strip(),
                            snippet=str(r.get("content", "")).strip(),
                            engine="tavily_api",
                        )
                    )
                return results
        except Exception:
            pass
        return []

    async def _query_brave_api(
        self, client: httpx.AsyncClient, query: str, max_results: int = 8
    ) -> List[SearchResultItem]:
        """Query Brave's configured API and preserve its actual result URLs."""
        if not settings.brave_search_api_key:
            return []
        try:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": min(max_results, 20)},
                headers={
                    "X-Subscription-Token": settings.brave_search_api_key,
                    "Accept": "application/json",
                },
                timeout=10.0,
            )
            if response.status_code != 200:
                return []
            items = (response.json().get("web") or {}).get("results") or []
            return [
                SearchResultItem(
                    title=str(item.get("title") or "").strip(),
                    url=str(item.get("url") or "").strip(),
                    snippet=str(item.get("description") or "").strip(),
                    engine="brave_api",
                )
                for item in items[:max_results]
                if str(item.get("url") or "").startswith("http")
            ]
        except Exception:
            return []

    async def _query_google_cse(
        self, client: httpx.AsyncClient, query: str, max_results: int = 8
    ) -> List[SearchResultItem]:
        """Query Google Custom Search when both the API key and engine ID exist."""
        if not settings.google_cse_api_key or not settings.google_cse_id:
            return []
        try:
            response = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": settings.google_cse_api_key,
                    "cx": settings.google_cse_id,
                    "q": query,
                    "num": min(max_results, 10),
                },
                timeout=10.0,
            )
            if response.status_code != 200:
                return []
            items = response.json().get("items") or []
            return [
                SearchResultItem(
                    title=str(item.get("title") or "").strip(),
                    url=str(item.get("link") or "").strip(),
                    snippet=str(item.get("snippet") or "").strip(),
                    engine="google_cse",
                )
                for item in items[:max_results]
                if str(item.get("link") or "").startswith("http")
            ]
        except Exception:
            return []

    async def search(
        self,
        query: str,
        max_results: int = 8,
        allow_tavily_fallback: bool = True,
    ) -> List[SearchResultItem]:
        provider_order = {
            "searxng": ["searxng", "native_metasearch", "tavily"],
            "native_metasearch": ["native_metasearch", "searxng", "tavily"],
            "tavily": ["tavily", "searxng", "native_metasearch"],
            "brave": ["brave", "searxng", "native_metasearch", "tavily"],
            "google_cse": ["google_cse", "searxng", "native_metasearch", "tavily"],
        }.get(
            settings.default_search_provider, ["searxng", "native_metasearch", "tavily"]
        )
        if not allow_tavily_fallback:
            provider_order = [
                provider for provider in provider_order if provider != "tavily"
            ]

        async with self._semaphore:
            async with httpx.AsyncClient(http2=True, follow_redirects=True) as client:
                for provider in provider_order:
                    if provider == "searxng":
                        items = await self._query_local_searxng(
                            client, query, max_results
                        )
                    elif provider == "native_metasearch":
                        items = await self._query_native_metasearch(
                            client, query, max_results
                        )
                    elif provider == "tavily":
                        items = await self._query_tavily_fallback(
                            client, query, max_results
                        )
                    elif provider == "brave":
                        items = await self._query_brave_api(client, query, max_results)
                    else:
                        items = await self._query_google_cse(client, query, max_results)
                    if items:
                        return items
                    if provider == "native_metasearch":
                        await asyncio.sleep(random.uniform(0.3, 0.7))

                return []


# Singleton SearchRouter instance
search_router = SearchRouter()
