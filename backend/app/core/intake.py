"""Stage 0 — intake. Deterministic: PDF bytes in, hashed and page-indexed text out.

No interpretation happens here. Pages keep the text exactly as the PDF's text
layer gives it; normalisation for quote matching belongs to extraction.
"""

import hashlib
import io
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.models import Document, ExtractedFact, Page
from app.core.storage import LocalStorage

log = logging.getLogger(__name__)


class IntakeError(ValueError):
    """The upload cannot be ingested; the message is safe to show the applicant."""


@dataclass(frozen=True)
class ParsedPage:
    page_no: int
    text: str
    has_text_layer: bool


def parse_pdf(data: bytes, max_pages: int) -> list[ParsedPage]:
    if not data.startswith(b"%PDF-"):
        raise IntakeError("file is not a PDF")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # Datasheets are often encrypted with an empty user password purely to
            # restrict editing. Those open fine; a real password requirement does not.
            if reader.decrypt("") == 0:
                raise IntakeError("PDF is password-protected")
        page_count = len(reader.pages)
    except PdfReadError as exc:
        raise IntakeError(f"PDF could not be read: {exc}") from exc

    if page_count == 0:
        raise IntakeError("PDF has no pages")
    if page_count > max_pages:
        raise IntakeError(f"PDF has {page_count} pages; the limit is {max_pages}")

    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # pypdf raises a wide range of errors on malformed content streams
            log.warning("text extraction failed on page %d; treating as image-only", i, exc_info=True)
            text = ""
        text = text.replace("\x00", "")  # Postgres text cannot hold NUL
        pages.append(ParsedPage(page_no=i, text=text, has_text_layer=bool(text.strip())))
    return pages


def ingest_document(
    session: Session,
    storage: LocalStorage,
    *,
    case_id: uuid.UUID,
    kind: str,
    filename: str,
    data: bytes,
    max_pages: int,
) -> tuple[Document, bool]:
    """Store and index one PDF. Returns (document, created).

    Re-uploading identical bytes to the same case returns the existing document.
    """
    sha256 = hashlib.sha256(data).hexdigest()
    existing = session.scalar(select(Document).where(Document.case_id == case_id, Document.sha256 == sha256))
    if existing is not None:
        return existing, False

    parsed = parse_pdf(data, max_pages)
    storage_uri = storage.put(sha256, data)

    document = Document(
        case_id=case_id,
        kind=kind,
        filename=filename,
        sha256=sha256,
        page_count=len(parsed),
        storage_uri=storage_uri,
        pages=[Page(page_no=p.page_no, text=p.text, has_text_layer=p.has_text_layer) for p in parsed],
    )
    session.add(document)
    session.flush()
    return document, True


def supersede_document(session: Session, document: Document) -> None:
    """Retire a document the applicant has replaced. The file and pages stay for the audit trail; its facts go,
    so the next review reads only the corrected version."""
    session.execute(delete(ExtractedFact).where(ExtractedFact.document_id == document.id))
    document.superseded_at = datetime.now(UTC)
    session.flush()
