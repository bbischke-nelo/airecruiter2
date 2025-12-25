"""Initial schema - all 17 tables.

Revision ID: 00001
Revises:
Create Date: 2024-12-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '00001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================
    # Independent tables (no foreign keys)
    # =====================

    # credentials
    op.create_table(
        'credentials',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_url', sa.String(500), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('client_id', sa.String(255), nullable=False),
        sa.Column('client_secret', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), default=False),
        sa.Column('last_validated', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id'),
    )

    # recruiters
    op.create_table(
        'recruiters',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('public_contact_info', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
    )

    # personas
    op.create_table(
        'personas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('system_prompt_template', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # settings
    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('[key]', sa.String(100), nullable=False),  # key is reserved in SQL Server
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('[key]', name='uq_settings_key'),
    )
    op.create_index('idx_settings_key', 'settings', ['[key]'])

    # email_templates
    op.create_table(
        'email_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('template_type', sa.String(50), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # =====================
    # Level 1 dependencies
    # =====================

    # requisitions (depends on recruiters)
    op.create_table(
        'requisitions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('external_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('detailed_description', sa.Text(), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('recruiter_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('sync_interval_minutes', sa.Integer(), default=15),
        sa.Column('lookback_hours', sa.Integer(), nullable=True),
        sa.Column('interview_instructions', sa.Text(), nullable=True),
        sa.Column('auto_send_interview', sa.Boolean(), default=False),
        sa.Column('auto_send_on_status', sa.String(100), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('workday_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
        sa.ForeignKeyConstraint(['recruiter_id'], ['recruiters.id'], ondelete='SET NULL'),
    )

    # =====================
    # Level 2 dependencies
    # =====================

    # prompts (depends on requisitions)
    op.create_table(
        'prompts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('prompt_type', sa.String(50), nullable=False),
        sa.Column('template_content', sa.Text(), nullable=False),
        sa.Column('schema_content', sa.Text(), nullable=True),
        sa.Column('requisition_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('updated_by', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['requisition_id'], ['requisitions.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_prompts_type', 'prompts', ['prompt_type'])
    op.create_index('idx_prompts_requisition', 'prompts', ['requisition_id'])

    # applications (depends on requisitions)
    op.create_table(
        'applications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('requisition_id', sa.Integer(), nullable=False),
        sa.Column('external_application_id', sa.String(255), nullable=False),
        sa.Column('external_candidate_id', sa.String(255), nullable=True),
        sa.Column('candidate_name', sa.String(255), nullable=False),
        sa.Column('candidate_email', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='new'),
        sa.Column('workday_status', sa.String(100), nullable=True),
        sa.Column('workday_status_changed', sa.DateTime(), nullable=True),
        sa.Column('human_requested', sa.Boolean(), default=False),
        sa.Column('compliance_review', sa.Boolean(), default=False),
        sa.Column('artifacts', sa.Text(), default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['requisition_id'], ['requisitions.id']),
        sa.UniqueConstraint('requisition_id', 'external_application_id', name='uq_applications_req_ext'),
    )

    # =====================
    # Level 3 dependencies
    # =====================

    # analyses (depends on applications, prompts)
    op.create_table(
        'analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('relevance_summary', sa.Text(), nullable=True),
        sa.Column('pros', sa.Text(), default='[]'),
        sa.Column('cons', sa.Text(), default='[]'),
        sa.Column('red_flags', sa.Text(), default='[]'),
        sa.Column('suggested_questions', sa.Text(), default='[]'),
        sa.Column('compliance_flags', sa.Text(), default='[]'),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('prompt_id', sa.Integer(), nullable=True),
        sa.Column('model_version', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prompt_id'], ['prompts.id']),
        sa.UniqueConstraint('application_id'),
        sa.CheckConstraint('risk_score BETWEEN 0 AND 100', name='ck_analyses_risk_score'),
    )

    # interviews (depends on applications, personas)
    op.create_table(
        'interviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('interview_type', sa.String(20), default='self_service'),
        sa.Column('token', sa.String(64), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(50), default='scheduled'),
        sa.Column('persona_id', sa.Integer(), nullable=True),
        sa.Column('human_requested', sa.Boolean(), default=False),
        sa.Column('human_requested_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id']),
        sa.UniqueConstraint('token'),
    )

    # reports (depends on applications)
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('s3_key', sa.String(500), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('uploaded_to_workday', sa.Boolean(), default=False),
        sa.Column('workday_document_id', sa.String(255), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('includes_analysis', sa.Boolean(), default=True),
        sa.Column('includes_interview', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
    )

    # jobs (depends on applications)
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('job_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('attempts', sa.Integer(), default=0),
        sa.Column('max_attempts', sa.Integer(), default=3),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
    )
    op.create_index('idx_jobs_pending', 'jobs', ['scheduled_for', 'priority'])
    op.create_index('idx_jobs_application', 'jobs', ['application_id'])

    # activities (depends on applications, requisitions, recruiters)
    op.create_table(
        'activities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=True),
        sa.Column('requisition_id', sa.Integer(), nullable=True),
        sa.Column('recruiter_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requisition_id'], ['requisitions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recruiter_id'], ['recruiters.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_activities_application', 'activities', ['application_id'])
    op.create_index('idx_activities_created', 'activities', ['created_at'])

    # email_log (depends on email_templates, applications)
    op.create_table(
        'email_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('to_email', sa.String(255), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('application_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(50), default='sent'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('clicked_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['email_templates.id']),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
    )

    # =====================
    # Level 4 dependencies
    # =====================

    # messages (depends on interviews)
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('sentiment', sa.Numeric(3, 2), nullable=True),
        sa.Column('topics', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
    )

    # evaluations (depends on interviews, prompts)
    op.create_table(
        'evaluations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('reliability_score', sa.Integer(), nullable=True),
        sa.Column('accountability_score', sa.Integer(), nullable=True),
        sa.Column('professionalism_score', sa.Integer(), nullable=True),
        sa.Column('communication_score', sa.Integer(), nullable=True),
        sa.Column('technical_score', sa.Integer(), nullable=True),
        sa.Column('growth_potential_score', sa.Integer(), nullable=True),
        sa.Column('overall_score', sa.Integer(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('strengths', sa.Text(), default='[]'),
        sa.Column('weaknesses', sa.Text(), default='[]'),
        sa.Column('red_flags', sa.Text(), default='[]'),
        sa.Column('recommendation', sa.String(50), nullable=True),
        sa.Column('next_interview_focus', sa.Text(), default='[]'),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('prompt_id', sa.Integer(), nullable=True),
        sa.Column('model_version', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prompt_id'], ['prompts.id']),
        sa.UniqueConstraint('interview_id'),
        sa.CheckConstraint('reliability_score BETWEEN 0 AND 10', name='ck_eval_reliability'),
        sa.CheckConstraint('accountability_score BETWEEN 0 AND 10', name='ck_eval_accountability'),
        sa.CheckConstraint('professionalism_score BETWEEN 0 AND 10', name='ck_eval_professionalism'),
        sa.CheckConstraint('communication_score BETWEEN 0 AND 10', name='ck_eval_communication'),
        sa.CheckConstraint('technical_score BETWEEN 0 AND 10', name='ck_eval_technical'),
        sa.CheckConstraint('growth_potential_score BETWEEN 0 AND 10', name='ck_eval_growth'),
        sa.CheckConstraint('overall_score BETWEEN 0 AND 100', name='ck_eval_overall'),
    )


def downgrade() -> None:
    # Drop in reverse order of dependencies
    op.drop_table('evaluations')
    op.drop_table('messages')
    op.drop_table('email_log')
    op.drop_table('activities')
    op.drop_table('jobs')
    op.drop_table('reports')
    op.drop_table('interviews')
    op.drop_table('analyses')
    op.drop_table('applications')
    op.drop_table('prompts')
    op.drop_table('requisitions')
    op.drop_table('email_templates')
    op.drop_index('idx_settings_key', 'settings')
    op.drop_table('settings')
    op.drop_table('personas')
    op.drop_table('recruiters')
    op.drop_table('credentials')
