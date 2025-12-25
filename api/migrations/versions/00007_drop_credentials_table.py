"""Drop credentials table.

Workday credentials are now loaded from environment variables,
not stored in the database.

Revision ID: 00007
"""

from alembic import op


revision = '00007'
down_revision = '00006'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('credentials')


def downgrade():
    # Not restoring - credentials should be in env vars
    pass
