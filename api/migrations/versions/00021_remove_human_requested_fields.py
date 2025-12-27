"""Remove human_requested fields.

The "Request Human" functionality has been removed from the interview
flow - candidates can contact recruiters directly if needed.

Revision ID: 00021
Revises: 00020
Create Date: 2024-12-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "00021"
down_revision = "00020"
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
    """Remove human_requested fields from interviews and applications."""
    # Remove from interviews table
    if column_exists("interviews", "human_requested"):
        op.drop_column("interviews", "human_requested")
    if column_exists("interviews", "human_requested_at"):
        op.drop_column("interviews", "human_requested_at")

    # Remove from applications table
    if column_exists("applications", "human_requested"):
        op.drop_column("applications", "human_requested")


def downgrade() -> None:
    """Restore human_requested fields."""
    # Restore to applications table
    if not column_exists("applications", "human_requested"):
        op.add_column("applications", sa.Column("human_requested", sa.Boolean(), nullable=True, server_default="0"))

    # Restore to interviews table
    if not column_exists("interviews", "human_requested_at"):
        op.add_column("interviews", sa.Column("human_requested_at", sa.DateTime(), nullable=True))
    if not column_exists("interviews", "human_requested"):
        op.add_column("interviews", sa.Column("human_requested", sa.Boolean(), nullable=True, server_default="0"))
