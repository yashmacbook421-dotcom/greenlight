"""Persist engine output as core `rule_results` rows. Kept outside screens/ so the engine stays I/O-free."""

import uuid
from typing import Any

from app.core.models import RuleResult
from app.domains.interconnection.screens.initial_review import InitialReview
from app.domains.interconnection.screens.rulebook import RULESET

RULE_SET = f"{RULESET}:initial_review"


def to_rows(case_id: uuid.UUID, review: InitialReview, overrides: dict[str, Any] | None = None) -> list[RuleResult]:
    return [
        RuleResult(
            case_id=case_id,
            rule_set=RULE_SET,
            rule_id=r.screen,
            status=r.status.value,
            inputs=r.inputs,
            formula=r.formula,
            computed=r.computed,
            threshold=r.threshold,
            citation=[c.as_dict() for c in r.citations] or None,
            classification=r.classification.value if r.classification else None,
            reason=r.reason,
            blocker=r.blocker.value if r.blocker else None,
            routed_by=r.routed_by,
            missing_inputs=list(r.missing_inputs),
            synthetic_inputs=list(r.synthetic_inputs),
            overrides=overrides or {},
            engine_version=review.engine_version,
            input_hash=review.input_hash,
        )
        for r in review.results
    ]
