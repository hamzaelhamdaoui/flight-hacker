from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger("kiwi_client")

SEARCH_BASE = "https://api.tequila.kiwi.com/v2"
LOCATIONS_BASE = "https://api.tequila.kiwi.com/locations"


class TokenBucket:
    def __init__(self, rate: float = 30, period: float = 60):
        self.rate = rate
        self.period = period
        self.tokens = rate
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / self.period))
            self.last_refill = now
            if self.tokens < 1:
                wait = (1 - self.tokens) * (self.period / self.rate)
                logger.info(f"Rate limited — sleeping {wait:.2f}s")
                await asyncio.sleep(wait)
                self.tokens = 0
                self.last_refill = time.monotonic()
            else:
                self.tokens -= 1


class LocationCache:
    def __init__(self, ttl: int = 3600):
        self._cache: dict[str, tuple[float, Any]] = {}
        self.ttl = ttl

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            ts, val = self._cache[key]
            if time.monotonic() - ts < self.ttl:
                return val
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = (time.monotonic(), value)


class KiwiClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._search_key = settings.kiwi_api_key_search
        self._multi_key = settings.kiwi_api_key_multi
        self._client = httpx.AsyncClient(timeout=30.0)
        self._bucket = TokenBucket(rate=30, period=60)
        self._loc_cache = LocationCache(ttl=3600)

    async def _request(
        self,
        method: str,
        url: str,
        api_key: str,
        params: dict | None = None,
        json_body: dict | None = None,
        retries: int = 3,
    ) -> Any:
        headers = {
            "apikey": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        for attempt in range(retries):
            await self._bucket.acquire()
            logger.info(f"[Kiwi] {method} {url} params={params} body_keys={list(json_body.keys()) if json_body else None}")
            try:
                resp = await self._client.request(
                    method, url, params=params, json=json_body, headers=headers
                )
                if resp.status_code == 429:
                    wait = 2 ** attempt * 2
                    logger.warning(f"429 rate limited — retrying in {wait}s (attempt {attempt + 1}/{retries})")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"[Kiwi] Response OK — {type(data).__name__} len={len(data) if isinstance(data, (list, dict)) else 'N/A'}")
                return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < retries - 1:
                    wait = 2 ** attempt * 2
                    logger.warning(f"429 rate limited — retrying in {wait}s")
                    await asyncio.sleep(wait)
                    continue
                logger.error(f"[Kiwi] HTTP error {e.response.status_code}: {e.response.text[:500]}")
                raise
            except Exception as e:
                logger.error(f"[Kiwi] Request error: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        return None

    async def search(self, params: dict) -> dict:
        params.setdefault("curr", "EUR")
        data = await self._request("GET", f"{SEARCH_BASE}/search", self._search_key, params=params)
        return data or {"data": [], "_results": 0}

    async def search_multi(self, body: dict) -> list:
        body.setdefault("curr", "EUR")
        body.setdefault("locale", "en")
        data = await self._request("POST", f"{SEARCH_BASE}/flights_multi", self._multi_key, json_body=body)
        if isinstance(data, list):
            return data
        return []

    async def locations_query(self, term: str, **kwargs: Any) -> list:
        cache_key = f"lq:{term}:{kwargs}"
        cached = self._loc_cache.get(cache_key)
        if cached is not None:
            return cached
        params = {"term": term, "active_only": "true", "limit": kwargs.get("limit", 10)}
        if "location_types" in kwargs:
            params["location_types"] = kwargs["location_types"]
        data = await self._request("GET", f"{LOCATIONS_BASE}/query", self._search_key, params=params)
        result = data.get("locations", []) if data else []
        self._loc_cache.set(cache_key, result)
        return result

    async def locations_radius(self, lat: float, lon: float, radius: int = 250, **kwargs: Any) -> list:
        cache_key = f"lr:{lat:.4f}:{lon:.4f}:{radius}:{kwargs}"
        cached = self._loc_cache.get(cache_key)
        if cached is not None:
            return cached
        params = {
            "lat": str(lat),
            "lon": str(lon),
            "radius": str(radius),
            "active_only": "true",
            "limit": str(kwargs.get("limit", 20)),
        }
        if "location_types" in kwargs:
            params["location_types"] = kwargs["location_types"]
        data = await self._request("GET", f"{LOCATIONS_BASE}/radius", self._search_key, params=params)
        result = data.get("locations", []) if data else []
        self._loc_cache.set(cache_key, result)
        return result

    async def locations_subentity(self, term: str, **kwargs: Any) -> list:
        cache_key = f"ls:{term}:{kwargs}"
        cached = self._loc_cache.get(cache_key)
        if cached is not None:
            return cached
        params = {"term": term, "active_only": "true", "limit": str(kwargs.get("limit", 20))}
        if "location_types" in kwargs:
            params["location_types"] = kwargs["location_types"]
        data = await self._request("GET", f"{LOCATIONS_BASE}/subentity", self._search_key, params=params)
        result = data.get("locations", []) if data else []
        self._loc_cache.set(cache_key, result)
        return result

    async def locations_topdestinations(self, term: str, **kwargs: Any) -> list:
        cache_key = f"lt:{term}:{kwargs}"
        cached = self._loc_cache.get(cache_key)
        if cached is not None:
            return cached
        params = {"term": term, "limit": str(kwargs.get("limit", 20))}
        data = await self._request("GET", f"{LOCATIONS_BASE}/topdestinations", self._search_key, params=params)
        result = data.get("locations", []) if data else []
        self._loc_cache.set(cache_key, result)
        return result

    async def close(self) -> None:
        await self._client.aclose()


_client: KiwiClient | None = None


def get_kiwi_client() -> KiwiClient:
    global _client
    if _client is None:
        _client = KiwiClient()
    return _client
