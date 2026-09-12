"""Load a case, reconcile its facts, run Initial Review, and persist discrepancies and screen results."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.llm import MessagesClient
from app.core.materiality import judge_conflicts
from app.core.models import Case, Discrepancy, Document, ExtractedFact, RuleResult
from app.domains.interconnection.circuits import to_circuit
from app.domains.interconnection.dispositions import Disposition
from app.domains.interconnection.models import CircuitModel, InterconnectionApplication
from app.domains.interconnection.reconcile import (
    FactView,
    Finding,
    Judge,
    Judgment,
    Reconciliation,
    disposition_floor,
    reconcile,
)
from app.domains.interconnection.screen_store import RULE_SET, to_rows
from app.domains.interconnection.screens.initial_review import InitialReview, run_initial_review
from app.domains.interconnection.screens.types import Circuit, ScreenInputs, UtilityPractice

SYNTHETIC_PRACTICE = UtilityPractice(
    source="synthetic demonstration values (not PG&E practice)",
    d_transformer_rating_multiplier=Decimal("1.0"),
    e_max_phase_imbalance_kva=Decimal("5"),
)


def practice() -> UtilityPractice | None:
    return SYNTHETIC_PRACTICE if settings.synthetic_utility_practice else None


def load_facts(session: Session, case_id: uuid.UUID) -> tuple[list[FactView], list[str]]:
    rows = session.execute(
        select(ExtractedFact, Document.kind).join(Document, ExtractedFact.document_id == Document.id)
        .where(ExtractedFact.case_id == case_id).order_by(Document.created_at, ExtractedFact.page_no, ExtractedFact.field)
    ).all()
    facts = [FactView(str(f.id), f.field, str(f.value), f.unit, f.instance, kind, f.page_no, f.quote) for f, kind in rows]
    kinds = list(session.scalars(select(Document.kind).where(Document.case_id == case_id)).all())
    return facts, kinds


def load_circuit(session: Session, case_id: uuid.UUID) -> tuple[Circuit, CircuitModel | None]:
    app = session.get(InterconnectionApplication, case_id)
    model = session.get(CircuitModel, app.circuit_model_id) if app and app.circuit_model_id else None
    return (to_circuit(model) if model else Circuit()), model


def llm_judge(client: MessagesClient) -> Judge:
    def judge(findings: list[Finding], facts: list[FactView]) -> list[Judgment]:
        by_id = {f.id: f for f in facts}
        conflicts = [{
            "field": finding.field,
            "values": [{"value": c.value, "quotes": [
                {"document": by_id[i].document_kind, "page": by_id[i].page_no, "quote": by_id[i].quote}
                for s in c.sources for i in s.fact_ids if i in by_id]} for c in finding.candidates],
        } for finding in findings]
        verdicts, _ = judge_conflicts(client, conflicts, model=settings.llm_model, effort=settings.llm_effort)
        return [Judgment(m, r) for m, r in verdicts]
    return judge  # type: ignore[return-value]


@dataclass
class ScreeningOutcome:
    reconciliation: Reconciliation
    review: InitialReview
    floor: Disposition
    inputs: ScreenInputs


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")
    return getattr(v, "value", v)


def screen_case(session: Session, case: Case, client: MessagesClient | None = None) -> ScreeningOutcome:
    facts, kinds = load_facts(session, case.id)
    circuit, _ = load_circuit(session, case.id)
    rec = reconcile(facts, kinds, circuit, practice(), judge=llm_judge(client) if client else None)
    inputs = ScreenInputs(rec.facility, circuit, practice())
    review = run_initial_review(inputs)
    floor = disposition_floor(rec, review.disposition_floor())

    now = datetime.now(UTC)
    session.execute(delete(Discrepancy).where(Discrepancy.case_id == case.id))
    session.add_all(Discrepancy(
        case_id=case.id, field=f.field, material=f.material, method=f.method.value if f.method else None,
        rationale=f.rationale, judged_at=now if f.material is not None else None,
        observed=[{"value": _jsonable(c.value), "sources": [s.as_dict() for s in c.sources],
                   "chosen": f.chosen is not None and c.value == f.chosen} for c in f.candidates],
    ) for f in rec.findings)
    session.execute(delete(RuleResult).where(RuleResult.case_id == case.id, RuleResult.rule_set == RULE_SET,
                                             RuleResult.overrides == {}))
    session.add_all(to_rows(case.id, review))
    session.flush()
    return ScreeningOutcome(rec, review, floor, inputs)
