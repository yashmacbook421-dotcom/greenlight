import uuid
from datetime import date
from typing import Any

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CircuitModel(Base):
    """What the utility knows about one line section, stored as screen-engine Circuit attributes.

    `attributes` keys are Circuit field names (validated in circuits.py). Anything
    not taken from a published utility dataset is listed in `synthetic_fields`
    and carried onto every screen result that uses it.
    """

    __tablename__ = "circuit_models"
    __table_args__ = (UniqueConstraint("utility", "feeder_id", "line_section_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    utility: Mapped[str] = mapped_column(String(64), nullable=False)
    feeder_id: Mapped[str] = mapped_column(String(64), nullable=False)
    line_section_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_as_of: Mapped[date | None] = mapped_column(Date)
    synthetic_fields: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")


class InterconnectionApplication(Base):
    """Domain extension of a core `cases` row (1:1)."""

    __tablename__ = "interconnection_applications"

    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    utility: Mapped[str] = mapped_column(String(64), nullable=False)
    applicant_name: Mapped[str | None] = mapped_column(Text)
    site_address: Mapped[str | None] = mapped_column(Text)
    # Resolved by the utility from the site, not asserted by the applicant; NULL until resolved.
    circuit_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("circuit_models.id"))
