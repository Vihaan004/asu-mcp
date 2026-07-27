"""Shared plumbing for every ASU data source this server exposes.

Hosting changes the calculus. Run locally, each student's queries come from
their own machine; run as one hosted connector and every request hits ASU's
undocumented endpoints from a single IP. So caching here is not a performance
nicety, it is what keeps this from looking like a scraper.
"""

from __future__ import annotations

import html as _html
import os
import re
import threading
import time
from typing import Any

import httpx

_TAG = re.compile(r"<[^>]+>")


def plain_text(value: Any) -> str:
    """Strip markup and entities out of a field.

    Several ASU sources hand back pre-rendered HTML inside what look like plain
    string fields -- class meeting times as '3:00 PM<br/>&nbsp;-5:45 PM',
    directory research interests wrapped in <p> tags. Not defensive coding;
    both fire on real records.
    """
    text = str(value or "")
    if not text:
        return ""
    text = _TAG.sub(" ", text)
    text = _html.unescape(text).replace("\xa0", " ")
    return " ".join(text.split())

# Identify ourselves where we can. Some ASU endpoints reject non-browser agents
# outright, so the default stays browser-shaped; set ASU_MCP_USER_AGENT to
# override with contact details if you run this at volume.
DEFAULT_USER_AGENT = os.environ.get(
    "ASU_MCP_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
)


class AsuApiError(RuntimeError):
    """Any failure talking to an ASU backend."""


class AnonymousAuthRejected(AsuApiError):
    """An endpoint stopped accepting anonymous access.

    Raised instead of returning nothing, because the fix is always to go
    re-read how the public site authenticates now -- never to retry.
    """


class TTLCache:
    """Small thread-safe TTL cache.

    Sync tool functions run in FastMCP's worker threadpool, so several
    requests can land here at once.
    """

    def __init__(self, max_entries: int = 512) -> None:
        self._data: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._max_entries = max_entries

    def get(self, key: Any) -> Any | None:
        now = time.monotonic()
        with self._lock:
            hit = self._data.get(key)
            if hit is None:
                return None
            expires_at, value = hit
            if expires_at < now:
                del self._data[key]
                return None
            return value

    def set(self, key: Any, value: Any, ttl: float) -> None:
        with self._lock:
            if len(self._data) >= self._max_entries:
                # Cheap eviction: drop whatever expires soonest.
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
            self._data[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


def cache_key(path: str, params: dict[str, Any] | None) -> tuple[Any, ...]:
    return (path, tuple(sorted((params or {}).items())))


class AsuHttpClient:
    """JSON client with a shared cache, aimed at one ASU backend."""

    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        cache: TTLCache | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._cache = cache if cache is not None else TTLCache()
        self._http = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "application/json",
                **(headers or {}),
            },
        )

    def close(self) -> None:
        self._http.close()

    def get_text(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        ttl: float = 0.0,
    ) -> str:
        """Fetch a page body. For sources with no API, only rendered HTML."""
        key = ("text", *cache_key(path, params)) if ttl > 0 else None
        if key is not None:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
        body = self._fetch(path, params).text
        if key is not None:
            self._cache.set(key, body, ttl)
        return body

    def get_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        ttl: float = 0.0,
    ) -> Any:
        key = cache_key(path, params) if ttl > 0 else None
        if key is not None:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

        response = self._fetch(path, params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise AsuApiError(f"{self.base_url}{path} returned non-JSON") from exc

        if key is not None:
            self._cache.set(key, payload, ttl)
        return payload

    def _fetch(self, path: str, params: dict[str, Any] | None) -> httpx.Response:
        url = f"{self.base_url}{path}"
        try:
            response = self._http.get(url, params=params)
        except httpx.HTTPError as exc:
            raise AsuApiError(f"could not reach {url}: {exc}") from exc

        if response.status_code in (401, 403):
            raise AnonymousAuthRejected(
                f"{url} rejected anonymous access ({response.status_code}). "
                "ASU changed how this public endpoint authenticates; this "
                "server needs updating against the current site."
            )
        if response.status_code >= 400:
            raise AsuApiError(
                f"{url} returned {response.status_code}: {response.text[:200]}"
            )
        return response
