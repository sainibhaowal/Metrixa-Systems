"""
Base Asynchronous HTTP Scraper with Token-Bucket Rate Limiting,
Rotating Browser Headers, Base64 URL Decoding, and Retry Logic.
"""

from __future__ import annotations

import asyncio
import base64
import random
import re
from typing import Dict, List, Optional
import httpx

from heidi_engine.config import settings
from heidi_engine.models import RawListing


USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]


class BaseAsyncScraper:
    """Common async HTTP client & rate-limiting primitives for Berlin scrapers."""

    source_name: str = "base"

    def __init__(self, concurrency: int = 6, delay_range: tuple[float, float] = (0.25, 0.75)) -> None:
        self.semaphore = asyncio.Semaphore(concurrency)
        self.delay_range = delay_range

    def get_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    async def fetch_text(
        self,
        client: httpx.AsyncClient,
        url: str,
        method: str = "GET",
        data: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
    ) -> Optional[str]:
        async with self.semaphore:
            await asyncio.sleep(random.uniform(*self.delay_range))
            for attempt in range(3):
                try:
                    if method.upper() == "POST":
                        resp = await client.post(
                            url,
                            data=data,
                            headers=self.get_headers(referer=referer),
                            timeout=settings.http_timeout_seconds,
                            follow_redirects=True,
                        )
                    else:
                        resp = await client.get(
                            url,
                            headers=self.get_headers(referer=referer),
                            timeout=settings.http_timeout_seconds,
                            follow_redirects=True,
                        )
                    if resp.status_code == 200:
                        return resp.text
                    if resp.status_code in (429, 502, 503, 504):
                        await asyncio.sleep(1.2 * (attempt + 1))
                except Exception:
                    await asyncio.sleep(0.8 * (attempt + 1))
            return None

    @staticmethod
    def decode_b64_url(encoded: Optional[str]) -> Optional[str]:
        """Decode base64-encoded website URLs used by German directory cards (e.g., Gelbe Seiten)."""
        if not encoded:
            return None
        val = encoded.strip()
        if val.startswith("http://") or val.startswith("https://"):
            return val
        try:
            # Add padding if needed
            pad = len(val) % 4
            if pad:
                val += "=" * (4 - pad)
            decoded = base64.b64decode(val).decode("utf-8", errors="ignore").strip()
            if decoded.startswith("http://") or decoded.startswith("https://"):
                return decoded
        except Exception:
            pass
        return None

    @staticmethod
    def clean_whitespace(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned if cleaned else None

    async def scrape_berlin(self, max_pages: int = 10) -> List[RawListing]:
        raise NotImplementedError

