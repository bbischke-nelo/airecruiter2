"""Add version column to candidate_profiles for optimistic locking.

Prevents race conditions when multiple processors update the same
candidate profile concurrently. Updates must include version check
and increment version on success.

Revision ID: 00024
Revises: 00023
Create Date: 2024-12-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "00024"
down_revision = "00023"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    result = conn.execute(text("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = :table AND COLUMN_NAME = :column
    """), {"table": table_name, "column": column_name})
    return result.scalar() > 0


def upgrade() -> None:
    """Add version column for optimistic locking."""
    if not column_exists("candidate_profiles", "version"):
        op.add_column(
            "candidate_profiles",
            sa.Column("version", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    """Remove version column."""
    if column_exists("candidate_profiles", "version"):
        op.drop_column("candidate_profiles", "version")
