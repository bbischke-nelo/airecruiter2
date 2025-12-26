#!/usr/bin/env python3
"""Test script to generate a candidate report with mock data.

Run from project root:
    python scripts/test_report_generation.py

Output: test_candidate_report.pdf in current directory
"""

from datetime import datetime
from pathlib import Path


# Mock data that matches what GenerateReportProcessor expects
MOCK_DATA = {
    # Candidate info
    "candidate_name": "Sarah Mitchell",
    "candidate_email": "sarah.mitchell@email.com",
    "position": "Senior Software Engineer",
    "requisition_id": "REQ-2024-0432",
    "applied_at": datetime(2024, 12, 15, 10, 30),
    "generated_date": datetime.utcnow(),

    # Summary stats
    "total_experience_months": 87,  # 7 years 3 months
    "recent_5yr_employers_count": 3,
    "recent_5yr_average_tenure_months": 22,
    "most_recent_employer": "TechCorp Inc.",
    "most_recent_title": "Software Engineer II",
    "months_since_last_employment": 0,

    # Employment history
    "employment_history": [
        {
            "employer": "TechCorp Inc.",
            "title": "Software Engineer II",
            "start_date": "March 2022",
            "end_date": None,
            "duration_months": 34,
            "is_current": True,
        },
        {
            "employer": "DataSystems LLC",
            "title": "Software Developer",
            "start_date": "June 2019",
            "end_date": "February 2022",
            "duration_months": 33,
            "is_current": False,
        },
        {
            "employer": "StartupXYZ",
            "title": "Junior Developer",
            "start_date": "January 2018",
            "end_date": "May 2019",
            "duration_months": 17,
            "is_current": False,
        },
        {
            "employer": "Freelance Consulting",
            "title": "Web Developer",
            "start_date": "August 2017",
            "end_date": "December 2017",
            "duration_months": 5,
            "is_current": False,
        },
    ],

    # Skills
    "skills": {
        "programming_languages": ["Python", "JavaScript", "TypeScript", "Go"],
        "frameworks": ["React", "FastAPI", "Django", "Node.js"],
        "databases": ["PostgreSQL", "MongoDB", "Redis"],
        "cloud": ["AWS", "Docker", "Kubernetes"],
        "other": ["Git", "CI/CD", "Agile", "REST APIs"],
    },

    # Education
    "education": [
        {
            "degree": "B.S. Computer Science",
            "field": "Computer Science",
            "institution": "State University",
            "year": 2017,
        }
    ],

    # Certifications
    "certifications": [
        {"name": "AWS Solutions Architect - Associate"},
        {"name": "Certified Kubernetes Administrator"},
    ],
    "licenses": [],

    # JD Match
    "jd_matches": [
        "Python 3+ years",
        "AWS experience",
        "Docker/Kubernetes",
        "REST API design",
        "CI/CD pipelines",
    ],
    "jd_gaps": [
        "Machine Learning experience",
        "Team leadership",
    ],

    # AI Observations
    "relevance_summary": "Strong technical candidate with solid backend experience. Good AWS/cloud skills match the JD requirements. Shows progression from junior to senior roles.",
    "pros": [
        {
            "observation": "Consistent career progression from Junior to Senior Engineer",
            "evidence": "4 roles with increasing responsibility over 7 years",
            "category": "career_growth",
        },
        {
            "observation": "Strong cloud infrastructure experience",
            "evidence": "AWS certification and hands-on Kubernetes experience",
            "category": "technical_skills",
        },
        "Excellent match on core Python and backend requirements",
        {
            "observation": "Demonstrated ability to work in fast-paced environments",
            "evidence": "Experience at both startups and established companies",
            "category": "adaptability",
        },
    ],
    "cons": [
        {
            "observation": "No direct machine learning experience mentioned",
            "evidence": "JD requires ML basics, not found in resume",
            "category": "skill_gap",
        },
        {
            "observation": "Leadership experience unclear",
            "evidence": "No mention of team lead or mentoring roles",
            "category": "experience_gap",
        },
        "Relatively short tenure at StartupXYZ (17 months)",
    ],
    "suggested_questions": [
        {
            "question": "Tell me about a complex system you designed and built from scratch.",
            "topic": "System Design",
            "reason": "Assess architectural thinking for senior role",
        },
        {
            "question": "How have you mentored junior developers in your current role?",
            "topic": "Leadership",
            "reason": "Probe leadership gap identified in analysis",
        },
        {
            "question": "What's your experience with machine learning or data pipelines?",
            "topic": "ML Experience",
            "reason": "JD requirement not evident in resume",
        },
        {
            "question": "Why did you leave StartupXYZ after 17 months?",
            "topic": "Job History",
            "reason": "Understand reason for shorter tenure",
        },
    ],
    "compliance_flags": [],
    "extraction_notes": "Resume was clear and well-formatted. All dates extracted with high confidence.",

    # Interview data - NOT included in pre-interview analysis report
    # Interview happens AFTER recruiter reviews this report
    "has_interview": False,
    "interview_type": None,
    "interview_date": None,
    "interview_summary": None,
    "interview_highlights": [],
    "next_interview_focus": [],
    "message_count": 0,
    "messages": [],

    # Company
    "company_name": "CCFS",
}

# Mock data for a problematic candidate (to test risk flags)
MOCK_DATA_RISKY = {
    "candidate_name": "John Doe",
    "candidate_email": "john.doe@email.com",
    "position": "Software Engineer",
    "requisition_id": "REQ-2024-0555",
    "applied_at": datetime(2024, 12, 20),
    "generated_date": datetime.utcnow(),

    # Summary stats showing risk flags
    "total_experience_months": 48,
    "recent_5yr_employers_count": 5,  # Job hopping flag
    "recent_5yr_average_tenure_months": 11,  # Short tenure flag
    "most_recent_employer": "QuickJobs Inc.",
    "most_recent_title": "Developer",
    "months_since_last_employment": 6,  # Employment gap flag

    # Employment history with gaps
    "employment_history": [
        {
            "employer": "QuickJobs Inc.",
            "title": "Developer",
            "start_date": "January 2024",
            "end_date": "June 2024",
            "duration_months": 6,
            "is_current": False,
        },
        {
            "employer": "TempTech",
            "title": "Junior Dev",
            "start_date": "March 2023",
            "end_date": "November 2023",
            "duration_months": 9,
            "is_current": False,
        },
        {
            "employer": "ShortStint LLC",
            "title": "Developer",
            "start_date": "August 2022",
            "end_date": "January 2023",
            "duration_months": 6,
            "is_current": False,
        },
        {
            "employer": "Contract Co",
            "title": "Contractor",
            "start_date": "January 2022",
            "end_date": "July 2022",
            "duration_months": 7,
            "is_current": False,
        },
        {
            "employer": "FirstJob Corp",
            "title": "Intern to Dev",
            "start_date": "June 2020",
            "end_date": "December 2021",
            "duration_months": 19,
            "is_current": False,
        },
    ],

    "skills": {
        "languages": ["JavaScript", "Python"],
        "frameworks": ["React"],
    },

    "education": [
        {"degree": "Associate's", "field": "IT", "institution": "Community College"}
    ],
    "certifications": [],
    "licenses": [],

    "jd_matches": ["JavaScript", "React"],
    "jd_gaps": ["Python 3+ years", "AWS", "Docker", "Team Lead experience", "Bachelor's degree"],

    "relevance_summary": "Entry-level candidate with unstable job history. Multiple short tenures raise concerns about commitment.",
    "pros": [
        "Has some React experience",
        "Eager to learn based on cover letter",
    ],
    "cons": [
        {
            "observation": "5 jobs in 4 years indicates potential job hopping pattern",
            "evidence": "Average tenure under 1 year",
            "category": "red_flag",
        },
        {
            "observation": "Current 6-month employment gap",
            "evidence": "Left last job June 2024",
            "category": "red_flag",
        },
        "Lacks most required technical skills",
        "No cloud or DevOps experience",
    ],
    "suggested_questions": [
        {
            "question": "Can you walk me through your career decisions over the past few years?",
            "topic": "Job History",
            "reason": "Understand pattern of short tenures",
        },
        {
            "question": "What have you been doing during your current employment gap?",
            "topic": "Gap",
            "reason": "6-month gap needs explanation",
        },
    ],
    "compliance_flags": [],
    "extraction_notes": "",

    "has_interview": False,
    "interview_type": None,
    "interview_date": None,
    "interview_summary": None,
    "interview_highlights": [],
    "next_interview_focus": [],
    "message_count": 0,
    "messages": [],

    "company_name": "CCFS",
}


def months_to_years_str(months: int) -> str:
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


def parse_observation(obs) -> str:
    """Parse observation from dict or string to readable text."""
    if isinstance(obs, str):
        return obs
    if isinstance(obs, dict):
        text = obs.get('observation') or obs.get('text') or obs.get('description', '')
        evidence = obs.get('evidence', '')
        if evidence and text:
            return f"{text} ({evidence})"
        return text or str(obs)
    return str(obs)


def parse_question(q) -> dict:
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


def detect_risk_flags(data: dict) -> list:
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


def calculate_match_score(data: dict) -> int:
    """Calculate approximate JD match percentage."""
    matches = len(data.get('jd_matches', []))
    gaps = len(data.get('jd_gaps', []))
    total = matches + gaps
    if total == 0:
        return 0
    return round((matches / total) * 100)


def render_template(data: dict) -> str:
    """Render the HITL report template."""

    # Pre-compute values
    total_exp = months_to_years_str(data.get('total_experience_months') or 0)
    avg_tenure = months_to_years_str(int(data.get('recent_5yr_average_tenure_months') or 0))
    risk_flags = detect_risk_flags(data)
    match_score = calculate_match_score(data)

    # Current role
    current_role = data.get('most_recent_title') or 'Unknown'
    current_employer = data.get('most_recent_employer') or 'Unknown'

    # Find tenure at current role from employment history
    current_tenure = ""
    for job in data.get('employment_history', []):
        if job.get('is_current') or job.get('end_date') in [None, 'Present', '']:
            months = job.get('duration_months', 0)
            current_tenure = f" ({months_to_years_str(months)})"
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

    # TWO COLUMN LAYOUT
    html += '    <div class="two-col">\n'

    # LEFT COLUMN: Strengths, Alerts, Questions
    html += '        <div class="col col-left">\n'

    # Core Strengths
    if data.get('pros'):
        html += '            <div class="section">\n'
        html += '                <div class="section-title">Core Strengths</div>\n'
        for i, pro in enumerate(data['pros'][:5]):
            parsed = parse_observation(pro)
            html += f'                <div class="strength"><div class="strength-text">{parsed}</div></div>\n'
        html += '            </div>\n'

    # Critical Alerts
    if data.get('cons'):
        html += '            <div class="section">\n'
        html += '                <div class="section-title">Areas to Probe</div>\n'
        for con in data['cons'][:5]:
            parsed = parse_observation(con)
            html += f'                <div class="alert"><div class="alert-text">{parsed}</div></div>\n'
        html += '            </div>\n'

    # Interview Questions
    if data.get('suggested_questions'):
        html += '            <div class="section">\n'
        html += '                <div class="section-title">Interview Questions</div>\n'
        for q in data['suggested_questions'][:4]:
            parsed = parse_question(q)
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
            duration_str = months_to_years_str(months)
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

    # Interview Summary (if exists)
    if data.get('has_interview'):
        html += f'''
    <div class="section clear">
        <div class="section-title">AI Interview Summary</div>
        <p><strong>Type:</strong> {data.get('interview_type', 'self_service')} |
           <strong>Date:</strong> {data['interview_date'].strftime('%B %d, %Y') if data.get('interview_date') else 'N/A'} |
           <strong>Messages:</strong> {data.get('message_count', 0)}</p>
        <p>{data.get('interview_summary', 'No summary available.')}</p>
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


def generate_pdf(data: dict, output_path: str):
    """Generate PDF from data."""
    try:
        from weasyprint import HTML
    except ImportError:
        print("ERROR: weasyprint not installed. Install with: pip install weasyprint")
        print("\nGenerating HTML file instead...")
        html = render_template(data)
        html_path = output_path.replace('.pdf', '.html')
        Path(html_path).write_text(html)
        print(f"HTML saved to: {html_path}")
        return

    html = render_template(data)
    pdf = HTML(string=html).write_pdf()
    Path(output_path).write_bytes(pdf)
    print(f"PDF generated: {output_path} ({len(pdf):,} bytes)")


def main():
    """Generate test reports."""
    print("=" * 60)
    print("Candidate Report Generator - Test Script")
    print("=" * 60)

    # Generate good candidate report
    print("\n1. Generating report for GOOD candidate (Sarah Mitchell)...")
    generate_pdf(MOCK_DATA, "test_candidate_report_good.pdf")

    # Generate risky candidate report
    print("\n2. Generating report for RISKY candidate (John Doe)...")
    generate_pdf(MOCK_DATA_RISKY, "test_candidate_report_risky.pdf")

    print("\n" + "=" * 60)
    print("Done! Open the PDF files to preview the report design.")
    print("=" * 60)


if __name__ == "__main__":
    main()
