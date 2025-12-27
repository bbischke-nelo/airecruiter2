"""Add idempotency index to jobs table.

Prevents duplicate jobs for the same application/job_type combination
when status is pending or running. This prevents expensive duplicate
AI calls when interview completion or recovery creates multiple jobs.

Revision ID: 00023
Revises: 00022
Create Date: 2024-12-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "00023"
down_revision = "00022"
branch_labels = None
depends_on = None


def index_exists(index_name: str) -> bool:
    """Check if an index exists."""
    conn = op.get_bind()
    result = conn.execute(text("""
        SELECT COUNT(*) FROM sys.indexes
        WHERE name = :index_name
    """), {"index_name": index_name})
    return result.scalar() > 0


def upgrade() -> None:
    """Add filtered unique index for job idempotency.

    Only one pending/running job per application+requisition+job_type combination.
    Completed/failed/dead jobs don't count - we can have many of those.

    The index includes both application_id and requisition_id because:
    - Application-level jobs (extract_facts, evaluate) use application_id
    - Requisition-level jobs (sync) use requisition_id with NULL application_id
    """
    if not index_exists("idx_jobs_idempotency"):
        # SQL Server filtered unique index
        # Include both IDs so sync jobs for different requisitions don't conflict
        op.execute(text("""
            CREATE UNIQUE INDEX idx_jobs_idempotency
            ON jobs (application_id, requisition_id, job_type)
            WHERE status IN ('pending', 'running')
        """))


def downgrade() -> None:
    """Remove the idempotency index."""
    if index_exists("idx_jobs_idempotency"):
        op.drop_index("idx_jobs_idempotency", table_name="jobs")
