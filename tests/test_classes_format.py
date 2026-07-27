"""Tests against a real captured response for CSE 310, Fall 2026 (term 2267).

The fixture has 11 sections with a useful mix: full lectures, open lectures,
sections with no scheduled meeting time, and both Tempe and online offerings.
"""

import json
from pathlib import Path

import pytest

from asu_mcp.classes.format import format_class_detail, format_search_results, normalize

FIXTURE = Path(__file__).parent / "fixtures" / "classes_cse310_2267.json"


@pytest.fixture
def payload():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {
        "total": data["total"]["value"],
        "classes": data["classes"],
        "aggregations": data.get("aggregations", {}),
        "truncated": False,
    }


@pytest.fixture
def lecture(payload):
    """Section 1011 - the open Monday/Wednesday lecture."""
    return next(
        r for r in payload["classes"] if r["CLAS"]["CLASSNBR"] == "66445"
    )


def test_normalize_extracts_student_facing_fields(lecture):
    row = normalize(lecture)
    assert row["class_number"] == "66445"
    assert row["course"] == "CSE 310"
    assert row["title"] == "Data Structures and Algorithms"
    assert row["section"] == "1011"
    assert row["component"] == "Lecture"
    assert row["units"] == "3"
    assert row["instructors"] == ["Nakul Gopalan"]
    assert row["days"] == "M W"
    assert row["start_time"] == "4:30 PM"
    assert row["end_time"] == "5:45 PM"
    assert row["campus"] == "Tempe"
    assert "PSH153" in row["room"]
    assert row["map_url"].startswith("http")


def test_normalize_reads_live_seat_counts(lecture):
    row = normalize(lecture)
    assert row["enrolled"] == 81
    assert row["capacity"] == 150
    assert row["seats_open"] == 69
    assert row["is_open"] is True


def test_normalize_marks_full_section_closed(payload):
    # Section 1016 is 150/150 with ENRLSTAT 'C'.
    full = next(r for r in payload["classes"] if r["CLAS"]["CLASSNBR"] == "70380")
    row = normalize(full)
    assert row["enrolled"] == row["capacity"] == 150
    assert row["seats_open"] == 0
    assert row["is_open"] is False


def test_normalize_trims_dates_and_deadlines(lecture):
    row = normalize(lecture)
    assert row["start_date"] == "2026-08-20"
    assert row["end_date"] == "2026-12-04"
    assert row["enroll_deadline"] == "2026-08-26"
    assert row["drop_deadline"] == "2026-09-02"


def test_open_only_filters_full_sections(payload):
    everything = format_search_results(payload, term_label="Fall 2026 (2267)")
    open_only = format_search_results(
        payload, term_label="Fall 2026 (2267)", open_only=True
    )

    assert "11 section(s)" in everything
    # Six of the eleven are full; the API cannot filter these for us.
    assert "5 section(s) with open seats" in open_only
    assert "#70380" in everything
    assert "#70380" not in open_only
    assert "#66445" in open_only


def test_search_results_group_by_course_and_show_class_numbers(payload):
    text = format_search_results(payload, term_label="Fall 2026 (2267)")
    assert "CSE 310 — Data Structures and Algorithms (3 credits)" in text
    assert "#66445" in text
    assert "Nakul Gopalan" in text
    assert "81/150 OPEN" in text
    assert "150/150 FULL" in text


def test_sections_without_meeting_times_are_labelled(payload):
    # Section 2001 has no days or times set.
    text = format_search_results(payload, term_label="Fall 2026 (2267)")
    assert "no set meeting time" in text


def test_all_full_reports_that_rather_than_empty(payload):
    full_only = {
        **payload,
        "classes": [r for r in payload["classes"] if r["CLAS"]["ENRLSTAT"] == "C"],
    }
    full_only["total"] = len(full_only["classes"])
    text = format_search_results(full_only, term_label="Fall 2026 (2267)", open_only=True)
    assert "all full" in text


def test_class_detail_includes_deadlines_and_seats(lecture):
    text = format_class_detail(lecture, term_label="Fall 2026 (2267)")
    assert "CSE 310 — Data Structures and Algorithms" in text
    assert "Class number 66445" in text
    assert "81/150 OPEN" in text
    assert "Last day to enroll: 2026-08-26" in text
    assert "Computer Science and Engineering" in text
