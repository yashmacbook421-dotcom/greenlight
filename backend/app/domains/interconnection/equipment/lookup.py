"""Screen B support: is an inverter model on the pinned CEC Grid Support Inverter List?

Matching is exact after removing whitespace and case differences. A near miss
("SE7600H-US" vs "SE7600HUS") is *not* silently accepted: it is reported as a
near match so a reviewer (or the agent) can decide whether it is a typo.
"""

import csv
import difflib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path

HERE = Path(__file__).parent


@dataclass(frozen=True)
class ListedInverter:
    list: str
    manufacturer: str
    model: str
    voltage_option: str
    hybrid: bool
    ul1741_sb: bool
    ul1741_sa: bool
    max_continuous_output_kw: Decimal | None
    nominal_vac: Decimal | None

    @property
    def grid_support_certified(self) -> bool:
        return self.ul1741_sb or self.ul1741_sa


@dataclass(frozen=True)
class LookupResult:
    model_as_given: str
    matches: tuple[ListedInverter, ...]
    near_matches: tuple[str, ...]

    @property
    def listed(self) -> bool:
        return bool(self.matches)

    @property
    def certified(self) -> bool:
        return any(m.grid_support_certified for m in self.matches)

    def basis(self) -> str:
        if not self.matches:
            hint = f"; near matches: {', '.join(self.near_matches)}" if self.near_matches else ""
            return f"{self.model_as_given!r} not found on the CEC Grid Support Inverter List{hint}"
        m = next((m for m in self.matches if m.grid_support_certified), self.matches[0])
        cert = "UL 1741 SB" if m.ul1741_sb else "UL 1741 SA" if m.ul1741_sa else "no UL 1741 SA/SB grid-support certification"
        return f"{m.manufacturer} {m.model} listed ({m.list} list): {cert}"


def _key(model: str) -> str:
    return "".join(model.split()).casefold()


def _flag(value: str) -> bool:
    return value.strip().upper().startswith("Y")


def _decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.strip()) if value.strip() else None
    except InvalidOperation:
        return None


@cache
def manifest() -> dict[str, object]:
    return json.loads((HERE / "manifest.json").read_text())


@cache
def _index() -> dict[str, tuple[ListedInverter, ...]]:
    index: dict[str, list[ListedInverter]] = {}
    with (HERE / "cec_inverters.csv").open(newline="") as f:
        for r in csv.DictReader(f):
            inv = ListedInverter(r["list"], r["manufacturer"].strip(), r["model"].strip(), r["voltage_option"].strip(),
                                 _flag(r["hybrid"]), _flag(r["ul1741_sb"]), _flag(r["ul1741_sa"]),
                                 _decimal(r["max_continuous_output_kw"]), _decimal(r["nominal_vac"]))
            index.setdefault(_key(inv.model), []).append(inv)
    return {k: tuple(v) for k, v in index.items()}


def lookup(model: str, nominal_vac: Decimal | None = None) -> LookupResult:
    index = _index()
    matches = index.get(_key(model), ())
    if nominal_vac is not None and matches:
        by_voltage = tuple(m for m in matches if m.nominal_vac == nominal_vac)
        matches = by_voltage or matches
    near: tuple[str, ...] = ()
    if not matches:
        keys = difflib.get_close_matches(_key(model), index.keys(), n=3, cutoff=0.85)
        near = tuple(index[k][0].model for k in keys)
    return LookupResult(model, matches, near)
