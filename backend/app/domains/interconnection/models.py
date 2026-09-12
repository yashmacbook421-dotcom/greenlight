import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


# Columns a circuit model may mark as synthesized; kept in sync with the check constraint below.
SYNTHESIZABLE_FIELDS = (
    "line_section_peak_kw",
    "existing_der_kw",
    "service_transformer_kva",
    "max_fault_current_a",
    "device_interrupting_rating_a",
    "primary_line_type",
    "substation_aggregate_der_kw",
    "transmission_construction_required",
)


class CircuitModel(Base):
    """One line section's grid data.

    Every screen input is nullable on purpose: a missing value makes the screen
    INCONCLUSIVE instead of letting it guess. Anything not taken from a
    published utility dataset is listed in `synthetic_fields`.
    """

    __tablename__ = "circuit_models"
    __table_args__ = (
        UniqueConstraint("utility", "feeder_id", "line_section_id"),
        CheckConstraint(
            "synthetic_fields <@ ARRAY[{}]::text[]".format(", ".join(f"'{f}'" for f in SYNTHESIZABLE_FIELDS)),
            name="synthetic_fields_known",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    utility: Mapped[str] = mapped_column(String(64), nullable=False)
    feeder_id: Mapped[str] = mapped_column(String(64), nullable=False)
    line_section_id: Mapped[str] = mapped_column(String(64), nullable=False)
    line_section_peak_kw: Mapped[Decimal | None] = mapped_column(Numeric)
    existing_der_kw: Mapped[Decimal | None] = mapped_column(Numeric)
    service_transformer_kva: Mapped[Decimal | None] = mapped_column(Numeric)
    max_fault_current_a: Mapped[Decimal | None] = mapped_column(Numeric)
    device_interrupting_rating_a: Mapped[Decimal | None] = mapped_column(Numeric)
    primary_line_type: Mapped[str | None] = mapped_column(String(32))
    substation_aggregate_der_kw: Mapped[Decimal | None] = mapped_column(Numeric)
    transmission_construction_required: Mapped[bool | None] = mapped_column()
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
