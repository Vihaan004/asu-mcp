"""ASU iSearch directory — faculty, staff and researchers.

Source: GET https://search.asu.edu/api/v1/webdir-profiles/faculty-staff
A de facto public API. Every field arrives wrapped in a {"raw": <value>}
envelope, which is why everything goes through _raw().
"""

from __future__ import annotations

import re
from typing import Any

from ..core import AsuApiError, AsuHttpClient, plain_text

API_ROOT = "https://search.asu.edu/api/v1"
PROFILE_BASE = "https://search.asu.edu/profile/"
SEARCH_TTL = 30 * 60


def _raw(field: Any) -> Any:
    return field.get("raw") if isinstance(field, dict) else field


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    # Bios and research interests come back as HTML fragments.
    cleaned = (plain_text(x) for x in items if x is not None)
    return [x for x in cleaned if x]


def _first(value: Any) -> str | None:
    items = _as_list(value)
    return items[0] if items else None


def _joined(value: Any) -> str | None:
    items = _as_list(value)
    return "; ".join(items) if items else None


# The directory AND-matches every query token, so one stray word from a
# conversational phrasing ("who is Aman Arora at ASU") returns nothing at all.
# Domain words (professor, robotics) are deliberately kept -- they match real
# title and expertise fields.
_STOPWORDS = frozenset({
    "who", "whos", "is", "are", "was", "the", "a", "an", "me", "my", "about",
    "tell", "find", "what", "whats", "search", "for", "please", "can", "could",
    "you", "show", "of", "to", "do", "does", "know", "any", "someone", "person",
    "people", "professor",
    # Org words never narrow an ASU-only directory; they only break the match.
    "asu", "arizona", "state", "university",
})


def _clean(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9'-]+", query)
    return " ".join(t for t in tokens if t.lower() not in _STOPWORDS)


def _candidates(query: str) -> list[str]:
    """Progressively relaxed query variants, most specific first.

    raw -> filler stripped -> first two tokens (a person lookup leads with the
    name). We stop at the first variant that returns anything.
    """
    out: list[str] = []
    seen: set[str] = set()
    cleaned = _clean(query)
    tokens = cleaned.split()
    for candidate in [query.strip(), cleaned, " ".join(tokens[:2]) if len(tokens) > 2 else ""]:
        key = candidate.lower()
        if candidate and key not in seen:
            seen.add(key)
            out.append(candidate)
    return out


def parse_people(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Map an iSearch response to flat rows, deduped by ASURITE."""
    rows: dict[str, dict[str, Any]] = {}
    for item in payload.get("results", []):
        def field(key: str) -> Any:
            return _raw(item.get(key))

        asurite = field("asurite_id")
        name = field("display_name")
        if not asurite or not name:
            continue
        eid = field("eid")
        rows[asurite] = {
            "asurite": asurite,
            "name": name,
            "email": field("email_address"),
            "title": _first(field("primary_title")) or _first(field("working_title")),
            "departments": _as_list(field("departments")),
            "expertise_areas": _as_list(field("expertise_areas")),
            "research_interests": _joined(field("research_interests")),
            "short_bio": _joined(field("short_bio")),
            "phone": _first(field("phone")),
            "campus": _first(field("campus")) or _first(field("location")),
            "profile_url": (
                f"{PROFILE_BASE}{eid}"
                if eid
                else f"https://search.asu.edu/?query={asurite}&searchType=people"
            ),
        }
    return list(rows.values())


def score(person: dict[str, Any], query: str) -> int:
    """How well a directory row actually answers the query.

    The endpoint fuzzy-matches surnames, so a one-word topic like 'robotics'
    comes back led by people named Root, Rootes and Root -- no title, no
    expertise, no relevance. Matching query terms against the fields that carry
    meaning pushes those under the people who really work on the topic, while
    an exact name match still wins outright for a directed lookup.
    """
    terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
    if not terms:
        return 0

    name = (person.get("name") or "").lower()
    title = (person.get("title") or "").lower()
    expertise = " ".join(person.get("expertise_areas") or []).lower()
    research = f"{person.get('research_interests') or ''} {person.get('short_bio') or ''}".lower()
    departments = " ".join(person.get("departments") or []).lower()

    total = 0
    if all(t in name for t in terms):
        total += 12  # they asked for this person by name
    for term in terms:
        if term in expertise:
            total += 4
        if term in title:
            total += 3
        if term in departments:
            total += 2
        if term in research:
            total += 1

    # A row with no title, expertise or research is a bare directory stub.
    if not any([title, expertise, research]):
        total -= 2
    return total


def rerank(people: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Sort by relevance, keeping the directory's order within equal scores."""
    return [
        person
        for _, person in sorted(
            enumerate(people),
            key=lambda pair: (-score(pair[1], query), pair[0]),
        )
    ]


class PeopleClient:
    def __init__(self) -> None:
        self._http = AsuHttpClient(API_ROOT)

    def close(self) -> None:
        self._http.close()

    def search(self, query: str, size: int = 8) -> list[dict[str, Any]]:
        """Search the directory, relaxing the query until something matches."""
        if not query.strip():
            raise AsuApiError("give a name, department or research topic to search for")

        # Over-fetch so rerank() has something to work with; the directory's own
        # ordering puts fuzzy surname matches first for short topic words.
        fetch = max(size * 4, 20)
        for candidate in _candidates(query):
            payload = self._http.get_json(
                "/webdir-profiles/faculty-staff",
                {
                    "query": candidate,
                    "page": 1,
                    "size": fetch,
                    "client": "asuis",
                    "sort-by": "",
                },
                ttl=SEARCH_TTL,
            )
            people = parse_people(payload)
            if people:
                return rerank(people, candidate)[:size]
        return []
