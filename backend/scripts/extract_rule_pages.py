"""Regenerate the pinned sheet-text fixture from the downloaded tariff PDF.

    python -m scripts.fetch_rules && python -m scripts.extract_rule_pages
"""

import json
from pathlib import Path

from app.core.intake import parse_pdf
from app.domains.interconnection.rules.text import RULES_DIR

ROOT = Path(__file__).resolve().parents[2]
RULESET = "pge_rule21_2025-08-29"
SHEET_RANGES = [(18, 36), (70, 91), (138, 163)]  # definitions · validation + Fast Track · screens


def main() -> None:
    pages = parse_pdf((ROOT / "data/rules" / f"{RULESET}.pdf").read_bytes(), max_pages=10_000)
    keep = {str(p.page_no): p.text for p in pages if any(a <= p.page_no <= b for a, b in SHEET_RANGES)}
    out = RULES_DIR / f"{RULESET}.sheets.json"
    existing = json.loads(out.read_text()) if out.exists() else {}
    existing.update({"ruleset": RULESET, "sheets": keep})
    out.write_text(json.dumps(existing, indent=1))
    print(f"wrote {len(keep)} sheets to {out}")


if __name__ == "__main__":
    main()
