"""Add configuration columns to requisitions.

Adds per-requisition config overrides for the Human-in-the-Loop pipeline:
- interview_enabled: Override global default
- interview_expiry_days: Custom expiry
- auto_update_stage: Update Workday on advance
- advance_to_stage: Target Workday stage
- blind_hiring_enabled: Redact PII from summaries
- role_level: For retention threshold
- custom_interview_instructions: Additional AI prompts
- jd_requirements_json: Extracted JD requirements

Part of Human-in-the-Loop pipeline redesign.

Revision ID: 00012
Revises: 00011
Create Date: 2024-12-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00012"
down_revision = "00011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add requisition config columns."""
    # Interview config (NULL = use global)
    op.add_column(
        "requisitions",
        sa.Column("interview_enabled", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "requisitions",
        sa.Column("interview_expiry_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "requisitions",
        sa.Column("auto_update_stage", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "requisitions",
        sa.Column("advance_to_stage", sa.String(50), nullable=True),
    )

    # Compliance config
    op.add_column(
        "requisitions",
        sa.Column("blind_hiring_enabled", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "requisitions",
        sa.Column(
            "role_level",
            sa.String(50),
            nullable=False,
            server_default="individual_contributor",
        ),
    )

    # Custom prompts and requirements
    op.add_column(
        "requisitions",
        sa.Column("custom_interview_instructions", sa.NVARCHAR(None), nullable=True),
    )
    op.add_column(
        "requisitions",
        sa.Column("jd_requirements_json", sa.NVARCHAR(None), nullable=True),
    )


def downgrade() -> None:
    """Remove requisition config columns."""
    op.drop_column("requisitions", "jd_requirements_json")
    op.drop_column("requisitions", "custom_interview_instructions")
    op.drop_column("requisitions", "role_level")
    op.drop_column("requisitions", "blind_hiring_enabled")
    op.drop_column("requisitions", "advance_to_stage")
    op.drop_column("requisitions", "auto_update_stage")
    op.drop_column("requisitions", "interview_expiry_days")
    op.drop_column("requisitions", "interview_enabled")
