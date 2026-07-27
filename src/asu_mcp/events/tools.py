"""Event tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..core import AsuApiError
from .client import EventsClient, parse_date_input
from .format import format_event_detail, format_events

_client = EventsClient()


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def search_events(
        keywords: Annotated[
            str | None,
            Field(description="Words that must all appear in the title or location."),
        ] = None,
        campus: Annotated[
            str | None,
            Field(description="Filter by location text, e.g. 'Tempe', 'Polytechnic', 'Online'."),
        ] = None,
        on_date: Annotated[
            str | None, Field(description="A single day, 'YYYY-MM-DD' or 'today'.")
        ] = None,
        through_date: Annotated[
            str | None, Field(description="Latest day to include, 'YYYY-MM-DD'.")
        ] = None,
        limit: Annotated[
            int, Field(description="Maximum events to return.", ge=1, le=50)
        ] = 15,
    ) -> str:
        """Search upcoming events on ASU's university-wide calendar.

        Covers roughly the next two months: talks, workshops, info sessions,
        exhibitions, club and athletics events. Returns date, time, location
        and a link.

        Keywords match event titles and locations only, not descriptions, so
        prefer one broad word ('research', 'career') over a specific phrase.
        The reply states how many events were searched and over what dates --
        an empty result means nothing matched, not that the search failed.
        Past events are not available.
        """
        try:
            result = _client.search(
                keywords=keywords,
                campus=campus,
                on_date=parse_date_input(on_date),
                through_date=parse_date_input(through_date),
                limit=limit,
            )
        except AsuApiError as exc:
            return f"Error: {exc}"

        described = ", ".join(
            f"{label} {value}"
            for label, value in [
                ("keywords", keywords),
                ("campus", campus),
                ("on", on_date),
                ("through", through_date),
            ]
            if value
        ) or "anything upcoming"
        return format_events(result, described=described)

    @mcp.tool()
    def get_event(
        url: Annotated[
            str,
            Field(
                description=(
                    "The event URL from search_events, e.g. "
                    "https://asuevents.asu.edu/event/some-slug?eventDate=2026-08-04"
                )
            ),
        ],
    ) -> str:
        """Get the full description and registration link for one event.

        Search results carry date, time and location already; use this when a
        student wants to know what an event actually involves, or how to sign up.
        """
        try:
            from urllib.parse import parse_qs, urlparse

            parsed = urlparse(url)
            slug = parsed.path.rstrip("/").split("/")[-1]
            event_date = (parse_qs(parsed.query).get("eventDate") or [""])[0]
            if not slug or not event_date:
                return (
                    "Error: that does not look like an ASU event URL. Use the "
                    "link from search_events, which includes ?eventDate=."
                )
            detail = _client.detail(slug, event_date)
            # The detail page does not repeat the time or venue, so recover them
            # from the listing card for this same date.
            card = next(
                (
                    row
                    for row in _client.upcoming()
                    if row["slug"] == slug and row["date"] == event_date
                ),
                None,
            )
        except AsuApiError as exc:
            return f"Error: {exc}"

        stub = card or {
            "title": detail.get("title") or slug.replace("-", " ").title(),
            "date": event_date,
            "date_display": event_date,
            "time": "",
            "location": "",
            "url": url,
        }
        return format_event_detail({**stub, "url": url}, detail)
