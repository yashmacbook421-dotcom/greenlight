"""Loading and normalising pinned rule text, for citation verification."""

import json
from functools import cache
from pathlib import Path

RULES_DIR = Path(__file__).parent

_TRANSLATE = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                            "–": "-", "—": "-", " ": " ", "­": ""})


def normalize(text: str) -> str:
    """Typographic quotes/dashes to ASCII, all whitespace runs (incl. line breaks) to one space."""
    return " ".join(text.translate(_TRANSLATE).split())


@cache
def sheets(ruleset: str) -> dict[int, str]:
    data = json.loads((RULES_DIR / f"{ruleset}.sheets.json").read_text())
    return {int(k): v for k, v in data["sheets"].items()}
