"""Generate report processor for PDF candidate reports.

HITL version - generates factual reports without scores.
Humans make all advance/reject decisions.
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
    ReportGenerator,
)

logger = structlog.get_logger()


class GenerateReportProcessor(BaseProcessor):
    """Generates PDF candidate reports for human review.

    HITL version - no scores, just facts for recruiter decision-making.
    """

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
        """Generate a factual candidate report for human review.

        Args:
            application_id: Application to generate report for
            requisition_id: Not used
            payload: Additional options
        """
        if not application_id:
            raise ValueError("application_id is required for generate_report")

        self.logger.info("Generating candidate report", application_id=application_id)

        # Get application and requisition data
        app_query = text("""
            SELECT a.id, a.candidate_name, a.candidate_email, a.requisition_id,
                   a.created_at as applied_at, r.name as position,
                   r.external_id as external_requisition_id,
                   r.detailed_description as job_description
            FROM applications a
            JOIN requisitions r ON a.requisition_id = r.id
            WHERE a.id = :app_id
        """)
        app = self.db.execute(app_query, {"app_id": application_id}).fetchone()

        if not app:
            raise ValueError(f"Application {application_id} not found")

        # Get analysis with extracted facts
        analysis_query = text("""
            SELECT extracted_facts, relevance_summary, pros, cons,
                   suggested_questions, compliance_flags, extraction_notes
            FROM analyses
            WHERE application_id = :app_id
        """)
        analysis = self.db.execute(analysis_query, {"app_id": application_id}).fetchone()

        # Get interview data if exists
        interview_query = text("""
            SELECT i.id as interview_id, i.interview_type, i.started_at, i.completed_at,
                   e.summary, e.interview_highlights, e.next_interview_focus
            FROM interviews i
            LEFT JOIN evaluations e ON e.interview_id = i.id
            WHERE i.application_id = :app_id
              AND i.status = 'completed'
            ORDER BY i.completed_at DESC
        """)
        interview = self.db.execute(interview_query, {"app_id": application_id}).fetchone()

        # Get interview messages if interview exists
        messages = []
        if interview:
            messages_query = text("""
                SELECT role, content
                FROM messages
                WHERE interview_id = :int_id
                ORDER BY created_at
            """)
            messages_result = self.db.execute(messages_query, {"int_id": interview.interview_id})
            messages = [{"role": m.role, "content": m.content} for m in messages_result.fetchall()]

        # Parse extracted facts
        extracted_facts = {}
        if analysis and analysis.extracted_facts:
            try:
                extracted_facts = json.loads(analysis.extracted_facts) if isinstance(
                    analysis.extracted_facts, str
                ) else analysis.extracted_facts
            except json.JSONDecodeError:
                self.logger.warning("Failed to parse extracted_facts", application_id=application_id)

        # Parse other JSON fields from analysis
        pros = []
        cons = []
        suggested_questions = []
        compliance_flags = []
        if analysis:
            pros = json.loads(analysis.pros) if analysis.pros else []
            cons = json.loads(analysis.cons) if analysis.cons else []
            suggested_questions = json.loads(analysis.suggested_questions) if analysis.suggested_questions else []
            compliance_flags = json.loads(analysis.compliance_flags) if analysis.compliance_flags else []

        # Parse interview highlights
        interview_highlights = []
        next_interview_focus = []
        if interview:
            if interview.interview_highlights:
                try:
                    interview_highlights = json.loads(interview.interview_highlights) if isinstance(
                        interview.interview_highlights, str
                    ) else interview.interview_highlights
                except json.JSONDecodeError:
                    pass
            if interview.next_interview_focus:
                try:
                    next_interview_focus = json.loads(interview.next_interview_focus) if isinstance(
                        interview.next_interview_focus, str
                    ) else interview.next_interview_focus
                except json.JSONDecodeError:
                    pass

        # Build HITL report data
        report_data = {
            # Candidate info
            "candidate_name": app.candidate_name,
            "candidate_email": app.candidate_email,
            "position": app.position,
            "requisition_id": app.external_requisition_id or str(app.requisition_id),
            "applied_at": app.applied_at,
            "generated_date": datetime.utcnow(),

            # Extracted facts (no scores!)
            "extracted_facts": extracted_facts,
            "employment_history": extracted_facts.get("employment", []),
            "skills": extracted_facts.get("skills", []),
            "certifications": extracted_facts.get("certifications", []),
            "education": extracted_facts.get("education", []),

            # JD match analysis
            "jd_matches": extracted_facts.get("jd_keyword_matches", {}).get("found", []),
            "jd_gaps": extracted_facts.get("jd_keyword_matches", {}).get("not_found", []),

            # AI observations (factual, not scores)
            "relevance_summary": analysis.relevance_summary if analysis else None,
            "pros": pros,
            "cons": cons,
            "suggested_questions": suggested_questions,
            "compliance_flags": compliance_flags,
            "extraction_notes": analysis.extraction_notes if analysis else None,

            # Interview data (if exists)
            "has_interview": interview is not None,
            "interview_type": interview.interview_type if interview else None,
            "interview_date": interview.completed_at if interview else None,
            "interview_summary": interview.summary if interview else None,
            "interview_highlights": interview_highlights,
            "next_interview_focus": next_interview_focus,
            "message_count": len(messages),
            "messages": messages,

            # Company
            "company_name": "CCFS",
        }

        # Generate PDF using HITL template
        pdf_content, filename = await self._generate_hitl_report(report_data)

        # Upload to S3
        s3_key = await self.s3.upload_report(application_id, pdf_content)

        # Create report record
        insert_query = text("""
            INSERT INTO reports (application_id, s3_key, includes_analysis,
                               includes_interview, created_at)
            OUTPUT INSERTED.id
            VALUES (:app_id, :s3_key, :has_analysis, :has_interview, GETUTCDATE())
        """)
        result = self.db.execute(
            insert_query,
            {
                "app_id": application_id,
                "s3_key": s3_key,
                "has_analysis": 1 if analysis else 0,
                "has_interview": 1 if interview else 0,
            },
        )
        report_id = result.scalar()
        self.db.commit()

        # Update application status to ready_for_review (HITL - wait for human)
        update_query = text("""
            UPDATE applications
            SET status = 'ready_for_review', updated_at = GETUTCDATE()
            WHERE id = :app_id
        """)
        self.db.execute(update_query, {"app_id": application_id})
        self.db.commit()

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
                "has_analysis": analysis is not None,
                "has_interview": interview is not None,
            },
        )

        self.logger.info(
            "Report generated - ready for human review",
            application_id=application_id,
            report_id=report_id,
            filename=filename,
            size=len(pdf_content),
        )

    async def _generate_hitl_report(self, data: dict) -> tuple[bytes, str]:
        """Generate HITL-style PDF report.

        Args:
            data: Report data dictionary

        Returns:
            Tuple of (PDF bytes, filename)
        """
        # Use the generator's template rendering
        import asyncio
        from weasyprint import HTML

        loop = asyncio.get_event_loop()

        # Render template
        html = await loop.run_in_executor(
            self.generator._executor,
            self._render_hitl_template,
            data,
        )

        # Generate PDF
        pdf = await loop.run_in_executor(
            self.generator._executor,
            lambda: HTML(string=html).write_pdf(),
        )

        # Generate filename
        safe_name = "".join(c for c in data["candidate_name"] if c.isalnum() or c in " -_").strip()
        filename = f"Candidate_Summary_{safe_name}.pdf"

        return pdf, filename

    def _render_hitl_template(self, data: dict) -> str:
        """Render HITL report template."""
        # Build HTML directly since we might not have a template file yet
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
        h1 {{ color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 10px; }}
        h2 {{ color: #2c5282; margin-top: 30px; }}
        h3 {{ color: #4a5568; }}
        .header {{ margin-bottom: 30px; }}
        .meta {{ color: #666; font-size: 14px; }}
        .section {{ margin-bottom: 25px; }}
        .match {{ color: #276749; }}
        .gap {{ color: #c53030; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #edf2f7; font-weight: 600; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; margin: 2px; }}
        .badge-green {{ background: #c6f6d5; color: #276749; }}
        .badge-blue {{ background: #bee3f8; color: #2b6cb0; }}
        .badge-yellow {{ background: #fefcbf; color: #975a16; }}
        .badge-red {{ background: #fed7d7; color: #c53030; }}
        .pro {{ color: #276749; }}
        .con {{ color: #c53030; }}
        ul {{ margin: 10px 0; padding-left: 25px; }}
        li {{ margin: 5px 0; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #666; font-size: 12px; }}
        .notice {{ background: #ebf8ff; border-left: 4px solid #3182ce; padding: 15px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Candidate Summary</h1>
        <p class="meta">
            <strong>{data['candidate_name']}</strong><br>
            {data['candidate_email'] or 'No email provided'}<br>
            Position: {data['position']}<br>
            Applied: {data['applied_at'].strftime('%B %d, %Y') if data['applied_at'] else 'N/A'}
        </p>
    </div>

    <div class="notice">
        <strong>Human Review Required</strong><br>
        This summary contains AI-extracted facts only. All hiring decisions must be made by a recruiter.
    </div>
"""

        # Employment History
        if data.get('employment_history'):
            html += """
    <div class="section">
        <h2>Employment History</h2>
        <table>
            <tr><th>Company</th><th>Title</th><th>Duration</th></tr>
"""
            for job in data['employment_history']:
                company = job.get('company', 'Unknown')
                title = job.get('title', 'Unknown')
                duration = job.get('duration', 'Unknown')
                html += f"            <tr><td>{company}</td><td>{title}</td><td>{duration}</td></tr>\n"
            html += "        </table>\n    </div>\n"

        # Skills
        if data.get('skills'):
            html += """
    <div class="section">
        <h2>Skills</h2>
        <p>
"""
            for skill in data['skills']:
                html += f'            <span class="badge badge-blue">{skill}</span>\n'
            html += "        </p>\n    </div>\n"

        # Certifications
        if data.get('certifications'):
            html += """
    <div class="section">
        <h2>Certifications</h2>
        <ul>
"""
            for cert in data['certifications']:
                html += f"            <li>{cert}</li>\n"
            html += "        </ul>\n    </div>\n"

        # JD Match Analysis
        if data.get('jd_matches') or data.get('jd_gaps'):
            html += """
    <div class="section">
        <h2>JD Requirements Match</h2>
        <table>
            <tr><th>Requirement</th><th>Status</th></tr>
"""
            for match in data.get('jd_matches', []):
                html += f'            <tr><td>{match}</td><td class="match">✓ Found</td></tr>\n'
            for gap in data.get('jd_gaps', []):
                html += f'            <tr><td>{gap}</td><td class="gap">✗ Not Found</td></tr>\n'
            html += "        </table>\n    </div>\n"

        # AI Observations
        if data.get('pros') or data.get('cons'):
            html += """
    <div class="section">
        <h2>AI Observations</h2>
"""
            if data.get('pros'):
                html += "        <h3>Strengths (Factual)</h3>\n        <ul>\n"
                for pro in data['pros']:
                    html += f'            <li class="pro">{pro}</li>\n'
                html += "        </ul>\n"

            if data.get('cons'):
                html += "        <h3>Gaps / Concerns (Factual)</h3>\n        <ul>\n"
                for con in data['cons']:
                    html += f'            <li class="con">{con}</li>\n'
                html += "        </ul>\n"
            html += "    </div>\n"

        # Suggested Questions
        if data.get('suggested_questions'):
            html += """
    <div class="section">
        <h2>Suggested Interview Questions</h2>
        <ul>
"""
            for q in data['suggested_questions']:
                html += f"            <li>{q}</li>\n"
            html += "        </ul>\n    </div>\n"

        # Interview Summary
        if data.get('has_interview'):
            html += f"""
    <div class="section">
        <h2>AI Interview Summary</h2>
        <p class="meta">
            Type: {data.get('interview_type', 'self_service')}<br>
            Date: {data['interview_date'].strftime('%B %d, %Y') if data.get('interview_date') else 'N/A'}<br>
            Messages: {data.get('message_count', 0)}
        </p>
        <p>{data.get('interview_summary', 'No summary available.')}</p>
"""
            if data.get('interview_highlights'):
                html += "        <h3>Key Points</h3>\n        <ul>\n"
                for h in data['interview_highlights']:
                    html += f"            <li>{h}</li>\n"
                html += "        </ul>\n"

            if data.get('next_interview_focus'):
                html += "        <h3>Areas for Live Interview</h3>\n        <ul>\n"
                for f in data['next_interview_focus']:
                    html += f"            <li>{f}</li>\n"
                html += "        </ul>\n"
            html += "    </div>\n"

        # Compliance Flags
        if data.get('compliance_flags'):
            html += """
    <div class="section">
        <h2>Compliance Flags</h2>
        <ul>
"""
            for flag in data['compliance_flags']:
                html += f'            <li class="con">{flag}</li>\n'
            html += "        </ul>\n    </div>\n"

        # Footer
        html += f"""
    <div class="footer">
        <p>
            Generated: {data['generated_date'].strftime('%B %d, %Y at %I:%M %p UTC')}<br>
            Requisition: {data['requisition_id']}<br>
            <em>This report is for internal use only. AI-extracted facts require human verification.</em>
        </p>
    </div>
</body>
</html>
"""
        return html
