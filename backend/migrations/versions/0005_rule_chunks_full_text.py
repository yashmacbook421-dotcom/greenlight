"""rule chunks full text

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-12 14:44:45.516301
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('rule_chunks',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('ruleset', sa.String(length=64), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('sheet', sa.Integer(), nullable=False),
    sa.Column('section', sa.String(length=32), nullable=False),
    sa.Column('heading', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('search', postgresql.TSVECTOR(), sa.Computed("setweight(to_tsvector('english', section || ' ' || heading), 'A') || setweight(to_tsvector('english', text), 'B')", persisted=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rule_chunks')),
    sa.UniqueConstraint('ruleset', 'ordinal', name=op.f('uq_rule_chunks_ruleset_ordinal'))
    )
    op.create_index('ix_rule_chunks_ruleset_sheet', 'rule_chunks', ['ruleset', 'sheet'], unique=False)
    op.create_index('ix_rule_chunks_search', 'rule_chunks', ['search'], unique=False, postgresql_using='gin')


def downgrade() -> None:
    op.drop_index('ix_rule_chunks_search', table_name='rule_chunks', postgresql_using='gin')
    op.drop_index('ix_rule_chunks_ruleset_sheet', table_name='rule_chunks')
    op.drop_table('rule_chunks')
