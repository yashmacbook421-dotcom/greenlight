"""Deterministic checks on model output. Prompting is not a control; these are.

Each check returns a Verdict that is stored on the proposal, so the eval can report
how often code had to overrule or flag the model.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class Verdict:
    name: str
    passed: bool
    detail: str
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# Identifiers that contain digits but are not quantities.
_NOT_QUANTITIES = re.compile(
    r"§\s*[A-Z](?:\.[A-Za-z0-9]+)*|\bSheets?\s+\d+(?:\s*[–-]\s*\d+)?|\bRule\s+21\b|\bScreens?\s+[A-R]1?\b|"
    r"\b(?:NEM|NBT)-\d\b|\bUL\s*1741(?:\s*S[AB]\d*)?\b|\bIEEE\s*1547(?:[.-]\d+)*\b|\bICA-(?:SG|OF)\s*576\b|"
    r"\bAdvice(?: Letter)?\s+\d+-E\b|\b[A-Z]{1,6}[-_]?\d[\w.-]*\b|^\s*\d+[.)]\s", re.MULTILINE)
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\s*%)?")


def _canon(text: str) -> str | None:
    try:
        return format(Decimal(text.replace(",", "")).normalize(), "f")
    except InvalidOperation:
        return None


def numbers_in(text: str) -> list[tuple[str, bool]]:
    """(canonical number, followed by %) for every quantity-like number in text."""
    stripped = _NOT_QUANTITIES.sub(" ", text)
    out = []
    for m in _NUMBER.finditer(stripped):
        c = _canon(m.group(1) + (m.group(2) or ""))
        if c is not None:
            out.append((c, bool(m.group(3))))
    return out


def evidence_numbers(evidence: Iterable[str]) -> set[str]:
    found: set[str] = set()
    for text in evidence:
        for m in _NUMBER.finditer(text):
            c = _canon(m.group(1) + (m.group(2) or ""))
            if c is not None:
                found.add(c)
    return found


def number_faithfulness(letter: str, evidence: Iterable[str]) -> Verdict:
    known = evidence_numbers(evidence)
    unsupported = []
    for number, is_percent in numbers_in(letter):
        if number in known:
            continue
        if is_percent and _canon(str(Decimal(number) / 100)) in known:  # 87.5% ↔ 0.875
            continue
        unsupported.append(number + ("%" if is_percent else ""))
    unsupported = sorted(set(unsupported))
    if unsupported:
        return Verdict("number_faithfulness", False,
                       f"numbers not found in any tool result or case evidence: {', '.join(unsupported)}",
                       {"unsupported": unsupported})
    return Verdict("number_faithfulness", True, "every number in the letter appears in recorded evidence")


_CITATION = re.compile(r"§\s*([A-Z](?:\.[A-Za-z0-9]+)*)(?:[^§\n]{0,12}?\bSheet\s+(\d+))?")
_BARE_SHEET = re.compile(r"\bSheet\s+(\d+)")


def citation_validity(letter: str, sections_on_sheet: Callable[[int], set[str]], known_sections: set[str]) -> Verdict:
    """Every §section must exist; when a sheet is given, that section (or a subsection) must be on that sheet."""
    invalid = []
    cited = []
    for m in _CITATION.finditer(letter):
        section, sheet = m.group(1).rstrip("."), m.group(2)
        cited.append({"section": section, "sheet": int(sheet) if sheet else None})
        if not any(s == section or s.startswith(section + ".") for s in known_sections):
            invalid.append(f"§{section} does not exist in the pinned rules")
        elif sheet and not any(s == section or s.startswith(section + ".") or section.startswith(s + ".")
                               for s in sections_on_sheet(int(sheet))):
            invalid.append(f"§{section} is not on Sheet {sheet}")
    for m in _BARE_SHEET.finditer(_CITATION.sub(" ", letter)):
        if not sections_on_sheet(int(m.group(1))):
            invalid.append(f"Sheet {m.group(1)} is not in the pinned rules")
    if invalid:
        return Verdict("citation_validity", False, "; ".join(invalid), {"invalid": invalid, "cited": cited})
    return Verdict("citation_validity", True, f"{len(cited)} citation(s) resolve to pinned rule text", {"cited": cited})


def disposition_veto(proposed: str, floor: str, severity: dict[str, int]) -> tuple[str, Verdict]:
    if severity[proposed] < severity[floor]:
        return floor, Verdict("disposition_veto", False,
                              f"model proposed {proposed}, but the evidence requires at least {floor}; overridden",
                              {"proposed": proposed, "floor": floor})
    return proposed, Verdict("disposition_veto", True, f"{proposed} is at or above the floor {floor}")


def provenance_completeness(items: list[dict[str, Any]], is_valid: Callable[[str, str], bool]) -> tuple[list[dict[str, Any]], Verdict]:
    kept = [i for i in items if is_valid(i["basis_kind"], i["basis_ref"])]
    stripped = [i for i in items if i not in kept]
    if stripped:
        return kept, Verdict("provenance_completeness", False, f"{len(stripped)} item(s) without valid evidence were removed",
                             {"stripped": stripped})
    return kept, Verdict("provenance_completeness", True, f"all {len(kept)} item(s) point at recorded evidence")
