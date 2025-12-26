"""Generate report processor for PDF candidate reports.

Uses Jinja2 templates from v1 for consistent report generation.
"""

import json
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.processors.base import BaseProcessor
from processor.queue_manager import QueueManager
from processor.integrations.s3 import S3Service
from processor.utils.report_generator import (
    get_report_generator,
    InterviewReportData,
)

logger = structlog.get_logger()


class GenerateReportProcessor(BaseProcessor):
    """Generates PDF candidate reports using v1 Jinja2 templates."""

    job_type = "generate_report"

    def __init__(self, db: Session, queue: QueueManager):
        super().__init__(db, queue)
        self.s3 = S3Service()
        self.generator = get_report_generator()

    async def process(
        self,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Process a report generation job.

        Args:
            application_id: Application to generate report for
            requisition_id: Not used
            payload: Additional options

        NOTE: This processor is disabled pending HITL rewrite.
        The old scoring columns (reliability_score, strengths, etc.) were removed.
        Report generation will be reimplemented to use extracted_facts instead.
        """
        if not application_id:
            raise ValueError("application_id is required for generate_report")

        # TODO: Rewrite for HITL - use extracted_facts instead of scoring columns
        self.logger.warning(
            "generate_report processor disabled pending HITL rewrite",
            application_id=application_id,
        )
        return  # Skip report generation for now

        self.logger.info("Generating candidate report", application_id=application_id)

        # Get application data
        query = text("""
            SELECT a.id, a.candidate_name, a.candidate_email, a.requisition_id,
                   r.external_id as external_requisition_id, a.created_at as applied_at, r.name as position
            FROM applications a
            JOIN requisitions r ON a.requisition_id = r.id
            WHERE a.id = :app_id
        """)
        result = self.db.execute(query, {"app_id": application_id})
        app = result.fetchone()

        if not app:
            raise ValueError(f"Application {application_id} not found")

        # Get interview and evaluation data
        eval_query = text("""
            SELECT i.id as interview_id, i.interview_type, i.started_at, i.completed_at,
                   e.reliability_score, e.accountability_score, e.professionalism_score,
                   e.communication_score, e.technical_score, e.growth_potential_score,
                   e.overall_score, e.summary, e.strengths, e.weaknesses, e.red_flags,
                   e.character_passed, e.retention_risk, e.authenticity_assessment,
                   e.readiness, e.next_interview_focus, e.recommendation
            FROM interviews i
            JOIN evaluations e ON e.interview_id = i.id
            WHERE i.application_id = :app_id
              AND i.status = 'completed'
            ORDER BY e.created_at DESC
        """)
        evaluation = self.db.execute(eval_query, {"app_id": application_id}).fetchone()

        if not evaluation:
            self.logger.warning("No completed interview/evaluation found", application_id=application_id)
            raise ValueError(f"No evaluation found for application {application_id}")

        # Get interview messages
        messages_query = text("""
            SELECT role, content
            FROM messages
            WHERE interview_id = :int_id
            ORDER BY created_at
        """)
        messages_result = self.db.execute(messages_query, {"int_id": evaluation.interview_id})
        messages = [{"role": m.role, "content": m.content} for m in messages_result.fetchall()]

        # Calculate overall score as 1-5 average for template display
        # (DB stores 0-100 for sorting, but v1 template expects 1-5)
        overall_score_1_5 = None
        if evaluation.reliability_score:
            overall_score_1_5 = round((
                evaluation.reliability_score +
                evaluation.accountability_score +
                evaluation.professionalism_score +
                evaluation.communication_score +
                evaluation.technical_score +
                evaluation.growth_potential_score
            ) / 6, 1)

        # Build evaluation dict for template (uses 1-5 scale like v1)
        eval_dict = {
            "reliability_score": evaluation.reliability_score,
            "accountability_score": evaluation.accountability_score,
            "professionalism_score": evaluation.professionalism_score,
            "communication_score": evaluation.communication_score,
            "technical_score": evaluation.technical_score,
            "growth_potential_score": evaluation.growth_potential_score,
            "overall_score": overall_score_1_5,  # 1-5 scale for v1 template
            "summary": evaluation.summary,
            "strengths": json.loads(evaluation.strengths) if evaluation.strengths else [],
            "weaknesses": json.loads(evaluation.weaknesses) if evaluation.weaknesses else [],
            "red_flags": json.loads(evaluation.red_flags) if evaluation.red_flags else [],
            "character_passed": evaluation.character_passed,
            "retention_risk": evaluation.retention_risk,
            "authenticity_assessment": evaluation.authenticity_assessment,
            "readiness": evaluation.readiness,
            "next_interview_focus": json.loads(evaluation.next_interview_focus) if evaluation.next_interview_focus else [],
            "recommendation": evaluation.recommendation,
        }

        # Build report data for v1 template
        report_data = InterviewReportData(
            interview_id=evaluation.interview_id,
            candidate_name=app.candidate_name,
            candidate_email=app.candidate_email,
            position_title=app.position,
            requisition_id=app.external_requisition_id or str(app.requisition_id),
            interview_type=evaluation.interview_type or "self_service",
            interview_date=evaluation.started_at or datetime.now(),
            message_count=len(messages),
            messages=messages,
            evaluation=eval_dict,
            company_name="CCFS",
        )

        # Generate PDF using v1 template
        pdf_content, filename = await self.generator.generate_interview_report(report_data)

        # Upload to S3
        s3_key = await self.s3.upload_report(application_id, pdf_content)

        # Create report record
        insert_query = text("""
            INSERT INTO reports (application_id, s3_key, includes_analysis,
                               includes_interview, created_at)
            OUTPUT INSERTED.id
            VALUES (:app_id, :s3_key, 0, 1, GETUTCDATE())
        """)
        result = self.db.execute(
            insert_query,
            {
                "app_id": application_id,
                "s3_key": s3_key,
            },
        )
        # Must fetch before commit with pyodbc
        report_id = result.scalar()
        self.db.commit()

        # Update application status
        update_query = text("""
            UPDATE applications
            SET status = 'report_pending', updated_at = GETUTCDATE()
            WHERE id = :app_id
        """)
        self.db.execute(update_query, {"app_id": application_id})
        self.db.commit()

        # Queue upload to Workday
        self.enqueue_next(
            job_type="upload_report",
            application_id=application_id,
            priority=0,
            payload={"report_id": report_id},
        )

        # Log activity
        self.log_activity(
            action="report_generated",
            application_id=application_id,
            requisition_id=app.requisition_id,
            details={
                "report_id": report_id,
                "s3_key": s3_key,
                "filename": filename,
                "size_bytes": len(pdf_content),
            },
        )

        self.logger.info(
            "Report generated",
            application_id=application_id,
            report_id=report_id,
            filename=filename,
            size=len(pdf_content),
        )
