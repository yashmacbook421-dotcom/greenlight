"""'Says who?' must always have an answer: every rulebook quote is on its cited sheet."""

import hashlib
import json
from pathlib import Path

import pytest

from app.domains.interconnection.rules.text import RULES_DIR, normalize, sheets
from app.domains.interconnection.screens import rulebook

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("citation", rulebook.ALL_CITATIONS, ids=lambda c: f"{c.section}@{c.sheet}:{c.quote[:40]}")
def test_quote_appears_on_cited_sheet(citation: rulebook.Citation) -> None:
    text = sheets(rulebook.RULESET).get(citation.sheet)
    assert text is not None, f"sheet {citation.sheet} is not in the pinned fixture"
    assert normalize(citation.quote) in normalize(text), f"quote not found on sheet {citation.sheet}"


def test_rulebook_is_not_empty() -> None:
    assert len(rulebook.ALL_CITATIONS) >= 30


def test_fixture_matches_pinned_pdf_when_available() -> None:
    """Guards the fixture itself: re-extract from the hash-verified PDF and compare."""
    pdf = ROOT / "data/rules" / f"{rulebook.RULESET}.pdf"
    if not pdf.exists():
        pytest.skip("pinned PDF not downloaded (python -m scripts.fetch_rules)")
    manifest = json.loads((RULES_DIR / "manifest.json").read_text())[rulebook.RULESET]
    data = pdf.read_bytes()
    assert hashlib.sha256(data).hexdigest() == manifest["sha256"]

    from app.core.intake import parse_pdf
    extracted = {p.page_no: p.text for p in parse_pdf(data, max_pages=10_000)}
    for sheet, text in sheets(rulebook.RULESET).items():
        assert extracted[sheet] == text, f"fixture sheet {sheet} differs from the PDF"
