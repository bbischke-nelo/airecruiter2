"""Remove scoring columns from evaluations.

Removes all AI scoring fields as human recruiters now make decisions.
Replaces strengths/weaknesses with interview_highlights for factual summary.

Part of Human-in-the-Loop pipeline redesign.

Revision ID: 00011
Revises: 00010
Create Date: 2024-12-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00011"
down_revision = "00010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove scoring columns, add interview_highlights."""
    # Add new factual summary column
    op.add_column(
        "evaluations",
        sa.Column("interview_highlights", sa.NVARCHAR(None), nullable=True),  # JSON
    )

    # Drop check constraints first (SQL Server requirement)
    # These constraints were created in 00001_initial_schema.py
    for col in ["reliability", "accountability", "professionalism", "communication", "technical", "growth_potential"]:
        try:
            op.drop_constraint(f"CK_evaluations_{col}", "evaluations", type_="check")
        except Exception:
            pass  # Constraint may not exist

    try:
        op.drop_constraint("CK_evaluations_overall", "evaluations", type_="check")
    except Exception:
        pass

    # Drop scoring columns
    scoring_columns = [
        "reliability_score",
        "accountability_score",
        "professionalism_score",
        "communication_score",
        "technical_score",
        "growth_potential_score",
        "overall_score",
        "recommendation",
        "character_passed",
        "retention_risk",
        "authenticity_assessment",
        "readiness",
        "strengths",
        "weaknesses",
        "red_flags",
    ]

    for col in scoring_columns:
        try:
            op.drop_column("evaluations", col)
        except Exception:
            pass  # Column may not exist


def downgrade() -> None:
    """Restore scoring columns, remove interview_highlights."""
    # Restore scoring columns (all nullable for safety)
    op.add_column("evaluations", sa.Column("reliability_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("accountability_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("professionalism_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("communication_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("technical_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("growth_potential_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("overall_score", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("recommendation", sa.String(50), nullable=True))
    op.add_column("evaluations", sa.Column("character_passed", sa.Boolean(), nullable=True))
    op.add_column("evaluations", sa.Column("retention_risk", sa.String(20), nullable=True))
    op.add_column("evaluations", sa.Column("authenticity_assessment", sa.String(20), nullable=True))
    op.add_column("evaluations", sa.Column("readiness", sa.String(50), nullable=True))
    op.add_column("evaluations", sa.Column("strengths", sa.Text(), nullable=True))
    op.add_column("evaluations", sa.Column("weaknesses", sa.Text(), nullable=True))
    op.add_column("evaluations", sa.Column("red_flags", sa.Text(), nullable=True))

    # Restore check constraints
    for col in ["reliability", "accountability", "professionalism", "communication", "technical", "growth_potential"]:
        op.create_check_constraint(
            f"CK_evaluations_{col}",
            "evaluations",
            f"{col}_score >= 0 AND {col}_score <= 10",
        )
    op.create_check_constraint(
        "CK_evaluations_overall",
        "evaluations",
        "overall_score >= 0 AND overall_score <= 100",
    )

    # Remove interview_highlights
    op.drop_column("evaluations", "interview_highlights")
