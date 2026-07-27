"""Directory tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..clients import people as _client
from ..core import AsuApiError
from .format import format_people


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def search_people(
        query: Annotated[
            str,
            Field(
                description=(
                    "A name, department, or research topic. A student's own "
                    "phrasing is fine -- filler words are stripped and "
                    "abbreviations expanded before searching."
                )
            ),
        ],
        limit: Annotated[
            int, Field(description="Maximum people to return.", ge=1, le=25)
        ] = 8,
    ) -> str:
        """Search ASU's public faculty and staff directory.

        Returns names, titles, departments, published contact details, research
        interests and profile links. Use it to find who works on a topic, or to
        look up one person a student already named.

        Name lookups are reliable. Topic lookups depend on the person having
        listed that expertise, so an empty result means the directory has
        nobody indexed under those words -- not that ASU has nobody. When a
        relaxed form of the query is what matched, the reply says so.
        """
        try:
            people, searched_as = _client.search(query, size=limit)
        except AsuApiError as exc:
            return f"Error: {exc}"
        return format_people(people, query=query, searched_as=searched_as)
