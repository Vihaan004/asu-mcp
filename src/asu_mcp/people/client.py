"""ASU iSearch directory — faculty, staff and researchers.

Source: GET https://search.asu.edu/api/v1/webdir-profiles/faculty-staff
A de facto public API. Every field arrives wrapped in a {"raw": <value>}
envelope, which is why everything goes through _raw().
"""

from __future__ import annotations

import re
from typing import Any

from ..core import AsuApiError, AsuHttpClient, plain_text
from ..query import expand

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
# Asking a model to phrase queries carefully does not work -- it phrases them
# the way the student did -- so the filler is stripped here instead.
#
# Field words are deliberately KEPT: robotics, research, lab, school,
# department, studies and instructor all match real title, department and
# expertise values, and dropping them would widen a narrow query.
_STOPWORDS = frozenset({
    # question and request framing
    "who", "whos", "whose", "whom", "what", "whats", "which", "where", "when",
    "how", "why", "is", "are", "was", "were", "be", "been", "being", "am",
    "has", "have", "had", "do", "does", "did", "can", "could", "will", "would",
    "shall", "should", "may", "might", "must",
    "tell", "find", "search", "show", "list", "give", "get", "know", "help",
    "need", "needs", "want", "wants", "looking", "look", "please", "thanks",
    # pronouns, articles, prepositions -- 'at' and 'on' are the ones that
    # actually broke real queries
    "a", "an", "the", "i", "me", "my", "we", "us", "our", "you", "your",
    "he", "she", "it", "they", "them", "their", "his", "her", "its",
    "at", "on", "in", "into", "of", "to", "for", "from", "by", "with", "about",
    "and", "or", "as", "that", "this", "these", "those", "there", "here",
    "any", "all", "some", "more", "most", "best", "top", "good", "great",
    "currently", "also", "well",
    # people-shaped filler
    "someone", "somebody", "anyone", "anybody", "person", "people", "faculty",
    "staff", "member", "members", "professor", "professors", "prof", "dr",
    "teaches", "teaching", "teacher", "expert", "experts", "expertise",
    "works", "work", "working", "worked", "studying",
    "focuses", "focused", "focusing", "specializes", "specializing",
    # contact-intent words: they ask for a field, they do not narrow the search
    "contact", "email", "phone", "reach",
    # org words never narrow an ASU-only directory; they only break the match
    "asu", "arizona", "state", "university",
})


def _clean(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9'-]+", query)
    return " ".join(t for t in tokens if t.lower() not in _STOPWORDS)


def _name_run(query: str) -> str:
    """The longest run of consecutive capitalised non-filler words.

    'who is professor Yezhou Yang at ASU' -> 'Yezhou Yang'. Only a hint: it
    needs the student to have capitalised the name, which is why it sits behind
    the cleaned query rather than in front of it.
    """
    best: list[str] = []
    current: list[str] = []
    for token in re.findall(r"[A-Za-z'-]+", query):
        if token[:1].isupper() and token.lower() not in _STOPWORDS:
            current.append(token)
        else:
            best = max(best, current, key=len)
            current = []
    best = max(best, current, key=len)
    return " ".join(best) if len(best) >= 2 else ""


def _candidates(query: str) -> list[str]:
    """Progressively relaxed query variants, most specific first.

    raw -> filler stripped -> capitalised name -> abbreviation expanded ->
    leading two words. We stop at the first variant that returns anything.

    The order matters more than it looks. An earlier version dropped straight
    to the first two tokens of the raw query, so 'someone who works on quantum
    computing' relaxed to 'works on' and confidently returned people with the
    surname Works.
    """
    out: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        cleaned = " ".join((candidate or "").split())
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            out.append(cleaned)

    cleaned = _clean(query)
    add(query)
    add(cleaned)
    add(_name_run(query))
    for variant in expand(cleaned)[1:]:
        add(variant)
    tokens = cleaned.split()
    if len(tokens) > 2:
        # Drops trailing qualifiers and keeps the head concept, so
        # 'computer architecture accelerators' relaxes to 'computer
        # architecture'.
        add(" ".join(tokens[:2]))
    # Deliberately no single-word relaxation. In an English topic the first
    # word carries the specificity, so 'quantum computing' would relax to
    # 'computing' and return a security architecture director -- an answer to
    # a question nobody asked, and harder to catch than an empty result.
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


def explains(person: dict[str, Any], query: str) -> bool:
    """Can we point at why this row came back at all?

    The endpoint fuzzy-matches surnames: 'quantum' returns Steve Quintua,
    Quantae Oliver and Ashley Quintus, and nothing else -- four rows in total,
    none of which contain the word. Reranking can only sort what it is given,
    so these still surface, and a model presents them as ASU's quantum people.

    A row survives only if some query word is visible somewhere in it. When
    that leaves nothing, 'nobody matched' is the honest answer.
    """
    terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
    if not terms:
        return True
    visible = " ".join(
        [
            person.get("name") or "",
            person.get("title") or "",
            " ".join(person.get("expertise_areas") or []),
            " ".join(person.get("departments") or []),
            person.get("research_interests") or "",
            person.get("short_bio") or "",
        ]
    ).lower()
    return any(term in visible for term in terms)


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

    def search(self, query: str, size: int = 8) -> tuple[list[dict[str, Any]], str]:
        """Search the directory, relaxing the query until something matches.

        Returns (people, searched_as). searched_as is empty unless a rewritten
        query is what produced the results -- a student who asked one thing and
        is shown the answer to another deserves to be told.
        """
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
            people = [p for p in parse_people(payload) if explains(p, candidate)]
            if people:
                searched_as = (
                    "" if candidate.strip().lower() == query.strip().lower() else candidate
                )
                return rerank(people, candidate)[:size], searched_as
        return [], ""
