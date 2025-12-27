"""Add raw_resume_text column to analyses table.

Caches extracted resume text to avoid re-parsing on retry.
When extract_facts fails after text extraction, the cached text
can be reused on retry instead of re-downloading and re-parsing.

Revision ID: 00022
Revises: 00021
Create Date: 2024-12-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "00022"
down_revision = "00021"
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
    """Add raw_resume_text column to analyses table."""
    if not column_exists("analyses", "raw_resume_text"):
        op.add_column(
            "analyses",
            sa.Column("raw_resume_text", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    """Remove raw_resume_text column from analyses table."""
    if column_exists("analyses", "raw_resume_text"):
        op.drop_column("analyses", "raw_resume_text")
