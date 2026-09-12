"""Engine output must be storable as-is: the database's invariants and the engine's must agree."""

from dataclasses import replace
from decimal import Decimal as D

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Case, RuleResult
from app.domains.interconnection import DOMAIN
from app.domains.interconnection.screen_store import to_rows
from app.domains.interconnection.screens.initial_review import run_initial_review
from app.domains.interconnection.screens.types import Program
from tests.test_initial_review import COMMERCIAL, RESIDENTIAL, cir, fac

SCENARIOS = {
    "residential": RESIDENTIAL,
    "commercial": COMMERCIAL,
    "missing-rating": fac(RESIDENTIAL, gross_rating_kva=None),
    "export-unknown": fac(COMMERCIAL, exports=None),
    "non-export-opt1": fac(COMMERCIAL, exports=False, export_option=1),
    "no-practice": replace(RESIDENTIAL, practice=None),
    "screen-l-runs": cir(fac(COMMERCIAL, program=Program.OTHER), islanding_possible=True),
    "fails": cir(fac(COMMERCIAL, equipment_certified=False), facility_fault_contribution_a=D("9999")),
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_scenario_persists(session: Session, name: str) -> None:
    case = Case(domain=DOMAIN)
    session.add(case)
    session.flush()
    review = run_initial_review(SCENARIOS[name])
    session.add_all(to_rows(case.id, review, overrides={"scenario": name}))
    session.flush()

    stored = session.scalars(select(RuleResult).where(RuleResult.case_id == case.id)).all()
    assert sorted(r.rule_id for r in stored) == sorted(r.screen for r in review.results)
    assert {r.input_hash for r in stored} == {review.input_hash}
