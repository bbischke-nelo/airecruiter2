"""Add global requisition default settings and make auto_send_interview nullable.

Changes:
- Makes requisitions.auto_send_interview nullable for 3-state logic
  (NULL = use global default, true = always send, false = never send)
- Adds global settings for requisition defaults:
  - auto_send_interview_default: Default behavior for auto-sending interviews
  - advance_stage_id: Workday stage ID for advancing candidates
  - reject_disposition_id: Workday disposition ID for rejecting candidates
  - default_recruiter_id: Default recruiter for new requisitions

Revision ID: 00017
Revises: 00016
Create Date: 2024-12-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00017"
down_revision = "00016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add global requisition defaults and make auto_send_interview nullable."""

    # Make auto_send_interview nullable on requisitions
    # In SQL Server, we need to drop default constraint first if any, then alter
    op.execute("""
        -- Drop any existing default constraint on auto_send_interview
        DECLARE @constraint_name NVARCHAR(255)
        SELECT @constraint_name = dc.name
        FROM sys.default_constraints dc
        JOIN sys.columns c ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
        WHERE OBJECT_NAME(dc.parent_object_id) = 'requisitions' AND c.name = 'auto_send_interview'

        IF @constraint_name IS NOT NULL
        BEGIN
            EXEC('ALTER TABLE requisitions DROP CONSTRAINT ' + @constraint_name)
        END
    """)

    # Alter column to be nullable (SQL Server doesn't change nullability with DROP DEFAULT)
    op.execute("""
        ALTER TABLE requisitions ALTER COLUMN auto_send_interview BIT NULL
    """)

    # Set existing false values to NULL (use global default)
    op.execute("""
        UPDATE requisitions SET auto_send_interview = NULL WHERE auto_send_interview = 0
    """)

    # Add new global settings for requisition defaults
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'auto_send_interview_default')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('auto_send_interview_default', 'false', 'bool', 'pipeline', 'Default: auto-send AI interviews after analysis');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'advance_stage_id')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('advance_stage_id', '', 'string', 'pipeline', 'Workday stage ID to move candidates to when advanced');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'reject_disposition_id')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('reject_disposition_id', '', 'string', 'pipeline', 'Workday disposition ID to use when rejecting candidates');
    """)

    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM settings WHERE [key] = 'default_recruiter_id')
        INSERT INTO settings ([key], value, value_type, category, description)
        VALUES ('default_recruiter_id', '', 'string', 'pipeline', 'Default recruiter ID for new requisitions');
    """)


def downgrade() -> None:
    """Remove global requisition defaults and make auto_send_interview non-nullable."""

    # Remove the settings we added
    op.execute("""
        DELETE FROM settings WHERE [key] IN (
            'auto_send_interview_default', 'advance_stage_id',
            'reject_disposition_id', 'default_recruiter_id'
        );
    """)

    # Set NULL values back to false
    op.execute("""
        UPDATE requisitions SET auto_send_interview = 0 WHERE auto_send_interview IS NULL
    """)

    # Make auto_send_interview non-nullable again
    op.execute("""
        ALTER TABLE requisitions ALTER COLUMN auto_send_interview BIT NOT NULL
    """)

    # Add default constraint
    op.execute("""
        ALTER TABLE requisitions ADD CONSTRAINT DF_requisitions_auto_send_interview DEFAULT 0 FOR auto_send_interview
    """)
