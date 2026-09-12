import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PageSummary(BaseModel):
    page_no: int
    anchor: str
    has_text_layer: bool
    char_count: int


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    filename: str
    sha256: str
    page_count: int
    created_at: datetime
    pages: list[PageSummary]


class PageOut(BaseModel):
    document_id: uuid.UUID
    page_no: int
    anchor: str
    has_text_layer: bool
    text: str


class CaseOut(BaseModel):
    id: uuid.UUID
    domain: str
    status: str
    submitter: str | None
    received_at: datetime
    documents: list[DocumentOut]
