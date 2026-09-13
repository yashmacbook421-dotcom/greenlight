"""End-to-end review of one case: extraction → reconciliation → screens → draft → guardrails → pending_review."""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.extraction import ExtractionResult, extract_document
from app.core.llm import MessagesClient
from app.core.models import Case, Document, ExtractedFact, Proposal
from app.core.storage import LocalStorage
from app.domains.interconnection.agent.review import draft_deterministic, draft_with_agent, finalize
from app.domains.interconnection.extraction_fields import FIELDS
from app.domains.interconnection.reconcile import Judge
from app.domains.interconnection.service import ScreeningOutcome, screen_case


@dataclass
class ReviewOutcome:
    proposal: Proposal
    screening: ScreeningOutcome
    extractions: list[ExtractionResult] = field(default_factory=list)


def review_case(session: Session, case: Case, *, client: MessagesClient | None, storage: LocalStorage,
                reextract: bool = False, judge: Judge | None = None) -> ReviewOutcome:
    extractions = []
    if client is not None:
        documents = session.scalars(select(Document).where(Document.case_id == case.id).order_by(Document.created_at)).all()
        extracted = set(session.scalars(select(ExtractedFact.document_id).where(ExtractedFact.case_id == case.id)).all())
        for doc in documents:
            if reextract or doc.id not in extracted:
                extractions.append(extract_document(session, client, storage, doc, FIELDS, model=settings.llm_model,
                                                    max_tokens=settings.llm_max_tokens, effort=settings.llm_effort))
    case.status = "screening"
    screening = screen_case(session, case, client, judge=judge)
    if client is not None:
        draft = draft_with_agent(session, client, case, screening)
    else:
        draft = draft_deterministic(session, case, screening, reason="no Claude API client configured")
    proposal = finalize(session, case, screening, draft)
    return ReviewOutcome(proposal, screening, extractions)
