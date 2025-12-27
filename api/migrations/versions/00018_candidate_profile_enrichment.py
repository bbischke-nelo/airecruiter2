"""Add enrichment columns to candidate_profiles.

Adds columns for data extracted from resumes that are useful for
filtering and recruiter workflows:
- linkedin_url: Direct link for recruiter research
- certifications: JSON array of professional certifications
- licenses: JSON array of licenses (CDL, forklift, etc.)
- total_experience_months: Calculated total for filtering

Revision ID: 00018
Revises: 00017
Create Date: 2024-12-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00018"
down_revision = "00017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add enrichment columns to candidate_profiles."""

    # LinkedIn URL - for recruiter research
    op.add_column(
        "candidate_profiles",
        sa.Column("linkedin_url", sa.String(500), nullable=True),
    )

    # Certifications - JSON array of professional certifications
    # e.g., [{"name": "PMP", "issuer": "PMI", "expiration": "2025-12"}]
    op.add_column(
        "candidate_profiles",
        sa.Column("certifications", sa.Text, nullable=True),
    )

    # Licenses - JSON array of licenses (critical for CDL/logistics jobs)
    # e.g., [{"type": "CDL-A", "class": "A", "endorsements": ["Hazmat"], "state": "TX"}]
    op.add_column(
        "candidate_profiles",
        sa.Column("licenses", sa.Text, nullable=True),
    )

    # Total experience in months - enables filtering like "5+ years experience"
    op.add_column(
        "candidate_profiles",
        sa.Column("total_experience_months", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    """Remove enrichment columns from candidate_profiles."""

    op.drop_column("candidate_profiles", "total_experience_months")
    op.drop_column("candidate_profiles", "licenses")
    op.drop_column("candidate_profiles", "certifications")
    op.drop_column("candidate_profiles", "linkedin_url")
