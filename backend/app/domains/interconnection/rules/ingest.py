"""Load the pinned Rule 21 edition into rule_chunks: from the hash-verified PDF when present, else the sheet fixture."""

import hashlib
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.intake import parse_pdf
from app.core.rules_search import replace_chunks
from app.domains.interconnection.rules.chunker import chunk_sheets
from app.domains.interconnection.rules.text import RULES_DIR, sheets
from app.domains.interconnection.screens.rulebook import RULESET

PDF_PATH = Path(__file__).resolve().parents[5] / "data" / "rules" / f"{RULESET}.pdf"


def load_sheets(pdf_path: Path = PDF_PATH) -> tuple[dict[int, str], str]:
    if pdf_path.exists():
        data = pdf_path.read_bytes()
        expected = json.loads((RULES_DIR / "manifest.json").read_text())[RULESET]["sha256"]
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"{pdf_path} does not match the pinned sha256 in manifest.json")
        return {p.page_no: p.text for p in parse_pdf(data, max_pages=10_000)}, "pdf"
    return sheets(RULESET), "fixture"


def ingest(session: Session, pdf_path: Path = PDF_PATH) -> tuple[int, str]:
    raw, source = load_sheets(pdf_path)
    chunks = chunk_sheets(raw.items())
    count = replace_chunks(session, RULESET, [
        {"ordinal": c.ordinal, "sheet": c.sheet, "section": c.section, "heading": c.heading, "text": c.text}
        for c in chunks
    ])
    return count, source
