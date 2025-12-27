"""PDF report generator for candidate reports.

Uses Jinja2 templates and WeasyPrint like v1 for consistent report generation.
"""

import re
import asyncio
import structlog
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jinja2

logger = structlog.get_logger()

# Try to import WeasyPrint
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("WeasyPrint not available - PDF generation disabled")


def markdown_to_html(text: str) -> str:
    """Convert markdown to HTML for PDF reports.

    Supports:
    - **bold** and *italic*
    - Bullet lists (- item or * item)
    - Numbered lists (1. item)
    - Headers (# ## ###)
    - Paragraphs with proper spacing
    """
    if not text:
        return ''

    lines = text.split('\n')
    html_lines = []
    in_ul = False
    in_ol = False

    for line in lines:
        stripped = line.strip()

        # Headers
        if stripped.startswith('### '):
            if in_ul:
                html_lines.append('</ul>')
                in_ul = False
            if in_ol:
                html_lines.append('</ol>')
                in_ol = False
            content = _inline_markdown(stripped[4:])
            html_lines.append(f'<h4>{content}</h4>')
            continue
        elif stripped.startswith('## '):
            if in_ul:
                html_lines.append('</ul>')
                in_ul = False
            if in_ol:
                html_lines.append('</ol>')
                in_ol = False
            content = _inline_markdown(stripped[3:])
            html_lines.append(f'<h3>{content}</h3>')
            continue
        elif stripped.startswith('# '):
            if in_ul:
                html_lines.append('</ul>')
                in_ul = False
            if in_ol:
                html_lines.append('</ol>')
                in_ol = False
            content = _inline_markdown(stripped[2:])
            html_lines.append(f'<h2>{content}</h2>')
            continue

        # Bullet lists (- or * at start)
        bullet_match = re.match(r'^[-*]\s+(.+)$', stripped)
        if bullet_match:
            if in_ol:
                html_lines.append('</ol>')
                in_ol = False
            if not in_ul:
                html_lines.append('<ul>')
                in_ul = True
            content = _inline_markdown(bullet_match.group(1))
            html_lines.append(f'<li>{content}</li>')
            continue

        # Numbered lists
        num_match = re.match(r'^\d+\.\s+(.+)$', stripped)
        if num_match:
            if in_ul:
                html_lines.append('</ul>')
                in_ul = False
            if not in_ol:
                html_lines.append('<ol>')
                in_ol = True
            content = _inline_markdown(num_match.group(1))
            html_lines.append(f'<li>{content}</li>')
            continue

        # Close any open lists on empty line or non-list content
        if in_ul:
            html_lines.append('</ul>')
            in_ul = False
        if in_ol:
            html_lines.append('</ol>')
            in_ol = False

        # Empty line = paragraph break
        if not stripped:
            html_lines.append('<br />')
            continue

        # Regular text with inline formatting
        content = _inline_markdown(stripped)
        html_lines.append(f'{content}<br />')

    # Close any unclosed lists
    if in_ul:
        html_lines.append('</ul>')
    if in_ol:
        html_lines.append('</ol>')

    return '\n'.join(html_lines)


def _inline_markdown(text: str) -> str:
    """Convert inline markdown (bold, italic) to HTML."""
    # Convert **bold** to <strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Convert *italic* to <em> (but not if it's a bullet)
    text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', text)
    return text


def format_date(dt: Optional[datetime]) -> str:
    """Format a datetime object for display."""
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt
    return dt.strftime("%B %d, %Y")


@dataclass
class InterviewReportData:
    """Data structure for interview report generation (matches v1)."""

    interview_id: int
    candidate_name: str
    candidate_email: Optional[str]
    position_title: str
    requisition_id: str
    interview_type: str  # 'recruiter' or 'self_service'
    interview_date: datetime
    message_count: int
    messages: List[Dict[str, str]]  # [{"role": "user/assistant", "content": "..."}]
    evaluation: Dict[str, Any]  # The full evaluation dict
    company_name: str = "CCFS"


@dataclass
class AnalysisReportData:
    """Data structure for resume analysis report generation."""

    # Candidate info
    candidate_name: str
    candidate_email: str
    position: str
    applied_at: datetime

    # Analysis data
    risk_score: int
    relevance_summary: str
    pros: List[str]
    cons: List[str]
    red_flags: List[str]
    suggested_questions: List[str]


class ReportGenerator:
    """Generates PDF reports using Jinja2 templates and WeasyPrint."""

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize the report generator.

        Args:
            template_dir: Path to template directory. Defaults to api/config/templates.
        """
        if template_dir is None:
            # Default to api/config/templates
            template_dir = Path(__file__).parent.parent.parent / "api" / "config" / "templates"

        self.template_dir = template_dir
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._init_template_engine()

    def _init_template_engine(self):
        """Initialize the Jinja2 template environment."""
        try:
            self.env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(self.template_dir)),
                autoescape=True,
                trim_blocks=True,
                lstrip_blocks=True
            )
            # Add custom filters
            self.env.filters['markdown'] = markdown_to_html
            self.env.filters['format_date'] = format_date
            logger.info("Report template engine initialized", path=str(self.template_dir))
        except Exception as e:
            logger.error("Failed to initialize template engine", error=str(e))
            raise

    async def generate_interview_report(self, data: InterviewReportData) -> Tuple[bytes, str]:
        """Generate a PDF interview report.

        Args:
            data: InterviewReportData with all interview information

        Returns:
            Tuple of (PDF bytes, filename)
        """
        if not WEASYPRINT_AVAILABLE:
            raise ReportError("WeasyPrint not available - cannot generate PDF reports")

        try:
            # Prepare template data
            template_data = {
                'interview_id': data.interview_id,
                'candidate_name': data.candidate_name,
                'candidate_email': data.candidate_email,
                'position_title': data.position_title,
                'requisition_id': data.requisition_id,
                'interview_type': data.interview_type,
                'interview_date': data.interview_date.strftime("%B %d, %Y at %I:%M %p"),
                'generated_date': datetime.now(timezone.utc).strftime("%B %d, %Y"),
                'message_count': data.message_count,
                'messages': data.messages,
                'evaluation': data.evaluation,
                'company_name': data.company_name,
            }

            # Render HTML in thread pool
            loop = asyncio.get_event_loop()
            html = await loop.run_in_executor(
                self._executor,
                self._render_template,
                'interview_report.html',
                template_data
            )

            # Generate PDF in thread pool
            pdf = await loop.run_in_executor(
                self._executor,
                self._generate_pdf,
                html
            )

            # Generate filename
            safe_name = "".join(c for c in data.candidate_name if c.isalnum() or c in " -_").strip()
            filename = f"Interview_Report_{safe_name}.pdf"

            logger.info("Generated interview report", candidate=data.candidate_name, size=len(pdf))
            return pdf, filename

        except Exception as e:
            logger.error("Failed to generate interview report", error=str(e))
            raise ReportError(f"Interview report generation failed: {str(e)}") from e

    async def generate_analysis_report(self, data: AnalysisReportData) -> Tuple[bytes, str]:
        """Generate a PDF analysis report.

        Args:
            data: AnalysisReportData with resume analysis information

        Returns:
            Tuple of (PDF bytes, filename)
        """
        if not WEASYPRINT_AVAILABLE:
            raise ReportError("WeasyPrint not available - cannot generate PDF reports")

        try:
            # Prepare template data
            template_data = {
                'candidate': {
                    'first_name': data.candidate_name.split()[0] if data.candidate_name else "",
                    'last_name': " ".join(data.candidate_name.split()[1:]) if data.candidate_name else "",
                    'email': data.candidate_email,
                },
                'position': data.position,
                'applied_at': data.applied_at,
                'generated_date': datetime.now(timezone.utc),
                'analysis': {
                    'risk_score': data.risk_score,
                    'relevance_summary': data.relevance_summary,
                    'pros': data.pros,
                    'cons': data.cons,
                    'red_flags': data.red_flags,
                    'suggested_questions': data.suggested_questions,
                },
                'company_name': 'CCFS',
            }

            # Render HTML in thread pool
            loop = asyncio.get_event_loop()
            html = await loop.run_in_executor(
                self._executor,
                self._render_template,
                'analysis.html',
                template_data
            )

            # Generate PDF in thread pool
            pdf = await loop.run_in_executor(
                self._executor,
                self._generate_pdf,
                html
            )

            # Generate filename
            safe_name = "".join(c for c in data.candidate_name if c.isalnum() or c in " -_").strip()
            filename = f"Analysis_Report_{safe_name}.pdf"

            logger.info("Generated analysis report", candidate=data.candidate_name, size=len(pdf))
            return pdf, filename

        except Exception as e:
            logger.error("Failed to generate analysis report", error=str(e))
            raise ReportError(f"Analysis report generation failed: {str(e)}") from e

    def _render_template(self, template_name: str, template_data: Dict[str, Any]) -> str:
        """Render an HTML template."""
        try:
            template = self.env.get_template(template_name)
            return template.render(template_data)
        except jinja2.TemplateError as e:
            logger.error("Template error", template=template_name, error=str(e))
            raise ReportError(f"Template rendering failed: {type(e).__name__}: {e}")

    def _generate_pdf(self, html: str) -> bytes:
        """Generate PDF from HTML."""
        try:
            doc = HTML(string=html)
            return doc.write_pdf()
        except Exception as e:
            raise ReportError(f"PDF generation failed: {e}")

    async def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=True)


# Legacy compatibility class
@dataclass
class ReportData:
    """Legacy data structure for backward compatibility."""

    # Candidate info
    candidate_name: str
    candidate_email: str
    position: str
    applied_at: datetime

    # Analysis data
    risk_score: int
    relevance_summary: str
    pros: List[str]
    cons: List[str]
    analysis_red_flags: List[str]

    # Interview data (optional)
    interview_completed_at: Optional[datetime] = None
    reliability_score: Optional[int] = None
    accountability_score: Optional[int] = None
    professionalism_score: Optional[int] = None
    communication_score: Optional[int] = None
    technical_score: Optional[int] = None
    growth_potential_score: Optional[int] = None
    evaluation_summary: Optional[str] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    evaluation_red_flags: Optional[List[str]] = None
    recommendation: Optional[str] = None

    # v1 evaluation fields
    character_passed: Optional[bool] = None
    retention_risk: Optional[str] = None
    authenticity_assessment: Optional[str] = None
    readiness: Optional[str] = None  # READY, NEEDS SUPPORT, NEEDS DEVELOPMENT
    next_interview_focus: Optional[List[str]] = None


class ReportError(Exception):
    """Raised when report generation fails."""
    pass


# Singleton instance
_generator_instance: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    """Get or create the report generator singleton."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = ReportGenerator()
    return _generator_instance
