"""rule result states blocker routing

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12 14:30:24.583614
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Alembic autogenerate does not detect CHECK constraint changes; these are hand-written.
    op.add_column('rule_results', sa.Column('blocker', sa.String(length=32), nullable=True))
    op.add_column('rule_results', sa.Column('routed_by', sa.String(length=32), nullable=True))
    op.execute("UPDATE rule_results SET blocker = 'unknown' WHERE status = 'INCONCLUSIVE' AND blocker IS NULL")
    op.execute("""
        UPDATE rule_results SET citation = jsonb_build_array(citation)
        WHERE citation IS NOT NULL AND jsonb_typeof(citation) <> 'array'
    """)

    op.drop_constraint(op.f('ck_rule_results_status_valid'), 'rule_results', type_='check')
    op.create_check_constraint(
        op.f('ck_rule_results_status_valid'), 'rule_results',
        "status IN ('PASS', 'FAIL', 'INCONCLUSIVE', 'NOT_APPLICABLE', 'SKIPPED')")
    op.create_check_constraint(
        op.f('ck_rule_results_inconclusive_has_blocker'), 'rule_results', "status <> 'INCONCLUSIVE' OR blocker IS NOT NULL")
    op.create_check_constraint(
        op.f('ck_rule_results_skipped_has_router'), 'rule_results', "status <> 'SKIPPED' OR routed_by IS NOT NULL")
    op.create_check_constraint(
        op.f('ck_rule_results_citation_is_array'), 'rule_results', "citation IS NULL OR jsonb_typeof(citation) = 'array'")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_rule_results_citation_is_array'), 'rule_results', type_='check')
    op.drop_constraint(op.f('ck_rule_results_skipped_has_router'), 'rule_results', type_='check')
    op.drop_constraint(op.f('ck_rule_results_inconclusive_has_blocker'), 'rule_results', type_='check')
    op.drop_constraint(op.f('ck_rule_results_status_valid'), 'rule_results', type_='check')
    op.execute("DELETE FROM rule_results WHERE status IN ('NOT_APPLICABLE', 'SKIPPED')")
    op.create_check_constraint(
        op.f('ck_rule_results_status_valid'), 'rule_results', "status IN ('PASS', 'FAIL', 'INCONCLUSIVE')")
    op.drop_column('rule_results', 'routed_by')
    op.drop_column('rule_results', 'blocker')
