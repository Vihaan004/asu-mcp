"""Parser and ranking tests for people, events and news.

Markup below is copied from the real pages, trimmed to one record each.
"""

from asu_mcp.core import plain_text
from asu_mcp.events.client import parse_listing
from asu_mcp.events.format import format_events
from asu_mcp.news.client import clean_summary, parse_search
from asu_mcp.news.format import relevance
from asu_mcp.people.client import (
    _candidates,
    _clean,
    _name_run,
    explains,
    parse_people,
    rerank,
    score,
)

EVENT_CARD = """
<ul><li class="card cards-components card-event">
  <div class="views-field views-field-nothing card-header">
    <h3 class="field-content card-title">
      <a href="/event/beginners-guide-research-computing-17?eventDate=2026-08-05">Beginner's Guide to Research Computing</a>
    </h3>
  </div>
  <div class="views-field views-field-field-event-date-value-1">
    <span class="field-content"><i class="far fa-calendar"></i>Wed, Aug 5, 2026</span>
  </div>
  <div class="views-field views-field-field-event-date-end-value">
    <span class="field-content"><span class="smart-date--time">10:00 am</span> &ndash; <span class="smart-date--time">11:15 am (MST)</span></span>
  </div>
  <div class="views-field views-field-field-asu-events-location card-event-details">
    <div class="field-content"><i class="fas fa-map-marker-alt"></i>&nbsp;&nbsp;Online event</div>
  </div>
</li></ul>
"""

NEWS_ROW = """
<table class="table"><tbody><tr>
  <td><img src="/x.jpg"/></td>
  <td class="views-field views-field-title views-field-created views-field-body">
    <h3><a href="/20260625-environment-and-sustainability-weather-jiujitsu">'Weather jiujitsu' could help us combat extreme weather</a></h3>
    Jun 25, 2026 In jiujitsu, a fighter can defeat a larger, stronger opponent.
  </td>
</tr></tbody></table>
"""


class TestPlainText:
    def test_strips_the_html_asu_embeds_in_time_fields(self):
        assert plain_text("W &nbsp; 3:00 PM<br/>&nbsp;-5:45 PM<br/>&nbsp;") == "W 3:00 PM -5:45 PM"

    def test_strips_paragraph_markup_from_bios(self):
        assert plain_text("<p>Field robotics</p><p>AI Ethics&nbsp;</p>") == "Field robotics AI Ethics"

    def test_empty_input(self):
        assert plain_text(None) == ""


class TestEventListing:
    def test_extracts_a_card(self):
        rows = parse_listing(EVENT_CARD)
        assert len(rows) == 1
        row = rows[0]
        assert row["slug"] == "beginners-guide-research-computing-17"
        assert row["date"] == "2026-08-05"
        assert row["title"] == "Beginner's Guide to Research Computing"
        assert row["title_truncated"] is False
        assert row["date_display"] == "Wed, Aug 5, 2026"
        assert "10:00 am" in row["time"] and "11:15 am (MST)" in row["time"]
        assert row["location"] == "Online event"
        assert row["url"].endswith("?eventDate=2026-08-05")

    def test_flags_truncated_titles_for_a_detail_fetch(self):
        rows = parse_listing(EVENT_CARD.replace("Research Computing", "Research Computing…"))
        assert rows[0]["title_truncated"] is True

    def test_ignores_non_event_links(self):
        assert parse_listing('<a href="/about">About</a>') == []


class TestEventResults:
    """An empty result has to be distinguishable from a broken tool.

    ASU really has no engineering-titled events over the next two months, so
    'nothing matched' is often the correct answer -- it just has to say what it
    checked, or a model reads it as a failure and tells the student the wrong
    thing.
    """

    def test_empty_result_reports_what_was_searched(self):
        text = format_events(
            {"events": [], "scanned": 141, "from_date": "2026-07-26", "to_date": "2026-08-31"},
            described="keywords engineering",
        )
        assert "141 upcoming events" in text
        assert "2026-07-26 to 2026-08-31" in text
        assert "titles and locations" in text

    def test_empty_result_without_coverage_still_reads_sensibly(self):
        text = format_events({"events": [], "scanned": 0}, described="anything upcoming")
        assert "No upcoming ASU events" in text
        assert "Searched" not in text

    def test_hits_report_coverage(self):
        row = parse_listing(EVENT_CARD)[0]
        text = format_events(
            {"events": [row], "scanned": 141, "from_date": "2026-07-26", "to_date": "2026-08-31"},
            described="keywords research",
        )
        assert "1 upcoming event(s)" in text
        assert "out of 141 upcoming events" in text
        assert "Wed, Aug 5, 2026" in text
        assert "Beginner's Guide to Research Computing" in text

    def test_relaxed_match_is_labelled(self):
        row = parse_listing(EVENT_CARD)[0]
        text = format_events(
            {"events": [row], "scanned": 141, "from_date": "a", "to_date": "b", "relaxed": True},
            described="keywords research computing",
        )
        assert "match at least one" in text

    def test_says_when_a_rewritten_query_is_what_matched(self):
        # Asking for 'artificial intelligence' and being shown events titled
        # 'AI ...' is only trustworthy if the swap is stated.
        row = parse_listing(EVENT_CARD)[0]
        text = format_events(
            {"events": [row], "scanned": 141, "from_date": "a", "to_date": "b", "matched_as": "AI"},
            described="keywords artificial intelligence",
        )
        assert "searched as 'AI'" in text


class TestNewsSearch:
    def test_extracts_a_story(self):
        stories = parse_search(NEWS_ROW)
        assert len(stories) == 1
        story = stories[0]
        assert story["title"] == "'Weather jiujitsu' could help us combat extreme weather"
        assert story["date"] == "2026-06-25"
        assert story["url"].startswith("https://news.asu.edu/20260625-")
        assert "jiujitsu, a fighter" in story["summary"]

    def test_summary_drops_the_leading_date(self):
        assert clean_summary("Jun 25, 2026 In jiujitsu, a fighter wins.") == "In jiujitsu, a fighter wins."

    def test_summary_truncates_long_text(self):
        assert clean_summary("x" * 400, limit=50).endswith("…")


class TestPeople:
    def test_parses_the_raw_envelope(self):
        payload = {
            "results": [
                {
                    "asurite_id": {"raw": "yyang"},
                    "display_name": {"raw": "Yezhou Yang"},
                    "email_address": {"raw": "yz.yang@asu.edu"},
                    "primary_title": {"raw": ["Associate Professor"]},
                    "expertise_areas": {"raw": ["Computer Vision"]},
                    "research_interests": {"raw": ["<p>Robot perception</p>"]},
                    "eid": {"raw": "3020558"},
                }
            ]
        }
        person = parse_people(payload)[0]
        assert person["name"] == "Yezhou Yang"
        assert person["title"] == "Associate Professor"
        assert person["research_interests"] == "Robot perception"
        assert person["profile_url"].endswith("/3020558")

    def test_drops_rows_without_a_name_or_id(self):
        assert parse_people({"results": [{"display_name": {"raw": "No ID"}}]}) == []

    def test_topic_query_ranks_experts_over_fuzzy_surname_matches(self):
        # The live directory answers "robotics" with people named Root first.
        stub = {"name": "Kyle Root", "title": None, "expertise_areas": [], "departments": []}
        expert = {
            "name": "Vivek Thangavelu",
            "title": "Assistant Professor",
            "expertise_areas": ["Robotics"],
            "departments": [],
        }
        assert rerank([stub, expert], "robotics")[0]["name"] == "Vivek Thangavelu"
        assert score(expert, "robotics") > score(stub, "robotics")

    def test_named_person_still_wins_for_a_direct_lookup(self):
        target = {"name": "Yezhou Yang", "title": "Associate Professor", "expertise_areas": [], "departments": []}
        other = {"name": "Someone Else", "title": "Yang Lab Manager", "expertise_areas": [], "departments": []}
        assert rerank([other, target], "Yezhou Yang")[0]["name"] == "Yezhou Yang"

    def test_unexplainable_fuzzy_surname_rows_are_dropped(self):
        # Live: 'quantum' returns Quintua, Quintus and Quantae -- four rows,
        # none containing the word. Sorting them is not enough.
        stub = {"name": "Steve Quintua", "title": None, "expertise_areas": [], "departments": []}
        assert not explains(stub, "quantum")

    def test_a_row_survives_on_any_visible_field(self):
        person = {"name": "A B", "title": None, "expertise_areas": ["Quantum Information"], "departments": []}
        assert explains(person, "quantum computing")

    def test_a_name_match_always_survives(self):
        person = {"name": "Christian Arenz", "title": None, "expertise_areas": [], "departments": []}
        assert explains(person, "Christian Arenz quantum computing")

    def test_ranking_is_stable_when_nothing_matches(self):
        a = {"name": "A", "title": "T", "expertise_areas": [], "departments": []}
        b = {"name": "B", "title": "T", "expertise_areas": [], "departments": []}
        assert [p["name"] for p in rerank([a, b], "zzz")] == ["A", "B"]


class TestPeopleQueryRelaxation:
    """A student's phrasing has to survive the trip to an AND-matching API.

    The live failure: 'can you find me someone who works on quantum computing
    at ASU' relaxed to the literal words 'works on', and the directory answered
    with Cody Works and Tiffany Works.
    """

    CONVERSATIONAL = "can you find me someone who works on quantum computing at ASU"

    def test_filler_is_stripped_down_to_the_topic(self):
        assert _clean(self.CONVERSATIONAL).lower() == "quantum computing"

    def test_no_variant_is_a_bare_verb_phrase(self):
        variants = [c.lower() for c in _candidates(self.CONVERSATIONAL)]
        assert "works on" not in variants
        assert "quantum computing" in variants

    def test_never_relaxes_to_the_tail_of_a_topic(self):
        # 'computing' alone answers a different question and looks plausible
        # doing it; an empty result is the safer failure.
        assert "computing" not in [c.lower() for c in _candidates(self.CONVERSATIONAL)]

    def test_trailing_qualifiers_are_dropped_but_the_head_survives(self):
        assert "computer architecture" in _candidates("computer architecture accelerators")

    def test_at_is_filler(self):
        # 'at' was the specific word missing from the stopword list.
        assert _clean("who is professor Yezhou Yang at ASU") == "Yezhou Yang"

    def test_a_name_survives_conversational_phrasing(self):
        assert "Yezhou Yang" in _candidates("who is professor Yezhou Yang at ASU")

    def test_name_run_finds_a_capitalised_name(self):
        assert _name_run("tell me about Michel Kinsy at ASU") == "Michel Kinsy"

    def test_name_run_ignores_a_single_capital(self):
        assert _name_run("Robotics research") == ""

    def test_abbreviations_are_offered_as_a_fallback(self):
        # The expansion replaces the abbreviation and keeps the rest.
        assert "artificial intelligence research" in _candidates("who does AI research")


class TestNewsRelevance:
    """The newsroom ranks on full article text, which is invisible here."""

    def test_flags_a_story_whose_headline_shows_nothing(self):
        story = {"title": "Breaking through the quantum noise barrier", "summary": "", "section": ""}
        assert "article text" in relevance(story, "machine learning")

    def test_silent_when_the_headline_carries_the_query(self):
        story = {"title": "ASU researchers advance machine learning", "summary": "", "section": ""}
        assert relevance(story, "machine learning") == ""

    def test_names_the_partial_match(self):
        story = {"title": "A new approach to learning", "summary": "", "section": ""}
        assert relevance(story, "machine learning") == "headline/summary matches only: learning"

    def test_no_query_means_no_note(self):
        assert relevance({"title": "x", "summary": "", "section": ""}, None) == ""
