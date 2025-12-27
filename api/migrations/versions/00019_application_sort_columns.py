"""Add sortable columns to applications table.

Denormalizes key metrics from extracted_facts (Analysis table) into
the applications table for efficient server-side sorting:
- jd_match_percentage: JD requirements match %
- total_experience_months: Total career experience
- avg_tenure_months: Average tenure (recent 5 years)
- current_title: Most recent job title
- current_employer: Most recent employer

These are populated by the extract_facts processor after analysis.

Revision ID: 00019
Revises: 00018
Create Date: 2024-12-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00019"
down_revision = "00018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add sortable columns to applications table."""

    # JD match percentage (0-100)
    op.add_column(
        "applications",
        sa.Column("jd_match_percentage", sa.Integer, nullable=True),
    )

    # Total experience in months
    op.add_column(
        "applications",
        sa.Column("total_experience_months", sa.Integer, nullable=True),
    )

    # Average tenure in months (recent 5 years)
    op.add_column(
        "applications",
        sa.Column("avg_tenure_months", sa.Float, nullable=True),
    )

    # Current/most recent title
    op.add_column(
        "applications",
        sa.Column("current_title", sa.String(200), nullable=True),
    )

    # Current/most recent employer
    op.add_column(
        "applications",
        sa.Column("current_employer", sa.String(200), nullable=True),
    )

    # Months since last employment (for gap detection)
    op.add_column(
        "applications",
        sa.Column("months_since_last_employment", sa.Integer, nullable=True),
    )

    # Add indexes for efficient sorting
    op.create_index(
        "ix_applications_jd_match_percentage",
        "applications",
        ["jd_match_percentage"],
    )
    op.create_index(
        "ix_applications_total_experience_months",
        "applications",
        ["total_experience_months"],
    )
    op.create_index(
        "ix_applications_avg_tenure_months",
        "applications",
        ["avg_tenure_months"],
    )


def downgrade() -> None:
    """Remove sortable columns from applications table."""

    op.drop_index("ix_applications_avg_tenure_months", "applications")
    op.drop_index("ix_applications_total_experience_months", "applications")
    op.drop_index("ix_applications_jd_match_percentage", "applications")

    op.drop_column("applications", "months_since_last_employment")
    op.drop_column("applications", "current_employer")
    op.drop_column("applications", "current_title")
    op.drop_column("applications", "avg_tenure_months")
    op.drop_column("applications", "total_experience_months")
    op.drop_column("applications", "jd_match_percentage")
