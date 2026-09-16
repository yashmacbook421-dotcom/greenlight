"""applicant notifications and a contact email

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-15 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('interconnection_applications', sa.Column('contact_email', sa.Text(), nullable=True))
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('channel', sa.String(length=16), nullable=False),
    sa.Column('recipient', sa.Text(), nullable=True),
    sa.Column('subject', sa.Text(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('queued', 'sent', 'failed', 'no_recipient')", name=op.f('ck_notifications_status_valid')),
    sa.CheckConstraint("(status = 'no_recipient') = (recipient IS NULL)", name=op.f('ck_notifications_recipient_iff_addressed')),
    sa.CheckConstraint("(status = 'sent') = (sent_at IS NOT NULL)", name=op.f('ck_notifications_sent_at_iff_sent')),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], name=op.f('fk_notifications_case_id_cases'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    op.create_index(op.f('ix_notifications_case_id'), 'notifications', ['case_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_case_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_column('interconnection_applications', 'contact_email')
