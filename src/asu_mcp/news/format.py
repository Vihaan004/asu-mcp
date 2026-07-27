"""Render news results."""

from __future__ import annotations

from typing import Any

from ..query import matches, words
from .client import clean_summary


def relevance(story: dict[str, Any], query: str | None) -> str:
    """Say why a story is in the list when the headline does not show it.

    The newsroom ranks on full article text, so a quantum-computing story can
    land in an AI search on the strength of one sentence nobody can see. Naming
    the terms that did and did not surface lets a reader judge it.
    """
    terms = words(query or "")
    if not terms:
        return ""
    visible = f"{story.get('title', '')} {story.get('summary', '')} {story.get('section', '')}"
    hit = [t for t in terms if matches(visible, t)]
    if len(hit) == len(terms):
        return ""
    if not hit:
        return "matched the article text, not the headline or summary"
    return f"headline/summary matches only: {', '.join(hit)}"


def format_news(
    stories: list[dict[str, Any]], *, described: str, query: str | None = None
) -> str:
    if not stories:
        return (
            f"No ASU News stories matched {described}. Try broader terms -- the "
            "newsroom search matches the story text, not tags."
        )

    lines = [f"{len(stories)} story/stories matching {described}, most relevant first:"]
    for story in stories:
        lines.append(f"\n{story['title']}")
        lines.append(f"  {story['date']}")
        summary = clean_summary(story.get("summary", ""))
        if summary:
            lines.append(f"  {summary}")
        note = relevance(story, query)
        if note:
            lines.append(f"  [{note}]")
        lines.append(f"  {story['url']}")
    return "\n".join(lines)
