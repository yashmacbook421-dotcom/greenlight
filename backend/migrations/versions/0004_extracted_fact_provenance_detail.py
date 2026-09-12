"""extracted fact provenance detail

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-12 14:39:38.250424
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('extracted_facts', sa.Column('value_as_written', sa.Text(), nullable=True))
    op.add_column('extracted_facts', sa.Column('unit_as_written', sa.String(length=32), nullable=True))
    op.add_column('extracted_facts', sa.Column('instance', sa.String(length=64), nullable=True))
    op.add_column('extracted_facts', sa.Column('verification', sa.String(length=32), server_default='text_match', nullable=False))
    op.add_column('extracted_facts', sa.Column('extracted_by', sa.String(length=64), nullable=True))

    op.create_check_constraint(op.f('ck_extracted_facts_verification_valid'), 'extracted_facts',
                               "verification IN ('text_match', 'image_unverified', 'oracle')")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_extracted_facts_verification_valid'), 'extracted_facts', type_='check')
    op.drop_column('extracted_facts', 'extracted_by')
    op.drop_column('extracted_facts', 'verification')
    op.drop_column('extracted_facts', 'instance')
    op.drop_column('extracted_facts', 'unit_as_written')
    op.drop_column('extracted_facts', 'value_as_written')
