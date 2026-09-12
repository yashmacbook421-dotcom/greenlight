import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select

from app.config import settings
from app.core.intake import IntakeError, ingest_document
from app.core.models import Case, Document, Page
from app.core.schemas import CaseOut, DocumentOut, PageOut, PageSummary
from app.deps import SessionDep, StorageDep
from app.domains import DOCUMENT_KINDS

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
