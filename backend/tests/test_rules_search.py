from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.rules_search import search_rules, sections_on_sheet, sheet_text
from app.domains.interconnection.rules.chunker import chunk_sheets
from app.domains.interconnection.rules.ingest import ingest
from app.domains.interconnection.rules.text import sheets
from app.domains.interconnection.screens import rulebook

R = rulebook.RULESET


@pytest.fixture
def corpus(session: Session) -> Session:
    ingest(session, pdf_path=Path("/nonexistent"))  # fixture sheets: deterministic in CI
    return session


def test_chunker_addresses_screens_and_deficiency_sections() -> None:
    chunks = {(c.sheet, c.section) for c in chunk_sheets(sheets(R).items())}
    assert {(151, "G.1.j"), (151, "G.1.k"), (70, "E.5.b.i"), (71, "E.5.b.ii"), (144, "G.1.f"), (155, "G.2.a")} <= chunks


def test_lettered_list_items_are_not_mistaken_for_sections() -> None:
    """Screen M's own questions a. and b. must stay inside G.1.m."""
    on_153 = [c.section for c in chunk_sheets(sheets(R).items()) if c.sheet == 153]
    assert on_153 == ["G.1.m"]


def test_wrapped_continuation_heading_keeps_the_deeper_section() -> None:
    """Sheet 71 repeats '5.INTERCONNECTION ... OF' with (Cont'd.) wrapped onto the next line."""
    on_71 = [c.section for c in chunk_sheets(sheets(R).items()) if c.sheet == 71]
    assert on_71 == ["E.5.b.i", "E.5.b.ii", "E.5.b.iii", "E.5.b.iv"]


def test_boilerplate_is_stripped() -> None:
    text = " ".join(c.text for c in chunk_sheets(sheets(R).items()))
    assert "Shilpa Ramaiya" not in text and "Cancelling Revised" not in text


@pytest.mark.parametrize(("query", "section", "sheet"), [
    ("gross rating 30 kVA", "G.1.j", 151),
    ("first notification of deficiency", "E.5.b.i", 70),
    ("short circuit contribution ratio", "G.1.f", 144),
    ("ICA-OF 576 Profile 90%", "G.1.m", 153),
    ("NEM-2 NBT-1 500 kW", "G.1.k", 151),
])
def test_search_finds_the_governing_section(corpus: Session, query: str, section: str, sheet: int) -> None:
    hits = search_rules(corpus, R, query, limit=3)
    assert (hits[0].section, hits[0].sheet) == (section, sheet), [(h.section, h.sheet) for h in hits]
    assert hits[0].snippet


def test_search_with_no_match_returns_nothing(corpus: Session) -> None:
    assert search_rules(corpus, R, "cryptocurrency blockchain") == []


def test_search_falls_back_to_any_term_when_no_chunk_has_every_term(corpus: Session) -> None:
    hits = search_rules(corpus, R, "certified equipment spaceship")
    assert hits and hits[0].section == "G.1.b"


def test_every_rulebook_citation_resolves_in_the_corpus(corpus: Session) -> None:
    """The corpus the agent searches and the rulebook the engine cites are the same text."""
    from app.core.text import normalize
    for c in rulebook.ALL_CITATIONS:
        text = sheet_text(corpus, R, c.sheet)
        assert text is not None, c.sheet
        if c.sheet >= 15:
            assert normalize(c.quote) in normalize(text), (c.section, c.sheet)
    assert "G.1.j" in sections_on_sheet(corpus, R, 151)
