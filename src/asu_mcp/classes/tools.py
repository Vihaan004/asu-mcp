"""Class search tools, registered onto the shared server."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..core import AsuApiError
from .client import ClassSearchClient
from .format import format_class_detail, format_search_results

_client = ClassSearchClient()


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_terms() -> str:
        """List ASU terms available in class search, with their term codes.

        Use when the user names a semester you are unsure about, or asks what
        can be searched. The current term is marked.
        """
        try:
            terms, current = _client.terms()
        except AsuApiError as exc:
            return f"Error: {exc}"
        lines = [f"Current term: {current}", ""]
        lines += [
            f"  {t.code}  {t.label}{'  <- current' if t.code == current else ''}"
            for t in terms
        ]
        return "\n".join(lines)

    @mcp.tool()
    def list_subjects(
        term: Annotated[
            str | None,
            Field(description="Term label or code, e.g. 'Fall 2026' or '2267'. Defaults to current."),
        ] = None,
    ) -> str:
        """List subject codes offered in a term (CSE, MAT, ENG, ...).

        Use this to turn a plain-language field into the subject code
        search_classes expects -- 'computer science' becomes 'CSE'.
        """
        try:
            resolved = _client.resolve_term(term)
            subjects = _client.subjects(resolved.code)
        except AsuApiError as exc:
            return f"Error: {exc}"
        if not subjects:
            return f"No subjects returned for {resolved}."
        lines = [f"{len(subjects)} subjects in {resolved}:", ""]
        lines += [
            f"  {s['code']:<8}{s['description']}".rstrip() for s in subjects
        ]
        return "\n".join(lines)

    @mcp.tool()
    def search_classes(
        subject: Annotated[
            str | None, Field(description="Subject code, e.g. 'CSE'. Use list_subjects if unsure.")
        ] = None,
        catalog_number: Annotated[
            str | None, Field(description="Course number, e.g. '310'. Needs subject to be useful.")
        ] = None,
        keywords: Annotated[
            str | None, Field(description="Free text over title, description and instructor.")
        ] = None,
        instructor: Annotated[
            str | None, Field(description="Instructor last or full name.")
        ] = None,
        term: Annotated[
            str | None,
            Field(description="Term label or code, e.g. 'Fall 2026' or '2267'. Defaults to current."),
        ] = None,
        open_only: Annotated[
            bool, Field(description="Only sections that still have open seats.")
        ] = False,
        campus: Annotated[
            str | None,
            Field(description="TEMPE, POLY, WEST, DTPHX, ASUONLINE. Omit for all campuses."),
        ] = None,
        days_of_week: Annotated[
            str | None, Field(description="Comma-separated day codes, e.g. 'MON,WED'.")
        ] = None,
        start_time: Annotated[
            str | None, Field(description="Earliest start time, e.g. '10:00 AM'.")
        ] = None,
        end_time: Annotated[
            str | None, Field(description="Latest end time, e.g. '3:00 PM'.")
        ] = None,
        level: Annotated[str | None, Field(description="'lower', 'upper', or 'grad'.")] = None,
        units: Annotated[str | None, Field(description="Credit hours, e.g. '3'.")] = None,
        honors: Annotated[bool, Field(description="Only honors sections.")] = False,
        max_results: Annotated[
            int, Field(description="Cap on sections returned.", ge=1, le=300)
        ] = 100,
    ) -> str:
        """Search ASU's live class schedule for a term.

        Returns each matching section with its class number, meeting pattern,
        instructor, location and current seat count, grouped by course.

        Give at least one of subject, catalog_number, keywords or instructor.
        The class number in the results is what a student enters in My ASU.
        """
        if not any([subject, catalog_number, keywords, instructor]):
            return (
                "Error: give at least one of subject, catalog_number, keywords "
                "or instructor. Searching a whole term at once is not supported."
            )
        try:
            resolved = _client.resolve_term(term)
            payload = _client.search_classes(
                resolved.code,
                subject=subject,
                catalog_number=catalog_number,
                keywords=keywords,
                instructor=instructor,
                campus=campus,
                days_of_week=days_of_week,
                start_time=start_time,
                end_time=end_time,
                level=level,
                units=units,
                honors=honors,
                max_results=max_results,
            )
        except AsuApiError as exc:
            return f"Error: {exc}"
        return format_search_results(payload, term_label=str(resolved), open_only=open_only)

    @mcp.tool()
    def get_class(
        class_number: Annotated[
            str, Field(description="The five-digit class number, e.g. '66445'.")
        ],
        term: Annotated[
            str | None,
            Field(description="Term label or code. Defaults to current; class numbers are term-specific."),
        ] = None,
    ) -> str:
        """Get full detail for one section by its class number.

        Includes seats, meeting pattern, room with a campus map link,
        enrollment and drop/withdraw deadlines, and any consent or
        reserved-seat restrictions.
        """
        try:
            resolved = _client.resolve_term(term)
            payload = _client.search_classes(
                resolved.code, class_number=class_number, max_results=5
            )
        except AsuApiError as exc:
            return f"Error: {exc}"
        classes = payload.get("classes") or []
        if not classes:
            return (
                f"No class numbered {class_number} in {resolved}. Class numbers "
                "are term-specific -- check the term, or search by subject."
            )
        return format_class_detail(classes[0], term_label=str(resolved))
