"""circuit model attributes

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-12 14:52:55.260858
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f('ck_circuit_models_synthetic_fields_known'), 'circuit_models', type_='check')
    op.add_column('circuit_models', sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.drop_column('circuit_models', 'line_section_peak_kw')
    op.drop_column('circuit_models', 'max_fault_current_a')
    op.drop_column('circuit_models', 'existing_der_kw')
    op.drop_column('circuit_models', 'transmission_construction_required')
    op.drop_column('circuit_models', 'device_interrupting_rating_a')
    op.drop_column('circuit_models', 'primary_line_type')
    op.drop_column('circuit_models', 'service_transformer_kva')
    op.drop_column('circuit_models', 'substation_aggregate_der_kw')


def downgrade() -> None:
    op.add_column('circuit_models', sa.Column('substation_aggregate_der_kw', sa.NUMERIC(), autoincrement=False, nullable=True))
    op.add_column('circuit_models', sa.Column('service_transformer_kva', sa.NUMERIC(), autoincrement=False, nullable=True))
    op.add_column('circuit_models', sa.Column('primary_line_type', sa.VARCHAR(length=32), autoincrement=False, nullable=True))
    op.add_column('circuit_models', sa.Column('device_interrupting_rating_a', sa.NUMERIC(), autoincrement=False, nullable=True))
    op.add_column('circuit_models', sa.Column('transmission_construction_required', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.add_column('circuit_models', sa.Column('existing_der_kw', sa.NUMERIC(), autoincrement=False, nullable=True))
    op.add_column('circuit_models', sa.Column('max_fault_current_a', sa.NUMERIC(), autoincrement=False, nullable=True))
    op.add_column('circuit_models', sa.Column('line_section_peak_kw', sa.NUMERIC(), autoincrement=False, nullable=True))
    op.drop_column('circuit_models', 'attributes')
    op.create_check_constraint(
        op.f('ck_circuit_models_synthetic_fields_known'), 'circuit_models',
        "synthetic_fields <@ ARRAY['line_section_peak_kw', 'existing_der_kw', 'service_transformer_kva', "
        "'max_fault_current_a', 'device_interrupting_rating_a', 'primary_line_type', 'substation_aggregate_der_kw', "
        "'transmission_construction_required']::text[]")
