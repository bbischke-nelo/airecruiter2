# Domain Terminology

This document establishes consistent terminology for AIRecruiter v2. All code, database schemas, and documentation should use these terms.

---

## Core Entities

### Requisition
A job opening that needs to be filled. Synced from Workday.

| Term | Definition | Workday Equivalent |
|------|------------|-------------------|
| `requisition` | A job opening | Job Requisition |
| `requisition_id` | Our internal primary key | - |
| `external_requisition_id` | ID in Workday | Job_Requisition_ID |

**v1 Issue Fixed**: v1 had `requisition_pk` (internal) and `requisition_id` (external string) which was confusing. v2 uses `id` (internal) and `external_id` (Workday ID).

---

### Candidate
A person who has applied for jobs. A candidate can have multiple applications.

| Term | Definition | Workday Equivalent |
|------|------------|-------------------|
| `candidate` | A person in the system | Candidate |
| `candidate_id` | Our internal primary key | - |
| `external_candidate_id` | ID in Workday | Candidate_ID |

---

### Application
A candidate's application for a specific requisition. This is the core entity we process.

| Term | Definition | Workday Equivalent |
|------|------------|-------------------|
| `application` | A candidate's submission for a requisition | Job Application |
| `application_id` | Our internal primary key | - |
| `external_application_id` | ID in Workday | Job_Application_ID |

**v1 Issue Fixed**: v1 used "ProcessingRecord" which was too implementation-focused. v2 uses "Application" which is domain-correct.

**v1 Issue Fixed**: v1 confused `applicant_id` and `candidate_id`. Workday uses:
- `Applicant` = candidate in context of a job (deprecated term)
- `Candidate` = the person entity
- `Job_Application` = the application itself

v2 uses `candidate` for the person and `application` for the submission.

---

### Analysis
AI-generated analysis of a candidate's resume/application.

| Term | Definition |
|------|------------|
| `analysis` | Resume/application analysis results |
| `analysis_id` | Primary key |
| `risk_score` | 0-100 score (higher = more risk) |

**v1 Issue Fixed**: v1 used `overall_score` for resume analysis which conflicted with interview evaluation's `overall_score`. v2 uses `risk_score` for resume analysis.

**Score Scale Standardization**: All scores in v2 use consistent 0-100 integer scale:
- `risk_score` (analyses): 0-100
- `overall_score` (evaluations): 0-100
- Sub-scores (evaluations): 0-10 (granular, then combined)

---

### Interview
An AI-conducted interview with a candidate.

| Term | Definition |
|------|------------|
| `interview` | A conversation session with a candidate |
| `interview_id` | Primary key |
| `interview_token` | Secure token for self-service access |

---

### Evaluation
AI-generated evaluation scores after interview completion.

| Term | Definition |
|------|------------|
| `evaluation` | Interview evaluation results |
| `overall_score` | Computed final score (0-100) |
| `transcript` | Full conversation log |

---

## TMS vs ATS

**v1 Issue Fixed**: v1 used "ATS" (Applicant Tracking System) inconsistently.

| Term | Use When |
|------|----------|
| TMS (Talent Management System) | Referring to Workday as a whole |
| ATS (Applicant Tracking System) | Never use - deprecated |
| Provider | When referring to TMS integration code |

Workday is a TMS that includes recruiting/ATS functionality, but calling it "ATS" is reductive. Use "TMS" or "Workday" specifically.

---

## Status Values

### Application Status
Status of an application in the processing pipeline.

| Status | Meaning |
|--------|---------|
| `new` | Just synced, not yet processed |
| `analyzing` | Resume analysis in progress |
| `analyzed` | Resume analysis complete |
| `interview_pending` | Interview created, not started |
| `interview_in_progress` | Candidate is taking interview |
| `interview_complete` | Interview finished |
| `report_pending` | Generating PDF report |
| `complete` | All processing done, report uploaded |
| `failed` | Processing failed |
| `skipped` | Intentionally skipped |

### Interview Status
Status of an interview session.

| Status | Meaning |
|--------|---------|
| `scheduled` | Interview created, link sent |
| `in_progress` | Candidate has started |
| `completed` | AI determined interview complete |
| `abandoned` | Candidate stopped without completion |
| `expired` | Token expired before completion |

### Workday Application Status
How we map to/from Workday status values.

| Our Status | Workday Status |
|------------|----------------|
| `new` | Review |
| `interview_pending` | Screen |
| `complete` | Interview (after report upload) |

---

## Artifacts

Files and documents generated during processing.

| Term | Description | Storage |
|------|-------------|---------|
| `resume` | Candidate's resume from Workday | S3 |
| `analysis_result` | JSON analysis output | Database + S3 |
| `transcript` | Interview conversation log | Database |
| `report` | Generated PDF report | S3 + Workday |

---

## Table Naming Conventions

Database tables use plural snake_case. Simplified from v1.

| Entity | v2 Table | v1 Table | Change |
|--------|----------|----------|--------|
| Requisition | `requisitions` | `requisitions` | - |
| Application | `applications` | `processing_records` | Renamed - it's an application! |
| Analysis | `analyses` | (JSON in processing_records) | New table |
| Interview | `interviews` | `interviews` | - |
| Evaluation | `evaluations` | `interview_evaluations` | Simplified |
| Message | `messages` | `interview_messages` | Simplified |
| Persona | `personas` | `interview_personas` | Simplified |
| Prompt | `prompts` | `prompt_templates` | Simplified |
| Report | `reports` | (JSON in processing_records) | New table |
| Recruiter | `recruiters` | `recruiters` | - |
| Credential | `credentials` | `ats_credentials` | Renamed (TMS not ATS) |
| Setting | `settings` | `system_settings` | Simplified |
| Activity | `activities` | `logs` | Renamed - business events, not operational logs |
| Job | `jobs` | `processing_queue` | Renamed - simpler, is the queue |

---

## Code Naming Conventions

### Python (API/Processor)
- Classes: `PascalCase` - `Application`, `Interview`
- Functions: `snake_case` - `get_application`, `process_candidate`
- Variables: `snake_case` - `candidate_id`, `interview_token`

### TypeScript (Web)
- Interfaces/Types: `PascalCase` - `Application`, `Interview`
- Functions: `camelCase` - `getApplication`, `processCandidate`
- Variables: `camelCase` - `candidateId`, `interviewToken`

### API Endpoints
- REST resources: plural, kebab-case paths
- Examples:
  - `GET /requisitions`
  - `GET /requisitions/{id}/applications`
  - `POST /interviews/{id}/messages`

---

## v1 → v2 Terminology Migration

### Table/Model Renames

| v1 Term | v2 Term | Reason |
|---------|---------|--------|
| `ProcessingRecord` | `Application` | Domain-correct - it IS an application |
| `ATSCredentials` | `Credential` | TMS not ATS, simpler |
| `PromptTemplate` | `Prompt` | Simpler |
| `SystemSettings` | `Setting` | Simpler |
| `InterviewPersona` | `Persona` | Simpler |
| `InterviewEvaluation` | `Evaluation` | Simpler |

### Field Renames

| v1 Field | v2 Field | Reason |
|---------|---------|--------|
| `requisition_pk` | `id` | Just use `id` for internal PK |
| `requisition_id` (string) | `external_id` | Clarity - it's the Workday ID |
| `applicant_id` | `external_application_id` | Workday terminology |
| `candidate_id` | `external_candidate_id` | Clarity |
| `overall_score` (resume) | `risk_score` | Distinguish from interview score |
| `min_check_interval` | `sync_interval_minutes` | Clear units |
| `auto_send_interview_state` | `auto_send_on_status` | Clearer |
| `rules` | removed | Was vague; v2 handles status mapping differently |

### Removed Redundant Fields

| v1 Field | Location | Reason for Removal |
|----------|----------|-------------------|
| `interview_sent` | ProcessingRecord | Derive from Interview existence |
| `interview_sent_at` | ProcessingRecord | Use `interviews.created_at` |
| `interview_status` | ProcessingRecord | Duplicates `interviews.status` |
| `human_requested` | ProcessingRecord | Only keep on `interviews` |
| `interview_score` | ProcessingRecord | Moved to `evaluations.overall_score` |

### Concept Renames

| v1 Term | v2 Term | Reason |
|---------|---------|--------|
| `policy` | `requisition` | It's not a policy, it's requisition config |
| `policy_manager` | `RequisitionService` | Call it what it is |
| `ATS` | `TMS` | Workday is a TMS, not just ATS |
