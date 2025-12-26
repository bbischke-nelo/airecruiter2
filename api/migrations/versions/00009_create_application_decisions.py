"""Create application_decisions table for audit trail.

Logs all human recruiter decisions (advance, reject, hold, unhold)
with full context for legal defensibility.

Part of Human-in-the-Loop pipeline redesign.

Revision ID: 00009
Revises: 00008
Create Date: 2024-12-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00009"
down_revision = "00008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create application_decisions table."""
    op.create_table(
        "application_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),  # advance, reject, hold, unhold
        sa.Column("from_status", sa.String(50), nullable=False),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column("reason_code", sa.String(50), nullable=True),  # Required for reject
        sa.Column("comment", sa.NVARCHAR(1000), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),  # Recruiter who made decision
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("GETUTCDATE()"), nullable=False),
    )

    # Indexes for efficient querying
    op.create_index("ix_application_decisions_application", "application_decisions", ["application_id"])
    op.create_index("ix_application_decisions_user", "application_decisions", ["user_id"])
    op.create_index("ix_application_decisions_reason", "application_decisions", ["reason_code"])
    op.create_index("ix_application_decisions_created", "application_decisions", ["created_at"])


def downgrade() -> None:
    """Drop application_decisions table."""
    op.drop_index("ix_application_decisions_created", table_name="application_decisions")
    op.drop_index("ix_application_decisions_reason", table_name="application_decisions")
    op.drop_index("ix_application_decisions_user", table_name="application_decisions")
    op.drop_index("ix_application_decisions_application", table_name="application_decisions")
    op.drop_table("application_decisions")
