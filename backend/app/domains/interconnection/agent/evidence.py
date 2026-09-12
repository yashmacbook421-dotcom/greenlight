"""Render screening outcomes as JSON the agent reads and the guardrails check numbers against."""

from dataclasses import replace
from decimal import Decimal
from typing import Any

from app.domains.interconnection.screens.initial_review import InitialReview
from app.domains.interconnection.screens.types import Facility, ScreenResult
from app.domains.interconnection.service import ScreeningOutcome


def num(v: Any) -> Any:
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")
    if isinstance(v, frozenset | tuple | list):
        return [num(x) for x in v]
    return getattr(v, "value", v)


def screen_json(r: ScreenResult) -> dict[str, Any]:
    return {
        "screen": r.screen, "status": r.status.value, "reason": r.reason,
        "computed": num(r.computed) if r.computed is not None else None,
        "threshold": num(r.threshold) if r.threshold is not None else None,
        "formula": r.formula, "classification": num(r.classification) if r.classification else None,
        "blocker": num(r.blocker) if r.blocker else None, "missing_inputs": list(r.missing_inputs),
        "synthetic_inputs": list(r.synthetic_inputs),
        "citations": [{"section": c.section, "sheet": c.sheet} for c in r.citations],
    }


def review_json(review: InitialReview, floor: Any) -> dict[str, Any]:
    return {"disposition_floor": num(floor), "screens": [screen_json(r) for r in review.results]}


def facility_json(f: Facility) -> dict[str, Any]:
    return {k: num(v) for k, v in vars(f).items() if v is not None}


def case_summary(outcome: ScreeningOutcome, application: dict[str, Any]) -> dict[str, Any]:
    rec = outcome.reconciliation
    return {
        "application": application,
        "facility_as_reconciled": facility_json(rec.facility),
        "facility_provenance": {k: [s.as_dict() for s in v] for k, v in rec.provenance.items()},
        "initial_review": review_json(outcome.review, outcome.floor),
        "discrepancies": [{"field": f.field, "values": [num(c.value) for c in f.candidates], "material": f.material,
                           "method": num(f.method) if f.method else None, "rationale": f.rationale,
                           "value_used": num(f.chosen) if f.chosen is not None else None} for f in rec.findings],
        "missing_documents": rec.missing_documents,
        "equipment": [{"model": e.model_as_given, "listed": e.listed, "certified": e.certified, "basis": e.basis()}
                      for e in rec.equipment],
        "notes": rec.notes,
        "utility_practice_source": outcome.inputs.practice.source if outcome.inputs.practice else None,
    }


def with_overrides(facility: Facility, overrides: dict[str, Any]) -> Facility:
    return replace(facility, **overrides)
