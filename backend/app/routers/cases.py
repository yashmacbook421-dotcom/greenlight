import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select

from app.config import settings
from app.core.extraction import extract_document
from app.core.intake import IntakeError, ingest_document
from app.core.llm import LLMError
from app.core.models import Case, Document, Page
from app.core.schemas import CaseOut, DocumentOut, ExtractionOut, FactOut, PageOut, PageSummary, RejectedFactOut
from app.deps import LLMDep, SessionDep, StorageDep
from app.domains import DOCUMENT_KINDS, EXTRACTION_FIELDS

router = APIRouter(prefix="/cases", tags=["cases"])


def _document_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        kind=doc.kind,
        filename=doc.filename,
        sha256=doc.sha256,
        page_count=doc.page_count,
        created_at=doc.created_at,
        pages=[
            PageSummary(page_no=p.page_no, anchor=doc.anchor(p.page_no), has_text_layer=p.has_text_layer,
                        char_count=len(p.text))
            for p in doc.pages
        ],
    )


def _get_case(session: SessionDep, case_id: uuid.UUID) -> Case:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case not found")
    return case


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: uuid.UUID, session: SessionDep) -> CaseOut:
    case = _get_case(session, case_id)
    return CaseOut(
        id=case.id,
        domain=case.domain,
        status=case.status,
        submitter=case.submitter,
        received_at=case.received_at,
        documents=[_document_out(d) for d in case.documents],
    )


@router.post("/{case_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    case_id: uuid.UUID,
    kind: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    session: SessionDep,
    storage: StorageDep,
    response: Response,
) -> DocumentOut:
    case = _get_case(session, case_id)
    allowed = DOCUMENT_KINDS[case.domain]
    if kind not in allowed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"kind must be one of {sorted(allowed)}")

    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"file exceeds {settings.max_upload_bytes} bytes")

    try:
        document, created = ingest_document(
            session, storage, case_id=case.id, kind=kind, filename=file.filename or "upload.pdf", data=data,
            max_pages=settings.max_pages_per_document,
        )
    except IntakeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    session.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return _document_out(document)


@router.get("/{case_id}/documents/{document_id}/pages/{page_no}", response_model=PageOut)
def get_page(case_id: uuid.UUID, document_id: uuid.UUID, page_no: int, session: SessionDep) -> PageOut:
    row = session.execute(
        select(Page, Document)
        .join(Document, Page.document_id == Document.id)
        .where(Document.case_id == case_id, Document.id == document_id, Page.page_no == page_no)
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "page not found")
    page, doc = row
    return PageOut(document_id=doc.id, page_no=page.page_no, anchor=doc.anchor(page.page_no),
                   has_text_layer=page.has_text_layer, text=page.text)


@router.post("/{case_id}/documents/{document_id}/extract", response_model=ExtractionOut)
def extract(case_id: uuid.UUID, document_id: uuid.UUID, session: SessionDep, storage: StorageDep,
            client: LLMDep) -> ExtractionOut:
    document = session.get(Document, document_id)
    if document is None or document.case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    case = _get_case(session, case_id)
    try:
        result = extract_document(session, client, storage, document, EXTRACTION_FIELDS[case.domain],
                                  model=settings.llm_model, max_tokens=settings.llm_max_tokens, effort=settings.llm_effort)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    session.commit()
    assert result.call is not None
    return ExtractionOut(
        document_id=document.id,
        model=result.call.model,
        cost_usd=format(result.call.cost_usd, "f") if result.call.cost_usd is not None else None,
        accepted=[FactOut(field=f.candidate.field, value=f.value, unit=f.unit, instance=f.candidate.instance,
                          page_no=f.candidate.page, quote=f.candidate.quote, verification=f.verification.value)
                  for f in result.accepted],
        rejected=[RejectedFactOut(field=r.candidate.field, page=r.candidate.page, quote=r.candidate.quote,
                                  value_as_written=r.candidate.value_as_written, unit_as_written=r.candidate.unit_as_written,
                                  reason=r.reason.value, detail=r.detail)
                  for r in result.rejected],
    )
