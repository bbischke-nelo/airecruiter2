"""Restore evaluation scoring columns.

Migration 00011 removed scoring columns for Human-in-the-Loop redesign,
but we still need AI-generated evaluations. This restores the scoring
columns and adds next_interview_focus which was missing.

Revision ID: 00020
Revises: 00019
Create Date: 2024-12-27
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00020"
down_revision = "00019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Restore evaluation scoring columns removed in 00011."""
    # Score columns (1-5 scale per v1 prompt)
    op.add_column("evaluations", sa.Column("reliability_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("accountability_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("professionalism_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("communication_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("technical_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("growth_potential_score", sa.Integer(), nullable=True))

    # Overall score (0-100 scale, computed from individual scores)
    op.add_column("evaluations", sa.Column("overall_score", sa.Float(), nullable=True))

    # Recommendation (recommend, review, do_not_recommend)
    op.add_column("evaluations", sa.Column("recommendation", sa.String(50), nullable=True))

    # Character assessment
    op.add_column("evaluations", sa.Column("character_passed", sa.Boolean(), nullable=True))
    op.add_column("evaluations", sa.Column("retention_risk", sa.String(20), nullable=True))
    op.add_column("evaluations", sa.Column("authenticity_assessment", sa.NVARCHAR(None), nullable=True))
    op.add_column("evaluations", sa.Column("readiness", sa.String(50), nullable=True))

    # Strengths, weaknesses, red flags (JSON arrays stored as text)
    op.add_column("evaluations", sa.Column("strengths", sa.NVARCHAR(None), nullable=True))
    op.add_column("evaluations", sa.Column("weaknesses", sa.NVARCHAR(None), nullable=True))
    op.add_column("evaluations", sa.Column("red_flags", sa.NVARCHAR(None), nullable=True))

    # Next interview focus (JSON array of questions for next interview)
    op.add_column("evaluations", sa.Column("next_interview_focus", sa.NVARCHAR(None), nullable=True))


def downgrade() -> None:
    """Remove evaluation scoring columns."""
    op.drop_column("evaluations", "next_interview_focus")
    op.drop_column("evaluations", "red_flags")
    op.drop_column("evaluations", "weaknesses")
    op.drop_column("evaluations", "strengths")
    op.drop_column("evaluations", "readiness")
    op.drop_column("evaluations", "authenticity_assessment")
    op.drop_column("evaluations", "retention_risk")
    op.drop_column("evaluations", "character_passed")
    op.drop_column("evaluations", "recommendation")
    op.drop_column("evaluations", "overall_score")
    op.drop_column("evaluations", "growth_potential_score")
    op.drop_column("evaluations", "technical_score")
    op.drop_column("evaluations", "communication_score")
    op.drop_column("evaluations", "professionalism_score")
    op.drop_column("evaluations", "accountability_score")
    op.drop_column("evaluations", "reliability_score")
