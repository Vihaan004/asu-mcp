"""The ASU MCP server.

One connector covering ASU's public data. Class search today; people, events
and news to follow, each registering its own tools onto this same server --
because making students install four connectors would recreate the
fragmentation this is meant to remove.

Transports:
  stdio            local install (Claude Desktop, Claude Code) -- the default
  streamable-http  hosted, for claude.ai custom connectors
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .classes.tools import register as register_classes
from .events.tools import register as register_events
from .news.tools import register as register_news
from .people.tools import register as register_people
from .topic import register as register_topic

INSTRUCTIONS = """\
Arizona State University's public data, live. Four areas:

- Classes: sections, meeting times, instructors, locations and real-time seat \
availability for any ASU term.
- People: the public faculty and staff directory -- who works on what, with \
published contact details.
- Events: the university-wide calendar of upcoming talks, workshops and \
info sessions.
- News: stories ASU's own newsroom published.

For a broad topic question, start with search_asu -- it covers all four at once. \
Use the individual tools when the question is already narrow.

Queries are passed through as the student phrased them. Abbreviations are \
expanded in both directions ('AI' also tries 'artificial intelligence', and the \
reverse), because ASU's sources disagree about which form they index, and \
conversational filler is stripped before searching.

Class term codes are opaque four-digit numbers (Fall 2026 is 2267). Never guess \
one -- the tools accept plain labels like 'Fall 2026' and default to the current \
term, or call list_terms.

Seat counts are live but are not reservations; a class showing open seats can \
fill before a student enrolls. Enrollment happens in My ASU and cannot be done \
through these tools. The events calendar only covers what is scheduled ahead, \
so past events cannot be searched.

This is an unofficial tool built on ASU's public data. It is not operated by or \
endorsed by Arizona State University.
"""


def _transport() -> str:
    transport = os.environ.get("ASU_MCP_TRANSPORT", "stdio").strip()
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise SystemExit(
            f"unknown ASU_MCP_TRANSPORT {transport!r}; expected stdio, sse or streamable-http"
        )
    return transport


def build_server(transport: str = "stdio") -> FastMCP:
    http = transport != "stdio"
    mcp = FastMCP(
        "asu",
        instructions=INSTRUCTIONS,
        # No subscriptions or per-session state, so each HTTP request can stand
        # alone. Keeps it safe to run behind a load balancer or restart freely.
        stateless_http=http,
        json_response=http,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )

    register_topic(mcp)
    register_classes(mcp)
    register_people(mcp)
    register_events(mcp)
    register_news(mcp)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "asu-mcp"})

    return mcp


mcp = build_server(_transport())


def main() -> None:
    mcp.run(transport=_transport())  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
