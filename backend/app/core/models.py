"""Core tables shared by every review domain.

Invariants from ARCHITECTURE.md are enforced here as database constraints,
not left to application code:

- an extracted fact without document/page/quote provenance cannot be stored
- a PASS/FAIL rule result must carry a citation; a FAIL must be classified
- an INCONCLUSIVE rule result must say why
- a proposal can only be created as `pending_review`, and only a named
  reviewer can move it out of that state (see the trigger in migration 0001)
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _in(column: str, enum_cls: type[enum.StrEnum]) -> str:
    values = ", ".join(f"'{member.value}'" for member in enum_cls)
    return f"{column} IN ({values})"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CaseStatus(enum.StrEnum):
    RECEIVED = "received"
    EXTRACTING = "extracting"
    RECONCILING = "reconciling"
    SCREENING = "screening"
    AGENT_REVIEW = "agent_review"
    PENDING_REVIEW = "pending_review"
    CLOSED = "closed"


class RuleStatus(enum.StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # excluded by the rule's own applicability note
    SKIPPED = "SKIPPED"  # routed around by an earlier rule


class AgentTermination(enum.StrEnum):
    PROPOSAL = "proposal"
    STEP_BUDGET = "step_budget"
    COST_CEILING = "cost_ceiling"
    ERROR = "error"


class AgentRole(enum.StrEnum):
    ASSISTANT = "assistant"
    TOOL = "tool"


class ProposalStatus(enum.StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"


class Case(Base):
    """One submission under review: an interconnection application, later an expense claim."""

    __tablename__ = "cases"
    __table_args__ = (CheckConstraint(_in("status", CaseStatus), name="status_valid"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=CaseStatus.RECEIVED.value)
    submitter: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = _created_at()

    documents: Mapped[list["Document"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("case_id", "sha256"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint("page_count >= 0", name="page_count_nonneg"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    case: Mapped[Case] = relationship(back_populates="documents")
    pages: Mapped[list["Page"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Page.page_no"
    )

    def anchor(self, page_no: int) -> str:
        """Citation anchor that survives re-ingestion: tied to file content, not database ids."""
        return f"{self.sha256[:12]}#p{page_no}"


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_no"),
        CheckConstraint("page_no >= 1", name="page_no_positive"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # False for scanned/image-only pages: extraction must read them as images, not text.
    has_text_layer: Mapped[bool] = mapped_column(nullable=False)

    document: Mapped[Document] = relationship(back_populates="pages")


class ExtractedFact(Base):
    """A typed fact pulled from a document. No provenance, no row.

    The composite foreign key means the cited page must actually exist. Whether
    the quote appears on that page is checked in extraction code, because OCR
    whitespace makes an exact database-level match too brittle.
    """

    __tablename__ = "extracted_facts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "page_no"],
            ["pages.document_id", "pages.page_no"],
            ondelete="CASCADE",
        ),
        CheckConstraint("length(btrim(quote)) > 0", name="quote_nonempty"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence_unit"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    extracted_at: Mapped[datetime] = _created_at()


class Discrepancy(Base):
    """Detected by code; `material` stays NULL until the LLM judges it, and a judgment needs a rationale."""

    __tablename__ = "discrepancies"
    __table_args__ = (
        CheckConstraint("material IS NULL OR rationale IS NOT NULL", name="judgment_has_rationale"),
        CheckConstraint("jsonb_typeof(observed) = 'array'", name="observed_is_array"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    # [{"value": ..., "fact_id": ...}, ...] — or a single entry with a null value for a missing field
    observed: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    material: Mapped[bool | None] = mapped_column()
    rationale: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = _created_at()
    judged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RuleResult(Base):
    """Output of the deterministic rule engine (the Rule 21 screens, for interconnection).

    `input_hash` + `engine_version` exist for the determinism test: the same
    inputs through the same engine must yield a byte-identical result.
    """

    __tablename__ = "rule_results"
    __table_args__ = (
        CheckConstraint(_in("status", RuleStatus), name="status_valid"),
        CheckConstraint("status = 'INCONCLUSIVE' OR citation IS NOT NULL", name="decided_result_cited"),
        CheckConstraint("status <> 'FAIL' OR classification IS NOT NULL", name="fail_classified"),
        CheckConstraint("status <> 'INCONCLUSIVE' OR reason IS NOT NULL", name="inconclusive_has_reason"),
        CheckConstraint("status <> 'INCONCLUSIVE' OR blocker IS NOT NULL", name="inconclusive_has_blocker"),
        CheckConstraint("status <> 'SKIPPED' OR routed_by IS NOT NULL", name="skipped_has_router"),
        CheckConstraint("citation IS NULL OR jsonb_typeof(citation) = 'array'", name="citation_is_array"),
        CheckConstraint("input_hash ~ '^[0-9a-f]{64}$'", name="input_hash_hex"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_set: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    formula: Mapped[str | None] = mapped_column(Text)
    computed: Mapped[Decimal | None] = mapped_column(Numeric)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric)
    # [{"ruleset": ..., "section": ..., "sheet": ..., "quote": ...}, ...]
    citation: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    classification: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    # Who must act to resolve an INCONCLUSIVE result; values are defined by the domain.
    blocker: Mapped[str | None] = mapped_column(String(32))
    routed_by: Mapped[str | None] = mapped_column(String(32))
    missing_inputs: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    synthetic_inputs: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    overrides: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    run_at: Mapped[datetime] = _created_at()


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint("step_budget > 0", name="step_budget_positive"),
        CheckConstraint("steps_used >= 0 AND steps_used <= step_budget", name="steps_within_budget"),
        CheckConstraint("cost_ceiling_usd > 0", name="cost_ceiling_positive"),
        CheckConstraint(f"terminated_by IS NULL OR {_in('terminated_by', AgentTermination)}", name="terminated_by_valid"),
        CheckConstraint("(terminated_by IS NULL) = (ended_at IS NULL)", name="termination_recorded"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    step_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    steps_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_ceiling_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
    terminated_by: Mapped[str | None] = mapped_column(String(16))
    started_at: Mapped[datetime] = _created_at()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list["AgentStep"]] = relationship(back_populates="run", order_by="AgentStep.n")


class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "n"),
        CheckConstraint(_in("role", AgentRole), name="role_valid"),
        CheckConstraint("role <> 'tool' OR tool IS NOT NULL", name="tool_step_names_tool"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    tool: Mapped[str | None] = mapped_column(String(64))
    args: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    result: Mapped[Any | None] = mapped_column(JSONB)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created_at()

    run: Mapped[AgentRun] = relationship(back_populates="steps")


class Proposal(Base):
    """The agent's terminal output. The human gate lives in this table.

    There is no `sent` status. A later outbound step may only pick up
    proposals a named reviewer moved to `approved` or `edited`.
    """

    __tablename__ = "proposals"
    __table_args__ = (
        CheckConstraint(_in("status", ProposalStatus), name="status_valid"),
        CheckConstraint(
            "(status = 'pending_review') = (reviewed_by IS NULL AND reviewed_at IS NULL)",
            name="reviewer_iff_reviewed",
        ),
        CheckConstraint("reviewed_by IS NULL OR length(btrim(reviewed_by)) > 0", name="reviewer_named"),
        CheckConstraint("jsonb_typeof(items) = 'array'", name="items_is_array"),
        CheckConstraint("jsonb_typeof(guardrail_verdicts) = 'array'", name="guardrail_verdicts_is_array"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"))
    disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    # Set when the disposition veto overrode the model: what the model originally proposed.
    model_disposition: Mapped[str | None] = mapped_column(String(32))
    letter_md: Mapped[str] = mapped_column(Text, nullable=False)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    guardrail_verdicts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=ProposalStatus.PENDING_REVIEW.value)
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
