"""eval runs

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-13 00:21:02.747693
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('eval_runs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('domain', sa.String(length=64), nullable=False),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='running', nullable=False),
    sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('packets', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("mode IN ('oracle', 'live')", name=op.f('ck_eval_runs_mode_valid')),
    sa.CheckConstraint("status IN ('running', 'completed', 'stopped', 'failed')", name=op.f('ck_eval_runs_status_valid')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_eval_runs'))
    )


def downgrade() -> None:
    op.drop_table('eval_runs')
