"""applicant portal: draft cases, superseded documents, case events

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-14 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_STATUSES = "'received', 'extracting', 'reconciling', 'screening', 'agent_review', 'pending_review', 'closed'"


def upgrade() -> None:
    op.drop_constraint(op.f('ck_cases_status_valid'), 'cases', type_='check')
    op.create_check_constraint(op.f('ck_cases_status_valid'), 'cases', f"status IN ('draft', {_OLD_STATUSES})")
    op.add_column('documents', sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('case_events',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('actor', sa.Text(), nullable=True),
    sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('created', 'document_added', 'document_replaced', 'submitted', 'resubmitted', "
                       "'review_failed')", name=op.f('ck_case_events_kind_valid')),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], name=op.f('fk_case_events_case_id_cases'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_case_events'))
    )
    op.create_index(op.f('ix_case_events_case_id'), 'case_events', ['case_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_case_events_case_id'), table_name='case_events')
    op.drop_table('case_events')
    op.drop_column('documents', 'superseded_at')
    op.execute("DELETE FROM cases WHERE status = 'draft'")
    op.drop_constraint(op.f('ck_cases_status_valid'), 'cases', type_='check')
    op.create_check_constraint(op.f('ck_cases_status_valid'), 'cases', f"status IN ({_OLD_STATUSES})")
