"""Add requisition_id and payload columns to jobs table.

Revision ID: 00004
Revises: 00003
Create Date: 2024-12-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '00004'
down_revision = '00003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add requisition_id and payload columns to jobs table."""
    # Add requisition_id column
    op.add_column(
        'jobs',
        sa.Column('requisition_id', sa.Integer(), nullable=True)
    )

    # Add payload column
    op.add_column(
        'jobs',
        sa.Column('payload', sa.Text(), nullable=True)
    )

    # Make application_id nullable (it was NOT NULL before)
    op.alter_column(
        'jobs',
        'application_id',
        existing_type=sa.Integer(),
        nullable=True
    )

    # Add foreign key for requisition_id
    op.create_foreign_key(
        'fk_jobs_requisition_id',
        'jobs',
        'requisitions',
        ['requisition_id'],
        ['id']
    )

    # Add index for requisition_id
    op.create_index('idx_jobs_requisition', 'jobs', ['requisition_id'])


def downgrade() -> None:
    """Remove requisition_id and payload columns from jobs table."""
    op.drop_index('idx_jobs_requisition', 'jobs')
    op.drop_constraint('fk_jobs_requisition_id', 'jobs', type_='foreignkey')
    op.alter_column(
        'jobs',
        'application_id',
        existing_type=sa.Integer(),
        nullable=False
    )
    op.drop_column('jobs', 'payload')
    op.drop_column('jobs', 'requisition_id')
