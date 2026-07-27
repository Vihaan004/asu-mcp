"""Render news results."""

from __future__ import annotations

from typing import Any

from .client import clean_summary


def format_news(stories: list[dict[str, Any]], *, described: str) -> str:
    if not stories:
        return (
            f"No ASU News stories matched {described}. Try broader terms -- the "
            "newsroom search matches the story text, not tags."
        )

    lines = [f"{len(stories)} story/stories matching {described}:"]
    for story in stories:
        lines.append(f"\n{story['title']}")
        lines.append(f"  {story['date']}")
        summary = clean_summary(story.get("summary", ""))
        if summary:
            lines.append(f"  {summary}")
        lines.append(f"  {story['url']}")
    return "\n".join(lines)
