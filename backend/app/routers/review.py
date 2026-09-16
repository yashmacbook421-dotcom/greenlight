"""The review queue, the review bundle (every claim beside its evidence), the agent trace, and the human gate."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core import notify
from app.core.llm import LLMError
from app.core.models import (
    AgentRun,
    AgentStep,
    Case,
    CaseEvent,
    CaseEventKind,
    CaseStatus,
    Discrepancy,
    Document,
    ExtractedFact,
    Notification,
    Proposal,
    RuleResult,
)
from app.deps import OptionalLLMDep, SessionDep, StorageDep
from app.domains.interconnection import DOMAIN
from app.domains.interconnection.applicant import DECISION_RELEASED, decision_notice
from app.domains.interconnection.models import InterconnectionApplication
from app.domains.interconnection.pipeline import review_case

router = APIRouter(tags=["review"])


def _proposal_json(p: Proposal) -> dict[str, Any]:
    return {"id": str(p.id), "disposition": p.disposition, "model_disposition": p.model_disposition,
            "status": p.status, "letter_md": p.letter_md, "items": p.items, "guardrail_verdicts": p.guardrail_verdicts,
            "agent_run_id": str(p.agent_run_id) if p.agent_run_id else None, "reviewed_by": p.reviewed_by,
            "reviewed_at": p.reviewed_at, "review_note": p.review_note, "created_at": p.created_at}


def _latest_proposal(session: SessionDep, case_id: uuid.UUID) -> Proposal | None:
    return session.scalars(select(Proposal).where(Proposal.case_id == case_id)
                           .order_by(Proposal.created_at.desc(), Proposal.id)).first()


@router.get("/cases")
def queue(session: SessionDep, limit: Annotated[int, Query(ge=1, le=500)] = 100) -> list[dict[str, Any]]:
    cases = session.scalars(select(Case).where(Case.status != CaseStatus.DRAFT)  # drafts belong to the applicant
                           .order_by(Case.received_at.desc()).limit(limit)).all()
    out = []
    for c in cases:
        app = session.get(InterconnectionApplication, c.id)
        latest = _latest_proposal(session, c.id)
        out.append({
            "case_id": str(c.id), "domain": c.domain, "status": c.status, "submitter": c.submitter,
            "received_at": c.received_at, "applicant_name": app.applicant_name if app else None,
            "site_address": app.site_address if app else None,
            "documents": session.scalar(select(func.count()).select_from(Document)
                                        .where(Document.case_id == c.id, Document.superseded_at.is_(None))),
            "submissions": session.scalar(select(func.count()).select_from(CaseEvent).where(
                CaseEvent.case_id == c.id, CaseEvent.kind.in_([CaseEventKind.SUBMITTED, CaseEventKind.RESUBMITTED]))),
            "proposal": None if latest is None else {
                "id": str(latest.id), "disposition": latest.disposition, "status": latest.status,
                "guardrail_failures": sum(1 for v in latest.guardrail_verdicts if not v.get("passed", True))},
        })
    return out


@router.post("/cases/{case_id}/review")
def run_review(case_id: uuid.UUID, session: SessionDep, storage: StorageDep, client: OptionalLLMDep,
               use_llm: bool = True, reextract: bool = False) -> dict[str, Any]:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case not found")
    try:
        outcome = review_case(session, case, client=client if use_llm else None, storage=storage, reextract=reextract)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    session.commit()
    return {"llm_used": bool(use_llm and client), "disposition_floor": outcome.screening.floor.value,
            "proposal": _proposal_json(outcome.proposal)}


@router.get("/cases/{case_id}/review")
def review_bundle(case_id: uuid.UUID, session: SessionDep) -> dict[str, Any]:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case not found")
    app = session.get(InterconnectionApplication, case_id)
    all_docs = session.scalars(select(Document).where(Document.case_id == case_id).order_by(Document.created_at)).all()
    docs = [d for d in all_docs if d.superseded_at is None]
    facts = session.execute(select(ExtractedFact, Document.kind).join(Document, ExtractedFact.document_id == Document.id)
                            .where(ExtractedFact.case_id == case_id).order_by(ExtractedFact.field)).all()
    results = session.scalars(select(RuleResult).where(RuleResult.case_id == case_id).order_by(RuleResult.run_at)).all()
    latest = _latest_proposal(session, case_id)
    return {
        "case": {"id": str(case.id), "status": case.status, "submitter": case.submitter, "received_at": case.received_at},
        "application": None if app is None else {"utility": app.utility, "applicant_name": app.applicant_name,
                                                 "site_address": app.site_address,
                                                 "circuit_model_id": str(app.circuit_model_id) if app.circuit_model_id else None},
        "documents": [{"id": str(d.id), "kind": d.kind, "filename": d.filename, "page_count": d.page_count,
                       "sha256": d.sha256, "pages": [{"page_no": p.page_no, "has_text_layer": p.has_text_layer,
                                                      "anchor": d.anchor(p.page_no)} for p in d.pages]} for d in docs],
        "replaced_documents": [{"id": str(d.id), "kind": d.kind, "filename": d.filename, "page_count": d.page_count,
                                "uploaded_at": d.created_at, "replaced_at": d.superseded_at}
                               for d in all_docs if d.superseded_at is not None],
        "facts": [{"id": str(f.id), "field": f.field, "value": f.value, "unit": f.unit, "instance": f.instance,
                   "value_as_written": f.value_as_written, "unit_as_written": f.unit_as_written,
                   "document_id": str(f.document_id), "document_kind": kind, "page_no": f.page_no, "quote": f.quote,
                   "verification": f.verification} for f, kind in facts],
        "discrepancies": [{"field": d.field, "observed": d.observed, "material": d.material, "method": d.method,
                           "rationale": d.rationale} for d in
                          session.scalars(select(Discrepancy).where(Discrepancy.case_id == case_id))],
        "screens": [_result_json(r) for r in results if not r.overrides],
        "scenarios": [_result_json(r) for r in results if r.overrides],
        "proposal": _proposal_json(latest) if latest else None,
        "notifications": [{"kind": n.kind, "subject": n.subject, "recipient": n.recipient, "status": n.status,
                           "created_at": n.created_at, "sent_at": n.sent_at, "error": n.error} for n in
                          session.scalars(select(Notification).where(Notification.case_id == case_id)
                                          .order_by(Notification.created_at.desc()))],
    }


def _result_json(r: RuleResult) -> dict[str, Any]:
    return {"screen": r.rule_id, "status": r.status, "reason": r.reason, "formula": r.formula,
            "computed": str(r.computed) if r.computed is not None else None,
            "threshold": str(r.threshold) if r.threshold is not None else None, "inputs": r.inputs,
            "citations": r.citation or [], "classification": r.classification, "blocker": r.blocker,
            "routed_by": r.routed_by, "missing_inputs": r.missing_inputs, "synthetic_inputs": r.synthetic_inputs,
            "overrides": r.overrides, "input_hash": r.input_hash, "engine_version": r.engine_version}


@router.get("/cases/{case_id}/trace")
def trace(case_id: uuid.UUID, session: SessionDep) -> list[dict[str, Any]]:
    runs = session.scalars(select(AgentRun).where(AgentRun.case_id == case_id).order_by(AgentRun.started_at)).all()
    return [{
        "id": str(run.id), "model": run.model, "step_budget": run.step_budget, "steps_used": run.steps_used,
        "cost_ceiling_usd": str(run.cost_ceiling_usd), "cost_usd": str(run.cost_usd), "terminated_by": run.terminated_by,
        "started_at": run.started_at, "ended_at": run.ended_at,
        "steps": [{"n": s.n, "role": s.role, "tool": s.tool, "args": s.args, "result": s.result,
                   "input_tokens": s.input_tokens, "output_tokens": s.output_tokens,
                   "cost_usd": str(s.cost_usd) if s.cost_usd is not None else None, "latency_ms": s.latency_ms}
                  for s in session.scalars(select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.n))],
    } for run in runs]


class Decision(BaseModel):
    action: Literal["approve", "edit", "reject"]
    reviewer: str = Field(min_length=1)
    letter_md: str | None = Field(default=None, description="Required for edit: the letter as the engineer revised it")
    note: str | None = None


@router.post("/proposals/{proposal_id}/decision")
def decide(proposal_id: uuid.UUID, body: Decision, session: SessionDep) -> dict[str, Any]:
    """The human gate. Only a named reviewer moves a draft out of pending_review; the database enforces the rest."""
    proposal = session.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "proposal not found")
    if proposal.status != "pending_review":
        raise HTTPException(status.HTTP_409_CONFLICT, f"proposal was already {proposal.status}")
    if body.action == "edit" and not body.letter_md:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "edit requires the revised letter_md")
    proposal.status = {"approve": "approved", "edit": "edited", "reject": "rejected"}[body.action]
    if body.action == "edit":
        proposal.letter_md = body.letter_md  # type: ignore[assignment]
    proposal.reviewed_by = body.reviewer
    proposal.reviewed_at = datetime.now(UTC)
    proposal.review_note = body.note
    case = session.get(Case, proposal.case_id)
    if case is not None:
        case.status = "closed"
        if proposal.status in ("approved", "edited"):
            _notify_applicant(session, case, proposal)
    session.commit()
    return _proposal_json(proposal)


def _notify_applicant(session: SessionDep, case: Case, proposal: Proposal) -> None:
    """Released decisions are the only thing that reaches the applicant, so this is the only place notices start."""
    if case.domain != DOMAIN:
        return
    recipient, subject, body = decision_notice(session, case, proposal)
    notification = notify.record(session, case_id=case.id, kind=DECISION_RELEASED, recipient=recipient,
                                 subject=subject, body=body)
    notify.deliver(session, notification)


@router.get("/cases/{case_id}/documents/{document_id}/file")
def document_file(case_id: uuid.UUID, document_id: uuid.UUID, session: SessionDep, storage: StorageDep) -> Response:
    doc = session.get(Document, document_id)
    if doc is None or doc.case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return Response(storage.open(doc.sha256), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{doc.filename}"'})
