"""Query expansion shared by every search tool.

ASU's sources disagree about abbreviations, and they disagree in opposite
directions. The class catalog indexes official course titles, which spell
things out: `artificial intelligence` finds 30 sections in Fall 2026 and `AI`
finds none. The events calendar indexes whatever a human typed into a title
field, which is where the abbreviation lives: `AI Upskilling Office Hours`
matches `AI` and not `artificial intelligence`.

A student asks in whichever form they think in, and either one silently returns
nothing. So every search tries both, most faithful variant first.

Matching is prefix-anchored rather than plain substring: `engineer` should still
find `Engineering`, but `ai` must not find `available` or `training`.
"""

from __future__ import annotations

import re
from functools import lru_cache

# Only pairs where the short form is unambiguous in a university context.
# Deliberately absent: 'cv' (curriculum vitae), 'me' (mechanical engineering),
# 'ar', 'ui' -- each collides with a common word or a different field.
_GROUPS: tuple[tuple[str, ...], ...] = (
    ("ai", "artificial intelligence"),
    ("ml", "machine learning"),
    ("dl", "deep learning"),
    ("nlp", "natural language processing"),
    ("hci", "human computer interaction"),
    ("iot", "internet of things"),
    ("vr", "virtual reality"),
    ("ux", "user experience"),
    ("gis", "geographic information systems"),
    ("cs", "computer science"),
    ("ee", "electrical engineering"),
    ("bme", "biomedical engineering"),
    ("psych", "psychology"),
    ("econ", "economics"),
    ("stats", "statistics"),
    ("undergrad", "undergraduate"),
    ("grad", "graduate"),
    # ASU's own shorthand.
    ("fse", "fulton schools of engineering"),
    ("wpc", "w. p. carey"),
)

_SYNONYMS: dict[str, tuple[str, ...]] = {}
for _group in _GROUPS:
    for _form in _group:
        _SYNONYMS[_form] = tuple(f for f in _group if f != _form)

# Longest first, so 'machine learning' is substituted before 'ml' could be.
_KEYS = sorted(_SYNONYMS, key=len, reverse=True)

_WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def initialism(phrase: str) -> str | None:
    """'natural language processing' -> 'nlp', for phrases not in the table.

    Two-letter results are dropped: they are noisy as prefixes ('ca' would
    match Career and Campus) and the ones worth having are in _GROUPS already.
    """
    parts = words(phrase)
    if not 2 <= len(parts) <= 4 or any(len(p) < 3 for p in parts):
        return None
    short = "".join(p[0] for p in parts)
    return short if len(short) >= 3 else None


def expand(query: str, *, limit: int = 4) -> list[str]:
    """Variants of a query to try in order, the original always first."""
    original = " ".join((query or "").split())
    if not original:
        return []

    variants = [original]
    seen = {original.lower()}

    def add(candidate: str) -> None:
        cleaned = " ".join(candidate.split())
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            variants.append(cleaned)

    lowered = original.lower()
    for key in _KEYS:
        pattern = re.compile(rf"\b{re.escape(key)}\b")
        if pattern.search(lowered):
            for alternative in _SYNONYMS[key]:
                add(pattern.sub(alternative, lowered))
            # One substitution per query. Chaining them multiplies variants
            # for no gain -- nobody searches 'AI and ML and NLP'.
            break

    auto = initialism(original)
    if auto and auto not in _SYNONYMS:
        add(auto)

    return variants[:limit]


@lru_cache(maxsize=512)
def _prefix(word: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(word)}")


def matches(haystack: str, query: str) -> bool:
    """True when every word of the query starts a word in the haystack."""
    hay = (haystack or "").lower()
    parts = words(query)
    return bool(parts) and all(_prefix(p).search(hay) for p in parts)


def matches_any(haystack: str, query: str) -> bool:
    hay = (haystack or "").lower()
    return any(_prefix(p).search(hay) for p in words(query))
