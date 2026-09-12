"""Split PG&E Rule 21 sheet text into section-addressed chunks (e.g. G.1.j on Sheet 151).

Tariff headings come in four levels: `G. ENGINEERING REVIEW DETAILS`, `1. INITIAL
REVIEW SCREENS`, `j. Screen J: ...`, `i) First Notification ...`. Every sheet
repeats its ancestors with "(Cont'd.)", so the section path is carried across
sheets. A chunk never spans two sheets, so a citation is always one sheet.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.core.text import normalize

_BOILERPLATE = re.compile(
    r"^\s*(U 39.*|(Revised|Original) Cal\. P\.U\.C\..*|Cancelling .*|ELECTRIC RULE NO\. 21.*|"
    r"GENERATING FACILITY INTERCONNECTIONS\s*|\(Continued\)\s*|Advice .*|Decision.*|Vice President.*|"
    r"Regulatory Proceedings and Rates.*|Shilpa Ramaiya.*|Resolution\s*)$"
)
_REVISION_MARK = re.compile(r"^\s*(\(?[LTNDCIR]\)?(/\([LTNDCIR]\))?|\||I)\s*$")
_CONTD = re.compile(r"\(\s*Cont[’']?d\.?\s*\)", re.IGNORECASE)
_TITLE_MARKS = re.compile(r"\s*\((?:[LTNDCIR])\)(?:/\((?:[LTNDCIR])\))?\s*$")
_ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]

_L1 = re.compile(r"^([A-Z])\.\s+([A-Z][^a-z]*)$")
_L2 = re.compile(r"^(\d{1,2})\.\s*([A-Z][^a-z]*)$")
_L3 = re.compile(r"^([a-z])\.\s+(\S.*)$")
_L4 = re.compile(r"^(i{1,3}|iv|v|vi{1,3}|ix|x)\)\s+([A-Z].*)$")


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    sheet: int
    section: str
    heading: str
    text: str


def _heading(line: str) -> tuple[int, str, str, bool] | None:
    contd = bool(_CONTD.search(line))
    bare = _TITLE_MARKS.sub("", _CONTD.sub("", line)).strip()
    for level, pattern in ((1, _L1), (2, _L2), (3, _L3), (4, _L4)):
        m = pattern.match(bare)
        if m:
            if level in (1, 2) and len(m.group(2).strip()) < 4:
                return None
            return level, m.group(1), _TITLE_MARKS.sub("", m.group(2)).strip(), contd
    return None


def _follows(level: int, label: str, previous: str | None) -> bool:
    """Lettered/roman headings advance in order (l→m, ii→iii); anything else is list text, not a heading."""
    if level == 3:
        return ord(label) == (ord(previous) + 1 if previous else ord("a"))
    nxt = _ROMAN.index(previous) + 1 if previous in _ROMAN else 0
    return nxt < len(_ROMAN) and label == _ROMAN[nxt]


def chunk_sheets(sheets: Iterable[tuple[int, str]], *, first_content_sheet: int = 15) -> list[Chunk]:
    chunks: list[Chunk] = []
    path: list[tuple[str, str]] = []  # (label, title) per level
    for sheet_no, raw in sorted(sheets):
        if sheet_no < first_content_sheet:  # table of contents
            continue
        body: list[str] = []
        current_section = ".".join(label for label, _ in path)

        def flush() -> None:
            text = "\n".join(body).strip()
            if normalize(text):
                chunks.append(Chunk(len(chunks), sheet_no, current_section or "front",
                                    path[-1][1] if path else "", text))
            body.clear()

        for line in raw.splitlines():
            if _BOILERPLATE.match(line) or _REVISION_MARK.match(line):
                continue
            h = _heading(line)
            if h and len(path) >= h[0] - 1:
                level, label, title, contd = h
                same = len(path) >= level and path[level - 1][0] == label
                if same:
                    # A section never restarts with its own label: this is the ancestor heading repeated at the
                    # top of a sheet (its "(Cont'd.)" marker sometimes wraps onto the next line).
                    continue
                previous = path[level - 1][0] if len(path) >= level else None
                # All-caps L1/L2 headings and "(Cont'd.)" headings are unambiguous. Plain `a.` / `i)` lines
                # are only headings when they advance the sequence; otherwise they are lettered list items.
                if level <= 2 or contd or _follows(level, label, previous):
                    flush()
                    path = path[: level - 1] + [(label, title)]
                    current_section = ".".join(lbl for lbl, _ in path)
            body.append(line.rstrip())
        flush()
    return chunks
