"""Query expansion and matching.

The numbers in these tests come from live Fall 2026 data: 'artificial
intelligence' matched 30 sections in the catalog and 'AI' matched none, while
the events calendar matched 'AI' nine times and 'artificial intelligence' zero.
Both directions are load-bearing.
"""

from asu_mcp.classes.client import Term, window
from asu_mcp.query import expand, initialism, matches, matches_any


class TestExpand:
    def test_abbreviation_expands(self):
        assert "artificial intelligence" in expand("AI")

    def test_phrase_contracts(self):
        assert "ml" in expand("machine learning")

    def test_original_is_always_tried_first(self):
        assert expand("AI")[0] == "AI"
        assert expand("machine learning")[0] == "machine learning"

    def test_expands_inside_a_longer_query(self):
        assert "artificial intelligence ethics" in expand("AI ethics")

    def test_only_whole_words_are_substituted(self):
        # 'ai' inside 'training' must not become 'artificial intelligence'.
        assert expand("training") == ["training"]

    def test_unknown_phrase_gets_its_initialism(self):
        assert "hci" in expand("human computer interaction")
        assert "gis" in expand("geographic information systems")

    def test_two_letter_initialisms_are_dropped_as_too_noisy(self):
        # 'computer architecture' -> 'ca' would match Career and Campus.
        assert expand("computer architecture") == ["computer architecture"]

    def test_empty_query(self):
        assert expand("") == []

    def test_variants_are_capped(self):
        assert len(expand("AI", limit=2)) <= 2


class TestInitialism:
    def test_builds_from_a_phrase(self):
        assert initialism("natural language processing") == "nlp"

    def test_rejects_short_words(self):
        assert initialism("internet of things") is None

    def test_rejects_a_single_word(self):
        assert initialism("robotics") is None


class TestMatches:
    def test_prefix_matching_keeps_stemming(self):
        assert matches("School of Engineering", "engineer")

    def test_does_not_match_mid_word(self):
        # The bug this exists to prevent: 'ai' matching 'available'.
        assert not matches("Tickets still available", "ai")
        assert not matches("Summer training series", "ai")

    def test_matches_a_real_abbreviation(self):
        assert matches("AI Upskilling Office Hours", "ai")

    def test_every_word_must_appear(self):
        assert matches("Quantum Computing Seminar", "quantum computing")
        assert not matches("Quantum Seminar", "quantum computing")

    def test_any_word_is_the_looser_form(self):
        assert matches_any("Quantum Seminar", "quantum computing")
        assert not matches_any("Poetry Reading", "quantum computing")

    def test_empty_query_matches_nothing(self):
        assert not matches("anything", "")


class TestTermWindow:
    """list_terms returned ~70 rows back to 2007 for a one-answer question."""

    def _terms(self):
        return [Term(code=str(2300 - i), label=f"Term {i}") for i in range(20)]

    def test_narrows_to_a_window_around_current(self):
        terms = self._terms()
        shown = window(terms, current="2290")
        assert len(shown) == 7
        assert any(t.code == "2290" for t in shown)

    def test_clamps_at_the_start_of_the_list(self):
        terms = self._terms()
        shown = window(terms, current=terms[0].code)
        assert shown[0].code == terms[0].code
        assert len(shown) == 4

    def test_unknown_current_falls_back_to_the_newest(self):
        terms = self._terms()
        assert window(terms, current="9999")[0].code == terms[0].code

    def test_empty(self):
        assert window([], current="2267") == []
