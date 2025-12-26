"""Add decision tracking columns to applications.

Adds columns for tracking human recruiter decisions:
- rejection_reason_code, rejection_comment, rejected_by, rejected_at
- advanced_by, advanced_at

Part of Human-in-the-Loop pipeline redesign.

Revision ID: 00008
Revises: 00007
Create Date: 2024-12-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00008"
down_revision = "00007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add decision tracking columns to applications table."""
    # Rejection tracking
    op.add_column(
        "applications",
        sa.Column("rejection_reason_code", sa.String(50), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("rejection_comment", sa.NVARCHAR(1000), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("rejected_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
    )

    # Advance tracking
    op.add_column(
        "applications",
        sa.Column("advanced_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("advanced_at", sa.DateTime(), nullable=True),
    )

    # Foreign keys to recruiters table
    # Use NO ACTION to avoid SQL Server "multiple cascade paths" error
    # (applications table already has FK to recruiters)
    op.create_foreign_key(
        "fk_applications_rejected_by",
        "applications",
        "recruiters",
        ["rejected_by"],
        ["id"],
        ondelete="NO ACTION",
    )
    op.create_foreign_key(
        "fk_applications_advanced_by",
        "applications",
        "recruiters",
        ["advanced_by"],
        ["id"],
        ondelete="NO ACTION",
    )


def downgrade() -> None:
    """Remove decision tracking columns from applications table."""
    op.drop_constraint("fk_applications_advanced_by", "applications", type_="foreignkey")
    op.drop_constraint("fk_applications_rejected_by", "applications", type_="foreignkey")
    op.drop_column("applications", "advanced_at")
    op.drop_column("applications", "advanced_by")
    op.drop_column("applications", "rejected_at")
    op.drop_column("applications", "rejected_by")
    op.drop_column("applications", "rejection_comment")
    op.drop_column("applications", "rejection_reason_code")
