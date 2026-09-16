"""The applicant portal: installers start an application, upload the packet, submit, and track the outcome.

What an applicant can see is deliberately narrow. Drafts, guardrail verdicts, the agent trace and anything
an engineer has not approved stay inside the utility. A letter reaches this API only after a named reviewer
moved its proposal to `approved` or `edited`.

There is no authentication yet: `installer` is typed, not verified (see README, Known limits).
"""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.intake import IntakeError, ingest_document, supersede_document
from app.core.models import (
    Case,
    CaseEvent,
    CaseEventKind,
    CaseStatus,
    Document,
    Notification,
    Proposal,
    ProposalStatus,
)
from app.db import SessionLocal
from app.deps import SessionDep, StorageDep, get_optional_llm_client, get_storage
from app.domains.interconnection import DOMAIN, DocumentKind
from app.domains.interconnection.applicant import DRAFT, OUTCOMES, UNDER_REVIEW, reference
from app.domains.interconnection.dispositions import Disposition
from app.domains.interconnection.models import InterconnectionApplication
from app.domains.interconnection.pipeline import review_case
from app.domains.interconnection.reconcile import REQUIRED_DOCUMENTS

log = logging.getLogger(__name__)
router = APIRouter(prefix="/portal", tags=["portal"])

RELEASED = (ProposalStatus.APPROVED, ProposalStatus.EDITED)
KIND_LABELS = {
    DocumentKind.APPLICATION_FORM: "Interconnection application form",
    DocumentKind.ONE_LINE_DIAGRAM: "Single-line diagram",
    DocumentKind.INVERTER_SPEC_SHEET: "Inverter specification sheet",
    DocumentKind.SITE_PLAN: "Site plan",
    DocumentKind.BATTERY_SPEC_SHEET: "Battery specification sheet",
    DocumentKind.CUSTOMER_AUTHORIZATION: "Customer authorization",
    DocumentKind.OTHER: "Other supporting document",
}
TIMELINE_LABELS = {
    CaseEventKind.CREATED: "Application started",
    CaseEventKind.DOCUMENT_ADDED: "Document uploaded",
    CaseEventKind.DOCUMENT_REPLACED: "Corrected document uploaded",
    CaseEventKind.SUBMITTED: "Submitted to the utility",
    CaseEventKind.RESUBMITTED: "Resubmitted with corrections",
}

ReviewRunner = Callable[[uuid.UUID], None]


# --- automatic review after submission -------------------------------------------------------------------------


def review_submitted(session: Session, storage: Any, client: Any, case_id: uuid.UUID) -> None:
    """Run the full review for a freshly submitted case. A failure leaves the case `received` for an engineer."""
    case = session.get(Case, case_id)
    if case is None or case.status != CaseStatus.RECEIVED:
        return
    case.status = CaseStatus.EXTRACTING
    session.commit()
    try:
        review_case(session, case, client=client, storage=storage)
        session.commit()
    except Exception as exc:
        log.exception("automatic review failed for case %s", case_id)
        session.rollback()
        case = session.get(Case, case_id)
        if case is not None:
            case.status = CaseStatus.RECEIVED
            session.add(CaseEvent(case_id=case_id, kind=CaseEventKind.REVIEW_FAILED, detail={"error": str(exc)[:500]}))
            session.commit()


def _review_in_background(case_id: uuid.UUID) -> None:
    with SessionLocal() as session:
        review_submitted(session, get_storage(), get_optional_llm_client(), case_id)


def get_review_runner() -> ReviewRunner:
    return _review_in_background


ReviewRunnerDep = Annotated[ReviewRunner, Depends(get_review_runner)]


# --- reading a case as the applicant sees it --------------------------------------------------------------------


class PortalApplicationCreate(BaseModel):
    installer: str = Field(min_length=1, max_length=200, description="Installer company filing the application")
    applicant_name: str = Field(min_length=1, max_length=200, description="Customer of record")
    site_address: str = Field(min_length=1, max_length=500)
    contact_email: str | None = Field(default=None, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
                                      description="Where decisions are sent")


def _get(session: Session, case_id: uuid.UUID) -> tuple[Case, InterconnectionApplication]:
    case = session.get(Case, case_id)
    app = session.get(InterconnectionApplication, case_id)
    if case is None or app is None or case.domain != DOMAIN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "application not found")
    return case, app


def _released(session: Session, case_id: uuid.UUID) -> list[Proposal]:
    return list(session.scalars(select(Proposal).where(Proposal.case_id == case_id, Proposal.status.in_(RELEASED))
                                .order_by(Proposal.reviewed_at)))


def _status(case: Case, released: list[Proposal]) -> tuple[str, str, str]:
    if case.status == CaseStatus.DRAFT:
        return DRAFT
    if case.status != CaseStatus.CLOSED or not released:
        return UNDER_REVIEW  # includes a draft the engineer rejected: the utility still owes a decision
    return OUTCOMES[Disposition(released[-1].disposition)]


def _documents(session: Session, case_id: uuid.UUID) -> list[Document]:
    return list(session.scalars(select(Document).where(Document.case_id == case_id).order_by(Document.created_at)))


def _events(session: Session, case_id: uuid.UUID) -> list[CaseEvent]:
    return list(session.scalars(select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.at)))


def _submit_blocker(status_code: str, docs: list[Document], events: list[CaseEvent],
                    released: list[Proposal]) -> str | None:
    current = [d for d in docs if d.superseded_at is None]
    if status_code == "draft":
        missing = [KIND_LABELS[DocumentKind(k)] for k in REQUIRED_DOCUMENTS if k not in {d.kind for d in current}]
        return f"Upload the required documents first: {', '.join(missing)}." if missing else None
    if status_code == "action_required":
        # Uploads made in response to a notice name it, so "has anything changed since?" needs no clock comparison.
        current_ids = {str(d.id) for d in current}
        changed = any(e.detail.get("responds_to") == str(released[-1].id) and e.detail.get("document_id") in current_ids
                      for e in events)
        return None if changed else "Upload at least one corrected document before resubmitting."
    return "This application is not waiting on you."


def _view(session: Session, case: Case, app: InterconnectionApplication) -> dict[str, Any]:
    released = _released(session, case.id)
    code, label, detail = _status(case, released)
    docs = _documents(session, case.id)
    current = [d for d in docs if d.superseded_at is None]
    events = _events(session, case.id)
    blocker = _submit_blocker(code, docs, events, released)
    submitted = next((e.at for e in events if e.kind == CaseEventKind.SUBMITTED), None)

    timeline = [{"at": e.at, "kind": e.kind, "label": TIMELINE_LABELS[CaseEventKind(e.kind)],
                 "detail": e.detail.get("summary")} for e in events if e.kind in TIMELINE_LABELS]
    timeline += [{"at": p.reviewed_at, "kind": "decision", "label": f"Decision issued: {OUTCOMES[Disposition(p.disposition)][1]}",
                  "detail": None} for p in released]
    timeline.sort(key=lambda t: t["at"])

    return {
        "id": str(case.id), "reference": reference(case.id), "installer": case.submitter, "utility": app.utility,
        "applicant_name": app.applicant_name, "site_address": app.site_address, "contact_email": app.contact_email,
        "status": code, "status_label": label, "status_detail": detail,
        "started_at": events[0].at if events else case.received_at, "submitted_at": submitted,
        "required_documents": [{"kind": k, "label": KIND_LABELS[DocumentKind(k)],
                                "uploaded": any(d.kind == k for d in current)} for k in REQUIRED_DOCUMENTS],
        "documents": [_doc(d) for d in current],
        "replaced_documents": [_doc(d) for d in docs if d.superseded_at is not None],
        "can_upload": code in ("draft", "action_required"),
        "can_submit": blocker is None, "submit_blocker": blocker,
        "letters": [{"id": str(p.id), "outcome": OUTCOMES[Disposition(p.disposition)][0],
                     "outcome_label": OUTCOMES[Disposition(p.disposition)][1], "letter_md": p.letter_md,
                     "issued_at": p.reviewed_at, "issued_by": p.reviewed_by} for p in reversed(released)],
        "timeline": timeline,
        "notifications": [{"kind": n.kind, "subject": n.subject, "recipient": n.recipient, "status": n.status,
                           "created_at": n.created_at, "sent_at": n.sent_at} for n in
                          session.scalars(select(Notification).where(Notification.case_id == case.id)
                                          .order_by(Notification.created_at.desc()))],
    }


def _doc(d: Document) -> dict[str, Any]:
    return {"id": str(d.id), "kind": d.kind, "label": KIND_LABELS[DocumentKind(d.kind)], "filename": d.filename,
            "page_count": d.page_count, "uploaded_at": d.created_at, "replaced_at": d.superseded_at}


# --- endpoints ----------------------------------------------------------------------------------------------------


@router.post("/applications", status_code=status.HTTP_201_CREATED)
def start_application(body: PortalApplicationCreate, session: SessionDep) -> dict[str, Any]:
    """Start a draft. Reviewers do not see it until it is submitted."""
    case = Case(domain=DOMAIN, submitter=body.installer.strip(), status=CaseStatus.DRAFT)
    session.add(case)
    session.flush()
    app = InterconnectionApplication(case_id=case.id, utility="PGE", applicant_name=body.applicant_name.strip(),
                                     site_address=body.site_address.strip(),
                                     contact_email=(body.contact_email or "").strip() or None)
    session.add_all([app, CaseEvent(case_id=case.id, kind=CaseEventKind.CREATED, actor=case.submitter)])
    session.commit()
    return _view(session, case, app)


@router.get("/applications")
def list_applications(session: SessionDep, installer: Annotated[str, Query(min_length=1)]) -> list[dict[str, Any]]:
    rows = session.execute(select(Case, InterconnectionApplication)
                           .join(InterconnectionApplication, InterconnectionApplication.case_id == Case.id)
                           .where(Case.domain == DOMAIN, Case.submitter == installer.strip())
                           .order_by(Case.received_at.desc())).all()
    out = []
    for case, app in rows:
        released = _released(session, case.id)
        code, label, _ = _status(case, released)
        events = _events(session, case.id)
        out.append({"id": str(case.id), "reference": reference(case.id), "applicant_name": app.applicant_name,
                    "site_address": app.site_address, "status": code, "status_label": label,
                    "updated_at": max([e.at for e in events] + [p.reviewed_at for p in released] + [case.received_at]),
                    "documents": sum(1 for d in _documents(session, case.id) if d.superseded_at is None)})
    return out


@router.get("/applications/{case_id}")
def get_application(case_id: uuid.UUID, session: SessionDep) -> dict[str, Any]:
    case, app = _get(session, case_id)
    return _view(session, case, app)


@router.post("/applications/{case_id}/documents")
def upload(case_id: uuid.UUID, kind: Annotated[str, Form()], file: Annotated[UploadFile, File()],
           session: SessionDep, storage: StorageDep, response: Response) -> dict[str, Any]:
    """Add a document, or replace the current document of the same kind (except `other`, which accumulates)."""
    case, app = _get(session, case_id)
    released = _released(session, case.id)
    code = _status(case, released)[0]
    if code not in ("draft", "action_required"):
        raise HTTPException(status.HTTP_409_CONFLICT, "documents can only be changed on a draft or after a deficiency notice")
    if kind not in {k.value for k in DocumentKind}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"kind must be one of {sorted(k.value for k in DocumentKind)}")
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"file exceeds {settings.max_upload_bytes} bytes")

    previous = [] if kind == DocumentKind.OTHER else list(session.scalars(select(Document).where(
        Document.case_id == case.id, Document.kind == kind, Document.superseded_at.is_(None))))
    try:
        doc, created = ingest_document(session, storage, case_id=case.id, kind=kind, filename=file.filename or "upload.pdf",
                                       data=data, max_pages=settings.max_pages_per_document)
    except IntakeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if not created:
        if doc.superseded_at is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "this exact file was already replaced; upload the corrected version")
        response.status_code = status.HTTP_200_OK
        return _view(session, case, app)

    label = KIND_LABELS[DocumentKind(kind)]
    if previous and code == "draft":  # never reviewed, so nothing to keep
        for old in previous:
            session.delete(old)
    elif previous:
        for old in previous:
            supersede_document(session, old)
    replaced = bool(previous) and code == "action_required"
    session.add(CaseEvent(case_id=case.id, actor=case.submitter,
                          kind=CaseEventKind.DOCUMENT_REPLACED if replaced else CaseEventKind.DOCUMENT_ADDED,
                          detail={"document_id": str(doc.id), "kind": kind, "summary": f"{label}: {doc.filename}",
                                  "responds_to": str(released[-1].id) if code == "action_required" else None}))
    session.commit()
    response.status_code = status.HTTP_201_CREATED
    return _view(session, case, app)


@router.post("/applications/{case_id}/submit")
def submit(case_id: uuid.UUID, session: SessionDep, background: BackgroundTasks, run_review: ReviewRunnerDep) -> dict[str, Any]:
    """Send the application (or its corrections) to the utility. The review starts automatically."""
    case, app = _get(session, case_id)
    released = _released(session, case.id)
    code = _status(case, released)[0]
    blocker = _submit_blocker(code, _documents(session, case.id), _events(session, case.id), released)
    if blocker is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, blocker)
    now = datetime.now(UTC)
    if code == "draft":
        case.received_at = now  # the utility's clock starts at submission, not when the draft was started
    case.status = CaseStatus.RECEIVED
    session.add(CaseEvent(case_id=case.id, actor=case.submitter, at=now,
                          kind=CaseEventKind.SUBMITTED if code == "draft" else CaseEventKind.RESUBMITTED))
    session.commit()
    background.add_task(run_review, case.id)
    return _view(session, case, app)
