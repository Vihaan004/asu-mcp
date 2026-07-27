"""Client for ASU's class search backend.

The public class search at catalog.apps.asu.edu is a React SPA over an
undocumented JSON API. This talks to that API directly.

Auth: the SPA builds its header as `"Bearer " + sessionStorage.getItem(...)`.
For a visitor who is not signed in that returns JS `null`, so the literal
string "Bearer null" goes over the wire -- and the backend accepts it as the
anonymous principal. We send the same. No credentials, no ASURITE, no SSO;
identical to loading the public page in a browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core import AsuApiError, AsuHttpClient, TTLCache

API_ROOT = "https://eadvs-cscc-catalog-api.apps.asu.edu/catalog-microservices/api/v1/search"

# See module docstring. Only this exact value works -- "Bearer x" gets a 401.
ANONYMOUS_BEARER = "Bearer null"

TERM_TTL = 6 * 60 * 60  # the term list turns over a couple of times a year
SUBJECT_TTL = 6 * 60 * 60
# Short enough that seat counts stay honest, long enough that a lecture hall
# full of students asking the same question does not become a load test.
SEARCH_TTL = 10 * 60

PAGE_SIZE_HINT = 200  # what the API returns per scroll page today


@dataclass(frozen=True)
class Term:
    code: str
    label: str

    def __str__(self) -> str:
        return f"{self.label} ({self.code})" if self.label else self.code


class ClassSearchClient:
    def __init__(self, cache: TTLCache | None = None) -> None:
        self._http = AsuHttpClient(
            API_ROOT,
            headers={
                "Authorization": ANONYMOUS_BEARER,
                "Origin": "https://catalog.apps.asu.edu",
                "Referer": "https://catalog.apps.asu.edu/",
            },
            cache=cache,
        )

    def close(self) -> None:
        self._http.close()

    # -- terms -------------------------------------------------------------

    def terms(self) -> tuple[list[Term], str]:
        """Return (terms newest-first, current term code)."""
        data = self._http.get_json("/terms", ttl=TERM_TTL)

        def rows(key: str) -> list[Term]:
            return [
                Term(code=str(t["value"]), label=str(t.get("label", "")).strip())
                for t in (data.get(key) or [])
                if t.get("value")
            ]

        # futureList holds terms that exist but have no schedule published yet.
        all_terms = sorted({*rows("fullList"), *rows("futureList")}, key=lambda t: t.code, reverse=True)
        current_list = data.get("currentTerm") or []
        current = (
            str(current_list[0]["value"])
            if current_list
            else (all_terms[0].code if all_terms else "")
        )
        return all_terms, current

    def resolve_term(self, term: str | None) -> Term:
        """Accept a code ('2267'), a label ('Fall 2026'), 'current', or None.

        Term codes are opaque, so guessing one silently searches the wrong
        semester. All user input routes through here.
        """
        terms, current = self.terms()
        by_code = {t.code: t for t in terms}

        raw = (term or "").strip()
        if not raw or raw.lower() == "current":
            return by_code.get(current, Term(current, ""))
        if raw in by_code:
            return by_code[raw]

        wanted = " ".join(raw.lower().split())
        for candidate in terms:
            if candidate.label.lower().strip() == wanted:
                return candidate
        squashed = wanted.replace("'", "").replace(" ", "")
        for candidate in terms:
            if candidate.label.lower().replace(" ", "") == squashed:
                return candidate

        known = ", ".join(str(t) for t in terms[:8])
        raise AsuApiError(
            f"unknown term {term!r}. Recent terms: {known}. Use list_terms for all."
        )

    # -- subjects ----------------------------------------------------------

    def subjects(self, term_code: str) -> list[dict[str, str]]:
        data = self._http.get_json(
            "/subjects", {"sl": "Y", "term": term_code}, ttl=SUBJECT_TTL
        )
        rows = data if isinstance(data, list) else (data.get("subjects") or [])
        out: list[dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = row.get("CODE") or row.get("code") or row.get("SUBJECT")
            if not code:
                continue
            out.append(
                {
                    "code": str(code).strip(),
                    "description": str(
                        row.get("DESCRIPTION") or row.get("DESCR") or row.get("description") or ""
                    ).strip(),
                }
            )
        out.sort(key=lambda s: s["code"])
        return out

    # -- classes -----------------------------------------------------------

    def search_classes(
        self,
        term_code: str,
        *,
        subject: str | None = None,
        catalog_number: str | None = None,
        keywords: str | None = None,
        instructor: str | None = None,
        class_number: str | None = None,
        campus: str | None = None,
        session: str | None = None,
        level: str | None = None,
        units: str | None = None,
        days_of_week: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        gen_studies: str | None = None,
        honors: bool = False,
        max_results: int = 200,
    ) -> dict[str, Any]:
        """Search sections, following scroll pagination up to max_results.

        Open-seat filtering happens downstream: the API's own searchType=open
        is a no-op that returns full sections too.
        """
        params: dict[str, Any] = {
            "refine": "Y",
            "term": term_code,
            "searchType": "all",
            # 'A' = every campus plus online. The SPA only narrows this for
            # signed-in students, based on their own enrollment type.
            "campusOrOnlineSelection": "A",
            "honors": "T" if honors else "F",
            "promod": "F",
        }
        optional = {
            "subject": subject.upper().strip() if subject else None,
            "catalogNbr": catalog_number.strip() if catalog_number else None,
            "keywords": keywords.strip() if keywords else None,
            "instructorName": instructor.strip() if instructor else None,
            "classNbr": class_number.strip() if class_number else None,
            "campus": campus.upper().strip() if campus else None,
            "session": session.strip() if session else None,
            "level": level.strip() if level else None,
            "units": units.strip() if units else None,
            "daysOfWeek": days_of_week.strip() if days_of_week else None,
            "startTime": start_time.strip() if start_time else None,
            "endTime": end_time.strip() if end_time else None,
            "gen_studies": gen_studies.strip() if gen_studies else None,
        }
        params.update({k: v for k, v in optional.items() if v})

        data = self._http.get_json("/classes", params, ttl=SEARCH_TTL)
        classes = list(data.get("classes") or [])
        total = int((data.get("total") or {}).get("value") or len(classes))

        # Paging is an Elasticsearch scroll cursor, ~200 rows a page. Keep
        # pulling while it hands one back and each page actually adds rows.
        scroll_id = data.get("scrollId")
        while scroll_id and len(classes) < min(total, max_results):
            page = self._http.get_json(
                "/classes", {**params, "scrollId": scroll_id}, ttl=SEARCH_TTL
            )
            rows = list(page.get("classes") or [])
            if not rows:
                break
            classes.extend(rows)
            next_scroll = page.get("scrollId")
            if next_scroll == scroll_id:
                break
            scroll_id = next_scroll

        return {
            "total": total,
            "classes": classes[:max_results],
            "aggregations": data.get("aggregations") or {},
            "truncated": total > len(classes[:max_results]),
        }
