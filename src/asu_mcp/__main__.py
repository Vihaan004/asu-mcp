"""CLI over the same code paths the MCP tools use.

Handy for checking ASU's API is still behaving without standing up a client:

    python -m asu_mcp terms
    python -m asu_mcp search CSE 310 --open
    python -m asu_mcp search --keywords "machine learning" --term "Spring 2026"
    python -m asu_mcp class 66445
"""

from __future__ import annotations

import argparse
import sys

from .classes.client import ClassSearchClient
from .classes.format import format_class_detail, format_search_results
from .core import AsuApiError


def main(argv: list[str] | None = None) -> int:
    # Windows consoles still default to cp1252, which mangles the separators.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="asu_mcp")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("terms", help="list available terms")

    p_subjects = sub.add_parser("subjects", help="list subject codes for a term")
    p_subjects.add_argument("--term")

    p_search = sub.add_parser("search", help="search class sections")
    p_search.add_argument("subject", nargs="?")
    p_search.add_argument("catalog_number", nargs="?")
    p_search.add_argument("--keywords")
    p_search.add_argument("--instructor")
    p_search.add_argument("--term")
    p_search.add_argument("--campus")
    p_search.add_argument("--open", action="store_true", dest="open_only")
    p_search.add_argument("--max", type=int, default=100, dest="max_results")

    p_class = sub.add_parser("class", help="detail for one class number")
    p_class.add_argument("class_number")
    p_class.add_argument("--term")

    args = parser.parse_args(argv)
    client = ClassSearchClient()

    try:
        if args.command == "terms":
            terms, current = client.terms()
            for term in terms:
                mark = "  <- current" if term.code == current else ""
                print(f"{term.code}  {term.label}{mark}")
            return 0

        resolved = client.resolve_term(getattr(args, "term", None))

        if args.command == "subjects":
            for subject in client.subjects(resolved.code):
                print(f"{subject['code']:<8}{subject['description']}".rstrip())
            return 0

        if args.command == "search":
            if not any([args.subject, args.catalog_number, args.keywords, args.instructor]):
                parser.error("give a subject, keywords or an instructor")
            payload, searched_as = client.search_expanding(
                resolved.code,
                keywords=args.keywords,
                subject=args.subject,
                catalog_number=args.catalog_number,
                instructor=args.instructor,
                campus=args.campus,
                max_results=args.max_results,
            )
            if searched_as:
                print(f"(no match for {args.keywords!r}, searched as {searched_as!r})")
            print(format_search_results(payload, term_label=str(resolved), open_only=args.open_only))
            return 0

        payload = client.search_classes(resolved.code, class_number=args.class_number, max_results=5)
        classes = payload.get("classes") or []
        if not classes:
            print(f"No class numbered {args.class_number} in {resolved}.")
            return 1
        print(format_class_detail(classes[0], term_label=str(resolved)))
        return 0

    except AsuApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
