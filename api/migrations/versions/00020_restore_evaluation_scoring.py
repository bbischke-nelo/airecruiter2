"""Restore evaluation scoring columns.

Migration 00011 removed scoring columns for Human-in-the-Loop redesign,
but we still need AI-generated evaluations. This restores the scoring
columns and adds next_interview_focus which was missing.

This migration is idempotent - it checks if columns exist before adding.

Revision ID: 00020
Revises: 00019
Create Date: 2024-12-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "00020"
down_revision = "00019"
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


def add_column_if_not_exists(table_name: str, column: sa.Column) -> None:
    """Add a column only if it doesn't already exist."""
    if not column_exists(table_name, column.name):
        op.add_column(table_name, column)


def upgrade() -> None:
    """Restore evaluation scoring columns removed in 00011."""
    # Score columns (1-5 scale per v1 prompt)
    add_column_if_not_exists("evaluations", sa.Column("reliability_score", sa.Integer(), nullable=True))
    add_column_if_not_exists("evaluations", sa.Column("accountability_score", sa.Integer(), nullable=True))
    add_column_if_not_exists("evaluations", sa.Column("professionalism_score", sa.Integer(), nullable=True))
    add_column_if_not_exists("evaluations", sa.Column("communication_score", sa.Integer(), nullable=True))
    add_column_if_not_exists("evaluations", sa.Column("technical_score", sa.Integer(), nullable=True))
    add_column_if_not_exists("evaluations", sa.Column("growth_potential_score", sa.Integer(), nullable=True))

    # Overall score (0-100 scale, computed from individual scores)
    add_column_if_not_exists("evaluations", sa.Column("overall_score", sa.Float(), nullable=True))

    # Recommendation (recommend, review, do_not_recommend)
    add_column_if_not_exists("evaluations", sa.Column("recommendation", sa.String(50), nullable=True))

    # Character assessment
    add_column_if_not_exists("evaluations", sa.Column("character_passed", sa.Boolean(), nullable=True))
    add_column_if_not_exists("evaluations", sa.Column("retention_risk", sa.String(20), nullable=True))
    add_column_if_not_exists("evaluations", sa.Column("authenticity_assessment", sa.NVARCHAR(None), nullable=True))
    add_column_if_not_exists("evaluations", sa.Column("readiness", sa.String(50), nullable=True))

    # Strengths, weaknesses, red flags (JSON arrays stored as text)
    add_column_if_not_exists("evaluations", sa.Column("strengths", sa.NVARCHAR(None), nullable=True))
    add_column_if_not_exists("evaluations", sa.Column("weaknesses", sa.NVARCHAR(None), nullable=True))
    add_column_if_not_exists("evaluations", sa.Column("red_flags", sa.NVARCHAR(None), nullable=True))

    # Next interview focus (JSON array of questions for next interview)
    add_column_if_not_exists("evaluations", sa.Column("next_interview_focus", sa.NVARCHAR(None), nullable=True))


def downgrade() -> None:
    """Remove evaluation scoring columns."""
    columns_to_drop = [
        "next_interview_focus", "red_flags", "weaknesses", "strengths",
        "readiness", "authenticity_assessment", "retention_risk", "character_passed",
        "recommendation", "overall_score", "growth_potential_score", "technical_score",
        "communication_score", "professionalism_score", "accountability_score", "reliability_score",
    ]
    for col in columns_to_drop:
        if column_exists("evaluations", col):
            op.drop_column("evaluations", col)
