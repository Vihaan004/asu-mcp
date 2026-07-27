"""ASU events calendar (asuevents.asu.edu).

The site is Drupal 10 and does expose JSON:API, but it is not usable here: the
`node--asu_event` index only holds 2021-2023 content, and date filtering on the
multi-value smart_date field is broken (a `> 2099` filter still returns rows).
The rendered listing is the only view that reflects the live calendar, so we
parse that.

The listing carries title, date, time and location per card, so a search costs
one request per page rather than one per event. Card titles are truncated at
~36 characters though, so we fetch the detail page for those -- roughly a
quarter of them -- and for get_event.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from bs4 import BeautifulSoup

from ..core import AsuApiError, AsuHttpClient
from ..query import expand, matches, matches_any

BASE = "https://asuevents.asu.edu"
LISTING_TTL = 30 * 60
DETAIL_TTL = 6 * 60 * 60
CARDS_PER_PAGE = 24

_EVENT_HREF = re.compile(r"^/event/([a-z0-9-]+)\?eventDate=(\d{4}-\d{2}-\d{2})")


def _text(node: Any) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _is_truncated(title: str) -> bool:
    return title.endswith("…") or title.endswith("...")


def parse_listing(html: str) -> list[dict[str, Any]]:
    """Parse one listing page into event rows. Pure."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    for card in soup.select("li.card-event"):
        link = card.select_one("h3.card-title a")
        if not link or not link.get("href"):
            continue
        match = _EVENT_HREF.match(link["href"])
        if not match:
            continue
        slug, event_date = match.groups()
        title = _text(link)
        rows.append(
            {
                "slug": slug,
                "date": event_date,
                "title": title,
                "title_truncated": _is_truncated(title),
                "date_display": _text(card.select_one(".views-field-field-event-date-value-1")),
                "time": _text(card.select_one(".views-field-field-event-date-end-value")),
                "location": _text(card.select_one(".views-field-field-asu-events-location")),
                "url": f"{BASE}/event/{slug}?eventDate={event_date}",
            }
        )
    return rows


def parse_detail(html: str) -> dict[str, Any]:
    """Pull the full title and description off an event page. Pure."""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    for selector in ("h1", "meta[property='og:title']"):
        node = soup.select_one(selector)
        if node is not None:
            title = _text(node) or (node.get("content") or "").strip()
            if title:
                break

    description = ""
    meta = soup.select_one("meta[name='description'], meta[property='og:description']")
    if meta is not None:
        description = (meta.get("content") or "").strip()

    registration = ""
    for anchor in soup.find_all("a", href=True):
        label = _text(anchor).lower()
        if label in {"rsvp", "register", "registration", "sign up"}:
            registration = anchor["href"]
            break

    return {"title": title, "description": description, "registration_url": registration}


class EventsClient:
    def __init__(self) -> None:
        self._http = AsuHttpClient(BASE, headers={"Accept": "text/html"})

    def close(self) -> None:
        self._http.close()

    def upcoming(self, pages: int = 3) -> list[dict[str, Any]]:
        """Fetch the next few listing pages, in chronological order."""
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for page in range(pages):
            html = self._http.get_text("/", {"page": page}, ttl=LISTING_TTL)
            parsed = parse_listing(html)
            if not parsed:
                break
            for row in parsed:
                key = (row["slug"], row["date"])
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
        return rows

    def detail(self, slug: str, event_date: str) -> dict[str, Any]:
        html = self._http.get_text(
            f"/event/{slug}", {"eventDate": event_date}, ttl=DETAIL_TTL
        )
        return parse_detail(html)

    def search(
        self,
        *,
        keywords: str | None = None,
        campus: str | None = None,
        on_date: str | None = None,
        through_date: str | None = None,
        limit: int = 15,
        pages: int = 6,
        relax: bool = True,
    ) -> dict[str, Any]:
        """Upcoming events, filtered client-side.

        The listing ignores a `search` query parameter -- it returns the same
        24 cards whatever you pass -- so every filter here is applied locally.

        Returns the matches plus what was actually searched. A caller that only
        gets an empty list cannot tell "ASU has no such event" from "this tool
        is broken", and will happily tell a student the wrong one.
        """
        scanned = self.upcoming(pages=pages)
        rows = scanned

        if on_date:
            rows = [r for r in rows if r["date"] == on_date]
        if through_date:
            rows = [r for r in rows if r["date"] <= through_date]
        if campus:
            needle = campus.strip().lower()
            rows = [r for r in rows if needle in r["location"].lower()]

        relaxed = False
        matched_as = ""
        if keywords:

            def haystack(row: dict[str, Any]) -> str:
                # The slug is built from the untruncated title, so it recovers
                # some of what the listing cut off.
                return f"{row['title']} {row['location']} {row['slug'].replace('-', ' ')}"

            # Organisers title events with abbreviations ('AI Upskilling Office
            # Hours'), students ask in full. Try every form before giving up.
            variants = expand(keywords)
            found: list[dict[str, Any]] = []
            for variant in variants:
                found = [r for r in rows if matches(haystack(r), variant)]
                if found:
                    matched_as = variant
                    break

            if not found and relax:
                # Nothing matched every word in any form; fall back to any word
                # rather than reporting a bare nothing. Callers that cannot
                # label the looser match turn this off -- 'quantum computing'
                # relaxes to every Research Computing office hour on the
                # calendar, which is noise wearing the shape of an answer.
                for variant in variants:
                    found = [r for r in rows if matches_any(haystack(r), variant)]
                    if found:
                        matched_as, relaxed = variant, True
                        break
            rows = found

        rows = rows[:limit]

        # Only pay for a detail fetch where the listing actually cut the title.
        for row in rows:
            if row["title_truncated"]:
                try:
                    full = self.detail(row["slug"], row["date"])
                except AsuApiError:
                    continue
                if full.get("title"):
                    row["title"] = full["title"]
                    row["title_truncated"] = False

        return {
            "events": rows,
            "scanned": len(scanned),
            "from_date": scanned[0]["date"] if scanned else "",
            "to_date": scanned[-1]["date"] if scanned else "",
            "relaxed": relaxed,
            # Only set when a rewritten form is what actually matched, so the
            # reply can say "searched as AI" instead of silently answering a
            # different question than the one asked.
            "matched_as": (
                matched_as
                if matched_as and matched_as.lower() != (keywords or "").strip().lower()
                else ""
            ),
        }


def today_iso() -> str:
    return date.today().isoformat()


def parse_date_input(value: str | None) -> str | None:
    """Accept YYYY-MM-DD or 'today'; anything else is an error worth surfacing."""
    if not value:
        return None
    raw = value.strip().lower()
    if raw == "today":
        return today_iso()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise AsuApiError(f"date {value!r} must be YYYY-MM-DD or 'today'") from exc
