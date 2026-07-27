"""One topic, all four sources at once.

Every other tool is shaped like the ASU system behind it, which is exactly the
fragmentation a student is stuck with today: to find out what ASU offers on a
subject you check the catalog, then the directory, then the calendar, then the
newsroom. This asks all four in parallel and answers in one pass.

It is deliberately a summary, not a replacement. Each section is capped at a
few rows and names the tool to call for depth -- seats and class numbers,
contact details, registration links.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from . import clients
from .classes.format import normalize
from .core import AsuApiError
from .news.client import clean_summary
from .news.format import relevance


def _classes_section(topic: str, term: str | None, limit: int) -> str:
    resolved = clients.classes.resolve_term(term)
    payload, searched_as = clients.classes.search_expanding(
        resolved.code, keywords=topic, max_results=200
    )
    rows = [normalize(record) for record in payload.get("classes") or []]
    if not rows:
        return f"CLASSES — nothing matching '{topic}' in {resolved}"

    courses: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        tally = courses.setdefault((row["course"], row["title"]), {"total": 0, "open": 0})
        tally["total"] += 1
        tally["open"] += 1 if row["is_open"] else 0

    ranked = sorted(courses.items(), key=lambda item: -item[1]["total"])
    header = f"CLASSES — {len(courses)} course(s) in {resolved}"
    if searched_as:
        header += f" (searched as '{searched_as}')"
    lines = [header]
    for (course, title), tally in ranked[:limit]:
        lines.append(
            f"  {course} — {title} · {tally['total']} section(s), "
            f"{tally['open']} with open seats"
        )
    if len(ranked) > limit:
        lines.append(f"  ... and {len(ranked) - limit} more")
    lines.append(f"  -> search_classes(query='{topic}') for times, seats and class numbers")
    return "\n".join(lines)


def _people_section(topic: str, limit: int) -> str:
    people, searched_as = clients.people.search(topic, size=limit)
    if not people:
        return (
            f"PEOPLE — nobody in the directory is indexed under '{topic}' "
            "(the directory matches stated expertise, not full text)"
        )
    header = f"PEOPLE — {len(people)} match(es)"
    if searched_as:
        header += f" (searched as '{searched_as}')"
    lines = [header]
    for person in people:
        bits = [person["name"]]
        if person.get("title"):
            bits.append(person["title"])
        if person.get("departments"):
            bits.append(person["departments"][0])
        line = " — ".join(bits)
        if person.get("email"):
            line += f" · {person['email']}"
        lines.append(f"  {line}")
    lines.append("  -> search_people for research interests and full contact details")
    return "\n".join(lines)


def _events_section(topic: str, limit: int) -> str:
    # No any-word relaxation in a digest: a partial match here reads as an
    # answer to the topic, and 'nothing on the calendar' is a better one.
    result = clients.events.search(keywords=topic, limit=limit, relax=False)
    events = result.get("events") or []
    if not events:
        scanned = result.get("scanned") or 0
        where = (
            f" out of {scanned} upcoming events "
            f"({result.get('from_date')} to {result.get('to_date')})"
            if scanned
            else ""
        )
        return f"EVENTS — nothing on the calendar matching '{topic}'{where}"

    header = f"EVENTS — {len(events)} upcoming"
    if result.get("matched_as"):
        header += f" (searched as '{result['matched_as']}')"
    if result.get("relaxed"):
        header += " (matching at least one word)"
    lines = [header]
    for event in events:
        when = event.get("date_display") or event["date"]
        lines.append(f"  {when} — {event['title']}")
        lines.append(f"    {event['url']}")
    return "\n".join(lines)


def _news_section(topic: str, limit: int) -> str:
    stories = clients.news.search(topic, limit=limit)
    if not stories:
        return f"NEWS — no ASU News stories matched '{topic}'"
    lines = [f"NEWS — {len(stories)} story/stories"]
    for story in stories:
        lines.append(f"  {story['date']} — {story['title']}")
        summary = clean_summary(story.get("summary", ""), limit=140)
        if summary:
            lines.append(f"    {summary}")
        # The newsroom ranks on full article text. In a digest a tangential hit
        # reads as ASU's answer on the topic, so say when it is one.
        note = relevance(story, topic)
        if note:
            lines.append(f"    [{note}]")
        lines.append(f"    {story['url']}")
    return "\n".join(lines)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def search_asu(
        topic: Annotated[
            str,
            Field(
                description=(
                    "One subject to look up everywhere, e.g. 'robotics', "
                    "'sustainability', 'quantum computing'."
                )
            ),
        ],
        term: Annotated[
            str | None,
            Field(description="Term for the class results, e.g. 'Fall 2026'. Defaults to current."),
        ] = None,
        limit_each: Annotated[
            int, Field(description="Rows per section.", ge=1, le=10)
        ] = 3,
    ) -> str:
        """Everything ASU has on one topic: classes, people, events and news.

        Use this to open a broad question -- "what does ASU do in robotics", "I
        want to get into sustainability" -- where a student does not yet know
        which system holds the answer. One call replaces four.

        Use the specific tool instead when the question is already narrow: a
        named person, a course's seats, a particular event, this week's news.
        Each section here is a summary and names the tool to call for depth.
        """
        sections: list[tuple[str, Any]] = [
            ("CLASSES", lambda: _classes_section(topic, term, limit_each)),
            ("PEOPLE", lambda: _people_section(topic, limit_each)),
            ("EVENTS", lambda: _events_section(topic, limit_each)),
            ("NEWS", lambda: _news_section(topic, limit_each)),
        ]

        def run(entry: tuple[str, Any]) -> str:
            label, work = entry
            try:
                return work()
            except AsuApiError as exc:
                # One dead source should not take the other three with it.
                return f"{label} — unavailable: {exc}"

        # Four independent backends; serially this is four round trips of
        # latency for a question that is one question.
        with ThreadPoolExecutor(max_workers=4) as pool:
            rendered = list(pool.map(run, sections))

        return f"ASU on '{topic}'\n\n" + "\n\n".join(rendered)
