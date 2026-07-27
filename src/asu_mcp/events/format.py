"""Render event listings."""

from __future__ import annotations

from typing import Any


def format_events(events: list[dict[str, Any]], *, described: str) -> str:
    if not events:
        return (
            f"No upcoming ASU events matched {described}. The calendar only "
            "covers what's scheduled ahead, so try broader keywords or drop the "
            "date filter."
        )

    lines = [f"{len(events)} upcoming event(s) matching {described}:"]
    current_day = None
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
