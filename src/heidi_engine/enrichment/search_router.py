"""
Unified 3-Tier Search Router for Heidi Engine:
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

from heidi_engine.config import settings
from heidi_engine.scrapers.base import USER_AGENTS


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

    async def search(
        self,
        query: str,
        max_results: int = 8,
        allow_tavily_fallback: bool = True,
    ) -> List[SearchResultItem]:
        async with self._semaphore:
            async with httpx.AsyncClient(http2=True, follow_redirects=True) as client:
                # Tier 1: Local SearXNG
                items = await self._query_local_searxng(
                    client, query, max_results=max_results
                )
                if items:
                    return items

                # Tier 2: Built-in Native Meta-Search
                await asyncio.sleep(random.uniform(0.3, 0.7))
                items = await self._query_native_metasearch(
                    client, query, max_results=max_results
                )
                if items:
                    return items

                # Tier 3: Tavily API Fallback
                if allow_tavily_fallback:
                    items = await self._query_tavily_fallback(
                        client, query, max_results=max_results
                    )
                    if items:
                        return items

                return []


# Singleton SearchRouter instance
search_router = SearchRouter()
