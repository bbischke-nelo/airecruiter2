"""Fix settings key column name.

Rename 'key' column to 'setting_key' to avoid SQL Server reserved word issues.

Revision ID: 00007
"""

from alembic import op
import sqlalchemy as sa


revision = '00007'
down_revision = '00006'
branch_labels = None
depends_on = None


def upgrade():
    # Rename 'key' to 'setting_key' to avoid reserved word issues
    op.execute("EXEC sp_rename 'settings.[key]', 'setting_key', 'COLUMN'")


def downgrade():
    op.execute("EXEC sp_rename 'settings.setting_key', 'key', 'COLUMN'")
