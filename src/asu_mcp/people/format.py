"""Render directory results."""

from __future__ import annotations

from typing import Any


def _truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def format_people(people: list[dict[str, Any]], *, query: str) -> str:
    if not people:
        return (
            f"Nobody in the ASU directory matched '{query}'. Try just a surname, "
            "a department, or a research topic."
        )

    lines = [f"{len(people)} match(es) for '{query}':"]
    for person in people:
        lines.append(f"\n{person['name']}")
        if person.get("title"):
            lines.append(f"  {person['title']}")
        if person.get("departments"):
            lines.append(f"  {', '.join(person['departments'])}")

        contact = [c for c in [person.get("email"), person.get("phone")] if c]
        if contact:
            lines.append(f"  {' · '.join(contact)}")

        if person.get("expertise_areas"):
            lines.append(f"  Expertise: {', '.join(person['expertise_areas'][:8])}")
        # Research interests run long; enough to judge fit, not the whole bio.
        interests = _truncate(person.get("research_interests"), 260)
        if interests:
            lines.append(f"  Research: {interests}")
        elif person.get("short_bio"):
            lines.append(f"  Bio: {_truncate(person.get('short_bio'), 260)}")

        lines.append(f"  {person['profile_url']}")

    lines.append(
        "\nEmail addresses are published in ASU's public directory. Introduce "
        "yourself and say why you're reaching out."
    )
    return "\n".join(lines)
