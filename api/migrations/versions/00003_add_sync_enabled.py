"""Add sync_enabled column to requisitions table.

Revision ID: 00003
Revises: 00002
Create Date: 2024-12-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '00003'
down_revision = '00002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add sync_enabled column to requisitions table."""
    op.add_column(
        'requisitions',
        sa.Column('sync_enabled', sa.Boolean(), nullable=False, server_default='1')
    )


def downgrade() -> None:
    """Remove sync_enabled column from requisitions table."""
    op.drop_column('requisitions', 'sync_enabled')
