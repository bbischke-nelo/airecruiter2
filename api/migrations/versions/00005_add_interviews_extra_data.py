"""Add extra_data column to interviews table.

Revision ID: 00005
Revises: 00004
Create Date: 2025-12-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "00005"
down_revision = "00004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("extra_data", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("interviews", "extra_data")
