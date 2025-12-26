"""Enhance global_settings table with type and category.

Adds:
- value_type: Data type (string, int, bool, json)
- category: Setting category (pipeline, interview, compliance, email)

Part of Human-in-the-Loop pipeline redesign.

Revision ID: 00013
Revises: 00012
Create Date: 2024-12-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00013"
down_revision = "00012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add type and category columns to settings table."""
    op.add_column(
        "settings",
        sa.Column("value_type", sa.String(20), nullable=False, server_default="string"),
    )
    op.add_column(
        "settings",
        sa.Column("category", sa.String(50), nullable=True),
    )

    # Insert default pipeline settings if they don't exist
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'interview_enabled')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('interview_enabled', 'false', 'bool', 'pipeline', 'Enable AI interview by default');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'interview_expiry_days')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('interview_expiry_days', '7', 'int', 'pipeline', 'Days before interview invitation expires');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'auto_update_stage')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('auto_update_stage', 'false', 'bool', 'pipeline', 'Update Workday stage when advanced');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'blind_hiring_enabled')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('blind_hiring_enabled', 'false', 'bool', 'compliance', 'Redact PII from AI summaries');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'retention_threshold_entry')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('retention_threshold_entry', '6', 'int', 'compliance', 'Entry-level avg tenure threshold (months)');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'retention_threshold_ic')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('retention_threshold_ic', '9', 'int', 'compliance', 'IC avg tenure threshold (months)');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'retention_threshold_manager')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('retention_threshold_manager', '12', 'int', 'compliance', 'Manager avg tenure threshold (months)');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'retention_threshold_director')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('retention_threshold_director', '18', 'int', 'compliance', 'Director+ avg tenure threshold (months)');
    """)


def downgrade() -> None:
    """Remove type and category columns from settings table."""
    # Remove the settings we added
    op.execute("""
        DELETE FROM settings WHERE [key] IN (
            'interview_enabled', 'interview_expiry_days', 'auto_update_stage',
            'blind_hiring_enabled', 'retention_threshold_entry', 'retention_threshold_ic',
            'retention_threshold_manager', 'retention_threshold_director'
        );
    """)

    op.drop_column("settings", "category")
    op.drop_column("settings", "value_type")
