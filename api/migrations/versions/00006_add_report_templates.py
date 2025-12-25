"""Add report_templates table.

Revision ID: 00006
Revises: 00005
Create Date: 2025-12-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "00006"
down_revision = "00005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("template_type", sa.String(length=50), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("custom_css", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("is_default", sa.Boolean(), nullable=True, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("report_templates")
