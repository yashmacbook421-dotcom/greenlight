"""Text normalisation used wherever a quote is checked against source text."""

import unicodedata

_TRANSLATE = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                            "–": "-", "—": "-", " ": " ", "­": ""})


def normalize(text: str) -> str:
    """NFKC (ligatures, full-width forms), typographic quotes/dashes to ASCII, whitespace runs to one space."""
    return " ".join(unicodedata.normalize("NFKC", text).translate(_TRANSLATE).split())
