"""Add interview enhancements for proxy interviews and email override.

Adds:
- recruiter_id FK to interviews (who conducted proxy interview)
- candidate_email to interviews (override email for self-service)
- invite_sent_at to interviews (when email was actually sent)

Supports new interview features:
- Recruiter proxy interviews (type='proxy')
- Email override with preview before sending
- Shareable link without sending email (status='draft' → 'scheduled')

Revision ID: 00015
Revises: 00014
Create Date: 2024-12-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00015"
down_revision = "00014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add interview enhancement columns."""

    # Add recruiter_id for tracking who conducted proxy interviews
    op.add_column(
        "interviews",
        sa.Column("recruiter_id", sa.Integer, nullable=True),
    )

    # Add foreign key constraint
    op.execute("""
        ALTER TABLE interviews
        ADD CONSTRAINT fk_interviews_recruiter
        FOREIGN KEY (recruiter_id) REFERENCES recruiters(id)
        ON DELETE SET NULL
    """)

    # Add candidate_email for email override
    op.add_column(
        "interviews",
        sa.Column("candidate_email", sa.String(255), nullable=True),
    )

    # Add invite_sent_at for tracking when email was sent
    op.add_column(
        "interviews",
        sa.Column("invite_sent_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    """Remove interview enhancement columns."""

    # Drop foreign key constraint first
    op.execute("""
        ALTER TABLE interviews
        DROP CONSTRAINT IF EXISTS fk_interviews_recruiter
    """)

    # Drop columns
    op.drop_column("interviews", "invite_sent_at")
    op.drop_column("interviews", "candidate_email")
    op.drop_column("interviews", "recruiter_id")
