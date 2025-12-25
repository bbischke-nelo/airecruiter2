"""Fix settings key column name.

The initial migration incorrectly created the column as '[key]' (with literal brackets)
instead of properly quoting the reserved word 'key'. This migration renames it.

Revision ID: 00007
"""

from alembic import op
import sqlalchemy as sa


revision = '00007'
down_revision = '00006'
branch_labels = None
depends_on = None


def upgrade():
    # The column was created with literal brackets in the name: [key]
    # We need to rename it to setting_key
    # Use quoted identifier syntax for the column with brackets in its name
    op.execute("EXEC sp_rename 'settings.[[key]]', 'setting_key', 'COLUMN'")


def downgrade():
    op.execute("EXEC sp_rename 'settings.setting_key', '[[key]]', 'COLUMN'")
