"""Render event listings."""

from __future__ import annotations

from typing import Any


def _coverage(result: dict[str, Any]) -> str:
    """State what was actually searched, so 'nothing' is a real answer."""
    if not result.get("scanned"):
        return ""
    return (
        f"{result['scanned']} upcoming events "
        f"({result['from_date']} to {result['to_date']})"
    )


def format_events(result: dict[str, Any], *, described: str) -> str:
    events = result.get("events") or []
    coverage = _coverage(result)

    if not events:
        # Say what was checked. Otherwise a model reads an empty result as a
        # tool failure, or tells the student ASU has nothing on at all.
        scope = f" Searched {coverage}." if coverage else ""
        return (
            f"No upcoming ASU events matched {described}.{scope} Only titles and "
            "locations are searchable -- not descriptions -- so an event about "
            "this may exist under a different name. Try one broader word, or "
            "drop the keywords to see what's on."
        )

    header = f"{len(events)} upcoming event(s) matching {described}"
    if result.get("matched_as"):
        header += f" (searched as '{result['matched_as']}')"
    if result.get("relaxed"):
        header += " (no event matched every word, so these match at least one)"
    if coverage:
        header += f", out of {coverage}"
    lines = [f"{header}:"]
    current_day: str | None = None
    for event in events:
        if event["date_display"] != current_day:
            current_day = event["date_display"]
            lines.append(f"\n{current_day or event['date']}")
        parts = [f"  {event['title']}"]
        detail = " · ".join(p for p in [event.get("time"), event.get("location")] if p)
        if detail:
            parts.append(f"    {detail}")
        parts.append(f"    {event['url']}")
        lines.extend(parts)
    return "\n".join(lines)


def format_event_detail(event: dict[str, Any], detail: dict[str, Any]) -> str:
    lines = [detail.get("title") or event["title"]]
    when = " · ".join(p for p in [event.get("date_display"), event.get("time")] if p)
    if when:
        lines.append(f"\nWhen:  {when}")
    if event.get("location"):
        lines.append(f"Where: {event['location']}")
    if detail.get("description"):
        lines.append(f"\n{detail['description']}")
    if detail.get("registration_url"):
        lines.append(f"\nRegister: {detail['registration_url']}")
    lines.append(f"\n{event['url']}")
    return "\n".join(lines)
