"""Directory tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..core import AsuApiError
from .client import PeopleClient
from .format import format_people

_client = PeopleClient()


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def search_people(
        query: Annotated[
            str,
            Field(
                description=(
                    "A name, department, or research topic. Keep it short -- the "
                    "directory matches every word, so 'Yezhou Yang' works and "
                    "'who is professor Yezhou Yang at ASU' does not."
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
        """
        try:
            people = _client.search(query, size=limit)
        except AsuApiError as exc:
            return f"Error: {exc}"
        return format_people(people, query=query)
