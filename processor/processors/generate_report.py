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

        # Get ALL completed interviews for this application
        interview_query = text("""
            SELECT i.id as interview_id, i.interview_type, i.started_at, i.completed_at,
                   e.summary, e.interview_highlights, e.next_interview_focus
            FROM interviews i
            LEFT JOIN evaluations e ON e.interview_id = i.id
            WHERE i.application_id = :app_id
              AND i.status = 'completed'
            ORDER BY i.completed_at DESC
        """)
        interview_rows = self.db.execute(interview_query, {"app_id": application_id}).fetchall()

        # Build list of all interviews with their messages
        interviews = []
        for interview_row in interview_rows:
            # Get messages for this interview
            messages_query = text("""
                SELECT role, content
                FROM messages
                WHERE interview_id = :int_id
                ORDER BY created_at
            """)
            messages_result = self.db.execute(messages_query, {"int_id": interview_row.interview_id})
            interview_messages = [{"role": m.role, "content": m.content} for m in messages_result.fetchall()]

            interviews.append({
                "interview_id": interview_row.interview_id,
                "interview_type": interview_row.interview_type,
                "started_at": interview_row.started_at,
                "completed_at": interview_row.completed_at,
                "summary": interview_row.summary,
                "interview_highlights": interview_row.interview_highlights,
                "next_interview_focus": interview_row.next_interview_focus,
                "messages": interview_messages,
                "message_count": len(interview_messages),
            })

        # For backwards compatibility, also set single interview variable (most recent)
        interview = interview_rows[0] if interview_rows else None
        messages = interviews[0]["messages"] if interviews else []

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
            "employment_history": extracted_facts.get("employment_history", []),
            "skills": extracted_facts.get("skills", {}),
            "certifications": extracted_facts.get("certifications", []),
            "licenses": extracted_facts.get("licenses", []),
            "education": extracted_facts.get("education", []),

            # Summary stats
            "summary_stats": extracted_facts.get("summary_stats", {}),
            "total_experience_months": extracted_facts.get("summary_stats", {}).get("total_experience_months", 0),
            "recent_5yr_employers_count": extracted_facts.get("summary_stats", {}).get("recent_5yr_employers_count", 0),
            "recent_5yr_average_tenure_months": extracted_facts.get("summary_stats", {}).get("recent_5yr_average_tenure_months", 0),
            "most_recent_employer": extracted_facts.get("summary_stats", {}).get("most_recent_employer"),
            "most_recent_title": extracted_facts.get("summary_stats", {}).get("most_recent_title"),
            "months_since_last_employment": extracted_facts.get("summary_stats", {}).get("months_since_last_employment", 0),

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

            # Interview data (if exists) - backwards compatible single interview fields
            "has_interview": interview is not None,
            "interview_type": interview.interview_type if interview else None,
            "interview_date": interview.completed_at if interview else None,
            "interview_summary": interview.summary if interview else None,
            "interview_highlights": interview_highlights,
            "next_interview_focus": next_interview_focus,
            "message_count": len(messages),
            "messages": messages,

            # ALL interviews (for multi-interview support)
            "interviews": interviews,
            "interview_count": len(interviews),

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

        # Update application status based on whether interview was completed
        # - interview_ready_for_review: had an interview, ready for human review
        # - ready_for_review: resume-only, ready for human review
        new_status = 'interview_ready_for_review' if interview else 'ready_for_review'
        update_query = text("""
            UPDATE applications
            SET status = :new_status, updated_at = GETUTCDATE()
            WHERE id = :app_id
        """)
        self.db.execute(update_query, {"app_id": application_id, "new_status": new_status})
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

    def _months_to_years_str(self, months: int) -> str:
        """Convert months to human-readable years/months string."""
        if not months:
            return "N/A"
        years = months // 12
        remaining_months = months % 12
        if years == 0:
            return f"{remaining_months} months"
        elif remaining_months == 0:
            return f"{years} year{'s' if years != 1 else ''}"
        else:
            return f"{years} year{'s' if years != 1 else ''}, {remaining_months} month{'s' if remaining_months != 1 else ''}"

    def _parse_observation(self, obs) -> str:
        """Parse observation from dict or string to readable text."""
        if isinstance(obs, str):
            return obs
        if isinstance(obs, dict):
            # Extract the observation text, ignoring category/evidence metadata
            text = obs.get('observation') or obs.get('text') or obs.get('description', '')
            evidence = obs.get('evidence', '')
            if evidence and text:
                return f"{text} ({evidence})"
            return text or str(obs)
        return str(obs)

    def _parse_question(self, q) -> dict:
        """Parse interview question from dict or string."""
        if isinstance(q, str):
            return {"question": q, "topic": None, "reason": None}
        if isinstance(q, dict):
            return {
                "question": q.get('question') or q.get('text', ''),
                "topic": q.get('topic') or q.get('category', ''),
                "reason": q.get('reason') or q.get('why', ''),
            }
        return {"question": str(q), "topic": None, "reason": None}

    def _detect_risk_flags(self, data: dict) -> list:
        """Detect key risk flags from data for header display."""
        flags = []

        # Job hopping (more than 4 jobs in 5 years)
        if (data.get('recent_5yr_employers_count') or 0) > 4:
            flags.append(("Job Hopping", f"{data['recent_5yr_employers_count']} jobs in 5 years"))

        # Employment gap (more than 3 months)
        gap_months = data.get('months_since_last_employment') or 0
        if gap_months > 3:
            flags.append(("Employment Gap", f"{gap_months} months since last role"))

        # Short average tenure (less than 18 months)
        avg_tenure = data.get('recent_5yr_average_tenure_months') or 0
        if avg_tenure > 0 and avg_tenure < 18:
            flags.append(("Short Tenure", f"Avg {round(avg_tenure)} months per job"))

        return flags

    def _calculate_match_score(self, data: dict) -> int:
        """Calculate approximate JD match percentage."""
        matches = len(data.get('jd_matches', []))
        gaps = len(data.get('jd_gaps', []))
        total = matches + gaps
        if total == 0:
            return 0
        return round((matches / total) * 100)

    def _render_hitl_template(self, data: dict) -> str:
        """Render HITL report template optimized for human decision-making."""

        # Pre-compute values
        total_exp = self._months_to_years_str(data.get('total_experience_months') or 0)
        avg_tenure = self._months_to_years_str(int(data.get('recent_5yr_average_tenure_months') or 0))
        risk_flags = self._detect_risk_flags(data)
        match_score = self._calculate_match_score(data)

        # Current role - show warning if data missing
        current_role = data.get('most_recent_title') or 'Not Available'
        current_employer = data.get('most_recent_employer') or 'Not Available'
        has_extracted_facts = bool(data.get('employment_history') or data.get('skills') or data.get('education'))

        # Find tenure at current role from employment history
        current_tenure = ""
        for job in data.get('employment_history', []):
            if job.get('is_current') or job.get('end_date') in [None, 'Present', '']:
                months = job.get('duration_months', 0)
                current_tenure = f" ({self._months_to_years_str(months)})"
                break

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @page {{ margin: 0.5in; size: letter; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 0; padding: 15px; color: #1a1a1a; font-size: 11px; line-height: 1.4; }}

        /* Header Flight Deck */
        .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: white; padding: 15px 20px; margin: -15px -15px 15px -15px; }}
        .header h1 {{ margin: 0 0 5px 0; font-size: 18px; font-weight: 600; }}
        .header-grid {{ display: flex; justify-content: space-between; align-items: flex-start; }}
        .header-left {{ flex: 1; }}
        .header-right {{ text-align: right; }}
        .current-role {{ font-size: 13px; color: #a0c4e8; margin-top: 3px; }}
        .position-applied {{ font-size: 11px; color: #7eb3d8; margin-top: 2px; }}

        /* Metrics Strip */
        .metrics {{ display: flex; gap: 20px; margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.2); }}
        .metric {{ text-align: center; }}
        .metric-value {{ font-size: 16px; font-weight: 700; }}
        .metric-label {{ font-size: 9px; color: #a0c4e8; text-transform: uppercase; }}
        .match-score {{ background: rgba(255,255,255,0.15); padding: 8px 15px; border-radius: 4px; }}
        .match-high {{ color: #68d391; }}
        .match-med {{ color: #f6e05e; }}
        .match-low {{ color: #fc8181; }}

        /* Risk Badges */
        .risk-badges {{ margin-top: 8px; }}
        .risk-badge {{ display: inline-block; background: #c53030; color: white; padding: 3px 8px; border-radius: 3px; font-size: 10px; font-weight: 600; margin-right: 5px; }}

        /* Two Column Layout - use float for better print pagination */
        .two-col {{ overflow: hidden; }}
        .two-col::after {{ content: ''; display: table; clear: both; }}
        .col {{ width: 48%; }}
        .col-left {{ float: left; }}
        .col-right {{ float: right; }}

        /* Clear after two-col */
        .clear {{ clear: both; }}

        /* Sections */
        .section {{ margin-bottom: 15px; page-break-inside: avoid; }}
        .section-title {{ font-size: 12px; font-weight: 700; color: #2d5a87; border-bottom: 2px solid #2d5a87; padding-bottom: 3px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}

        /* Strengths & Alerts */
        .strength {{ background: #f0fff4; border-left: 3px solid #38a169; padding: 8px 10px; margin-bottom: 6px; }}
        .strength-title {{ font-weight: 600; color: #276749; font-size: 11px; }}
        .strength-text {{ color: #2f855a; margin-top: 2px; }}

        .alert {{ background: #fff5f5; border-left: 3px solid #c53030; padding: 8px 10px; margin-bottom: 6px; }}
        .alert-title {{ font-weight: 600; color: #c53030; font-size: 11px; }}
        .alert-text {{ color: #9b2c2c; margin-top: 2px; }}

        /* Employment Timeline */
        .job {{ border-left: 3px solid #cbd5e0; padding: 6px 0 6px 12px; margin-bottom: 8px; position: relative; }}
        .job::before {{ content: ''; position: absolute; left: -5px; top: 10px; width: 8px; height: 8px; background: #4a5568; border-radius: 50%; }}
        .job.current::before {{ background: #38a169; }}
        .job.gap {{ border-left-color: #fc8181; background: #fff5f5; }}
        .job-title {{ font-weight: 600; color: #1a202c; }}
        .job-company {{ color: #4a5568; }}
        .job-duration {{ font-size: 10px; color: #718096; }}

        /* Skills */
        .skill-category {{ margin-bottom: 8px; }}
        .skill-category-title {{ font-size: 10px; font-weight: 600; color: #4a5568; margin-bottom: 4px; }}
        .skill {{ display: inline-block; padding: 2px 8px; margin: 2px; border-radius: 3px; font-size: 10px; }}
        .skill-required {{ background: #2d5a87; color: white; }}
        .skill-bonus {{ background: #e2e8f0; color: #4a5568; border: 1px solid #cbd5e0; }}

        /* Question Cards */
        .question-card {{ background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 10px; margin-bottom: 8px; }}
        .question-topic {{ font-size: 10px; font-weight: 600; color: #2d5a87; text-transform: uppercase; margin-bottom: 4px; }}
        .question-text {{ font-weight: 500; color: #1a202c; margin-bottom: 6px; }}
        .question-meta {{ font-size: 10px; color: #718096; }}
        .question-meta strong {{ color: #4a5568; }}

        /* JD Match */
        .jd-item {{ display: flex; align-items: center; padding: 4px 0; border-bottom: 1px solid #edf2f7; }}
        .jd-item:last-child {{ border-bottom: none; }}
        .jd-status {{ width: 20px; font-size: 14px; }}
        .jd-match {{ color: #38a169; }}
        .jd-gap {{ color: #e53e3e; }}

        /* Education & Certs */
        .credential {{ padding: 4px 0; }}
        .credential-name {{ font-weight: 500; }}
        .credential-detail {{ font-size: 10px; color: #718096; }}

        /* Footer */
        .footer {{ margin-top: 15px; padding-top: 10px; border-top: 1px solid #e2e8f0; font-size: 9px; color: #718096; text-align: center; }}

        /* Transcript */
        .transcript {{ margin-top: 10px; }}
        .message {{ margin-bottom: 10px; padding: 8px 12px; border-radius: 4px; }}
        .message-assistant {{ background: #f7fafc; border-left: 3px solid #4a5568; }}
        .message-user {{ background: #ebf8ff; border-left: 3px solid #3182ce; }}
        .message-role {{ font-size: 9px; font-weight: 600; color: #718096; text-transform: uppercase; margin-bottom: 4px; }}
        .message-content {{ font-size: 10px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; }}

        /* Print optimization */
        @media print {{
            body {{ padding: 0; }}
            .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
        }}
    </style>
</head>
<body>
    <!-- HEADER FLIGHT DECK -->
    <div class="header">
        <div class="header-grid">
            <div class="header-left">
                <h1>{data['candidate_name']}</h1>
                <div class="current-role">Currently: {current_role} @ {current_employer}{current_tenure}</div>
                <div class="position-applied">Applied for: {data['position']}</div>
            </div>
            <div class="header-right">
                <div class="match-score">
                    <div class="metric-value {'match-high' if match_score >= 70 else 'match-med' if match_score >= 50 else 'match-low'}">{match_score}%</div>
                    <div class="metric-label">JD Match</div>
                </div>
            </div>
        </div>
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{total_exp}</div>
                <div class="metric-label">Total Experience</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data.get('recent_5yr_employers_count') or 0}</div>
                <div class="metric-label">Jobs (5yr)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{avg_tenure}</div>
                <div class="metric-label">Avg Tenure</div>
            </div>
        </div>
"""

        # Risk badges
        if risk_flags:
            html += '        <div class="risk-badges">\n'
            for flag_name, flag_detail in risk_flags:
                html += f'            <span class="risk-badge">⚠ {flag_name}: {flag_detail}</span>\n'
            html += '        </div>\n'

        html += '    </div>\n\n'

        # Warning banner if no extracted facts (resume not processed)
        if not has_extracted_facts:
            html += '''
    <div style="background: #FEF3C7; border: 2px solid #F59E0B; border-radius: 4px; padding: 12px; margin-bottom: 15px;">
        <strong style="color: #92400E;">⚠ Resume Data Not Available</strong>
        <p style="color: #78350F; margin: 8px 0 0 0; font-size: 11px;">
            This candidate's resume could not be processed. Employment history, skills, and education information are unavailable.
            The interview analysis below is based solely on the candidate's responses during the AI interview.
        </p>
    </div>
'''

        # TWO COLUMN LAYOUT
        html += '    <div class="two-col">\n'

        # LEFT COLUMN: Strengths, Alerts, Questions
        html += '        <div class="col col-left">\n'

        # Core Strengths
        if data.get('pros'):
            html += '            <div class="section">\n'
            html += '                <div class="section-title">Core Strengths</div>\n'
            for i, pro in enumerate(data['pros'][:5]):
                parsed = self._parse_observation(pro)
                html += f'                <div class="strength"><div class="strength-text">{parsed}</div></div>\n'
            html += '            </div>\n'

        # Critical Alerts
        if data.get('cons'):
            html += '            <div class="section">\n'
            html += '                <div class="section-title">Areas to Probe</div>\n'
            for con in data['cons'][:5]:
                parsed = self._parse_observation(con)
                html += f'                <div class="alert"><div class="alert-text">{parsed}</div></div>\n'
            html += '            </div>\n'

        # Interview Questions
        if data.get('suggested_questions'):
            html += '            <div class="section">\n'
            html += '                <div class="section-title">Interview Questions</div>\n'
            for q in data['suggested_questions'][:4]:
                parsed = self._parse_question(q)
                html += '                <div class="question-card">\n'
                if parsed['topic']:
                    html += f'                    <div class="question-topic">{parsed["topic"]}</div>\n'
                html += f'                    <div class="question-text">{parsed["question"]}</div>\n'
                if parsed['reason']:
                    html += f'                    <div class="question-meta"><strong>Why ask:</strong> {parsed["reason"]}</div>\n'
                html += '                </div>\n'
            html += '            </div>\n'

        html += '        </div>\n'  # End left column

        # RIGHT COLUMN: Timeline, Skills, Education
        html += '        <div class="col col-right">\n'

        # Employment Timeline
        if data.get('employment_history'):
            html += '            <div class="section">\n'
            html += '                <div class="section-title">Employment Timeline</div>\n'
            for i, job in enumerate(data['employment_history'][:6]):
                is_current = job.get('is_current') or job.get('end_date') in [None, 'Present', '']
                months = job.get('duration_months', 0)
                duration_str = self._months_to_years_str(months)
                dates = f"{job.get('start_date', '?')} - {job.get('end_date') or 'Present'}"

                job_class = "job current" if is_current else "job"
                html += f'                <div class="{job_class}">\n'
                html += f'                    <div class="job-title">{job.get("title", "Unknown")}</div>\n'
                html += f'                    <div class="job-company">{job.get("employer", "Unknown")}</div>\n'
                html += f'                    <div class="job-duration">{duration_str} • {dates}</div>\n'
                html += '                </div>\n'
            html += '            </div>\n'

        # Skills (Categorized)
        skills = data.get('skills', {})
        if skills:
            html += '            <div class="section">\n'
            html += '                <div class="section-title">Skills</div>\n'

            if isinstance(skills, dict):
                for category, skill_list in skills.items():
                    if skill_list:
                        category_name = category.replace('_', ' ').title()
                        html += f'                <div class="skill-category">\n'
                        html += f'                    <div class="skill-category-title">{category_name}</div>\n'
                        for skill in skill_list[:8]:
                            html += f'                    <span class="skill skill-bonus">{skill}</span>\n'
                        html += '                </div>\n'
            elif isinstance(skills, list):
                html += '                <div class="skill-category">\n'
                for skill in skills[:12]:
                    html += f'                    <span class="skill skill-bonus">{skill}</span>\n'
                html += '                </div>\n'

            html += '            </div>\n'

        # JD Match Details
        if data.get('jd_matches') or data.get('jd_gaps'):
            html += '            <div class="section">\n'
            html += '                <div class="section-title">JD Requirements</div>\n'
            for match in data.get('jd_matches', [])[:5]:
                html += f'                <div class="jd-item"><span class="jd-status jd-match">✓</span> {match}</div>\n'
            for gap in data.get('jd_gaps', [])[:5]:
                html += f'                <div class="jd-item"><span class="jd-status jd-gap">✗</span> {gap}</div>\n'
            html += '            </div>\n'

        # Education & Certifications
        education = data.get('education', [])
        certs = data.get('certifications', [])
        licenses = data.get('licenses', [])
        if education or certs or licenses:
            html += '            <div class="section">\n'
            html += '                <div class="section-title">Education & Credentials</div>\n'
            for edu in education[:2]:
                if isinstance(edu, dict):
                    html += f'                <div class="credential"><div class="credential-name">{edu.get("degree", "Degree")} - {edu.get("field", "")}</div><div class="credential-detail">{edu.get("institution", "")}</div></div>\n'
                else:
                    html += f'                <div class="credential"><div class="credential-name">{edu}</div></div>\n'
            for cert in certs[:3]:
                cert_name = cert.get('name', cert) if isinstance(cert, dict) else cert
                html += f'                <div class="credential"><div class="credential-name">{cert_name}</div></div>\n'
            for lic in licenses[:2]:
                if isinstance(lic, dict):
                    html += f'                <div class="credential"><div class="credential-name">{lic.get("type", "License")}</div></div>\n'
            html += '            </div>\n'

        html += '        </div>\n'  # End right column
        html += '    </div>\n'  # End two-col

        # All Interviews (supports multiple interviews per candidate)
        interviews = data.get('interviews', [])
        if interviews:
            from processor.utils.report_generator import markdown_to_html

            for idx, interview_data in enumerate(interviews):
                interview_num = idx + 1
                interview_label = f"AI Interview {interview_num}" if len(interviews) > 1 else "AI Interview Summary"
                interview_summary_html = markdown_to_html(interview_data.get('summary') or 'No summary available.')
                interview_date = interview_data.get('completed_at')
                interview_date_str = interview_date.strftime('%B %d, %Y') if interview_date else 'N/A'

                html += f'''
    <div class="section clear">
        <div class="section-title">{interview_label}</div>
        <p><strong>Type:</strong> {interview_data.get('interview_type', 'self_service')} |
           <strong>Date:</strong> {interview_date_str} |
           <strong>Messages:</strong> {interview_data.get('message_count', 0)}</p>
        <div>{interview_summary_html}</div>
    </div>
'''
                # Interview Transcript
                messages = interview_data.get('messages', [])
                if messages:
                    transcript_title = f"Interview {interview_num} Transcript" if len(interviews) > 1 else "Interview Transcript"
                    html += f'''
    <div class="section clear" style="page-break-before: always;">
        <div class="section-title">{transcript_title}</div>
        <div class="transcript">
'''
                    for msg in messages:
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        # Apply markdown conversion to message content
                        content_html = markdown_to_html(content)
                        role_label = 'Interviewer' if role == 'assistant' else 'Candidate'
                        html += f'''            <div class="message message-{role}">
                <div class="message-role">{role_label}</div>
                <div class="message-content">{content_html}</div>
            </div>
'''
                    html += '''        </div>
    </div>
'''

        # Footer
        html += f'''
    <div class="footer clear">
        Generated: {data['generated_date'].strftime('%B %d, %Y %I:%M %p UTC')} |
        Requisition: {data['requisition_id']} |
        AI-extracted facts require human verification
    </div>
</body>
</html>
'''
        return html
