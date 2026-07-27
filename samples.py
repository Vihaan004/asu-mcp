"""Call every tool through the real MCP path and print input -> output.

Not a test -- it hits the live ASU endpoints. Run it to see what a model
actually receives, and to spot a source that has changed shape.

    uv run python samples.py
"""

import asyncio
import sys

from asu_mcp.server import mcp

CASES: list[tuple[str, dict]] = [
    ("search_asu", {"topic": "robotics"}),
    ("search_classes", {"subject": "CSE", "catalog_number": "310", "open_only": True}),
    ("search_classes", {"query": "machine learning", "open_only": True, "max_results": 6}),
    # The catalog indexes spelled-out course titles, so this only works expanded.
    ("search_classes", {"query": "AI", "max_results": 4}),
    ("get_class", {"class_number": "66445"}),
    ("list_terms", {}),
    ("search_people", {"query": "robotics", "limit": 3}),
    ("search_people", {"query": "who is professor Yezhou Yang at ASU", "limit": 2}),
    ("search_people", {"query": "someone who works on quantum computing at ASU", "limit": 3}),
    ("search_events", {"limit": 6}),
    ("search_events", {"query": "research", "limit": 4}),
    # ...and this only works contracted: organisers title these events 'AI'.
    ("search_events", {"query": "artificial intelligence", "limit": 3}),
    ("get_event", {"url": ""}),  # filled in from search_events below
    ("search_news", {"query": "robotics", "limit": 3}),
]

TRIM = {
    "list_terms": 12,
    "search_classes": 40,
    "search_people": 40,
    "search_news": 40,
    "search_asu": 40,
}


async def call(name: str, args: dict) -> str:
    result = await mcp.call_tool(name, args)
    blocks = result[0] if isinstance(result, tuple) else result
    return "\n".join(getattr(b, "text", "") for b in blocks)


def show(name: str, args: dict, output: str) -> None:
    print("=" * 78)
    print(f"TOOL   {name}")
    print(f"INPUT  {args}")
    print("-" * 78)
    limit = TRIM.get(name, 60)
    lines = output.splitlines()
    print("\n".join(lines[:limit]))
    if len(lines) > limit:
        print(f"... [{len(lines) - limit} more lines]")
    print()


async def main() -> int:
    first_event_url = ""
    for name, args in CASES:
        if name == "get_event":
            if not first_event_url:
                print("(skipping get_event: no event URL captured)")
                continue
            args = {"url": first_event_url}
        try:
            output = await call(name, args)
        except Exception as exc:  # noqa: BLE001 - sample script, show anything
            output = f"RAISED {type(exc).__name__}: {exc}"
        if name == "search_events" and not first_event_url:
            for line in output.splitlines():
                if line.strip().startswith("https://asuevents.asu.edu/event/"):
                    first_event_url = line.strip()
                    break
        show(name, args, output)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
