"""page text layer flag

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-12 13:21:02.306047
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Backfill existing rows from their text before enforcing NOT NULL.
    op.add_column('pages', sa.Column('has_text_layer', sa.Boolean(), nullable=True))
    op.execute("UPDATE pages SET has_text_layer = length(btrim(text)) > 0")
    op.alter_column('pages', 'has_text_layer', nullable=False)


def downgrade() -> None:
    op.drop_column('pages', 'has_text_layer')
