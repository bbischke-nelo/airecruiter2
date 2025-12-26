"""Add application metadata and candidate profiles.

Adds to applications:
- phone_number: Candidate phone from Workday
- application_source: Where candidate applied from
- applied_at: Actual Workday application date
- candidate_profile_id: FK to candidate_profiles

Creates candidate_profiles table:
- Stores rich candidate data (work history, education, skills)
- Reusable across multiple applications from same candidate
- Linked by external_candidate_id from Workday

Revision ID: 00016
Revises: 00015
Create Date: 2024-12-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00016"
down_revision = "00015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add application metadata and create candidate_profiles table."""

    # Create candidate_profiles table
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("external_candidate_id", sa.String(255), unique=True, nullable=False),
        sa.Column("candidate_wid", sa.String(100), nullable=True),

        # Contact info
        sa.Column("primary_email", sa.String(255), nullable=True),
        sa.Column("secondary_email", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(50), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(50), nullable=True),

        # Background data (JSON)
        sa.Column("work_history", sa.Text, nullable=True),
        sa.Column("education", sa.Text, nullable=True),
        sa.Column("skills", sa.Text, nullable=True),

        # Metadata
        sa.Column("last_synced_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Add index for faster lookups
    op.create_index(
        "ix_candidate_profiles_external_candidate_id",
        "candidate_profiles",
        ["external_candidate_id"],
    )

    # Add columns to applications table
    op.add_column(
        "applications",
        sa.Column("phone_number", sa.String(50), nullable=True),
    )

    op.add_column(
        "applications",
        sa.Column("application_source", sa.String(100), nullable=True),
    )

    op.add_column(
        "applications",
        sa.Column("applied_at", sa.DateTime, nullable=True),
    )

    op.add_column(
        "applications",
        sa.Column("candidate_profile_id", sa.Integer, nullable=True),
    )

    # Add foreign key constraint
    op.execute("""
        ALTER TABLE applications
        ADD CONSTRAINT fk_applications_candidate_profile
        FOREIGN KEY (candidate_profile_id) REFERENCES candidate_profiles(id)
        ON DELETE SET NULL
    """)


def downgrade() -> None:
    """Remove application metadata and candidate_profiles table."""

    # Drop foreign key constraint first
    op.execute("""
        ALTER TABLE applications
        DROP CONSTRAINT IF EXISTS fk_applications_candidate_profile
    """)

    # Drop columns from applications
    op.drop_column("applications", "candidate_profile_id")
    op.drop_column("applications", "applied_at")
    op.drop_column("applications", "application_source")
    op.drop_column("applications", "phone_number")

    # Drop index
    op.drop_index("ix_candidate_profiles_external_candidate_id", "candidate_profiles")

    # Drop candidate_profiles table
    op.drop_table("candidate_profiles")
