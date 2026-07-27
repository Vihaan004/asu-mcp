"""ASU News (news.asu.edu).

collagent sourced news through Tavily, a paid web-search API. That is wrong for
a connector other people install: it needs an API key, it bills the operator for
every user's query, and it returns whatever the open web says about ASU rather
than what ASU published. This reads the newsroom's own search instead -- free,
keyless, and authoritative.

news.asu.edu is Drupal 10 with no JSON:API, so the search results page is the
interface. Results come back in a table, one row per story.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from ..core import AsuHttpClient

BASE = "https://news.asu.edu"
SEARCH_TTL = 30 * 60

# Story URLs encode their date and section: /20260625-environment-and-...
_STORY_HREF = re.compile(r"^/(\d{4})(\d{2})(\d{2})-([a-z0-9-]+)")


def _text(node: Any) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def parse_search(html: str) -> list[dict[str, Any]]:
    """Parse the newsroom search page into story rows. Pure."""
    soup = BeautifulSoup(html, "html.parser")
    stories: list[dict[str, Any]] = []
    seen: set[str] = set()

    for cell in soup.select("table td"):
        link = None
        for anchor in cell.find_all("a", href=True):
            if _STORY_HREF.match(anchor["href"]):
                link = anchor
                break
        if link is None:
            continue

        href = link["href"]
        if href in seen:
            continue
        seen.add(href)

        match = _STORY_HREF.match(href)
        year, month, day, slug = match.groups()
        # The section is the leading words of the slug, before the headline.
        section = slug.replace("-", " ")

        title = _text(link)
        # Everything after the headline in the cell is date + summary text.
        body = _text(cell)
        summary = body.replace(title, "", 1).strip() if title else body

        stories.append(
            {
                "title": title,
                "url": f"{BASE}{href}",
                "date": f"{year}-{month}-{day}",
                "section": section,
                "summary": summary,
            }
        )
    return stories


class NewsClient:
    def __init__(self) -> None:
        self._http = AsuHttpClient(BASE, headers={"Accept": "text/html"})

    def close(self) -> None:
        self._http.close()

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Search stories, preserving the newsroom's own relevance ranking.

        Deliberately not re-sorted by date: the search page returns results
        ranked by relevance, and sorting by date instead floats whatever is
        newest to the top regardless of whether it matches the query.
        """
        html = self._http.get_text("/search", {"search": query}, ttl=SEARCH_TTL)
        return parse_search(html)[:limit]

    def latest(self, limit: int = 8) -> list[dict[str, Any]]:
        html = self._http.get_text("/", None, ttl=SEARCH_TTL)
        stories = parse_search(html)
        if not stories:
            # The front page is not a table; fall back to a broad search.
            return self.search("ASU", limit=limit)
        stories.sort(key=lambda s: s["date"], reverse=True)
        return stories[:limit]


def clean_summary(text: str, limit: int = 240) -> str:
    """Strip the leading 'Jun 25, 2026' the cell text carries, then trim."""
    trimmed = re.sub(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}\s*", "", text).strip()
    if len(trimmed) <= limit:
        return trimmed
    return trimmed[: limit - 1].rstrip() + "…"
