"""discrepancy method

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-12 14:53:15.684460
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('discrepancies', sa.Column('method', sa.String(length=16), nullable=True))
    op.execute("UPDATE discrepancies SET material = NULL, rationale = NULL WHERE method IS NULL")
    op.create_check_constraint(op.f('ck_discrepancies_method_valid'), 'discrepancies',
                               "method IS NULL OR method IN ('rule_outcome', 'llm')")
    op.create_check_constraint(op.f('ck_discrepancies_judged_has_method'), 'discrepancies',
                               "(material IS NULL) = (method IS NULL)")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_discrepancies_judged_has_method'), 'discrepancies', type_='check')
    op.drop_constraint(op.f('ck_discrepancies_method_valid'), 'discrepancies', type_='check')
    op.drop_column('discrepancies', 'method')
