"""Add extracted facts columns to analyses, remove risk_score.

Replaces AI scoring with factual extraction:
- extracted_facts: JSON blob with employment, skills, certs, education
- extraction_version: Schema version for compatibility
- extraction_notes: Flags for manual review

Removes risk_score as AI no longer scores candidates.

Part of Human-in-the-Loop pipeline redesign.

Revision ID: 00010
Revises: 00009
Create Date: 2024-12-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00010"
down_revision = "00009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add extracted facts columns, remove risk_score."""
    # Add new fact extraction columns
    op.add_column(
        "analyses",
        sa.Column("extracted_facts", sa.NVARCHAR(None), nullable=True),  # JSON blob
    )
    op.add_column(
        "analyses",
        sa.Column("extraction_version", sa.String(20), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("extraction_notes", sa.NVARCHAR(500), nullable=True),
    )

    # Drop risk_score constraint first, then column
    # Note: SQL Server requires dropping constraint before column
    op.drop_constraint("CK_analyses_risk_score", "analyses", type_="check")
    op.drop_column("analyses", "risk_score")


def downgrade() -> None:
    """Restore risk_score, remove extracted facts columns."""
    # Restore risk_score column
    op.add_column(
        "analyses",
        sa.Column("risk_score", sa.Integer(), nullable=True),
    )
    # Restore check constraint
    op.create_check_constraint(
        "CK_analyses_risk_score",
        "analyses",
        "risk_score >= 0 AND risk_score <= 100",
    )

    # Remove extracted facts columns
    op.drop_column("analyses", "extraction_notes")
    op.drop_column("analyses", "extraction_version")
    op.drop_column("analyses", "extracted_facts")
