"""Add v1 evaluation fields.

Adds character gate, retention risk, authenticity assessment,
build vs buy classification, and transcript storage from v1.

Revision ID: 00002
Revises: 00001
Create Date: 2024-12-24
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00002"
down_revision = "00001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add v1 evaluation fields to evaluations table."""
    # Add character_passed (BIT for SQL Server)
    op.add_column(
        "evaluations",
        sa.Column("character_passed", sa.Boolean(), nullable=True),
    )

    # Add retention_risk (LOW, MEDIUM, HIGH)
    op.add_column(
        "evaluations",
        sa.Column("retention_risk", sa.String(20), nullable=True),
    )

    # Add authenticity_assessment (PASS, FAIL, REVIEW)
    op.add_column(
        "evaluations",
        sa.Column("authenticity_assessment", sa.String(20), nullable=True),
    )

    # Add readiness (READY, NEEDS SUPPORT, NEEDS DEVELOPMENT)
    op.add_column(
        "evaluations",
        sa.Column("readiness", sa.String(50), nullable=True),
    )

    # Add transcript storage
    op.add_column(
        "evaluations",
        sa.Column("transcript", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove v1 evaluation fields from evaluations table."""
    op.drop_column("evaluations", "transcript")
    op.drop_column("evaluations", "readiness")
    op.drop_column("evaluations", "authenticity_assessment")
    op.drop_column("evaluations", "retention_risk")
    op.drop_column("evaluations", "character_passed")
