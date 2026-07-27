"""News tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..clients import news as _client
from ..core import AsuApiError
from .format import format_news


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def search_news(
        query: Annotated[
            str | None,
            Field(
                description=(
                    "Topic to search ASU News for, e.g. 'robotics', 'semiconductor "
                    "research'. Omit for the latest stories."
                )
            ),
        ] = None,
        limit: Annotated[
            int, Field(description="Maximum stories to return.", ge=1, le=25)
        ] = 8,
    ) -> str:
        """Search ASU's newsroom for university news and research stories.

        Covers what ASU itself published: research announcements, student and
        faculty stories, university news.

        Results keep the newsroom's own relevance order, which ranks on full
        article text. A story whose headline looks unrelated is marked with
        what actually matched, so a tangential hit is visible as one.
        """
        try:
            stories = (
                _client.search(query, limit=limit) if query else _client.latest(limit=limit)
            )
        except AsuApiError as exc:
            return f"Error: {exc}"
        return format_news(
            stories,
            described=f"'{query}'" if query else "the latest news",
            query=query,
        )
