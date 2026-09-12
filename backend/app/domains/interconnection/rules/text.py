"""Loading pinned rule text, for citation verification."""

import json
from functools import cache
from pathlib import Path

from app.core.text import normalize

__all__ = ["RULES_DIR", "normalize", "sheets"]

RULES_DIR = Path(__file__).parent


@cache
def sheets(ruleset: str) -> dict[int, str]:
    data = json.loads((RULES_DIR / f"{ruleset}.sheets.json").read_text())
    return {int(k): v for k, v in data["sheets"].items()}
