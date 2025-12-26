"""Add TMS sync tracking and rejection reasons table.

Adds:
- tms_sync_status, tms_sync_error, tms_sync_at to applications
- rejection_reasons table for recruiter dropdown
- TMS stage mapping settings
- Removes lookback_hours from requisitions

Part of Human-in-the-Loop pipeline redesign.

Revision ID: 00014
Revises: 00013
Create Date: 2024-12-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00014"
down_revision = "00013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add TMS sync tracking and configuration."""

    # Add TMS sync tracking columns to applications
    op.add_column(
        "applications",
        sa.Column("tms_sync_status", sa.String(20), nullable=False, server_default="synced"),
    )
    op.add_column(
        "applications",
        sa.Column("tms_sync_error", sa.String(500), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("tms_sync_at", sa.DateTime, nullable=True),
    )

    # Create rejection_reasons table
    op.execute("""
        CREATE TABLE rejection_reasons (
            id INT IDENTITY(1,1) PRIMARY KEY,
            code VARCHAR(50) NOT NULL UNIQUE,
            external_id VARCHAR(100) NOT NULL,
            name NVARCHAR(255) NOT NULL,
            requires_comment BIT NOT NULL DEFAULT 0,
            sort_order INT NOT NULL DEFAULT 0,
            is_active BIT NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT GETUTCDATE(),
            updated_at DATETIME NULL
        )
    """)

    # Seed default rejection reasons
    op.execute("""
        INSERT INTO rejection_reasons (code, external_id, name, sort_order) VALUES
        ('EXPERIENCE_SKILLS', 'Experience/Skills', 'Experience/Skills', 1),
        ('NOT_INTERESTED', 'Not Interested in Position', 'Not Interested in Position', 2),
        ('OFF_THE_MARKET', 'Off the Market', 'Off the Market', 3),
        ('DIDNT_MEET_GUIDELINES', 'Didn''t Meet Hiring Guidelines', 'Didn''t Meet Hiring Guidelines', 4),
        ('CANDIDATE_WITHDRAWN', 'Candidate Withdrawn', 'Candidate Withdrawn', 5),
        ('REQUISITION_CLOSED', 'Job Requisition Closed or Cancelled', 'Requisition Closed', 6),
        ('ANOTHER_CANDIDATE_HIRED', 'Another Candidate Hired', 'Another Candidate Hired', 7),
        ('NO_SHOW', 'No Show or Failed Road Test', 'No Show', 8)
    """)

    # Add TMS stage mapping settings
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'tms_status_ai_interview')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('tms_status_ai_interview', 'Screen', 'string', 'tms', 'TMS status when sending AI interview');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'tms_status_live_interview')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('tms_status_live_interview', 'Interview', 'string', 'tms', 'TMS status for live/manager interview');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'tms_status_advanced')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('tms_status_advanced', 'Offer', 'string', 'tms', 'TMS status when fully advanced');
    """)

    # Remove lookback_hours from requisitions
    op.drop_column("requisitions", "lookback_hours")


def downgrade() -> None:
    """Remove TMS sync tracking and configuration."""

    # Remove settings
    op.execute("""
        DELETE FROM settings WHERE [key] IN (
            'tms_status_ai_interview', 'tms_status_live_interview', 'tms_status_advanced'
        );
    """)

    # Drop table
    op.execute("DROP TABLE IF EXISTS rejection_reasons")

    # Remove columns from applications
    op.drop_column("applications", "tms_sync_at")
    op.drop_column("applications", "tms_sync_error")
    op.drop_column("applications", "tms_sync_status")

    # Re-add lookback_hours to requisitions
    op.add_column(
        "requisitions",
        sa.Column("lookback_hours", sa.Integer, nullable=True),
    )
