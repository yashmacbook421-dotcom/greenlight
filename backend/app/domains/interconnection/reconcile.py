"""Stage 2 — reconciliation: extracted facts → screen-engine Facility, plus discrepancies.

Code finds; code or the LLM judges:

- Values are grouped per field; totals are *derived* in code (per-inverter rating × quantity,
  fault current ÷ rated current) and compared with what the application states.
- A conflict in anything the screens consume is judged by **re-running Initial Review with each
  value**. If no screen outcome changes, the conflict is immaterial by construction; if one does,
  it is material and the diff is the rationale.
- Conflicts the screens never see (names, model numbers, addresses) go to an LLM judge. Without a
  judge they stay unjudged and are surfaced to the reviewer.

Pure: no database, no network. `service.py` loads facts and persists the outcome.
"""

import enum
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from decimal import ROUND_CEILING, Decimal
from itertools import product
from typing import Any

from app.core.text import normalize
from app.domains.interconnection.dispositions import Disposition
from app.domains.interconnection.equipment.lookup import LookupResult, lookup
from app.domains.interconnection.screens.initial_review import run_initial_review
from app.domains.interconnection.screens.rulebook import Citation
from app.domains.interconnection.screens.types import Circuit, Facility, Program, ScreenInputs, UtilityPractice

SEVERITY = {Disposition.INITIAL_REVIEW_PASS: 0, Disposition.NEEDS_ENGINEER_DETERMINATION: 1,
            Disposition.SUPPLEMENTAL_REVIEW_REQUIRED: 2, Disposition.DEFICIENCY_NOTICE: 3}

# Completeness is anchored in the tariff but the checklist itself comes from the utility's application
# form, which the tariff defers to; it is labelled as Greenlight's checklist, not quoted as tariff text.
COMPLETE_AND_VALID = Citation("E.5", 70, "An Interconnection Request will be considered complete and valid when all "
                                         "items required for an Interconnection Request have been received by "
                                         "Distribution Provider and deemed valid by Distribution Provider.")
REQUIRED_DOCUMENTS = ("application_form", "one_line_diagram", "inverter_spec_sheet")

# Greenlight policy, not tariff text: numeric statements of the same quantity that differ by more than this
# relative spread need the applicant to clarify, even when no screen outcome changes (e.g. 1 vs 2 inverters).
ROUNDING_TOLERANCE = Decimal("0.02")
PU_QUANTUM = Decimal("0.000001")

IDENTITY_FIELDS = ("applicant_name", "site_address", "installer_name", "inverter_manufacturer", "inverter_model",
                   "battery_manufacturer", "battery_model", "inverter_certification", "system_dc_rating",
                   "battery_usable_capacity", "battery_rated_power", "inverter_nominal_ac_voltage")


class Method(enum.StrEnum):
    RULE_OUTCOME = "rule_outcome"
    LLM = "llm"


@dataclass(frozen=True)
class FactView:
    id: str
    field: str
    value: str
    unit: str | None
    instance: str | None
    document_kind: str
    page_no: int
    quote: str


@dataclass(frozen=True)
class Source:
    fact_ids: tuple[str, ...]
    derivation: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"fact_ids": list(self.fact_ids), "derivation": self.derivation}


@dataclass(frozen=True)
class Candidate:
    value: Any
    sources: tuple[Source, ...]


@dataclass(frozen=True)
class Finding:
    field: str
    candidates: tuple[Candidate, ...]
    material: bool | None = None
    method: Method | None = None
    rationale: str | None = None
    chosen: Any = None


@dataclass(frozen=True)
class Judgment:
    material: bool
    rationale: str


# field, candidate values with their quotes -> judgment
Judge = Callable[[Sequence[Finding], Sequence[FactView]], Sequence[Judgment]]


@dataclass
class Reconciliation:
    facility: Facility
    provenance: dict[str, tuple[Source, ...]]
    findings: list[Finding]
    missing_documents: list[str]
    equipment: list[LookupResult]
    notes: list[str] = field(default_factory=list)

    def applicant_blockers(self) -> list[str]:
        items = [f"missing document: {d}" for d in self.missing_documents]
        items += [f"conflicting values for {f.field}: {f.rationale}" for f in self.findings if f.material]
        return items

    def unjudged(self) -> list[Finding]:
        return [f for f in self.findings if f.material is None]


# --- grouping helpers -------------------------------------------------------------------------------


def _inst(instance: str | None) -> str:
    return normalize(instance or "").casefold()


def _fmt(v: Any) -> str:
    return format(v.normalize(), "f") if isinstance(v, Decimal) else str(v.value if isinstance(v, enum.Enum) else v)


def _distinct(facts: Iterable[FactView], convert: Callable[[FactView], Any]) -> list[Candidate]:
    groups: dict[Any, list[str]] = {}
    for f in facts:
        groups.setdefault(convert(f), []).append(f.id)
    return [Candidate(v, (Source(tuple(ids)),)) for v, ids in groups.items()]


def _merge(candidates: Iterable[Candidate]) -> list[Candidate]:
    merged: dict[Any, list[Source]] = {}
    for c in candidates:
        merged.setdefault(c.value, []).extend(c.sources)
    return [Candidate(v, tuple(s)) for v, s in merged.items()]


def _by_instance(facts: Sequence[FactView], name: str) -> dict[str, list[FactView]]:
    out: dict[str, list[FactView]] = {}
    for f in facts:
        if f.field == name:
            out.setdefault(_inst(f.instance), []).append(f)
    return out


def _dec(f: FactView) -> Decimal:
    return Decimal(f.value)


def _derived_total(facts: Sequence[FactView], per_unit_field: str, label: str) -> list[Candidate]:
    """Σ over inverter instances of (per-unit value × quantity); one candidate per combination of conflicting inputs."""
    ratings = _by_instance(facts, per_unit_field)
    quantities = _by_instance(facts, "inverter_quantity")
    if not ratings:
        return []
    per_instance: list[list[tuple[Decimal, Source]]] = []
    for inst, rating_facts in sorted(ratings.items()):
        qty_facts = quantities.get(inst) or (quantities.get("") if len(ratings) == 1 else None)
        if not qty_facts:
            return []  # a total cannot be derived without a stated quantity
        options = []
        for r, q in product(_distinct(rating_facts, _dec), _distinct(qty_facts, _dec)):
            ids = r.sources[0].fact_ids + q.sources[0].fact_ids
            name = f" ({inst})" if inst else ""
            options.append((r.value * q.value, Source(ids, f"{_fmt(q.value)} × {_fmt(r.value)}{name}")))
        per_instance.append(options)
    out = []
    for combo in product(*per_instance):
        total = sum((v for v, _ in combo), Decimal(0))
        derivation = f"{label} = " + " + ".join(s.derivation or "" for _, s in combo)
        out.append(Candidate(total, (Source(tuple(i for _, s in combo for i in s.fact_ids), derivation),)))
    return _merge(out)


def _pu_candidates(facts: Sequence[FactView]) -> list[Candidate]:
    faults = _by_instance(facts, "inverter_max_fault_current")
    currents = _by_instance(facts, "inverter_max_continuous_output_current")
    per_instance = []
    for inst in sorted(set(faults) & set(currents)):
        options = []
        for fc, rc in product(_distinct(faults[inst], _dec), _distinct(currents[inst], _dec)):
            if rc.value > 0:
                # Rounded up to 6 places: never makes a failing contribution pass (Screen F1 tests <= 1.2).
                ratio = (fc.value / rc.value).quantize(PU_QUANTUM, rounding=ROUND_CEILING)
                options.append((ratio, Source(fc.sources[0].fact_ids + rc.sources[0].fact_ids,
                                                            f"{_fmt(fc.value)} A ÷ {_fmt(rc.value)} A")))
        if options:
            per_instance.append(options)
    if not per_instance:
        return []
    out = []
    for combo in product(*per_instance):
        worst, source = max(combo, key=lambda t: t[0])
        out.append(Candidate(worst, (Source(source.fact_ids, f"short_circuit_pu = max over inverters of {source.derivation}"),)))
    return _merge(out)


_CHOICE = {"export": True, "non_export": False}


def _bindings(facts: Sequence[FactView]) -> dict[str, list[Candidate]]:
    """Candidate values for each primary Facility attribute."""
    by_field: dict[str, list[FactView]] = {}
    for f in facts:
        by_field.setdefault(f.field, []).append(f)
    get = by_field.get

    c: dict[str, list[Candidate]] = {}
    c["gross_rating_kw"] = _merge(_distinct(get("system_ac_rating", []), _dec)
                                  + _derived_total(facts, "inverter_rated_ac_power", "Σ inverter rated AC power"))
    c["gross_rating_kva"] = _merge(_distinct(get("system_apparent_power_rating", []), _dec)
                                   + _derived_total(facts, "inverter_max_apparent_power", "Σ inverter max apparent power"))
    c["short_circuit_pu"] = _pu_candidates(facts)
    c["exports"] = _distinct(get("export_intent", []), lambda f: _CHOICE[f.value])
    c["export_option"] = _distinct(get("non_export_option", []), lambda f: int(Decimal(f.value)))
    c["program"] = _distinct(get("tariff_program", []), lambda f: Program(f.value) if f.value in Program._value2member_map_ else Program.OTHER)
    c["service_equipment_amps"] = _distinct(get("service_panel_rating", []), _dec)
    c["service_voltage_v"] = _distinct(get("service_voltage", []), _dec)
    c["service_phases"] = _distinct(get("service_phases", []), lambda f: int(Decimal(f.value)))
    c["min_host_load_kw_12mo"] = _distinct(get("min_host_load_12mo", []), _dec)
    c["phase_configuration"] = _distinct(get("inverter_phase_configuration", []), lambda f: f.value)
    return {k: v for k, v in c.items() if v}


def _facility(chosen: dict[str, Any], equipment_certified: bool | None, inverter_based: bool | None) -> Facility:
    config = chosen.get("phase_configuration")
    kva = chosen.get("gross_rating_kva")
    single_phase = None if config is None else config != "three_phase"
    if config == "single_phase_240v_split":
        center_tap, imbalance = True, Decimal(0)
    elif config == "single_phase_120v":
        center_tap = (chosen.get("service_phases") == 1 and chosen.get("service_voltage_v") == Decimal(240)) \
            if "service_phases" in chosen and "service_voltage_v" in chosen else None
        imbalance = kva
    else:
        center_tap = False if config == "three_phase" else None
        imbalance = None
    return Facility(
        gross_rating_kva=kva, gross_rating_kw=chosen.get("gross_rating_kw"), inverter_based=inverter_based,
        starts_by_motoring=False if inverter_based else None, equipment_certified=equipment_certified,
        certified_non_islanding=equipment_certified, single_phase=single_phase, on_240v_center_tap=center_tap,
        phase_imbalance_kva=imbalance, exports=chosen.get("exports"), export_option=chosen.get("export_option"),
        program=chosen.get("program"), short_circuit_pu=chosen.get("short_circuit_pu"),
        service_equipment_amps=chosen.get("service_equipment_amps"), service_voltage_v=chosen.get("service_voltage_v"),
        service_phases=chosen.get("service_phases"), min_host_load_kw_12mo=chosen.get("min_host_load_kw_12mo"),
    )


def _signature(x: ScreenInputs) -> tuple[Disposition, dict[str, str]]:
    review = run_initial_review(x)
    return review.disposition_floor(), {r.screen: r.status.value for r in review.results}


def _sort_key(c: Candidate) -> tuple[int, Any]:
    return (0, c.value) if isinstance(c.value, Decimal | int) else (1, _fmt(c.value))


def reconcile(facts: Sequence[FactView], document_kinds: Iterable[str], circuit: Circuit,
              practice: UtilityPractice | None, judge: Judge | None = None) -> Reconciliation:
    notes: list[str] = []
    bindings = _bindings(facts)

    # Equipment: every distinct inverter model must be on the certified list.
    models = sorted({normalize(f.value) for f in facts if f.field == "inverter_model"})
    voltages = {Decimal(f.value) for f in facts if f.field == "inverter_nominal_ac_voltage"}
    voltage = next(iter(voltages)) if len(voltages) == 1 else None
    equipment = [lookup(m, voltage) for m in models]
    equipment_certified = all(e.certified for e in equipment) if equipment else None
    inverter_based = True if any(f.field.startswith("inverter_") for f in facts) else None

    chosen = {k: sorted(v, key=_sort_key)[0].value for k, v in bindings.items()}
    provenance = {k: sorted(v, key=_sort_key)[0].sources for k, v in bindings.items()}

    def inputs_with(overrides: dict[str, Any]) -> ScreenInputs:
        return ScreenInputs(_facility({**chosen, **overrides}, equipment_certified, inverter_based), circuit, practice)

    findings: list[Finding] = []
    for name, candidates in sorted(bindings.items()):
        if len(candidates) < 2:
            continue
        outcomes = {id(c): _signature(inputs_with({name: c.value})) for c in candidates}
        distinct = {(d, tuple(sorted(s.items()))) for d, s in outcomes.values()}
        worst = max(candidates, key=lambda c: (SEVERITY[outcomes[id(c)][0]], _sort_key(c)))
        values = ", ".join(_fmt(c.value) for c in sorted(candidates, key=_sort_key))
        numeric = [c.value for c in candidates if isinstance(c.value, Decimal)]
        spread = (max(numeric) - min(numeric)) / max(numeric) if len(numeric) == len(candidates) and max(numeric) > 0 else None
        if len(distinct) == 1 and (spread is None or spread <= ROUNDING_TOLERANCE):
            rationale = f"Re-running Initial Review with each value ({values}) leaves every screen outcome unchanged."
            if spread is not None:
                rationale += f" The values differ by {_fmt((spread * 100).quantize(Decimal('0.01')))}%, within the 2% rounding tolerance."
            material = False
        elif len(distinct) == 1:
            rationale = (f"Values {values} differ by {_fmt((spread * 100).quantize(Decimal('0.1')))}%, beyond the 2% "
                         "rounding tolerance; no screen outcome changes, but the application must state one value.")
            material = True
        else:
            base_d, base_s = outcomes[id(candidates[0])]
            diffs = []
            for c in candidates[1:]:
                d, s = outcomes[id(c)]
                changed = [f"Screen {k}: {base_s[k]} with {_fmt(candidates[0].value)} → {s[k]} with {_fmt(c.value)}"
                           for k in base_s if base_s[k] != s[k]]
                if d != base_d:
                    changed.append(f"disposition floor {base_d.value} → {d.value}")
                diffs += changed
            rationale = "Values change the review: " + "; ".join(diffs)
            material = True
        chosen[name] = worst.value
        provenance[name] = worst.sources
        findings.append(Finding(name, tuple(candidates), material, Method.RULE_OUTCOME, rationale, worst.value))

    # Conflicts no screen consumes: equal after case/punctuation normalisation is not a conflict.
    judged_later = []
    for name in IDENTITY_FIELDS:
        group = [f for f in facts if f.field == name]
        by_key: dict[str, list[FactView]] = {}
        for f in group:
            by_key.setdefault(re.sub(r"[\W_]+", "", normalize(f.value).casefold()), []).append(f)
        if len(by_key) > 1:
            judged_later.append(Finding(name, tuple(Candidate(v[0].value, (Source(tuple(x.id for x in v)),))
                                                    for v in by_key.values())))
    if judged_later and judge is not None:
        for finding, j in zip(judged_later, judge(judged_later, facts), strict=True):
            findings.append(replace(finding, material=j.material, method=Method.LLM, rationale=j.rationale))
    else:
        findings += judged_later
        if judged_later:
            notes.append("identity conflicts left unjudged (no materiality judge available)")

    present = set(document_kinds)
    missing = [d for d in REQUIRED_DOCUMENTS if d not in present]
    if any(f.field.startswith("battery_") for f in facts) and "battery_spec_sheet" not in present:
        missing.append("battery_spec_sheet")

    if equipment_certified is None and inverter_based:
        notes.append("no inverter model extracted; Screen B cannot be evaluated")
    notes.append("Screen B certification uses the CEC Grid Support Inverter List as a proxy for Rule 21 §L")
    if chosen.get("phase_configuration") == "single_phase_120v":
        notes.append("120 V single-phase connection: phase imbalance taken as the full gross rating (kVA)")

    return Reconciliation(_facility(chosen, equipment_certified, inverter_based), provenance, findings, missing,
                          equipment, notes)


def disposition_floor(reconciliation: Reconciliation, screens_floor: Disposition) -> Disposition:
    """Reconciliation can only make the floor worse: an incomplete or self-contradicting packet is a deficiency."""
    if reconciliation.applicant_blockers():
        return Disposition.DEFICIENCY_NOTICE
    if reconciliation.unjudged() and SEVERITY[screens_floor] < SEVERITY[Disposition.NEEDS_ENGINEER_DETERMINATION]:
        return Disposition.NEEDS_ENGINEER_DETERMINATION
    return screens_floor
