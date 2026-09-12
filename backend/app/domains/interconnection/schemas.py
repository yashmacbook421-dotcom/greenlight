import uuid

from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    utility: str = Field(min_length=1, max_length=64)
    submitter: str | None = Field(default=None, description="Who filed it — usually the installer")
    applicant_name: str | None = None
    site_address: str | None = None


class ApplicationCreated(BaseModel):
    case_id: uuid.UUID
    status: str
