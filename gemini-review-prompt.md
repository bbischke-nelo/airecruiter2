# AIRecruiter v2 Design Review

You are reviewing the design documentation for AIRecruiter v2, a rewrite of an existing AI-powered recruitment system. The v1 system exists and works, but has accumulated technical debt and naming confusion.

## Context

- **v1**: Working system with PostgreSQL, multi-TMS support (UltiPro + Workday), browser automation
- **v2**: Clean rewrite with SQL Server, Workday-only, API-only integration, cleaned up terminology

## Your Task

Review all the documentation below and provide critical feedback on:

### 1. Naming & Terminology
- Are there any names that are still confusing or could be better?
- Any inconsistencies between documents?
- Any terms that don't match domain language?

### 2. Database Schema
- Missing fields or tables?
- Wrong relationships or cardinality?
- Indexing strategy issues?
- SQL Server-specific issues?

### 3. Architecture
- Any design smells or anti-patterns?
- Missing components?
- Unclear boundaries between services?
- Queue/job processing issues?

### 4. API Design
- RESTful issues?
- Missing endpoints?
- Inconsistent patterns?

### 5. Workflow/Processing
- Missing steps in the pipeline?
- Error handling gaps?
- Race conditions or edge cases?

### 6. ADRs (Architecture Decision Records)
- Any decisions that seem wrong or poorly justified?
- Missing decisions that should be documented?

### 7. What's Missing?
- What important aspects haven't been documented?
- What questions would a developer have that aren't answered?

Be critical and specific. Point out problems, not just praise. If something looks good, you can say so briefly, but focus on finding issues.

---

# DOCUMENTATION BEGINS HERE

---

# AIRecruiter v2

AI-powered candidate screening and interview system with Talent Management System (TMS) integration.

## Overview

AIRecruiter automates the initial stages of recruitment by:
1. Syncing job requisitions and candidates from your TMS (Workday)
2. Analyzing resumes using AI to score and evaluate candidates
3. Conducting self-service AI interviews
4. Generating comprehensive candidate reports
5. Uploading results back to the TMS

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Workday   │◄───►│  Processor  │◄───►│  SQL Server │
│    TMS      │     │   Worker    │     │  + Job Queue│
└─────────────┘     └──────┬──────┘     └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   Claude    │
                   │     AI      │
                   └─────────────┘

┌─────────────┐     ┌─────────────┐
│  Candidate  │◄───►│   Web API   │
│   Web UI    │     │  (FastAPI)  │
└─────────────┘     └─────────────┘
```

## Project Structure

```
airecruiter2/
├── docs/                    # Design documentation
│   ├── architecture/        # System architecture
│   ├── database/           # Schema design
│   ├── api/                # API specifications
│   ├── processor/          # Processing pipeline
│   └── decisions/          # Architecture Decision Records
├── api/                    # FastAPI backend
├── processor/              # Background processing service
└── web/                    # Next.js frontend
```

## Key Design Principles

1. **Clean Separation** - API, Processor, and Web are independent services
2. **Provider Extensibility** - TMS provider interface designed for extension
3. **Clear Terminology** - Consistent naming across codebase
4. **API-First** - No browser automation; clean API integrations only
5. **Observable** - Comprehensive logging and monitoring

## Documentation

### Requirements
- [Project Goals](docs/requirements/goals.md) - Problem statement, MVP scope
- [Feature Requirements](docs/requirements/features.md) - Complete feature list

### Architecture
- [Terminology](docs/architecture/terminology.md) - Domain terms and naming conventions
- [Database Schema](docs/database/schema.md) - SQL Server table definitions
- [Processor Workflow](docs/processor/workflow.md) - Background processing pipeline
- [API Design](docs/api/endpoints.md) - REST API specification
- [Web UI](docs/ui/pages.md) - Frontend page specifications

### Integrations
- [Workday Integration](docs/integrations/workday.md) - SOAP API details

### Decisions
- [ADR 001: Workday Only](docs/decisions/001-workday-only.md)
- [ADR 002: SQL Server](docs/decisions/002-sql-server-database.md)
- [ADR 003: Shared S3](docs/decisions/003-shared-s3-storage.md)
- [ADR 004: Terminology](docs/decisions/004-terminology-cleanup.md)
- [ADR 005: Queue Processing](docs/decisions/005-queue-based-processing.md)
- [ADR 006: API Only](docs/decisions/006-api-only-integration.md)
- [ADR 007: Logging Strategy](docs/decisions/007-logging-strategy.md)

## Tech Stack

- **API**: Python, FastAPI, SQLAlchemy
- **Processor**: Python, async/await
- **Database**: Microsoft SQL Server
- **Web**: Next.js, TypeScript, Tailwind
- **AI**: Claude API (Anthropic)
- **TMS**: Workday SOAP API
- **Storage**: AWS S3 (shared with v1)

## Development

```bash
# Setup (TBD)
```

## License

Proprietary
# Project Goals & Scope

## Problem Statement

Recruiters spend significant time on initial candidate screening:
- Reviewing resumes manually
- Conducting initial phone screens
- Tracking candidate status across systems
- Generating evaluation summaries

## Solution

AIRecruiter automates early-stage recruitment screening by:
1. Integrating with the company's TMS (Workday) to sync job requisitions and candidates
2. Using AI to analyze resumes against job requirements
3. Conducting AI-powered self-service interviews
4. Generating comprehensive candidate reports
5. Pushing results back to the TMS

## Target Users

- **Recruiters**: Primary users - configure jobs, review AI outputs, make decisions
- **Candidates**: Take self-service AI interviews
- **Hiring Managers**: (Future) Review candidate summaries

## Core Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                         SYNC PHASE                               │
├─────────────────────────────────────────────────────────────────┤
│  Workday ──► Sync Requisitions ──► Sync Candidates/Applications │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       ANALYSIS PHASE                             │
├─────────────────────────────────────────────────────────────────┤
│  Fetch Resume ──► AI Analysis ──► Score & Evaluate              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      INTERVIEW PHASE (Optional)                  │
├─────────────────────────────────────────────────────────────────┤
│  Send Interview Link ──► Candidate Takes Interview ──► Evaluate │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        OUTPUT PHASE                              │
├─────────────────────────────────────────────────────────────────┤
│  Generate Report ──► Upload to Workday ──► Notify Recruiter     │
└─────────────────────────────────────────────────────────────────┘
```

## MVP Features (v1.0)

### Must Have
- [ ] Workday OAuth2 authentication
- [ ] Sync job requisitions from Workday
- [ ] Sync candidates/applications from Workday
- [ ] AI resume analysis with scoring
- [ ] Generate PDF candidate reports
- [ ] Upload reports to Workday as attachments
- [ ] Basic settings UI (credentials, prompts)

### Should Have
- [ ] Self-service AI interviews
- [ ] Email notifications (interview invites, alerts)
- [ ] Configurable AI prompts/personas
- [ ] Processing logs/history

### Could Have (Future)
- [ ] Candidate status updates back to Workday
- [ ] Multiple TMS provider support
- [ ] Hiring manager portal
- [ ] Analytics dashboard

---

## DECISION REQUIRED

**Q1: Does this MVP scope look right? Anything to add/remove from Must Have?**

**Q2: Should self-service interviews be in MVP or deferred?**

**Q3: Any other workflows or features I'm missing from v1 that you want to keep?**
# AIRecruiter v2 - Feature Requirements

Everything from v1, cleaned up. UltiPro/Playwright/MFA hacks removed.

---

## 1. TMS Integration (Workday)

### Authentication
- OAuth2 with refresh token
- Encrypted credential storage
- Token auto-refresh
- Connection health checks

### Sync Operations
- Sync job requisitions
- Sync candidates/applications per requisition
- **Configurable lookback window**:
  - System setting: min/max hours to look back for new applications
  - Per-requisition override (optional)
  - Default: 24 hours
- Manual sync trigger (UI button to force sync)

### Write Operations
- Upload documents (reports) to candidate records
- Update candidate application status (future)

---

## 2. Requisition Management

### CRUD
- Create, read, update, delete requisitions
- List with search/filter (name, recruiter, location, status)
- Pagination

### Configuration Per-Requisition
- Custom interview instructions
- Auto-send interview toggle (+ trigger state)
- Min check interval
- Assigned recruiter
- Active/inactive status

---

## 3. AI Resume Analysis

### Processing
- Fetch resume from Workday
- Extract text (PDF/DOCX support)
- AI analysis against job requirements

### Output
- Job relevance assessment
- **Risk rating** (0.0-1.0 scale, higher = more risk)
  - Also stored as `overall_score` for backward compatibility
- Pros / Cons / Red flags (structured lists)
- Suggested interview questions (AI-generated based on resume gaps)
- Compliance flags (potential legal/ethical concerns)

### Storage
- Store analysis results (S3 or DB)
- Link to processing record

---

## 4. Self-Service AI Interviews

### Interview Flow
- Generate secure token-based link (7-day expiry)
- Candidate accesses without login
- Real-time chat with AI interviewer
- AI determines when complete
- Human handoff option (candidate requests human)

### Configuration
- Interview personas (AI personality/prompts)
- Customizable system prompts
- Per-requisition interview instructions

### Evaluation
- Auto-generate scores on completion:
  - **Granular sub-scores** (each 0-10 scale):
    - Reliability
    - Accountability
    - Professionalism
    - Communication
    - Technical Competency
    - Growth Potential
  - **Overall score** (computed from sub-scores)
- Transcript storage (full conversation log as first-class field)
- Summary, strengths, weaknesses, red flags
- Recommendations

---

## 5. Email Notifications

### Interview Invites
- Send self-service interview link to candidate
- Customizable email template
- Include recruiter contact info

### System Alerts
- Credential failure notifications
- Processing error alerts

### Configuration
- SMTP or AWS SES provider
- From address/name
- Recipient list management
- Enable/disable toggle

---

## 6. Report Generation

### PDF Reports
- Generate from interview + analysis
- Include evaluation scores
- Include transcript

### Storage & Delivery
- Store in S3
- Upload to Workday as attachment

---

## 7. Processing Pipeline

### Workflow
```
New Application Detected
    → Fetch Resume
    → AI Analysis
    → (Optional) Auto-send Interview
    → Wait for Interview Completion
    → Generate Report
    → Upload to Workday
```

### Processing Records
- Track each candidate application
- States: analysis pending/complete, interview scheduled/complete
- Link to all artifacts (resume, analysis, interview, report)

### Queue Management
- View pending/running/completed items
- Prioritize items
- Manual queue addition
- Clear queue operations

---

## 8. Prompt Management

### Prompt Types
- Resume analysis prompts
- Interview conversation prompts
- Interview evaluation prompts
- Email templates

### Features
- CRUD operations
- Set default per type
- Active/inactive toggle
- Global vs per-requisition override

---

## 9. Settings & Configuration

### System Settings
- Application lookback window (min/max hours)
- Default recruiter contact info

### Credential Management
- Workday OAuth2 credentials
- Encrypted storage
- Connection test

### Email Configuration
- Provider selection (SMTP/SES)
- Server settings
- Test email

---

## 10. Recruiter Management

- CRUD for recruiter profiles
- Contact info storage
- Assignment to requisitions

---

## 11. Logging & Monitoring

### Logs
- Structured logging
- Filter by level, requisition, application, date
- Search within logs

### Metrics
- Processing counts (24h, 7d, 30d)
- Per-requisition metrics
- Last processed timestamp

### Health
- System health endpoint
- TMS connection status

---

## 12. Web UI

### Pages
- Dashboard (home)
- Requisitions list + detail + edit
- Processing records (candidates) with search/filter
- Processing queue
- Interviews list
- Interview chat (admin)
- Public interview (candidate self-service)
- Settings (credentials, email, prompts, personas, recruiters)
- Logs viewer

### Features
- Responsive design
- Dark/light theme
- Toast notifications
- Real-time updates (interviews)

---

## 13. API

### Design
- RESTful endpoints
- JWT authentication (except public interview)
- Pagination on list endpoints
- Consistent error responses
- OpenAPI documentation

---

## Out of Scope (Removed from v1)

- ❌ UltiPro integration
- ❌ Playwright browser automation
- ❌ MFA session management
- ❌ WebSocket MFA flow
- ❌ Multi-provider TMS abstraction (Workday only for now)

---

## DECISION REQUIRED

**Q1: Anything missing from this list?**

**Q2: Any features you want to simplify or cut for initial v2 release?**

**Q3: SSO/Auth - keep the same approach or change?**
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
| `risk_score` | 0.0-1.0 score (higher = more risk) |

**v1 Issue Fixed**: v1 used `overall_score` for resume analysis which conflicted with interview evaluation's `overall_score`. v2 uses `risk_score` for resume analysis.

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
# Database Schema

Microsoft SQL Server database schema for AIRecruiter v2. Uses terminology defined in [terminology.md](../architecture/terminology.md).

---

## SQL Server Notes

**Type Mappings (PostgreSQL → SQL Server):**
| PostgreSQL | SQL Server | Notes |
|------------|------------|-------|
| `SERIAL` | `INT IDENTITY(1,1)` | Auto-increment |
| `BOOLEAN` | `BIT` | 0/1 |
| `TEXT` | `NVARCHAR(MAX)` | Unicode large text |
| `JSONB` | `NVARCHAR(MAX)` | Store as JSON string, use JSON functions |
| `TIMESTAMPTZ` | `DATETIME2` | High precision timestamps |
| `NOW()` | `GETUTCDATE()` | Current UTC time |
| `DEFAULT TRUE` | `DEFAULT 1` | Boolean defaults |

**JSON Handling:**
- JSON stored as `NVARCHAR(MAX)` strings
- Use `JSON_VALUE()`, `JSON_QUERY()`, `ISJSON()` for queries
- SQL Server 2016+ required for JSON functions

**Shared S3 Storage:**
- v2 shares the S3 bucket with v1
- v2 artifacts use `airecruiter2/` prefix to avoid conflicts

---

## Entity Relationship Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   credentials   │     │   requisitions  │────▶│    recruiters   │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 │ 1:N
                                 ▼
                        ┌─────────────────┐
                        │   applications  │
                        └────────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
           ┌─────────────┐ ┌──────────┐ ┌──────────┐
           │  analyses   │ │interviews│ │ reports  │
           └─────────────┘ └────┬─────┘ └──────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
           ┌─────────────────┐    ┌─────────────────┐
           │interview_messages│   │   evaluations   │
           └─────────────────┘    └─────────────────┘

┌─────────────────┐     ┌─────────────────┐
│     prompts     │     │interview_personas│
└─────────────────┘     └─────────────────┘

┌─────────────────┐     ┌─────────────────┐
│    settings     │     │      logs       │
└─────────────────┘     └─────────────────┘
```

---

## Core Tables

### credentials

Workday OAuth2 credentials. Encrypted at rest.

```sql
CREATE TABLE credentials (
    id              INT IDENTITY(1,1) PRIMARY KEY,

    -- Workday connection
    tenant_url      VARCHAR(500) NOT NULL,      -- https://services1.wd503.myworkday.com
    tenant_id       VARCHAR(100) NOT NULL,      -- ccfs
    client_id       VARCHAR(255) NOT NULL,
    client_secret   NVARCHAR(MAX) NOT NULL,     -- Encrypted
    refresh_token   NVARCHAR(MAX),              -- Encrypted

    -- Status
    is_valid        BIT DEFAULT 0,
    last_validated  DATETIME2,
    expires_at      DATETIME2,

    -- Metadata
    created_at      DATETIME2 DEFAULT GETUTCDATE(),
    updated_at      DATETIME2,

    CONSTRAINT UQ_credentials_tenant UNIQUE (tenant_id)
);
```

**Notes:**
- Simplified from v1 (no UltiPro/MFA complexity)
- `client_secret` and `refresh_token` encrypted with Fernet
- One credential set per tenant (usually just one)
- SQL Server uses `BIT` for boolean, `DATETIME2` for timestamps

---

### recruiters

Recruiter profiles for assignment and email templates.

```sql
CREATE TABLE recruiters (
    id                  INT IDENTITY(1,1) PRIMARY KEY,
    external_id         VARCHAR(100),               -- Workday Worker ID if available

    -- Identity
    name                VARCHAR(255) NOT NULL,
    email               VARCHAR(255),
    phone               VARCHAR(50),
    title               VARCHAR(255),
    department          VARCHAR(255),

    -- For email templates
    public_contact_info NVARCHAR(MAX),              -- Free-form contact block

    -- Metadata
    is_active           BIT DEFAULT 1,
    created_at          DATETIME2 DEFAULT GETUTCDATE(),
    updated_at          DATETIME2,

    CONSTRAINT UQ_recruiters_external UNIQUE (external_id)
);
```

---

### requisitions

Job openings synced from Workday.

```sql
CREATE TABLE requisitions (
    id                      INT IDENTITY(1,1) PRIMARY KEY,
    external_id             VARCHAR(255) NOT NULL,          -- Workday Job_Requisition_ID

    -- Basic info
    name                    VARCHAR(255) NOT NULL,
    description             NVARCHAR(MAX),                  -- Brief for display
    detailed_description    NVARCHAR(MAX),                  -- Full JD for AI
    location                VARCHAR(255),

    -- Assignment
    recruiter_id            INT FOREIGN KEY REFERENCES recruiters(id) ON DELETE SET NULL,

    -- Processing config
    is_active               BIT DEFAULT 1,
    sync_interval_minutes   INT DEFAULT 15,                 -- Minutes between sync checks
    lookback_hours          INT,                            -- Override system default

    -- Interview config
    interview_instructions  NVARCHAR(MAX),                  -- Extra prompts for AI
    auto_send_interview     BIT DEFAULT 0,
    auto_send_on_status     VARCHAR(100),                   -- Only send when candidate reaches this Workday status

    -- Workday sync metadata
    last_synced_at          DATETIME2,
    workday_data            NVARCHAR(MAX),                  -- Raw Workday fields (JSON string)

    -- Metadata
    created_at              DATETIME2 DEFAULT GETUTCDATE(),
    updated_at              DATETIME2,

    CONSTRAINT UQ_requisitions_external UNIQUE (external_id)
);

CREATE INDEX idx_requisitions_external_id ON requisitions(external_id);
CREATE INDEX idx_requisitions_is_active ON requisitions(is_active);
```

**Changes from v1:**
- Renamed `requisition_id` (string) → `external_id`
- Removed `tms_provider` (Workday only)
- Added `lookback_hours` for per-req override
- Added `workday_data` for raw sync data (stored as JSON string, use SQL Server JSON functions to query)

---

### applications

Candidate applications being processed. This is the central entity.

```sql
CREATE TABLE applications (
    id                      INT IDENTITY(1,1) PRIMARY KEY,
    requisition_id          INT NOT NULL FOREIGN KEY REFERENCES requisitions(id),

    -- Workday IDs
    external_application_id VARCHAR(255) NOT NULL,          -- Job_Application_ID
    external_candidate_id   VARCHAR(255),                   -- Candidate_ID

    -- Candidate info (denormalized for convenience)
    candidate_name          VARCHAR(255) NOT NULL,
    candidate_email         VARCHAR(255),

    -- Processing status
    status                  VARCHAR(50) NOT NULL DEFAULT 'new',
    -- new, analyzing, analyzed, interview_pending, interview_in_progress,
    -- interview_complete, report_pending, complete, failed, skipped

    -- Workday status tracking
    workday_status          VARCHAR(100),                   -- Current status in Workday
    workday_status_changed  DATETIME2,

    -- Flags
    human_requested         BIT DEFAULT 0,                  -- Candidate asked for human
    compliance_review       BIT DEFAULT 0,                  -- Flagged for review

    -- Artifacts (S3 keys) - stored as JSON string
    artifacts               NVARCHAR(MAX) DEFAULT '{}',
    -- {"resume": "s3://...", "analysis": "s3://...", "report": "s3://..."}

    -- Metadata
    created_at              DATETIME2 DEFAULT GETUTCDATE(),
    updated_at              DATETIME2,
    processed_at            DATETIME2,                      -- When fully processed

    CONSTRAINT UQ_applications_req_ext UNIQUE (requisition_id, external_application_id)
);

CREATE INDEX idx_applications_requisition ON applications(requisition_id);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_external_app ON applications(external_application_id);
CREATE INDEX idx_applications_external_cand ON applications(external_candidate_id);
```

**Changes from v1:**
- Renamed from `processing_records`
- Renamed `applicant_id` → `external_application_id`
- Renamed `overall_score` moved to `analyses` table
- Renamed `interview_score` moved to `evaluations` table
- Added proper foreign key to `requisitions`
- Added `workday_status` tracking

**S3 Storage Note:**
- v2 shares the same S3 bucket as v1
- Artifacts stored with `airecruiter2/` prefix to avoid conflicts
- Bucket: configured via `S3_BUCKET` environment variable

---

### analyses

AI resume analysis results.

```sql
CREATE TABLE analyses (
    id                  SERIAL PRIMARY KEY,
    application_id      INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    -- Scores
    risk_score          DECIMAL(3,2),                       -- 0.00-1.00

    -- Structured output
    relevance_summary   TEXT,                               -- Job fit assessment
    pros                JSONB DEFAULT '[]',                 -- ["Strong Python", ...]
    cons                JSONB DEFAULT '[]',                 -- ["No management exp", ...]
    red_flags           JSONB DEFAULT '[]',                 -- ["Employment gap", ...]

    -- AI-generated content
    suggested_questions JSONB DEFAULT '[]',                 -- Interview questions
    compliance_flags    JSONB DEFAULT '[]',                 -- Legal/ethical concerns

    -- Raw AI response
    raw_response        JSONB,                              -- Full AI output for debugging

    -- Prompt used
    prompt_id           INTEGER REFERENCES prompts(id),

    -- Metadata
    model_version       VARCHAR(50),                        -- claude-3-opus, etc.
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(application_id)                                  -- One analysis per application
);

CREATE INDEX idx_analyses_application ON analyses(application_id);
CREATE INDEX idx_analyses_risk ON analyses(risk_score);
```

**Changes from v1:**
- New table (was embedded in `processing_records`)
- Clear separation of resume analysis from interview evaluation
- `risk_score` instead of confusing `overall_score`

---

### interviews

AI interview sessions.

```sql
CREATE TABLE interviews (
    id                  SERIAL PRIMARY KEY,
    application_id      INTEGER NOT NULL REFERENCES applications(id),

    -- Type
    interview_type      VARCHAR(20) DEFAULT 'self_service',  -- self_service, admin

    -- Self-service access
    token               VARCHAR(64) UNIQUE,
    token_expires_at    TIMESTAMPTZ,

    -- Status
    status              VARCHAR(50) DEFAULT 'scheduled',
    -- scheduled, in_progress, completed, abandoned, expired

    -- Configuration
    persona_id          INTEGER REFERENCES personas(id),

    -- Flags
    human_requested     BOOLEAN DEFAULT FALSE,
    human_requested_at  TIMESTAMPTZ,

    -- Timestamps
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,

    -- Extra context
    metadata            JSONB
);

CREATE INDEX idx_interviews_application ON interviews(application_id);
CREATE INDEX idx_interviews_token ON interviews(token);
CREATE INDEX idx_interviews_status ON interviews(status);
```

---

### messages

Conversation log for interviews.

```sql
CREATE TABLE messages (
    id              SERIAL PRIMARY KEY,
    interview_id    INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,

    -- Message
    role            VARCHAR(20) NOT NULL,                   -- system, assistant, user
    content         TEXT,

    -- Optional per-message analysis
    sentiment       DECIMAL(3,2),                           -- -1.00 to 1.00
    topics          JSONB,                                  -- ["salary", "remote"]

    -- Timestamp
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_interview ON messages(interview_id);
```

---

### evaluations

AI-generated interview evaluation scores.

```sql
CREATE TABLE evaluations (
    id                      SERIAL PRIMARY KEY,
    interview_id            INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,

    -- Granular scores (0-10 scale)
    reliability_score       INTEGER CHECK (reliability_score BETWEEN 0 AND 10),
    accountability_score    INTEGER CHECK (accountability_score BETWEEN 0 AND 10),
    professionalism_score   INTEGER CHECK (professionalism_score BETWEEN 0 AND 10),
    communication_score     INTEGER CHECK (communication_score BETWEEN 0 AND 10),
    technical_score         INTEGER CHECK (technical_score BETWEEN 0 AND 10),
    growth_potential_score  INTEGER CHECK (growth_potential_score BETWEEN 0 AND 10),

    -- Computed overall (0-100 scale)
    overall_score           INTEGER CHECK (overall_score BETWEEN 0 AND 100),

    -- Textual analysis
    summary                 TEXT,
    strengths               JSONB DEFAULT '[]',
    weaknesses              JSONB DEFAULT '[]',
    red_flags               JSONB DEFAULT '[]',

    -- Recommendation
    recommendation          VARCHAR(50),                    -- hire, strong_hire, no_hire, review
    next_interview_focus    JSONB DEFAULT '[]',            -- Focus areas for next round

    -- Transcript storage (first-class field)
    transcript              TEXT,                           -- Full formatted transcript

    -- Raw AI response
    raw_response            JSONB,

    -- Prompt used
    prompt_id               INTEGER REFERENCES prompts(id),

    -- Metadata
    model_version           VARCHAR(50),
    created_at              TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(interview_id)
);

CREATE INDEX idx_evaluations_interview ON evaluations(interview_id);
CREATE INDEX idx_evaluations_recommendation ON evaluations(recommendation);
```

**Changes from v1:**
- Added `transcript` as first-class field
- Added CHECK constraints on scores
- Added `raw_response` for debugging

---

### reports

Generated PDF reports.

```sql
CREATE TABLE reports (
    id                  SERIAL PRIMARY KEY,
    application_id      INTEGER NOT NULL REFERENCES applications(id),

    -- Storage
    s3_key              VARCHAR(500) NOT NULL,
    file_name           VARCHAR(255),
    file_size           INTEGER,

    -- Upload status
    uploaded_to_workday BOOLEAN DEFAULT FALSE,
    workday_document_id VARCHAR(255),                       -- Workday attachment ID
    uploaded_at         TIMESTAMPTZ,

    -- Content included
    includes_analysis   BOOLEAN DEFAULT TRUE,
    includes_interview  BOOLEAN DEFAULT TRUE,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reports_application ON reports(application_id);
```

---

## Configuration Tables

### prompts

AI prompt templates.

```sql
CREATE TABLE prompts (
    id                  SERIAL PRIMARY KEY,

    -- Identity
    name                VARCHAR(255) NOT NULL,
    prompt_type         VARCHAR(50) NOT NULL,
    -- resume_analysis, interview, self_service_interview, evaluation, interview_email

    -- Content
    template_content    TEXT NOT NULL,
    schema_content      TEXT,                               -- JSON schema for structured output

    -- Scope
    requisition_id      INTEGER REFERENCES requisitions(id) ON DELETE CASCADE,
    -- NULL = global, otherwise requisition-specific override

    -- Status
    is_active           BOOLEAN DEFAULT TRUE,
    is_default          BOOLEAN DEFAULT FALSE,              -- One default per type

    -- Versioning
    version             INTEGER DEFAULT 1,
    description         TEXT,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ,
    created_by          VARCHAR(255),
    updated_by          VARCHAR(255)
);

CREATE INDEX idx_prompts_type ON prompts(prompt_type);
CREATE INDEX idx_prompts_requisition ON prompts(requisition_id);
CREATE UNIQUE INDEX idx_prompts_default ON prompts(prompt_type)
    WHERE is_default = TRUE AND requisition_id IS NULL;
```

---

### personas

AI interviewer personalities.

```sql
CREATE TABLE personas (
    id                      SERIAL PRIMARY KEY,

    name                    VARCHAR(100) NOT NULL,
    description             TEXT,

    -- The AI personality/system prompt
    system_prompt_template  TEXT NOT NULL,

    -- Status
    is_active               BOOLEAN DEFAULT TRUE,
    is_default              BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_personas_default ON personas(is_default)
    WHERE is_default = 1;
```

---

### settings

System configuration key-value store.

```sql
CREATE TABLE settings (
    id              SERIAL PRIMARY KEY,
    key             VARCHAR(100) NOT NULL UNIQUE,
    value           TEXT NOT NULL,
    description     TEXT,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

CREATE INDEX idx_settings_key ON settings(key);
```

**Expected settings:**
- `lookback_hours_min` - Minimum hours to look back (default: 1)
- `lookback_hours_max` - Maximum hours to look back (default: 48)
- `lookback_hours_default` - Default lookback (default: 24)
- `default_recruiter_id` - Default recruiter for new reqs
- `email_from_address` - Sender address for emails
- `email_from_name` - Sender name for emails
- `s3_bucket` - S3 bucket for artifacts
- `interview_token_expiry_days` - Days until token expires (default: 7)

---

### activities

Business audit trail (NOT for operational logs - those go to CloudWatch).

See [ADR 007: Logging Strategy](../decisions/007-logging-strategy.md) for details.

```sql
CREATE TABLE activities (
    id              INT IDENTITY(1,1) PRIMARY KEY,

    -- What happened
    action          VARCHAR(100) NOT NULL,
    -- status_changed, interview_sent, report_uploaded, human_requested, etc.

    -- Context
    application_id  INT REFERENCES applications(id) ON DELETE CASCADE,
    requisition_id  INT REFERENCES requisitions(id) ON DELETE SET NULL,
    recruiter_id    INT REFERENCES recruiters(id) ON DELETE SET NULL,

    -- Details (JSON)
    details         NVARCHAR(MAX),
    -- {"from_status": "new", "to_status": "analyzed", "by": "system"}

    -- Timestamp
    created_at      DATETIME2 DEFAULT GETUTCDATE()
);

CREATE INDEX idx_activities_application ON activities(application_id);
CREATE INDEX idx_activities_created ON activities(created_at);
```

**Note**: Operational logs (debug, errors, performance) go to CloudWatch Logs, not this table.
This table is for user-visible business events only.

---

## Job Queue Table

### jobs

Queue for processing jobs. Worker polls this table.

See [ADR 005: Queue-Based Processing](../decisions/005-queue-based-processing.md) for details.

```sql
CREATE TABLE jobs (
    id              INT IDENTITY(1,1) PRIMARY KEY,

    -- Job info
    application_id  INT NOT NULL REFERENCES applications(id),
    job_type        VARCHAR(50) NOT NULL,
    -- sync, analyze, send_interview, evaluate, generate_report, upload_report

    -- Queue status
    status          VARCHAR(50) DEFAULT 'pending',
    -- pending, running, completed, failed

    priority        INT DEFAULT 0,                      -- Higher = more urgent
    attempts        INT DEFAULT 0,
    max_attempts    INT DEFAULT 3,

    -- Error tracking
    last_error      NVARCHAR(MAX),

    -- Timing
    created_at      DATETIME2 DEFAULT GETUTCDATE(),
    started_at      DATETIME2,
    completed_at    DATETIME2,
    scheduled_for   DATETIME2 DEFAULT GETUTCDATE()      -- For delayed/retry jobs
);

CREATE INDEX idx_jobs_pending ON jobs(scheduled_for, priority DESC)
    WHERE status = 'pending';
CREATE INDEX idx_jobs_application ON jobs(application_id);
```

**Worker Pattern**:
```sql
-- Claim next job (SQL Server)
UPDATE TOP(1) jobs WITH (UPDLOCK, READPAST)
SET status = 'running', started_at = GETUTCDATE()
OUTPUT INSERTED.*
WHERE status = 'pending' AND scheduled_for <= GETUTCDATE()
ORDER BY priority DESC, created_at ASC;
```

---

## Email Tables (Optional - if not using SES directly)

### email_templates

```sql
CREATE TABLE email_templates (
    id              SERIAL PRIMARY KEY,

    name            VARCHAR(100) NOT NULL,
    template_type   VARCHAR(50) NOT NULL,                   -- interview_invite, alert

    subject         VARCHAR(500) NOT NULL,
    body_html       TEXT NOT NULL,
    body_text       TEXT,

    is_active       BOOLEAN DEFAULT TRUE,
    is_default      BOOLEAN DEFAULT FALSE,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);
```

### email_log

```sql
CREATE TABLE email_log (
    id              SERIAL PRIMARY KEY,

    -- Recipient
    to_email        VARCHAR(255) NOT NULL,

    -- Content
    template_id     INTEGER REFERENCES email_templates(id),
    subject         VARCHAR(500),

    -- Context
    application_id  INTEGER REFERENCES applications(id),

    -- Status
    status          VARCHAR(50) DEFAULT 'sent',             -- sent, failed, bounced
    error           TEXT,

    -- Tracking
    sent_at         TIMESTAMPTZ DEFAULT NOW(),
    opened_at       TIMESTAMPTZ,
    clicked_at      TIMESTAMPTZ
);
```

---

## Migration Strategy

When migrating from v1:

1. **Create new tables** with v2 schema
2. **Migrate requisitions**:
   - `requisition_id` → `external_id`
   - `min_check_interval` → `sync_interval_minutes`
   - Drop `rules` column
3. **Migrate processing_records → applications**:
   - Split `overall_score` → `analyses.risk_score`
   - Drop `interview_sent`, `interview_status` (derive from interviews table)
   - Drop `interview_score` (lives in evaluations)
4. **Migrate interviews**: Mostly 1:1, but reference `personas` not `interview_personas`
5. **Migrate prompt_templates → prompts**
6. **Migrate interview_personas → personas**
7. **Migrate interview_evaluations → evaluations**
8. **Migrate system_settings → settings**
9. **Migrate ats_credentials → credentials**
10. **Drop legacy tables** after validation

---

## Indexes Summary

Key indexes for query performance:

| Table | Index | Purpose |
|-------|-------|---------|
| applications | status | Filter by processing status |
| applications | requisition_id | List apps per requisition |
| applications | external_application_id | Lookup by Workday ID |
| interviews | token | Self-service auth |
| interviews | status | Filter active interviews |
| analyses | risk_score | Sort by risk |
| evaluations | recommendation | Filter by outcome |
| logs | created_at, level | Log browsing |
| queue | status, scheduled_for | Job scheduling |
# Processor Architecture

The Processor is a background service that orchestrates the entire candidate processing pipeline.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          PROCESSOR SERVICE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │   Scheduler │───▶│   Queue     │───▶│   Worker    │              │
│  │             │    │   Manager   │    │             │              │
│  └─────────────┘    └─────────────┘    └──────┬──────┘              │
│                                               │                       │
│  ┌────────────────────────────────────────────┼──────────────────┐   │
│  │                    JOB PROCESSORS          │                   │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │  ┌──────────┐    │   │
│  │  │   Sync   │  │ Analyze  │  │Interview │  ▼  │  Report  │    │   │
│  │  │          │  │          │  │          │     │          │    │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘     └────┬─────┘    │   │
│  └───────┼─────────────┼─────────────┼────────────────┼──────────┘   │
│          │             │             │                │               │
└──────────┼─────────────┼─────────────┼────────────────┼───────────────┘
           │             │             │                │
           ▼             ▼             ▼                ▼
    ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
    │  Workday  │  │  Claude   │  │  Email    │  │    S3     │
    │  SOAP API │  │    AI     │  │  (SES)    │  │  Storage  │
    └───────────┘  └───────────┘  └───────────┘  └───────────┘
```

---

## Components

### Scheduler

Periodically checks for work that needs to be done.

**Responsibilities:**
- Check for requisitions with new applications (based on lookback window)
- Detect applications needing each pipeline stage
- Create queue items for pending work

**Configuration:**
- `SCHEDULER_INTERVAL`: How often to check (default: 60 seconds)
- `LOOKBACK_HOURS`: How far back to look for new applications

```python
class Scheduler:
    async def run(self):
        while True:
            # Check for requisitions with recent activity
            active_reqs = await self.workday.get_requisitions_with_activity(
                since=datetime.now() - timedelta(hours=self.lookback_hours)
            )

            # Queue sync jobs for active requisitions
            for req in active_reqs:
                if self.should_sync(req):
                    await self.queue.enqueue('sync', req.id)

            # Check for applications needing processing
            pending_apps = await self.db.get_applications_by_status('new')
            for app in pending_apps:
                await self.queue.enqueue('analyze', app.id)

            await asyncio.sleep(self.interval)
```

---

### Queue Manager

Manages the processing queue for reliable job execution.

**Features:**
- Priority ordering (manual items > scheduled items > retries)
- Retry logic with exponential backoff
- Dead letter queue for failed jobs
- Concurrency limiting

**Queue Item States:**
- `pending` - Waiting to be processed
- `running` - Currently being processed
- `completed` - Successfully finished
- `failed` - Failed (will retry)
- `dead` - Failed max retries (requires manual intervention)

```python
@dataclass
class QueueItem:
    id: int
    job_type: str          # sync, analyze, send_interview, evaluate, generate_report, upload_report
    application_id: int
    priority: int
    status: str
    attempts: int
    max_attempts: int
    last_error: Optional[str]
    created_at: datetime
    scheduled_for: datetime
```

---

### Worker

Executes jobs from the queue.

**Execution Flow:**
1. Pop next pending job from queue
2. Mark as `running`
3. Execute appropriate job processor
4. On success: mark `completed`, delete from queue
5. On failure: increment attempts, schedule retry or move to dead letter

```python
class Worker:
    async def run(self):
        while True:
            job = await self.queue.pop_next()
            if not job:
                await asyncio.sleep(5)
                continue

            try:
                await self.process_job(job)
                await self.queue.complete(job.id)
            except Exception as e:
                await self.queue.fail(job.id, error=str(e))
```

---

## Job Processors

### 1. SyncProcessor

Syncs requisitions and applications from Workday.

**Input:** Requisition ID or full sync flag
**Output:** New/updated applications in database

```
Workday ─────────────────────────────────────────────────────▶ Database
         Get_Job_Requisitions                                   requisitions
         Get_Candidates (per requisition)                       applications
         Get_Candidate_Attachments (resume)                     artifacts.resume
```

**Steps:**
1. Authenticate with Workday (OAuth2)
2. Fetch requisition details
3. Fetch candidates/applications for requisition
4. For each new application:
   - Create application record (status: `new`)
   - Download resume attachment
   - Store resume in S3
   - Update `artifacts.resume` with S3 key

```python
class SyncProcessor:
    async def process(self, requisition_id: int):
        req = await self.db.get_requisition(requisition_id)

        # Get applications from Workday
        apps = await self.workday.get_candidates(req.external_id)

        for app in apps:
            # Check if we already have this application
            existing = await self.db.get_application_by_external_id(
                app.external_application_id
            )
            if existing:
                continue

            # Create new application
            new_app = await self.db.create_application(
                requisition_id=req.id,
                external_application_id=app.external_application_id,
                external_candidate_id=app.external_candidate_id,
                candidate_name=app.candidate_name,
                candidate_email=app.candidate_email,
                status='new'
            )

            # Download and store resume
            resume = await self.workday.get_resume(app.external_candidate_id)
            if resume:
                s3_key = await self.s3.upload_resume(new_app.id, resume)
                await self.db.update_application_artifacts(
                    new_app.id, {'resume': s3_key}
                )

            # Queue analysis
            await self.queue.enqueue('analyze', new_app.id)
```

---

### 2. AnalyzeProcessor

AI analysis of resume against job requirements.

**Input:** Application ID
**Output:** Analysis record with scores and insights

```
S3 (resume) ──▶ Text Extraction ──▶ Claude AI ──▶ Analysis Record
                    │                    │
                    │                    └─ Job requirements context
                    └─ PDF/DOCX parsing
```

**Steps:**
1. Load resume from S3
2. Extract text (PDF/DOCX parsing)
3. Load requisition's job description
4. Call Claude API with analysis prompt
5. Parse structured response
6. Store analysis record
7. Update application status to `analyzed`

```python
class AnalyzeProcessor:
    async def process(self, application_id: int):
        app = await self.db.get_application(application_id)
        req = await self.db.get_requisition(app.requisition_id)

        # Get resume text
        resume_bytes = await self.s3.download(app.artifacts['resume'])
        resume_text = self.extract_text(resume_bytes)

        # Get analysis prompt
        prompt = await self.prompts.get_active('resume_analysis', req.id)

        # Call Claude
        response = await self.claude.analyze(
            prompt=prompt.template_content,
            resume=resume_text,
            job_description=req.detailed_description
        )

        # Store analysis
        analysis = await self.db.create_analysis(
            application_id=app.id,
            risk_score=response.risk_score,
            relevance_summary=response.relevance_summary,
            pros=response.pros,
            cons=response.cons,
            red_flags=response.red_flags,
            suggested_questions=response.suggested_questions,
            raw_response=response.raw
        )

        # Update application status
        await self.db.update_application(app.id, status='analyzed')

        # Check if auto-send interview is enabled
        if req.auto_send_interview:
            await self.queue.enqueue('send_interview', app.id)
```

---

### 3. SendInterviewProcessor

Creates and sends self-service interview invitation.

**Input:** Application ID
**Output:** Interview record, email sent

**Steps:**
1. Generate secure token
2. Create interview record
3. Build interview URL
4. Send email via SES
5. Update application status

```python
class SendInterviewProcessor:
    async def process(self, application_id: int):
        app = await self.db.get_application(application_id)
        req = await self.db.get_requisition(app.requisition_id)

        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires = datetime.now(UTC) + timedelta(days=7)

        # Get interview context from analysis
        analysis = await self.db.get_analysis(app.id)

        # Create interview
        interview = await self.db.create_interview(
            application_id=app.id,
            token=token,
            token_expires_at=expires,
            status='scheduled'
        )

        # Build URL
        url = f"{settings.FRONTEND_URL}/interview/{token}"

        # Send email
        await self.email.send_interview_invite(
            to=app.candidate_email,
            candidate_name=app.candidate_name,
            position=req.name,
            interview_url=url,
            recruiter=req.recruiter
        )

        # Update application
        await self.db.update_application(app.id, status='interview_pending')
```

---

### 4. EvaluateProcessor

Evaluates completed interview and generates scores.

**Input:** Interview ID
**Output:** Evaluation record with scores

**Trigger:** Called when interview status changes to `completed`

```python
class EvaluateProcessor:
    async def process(self, interview_id: int):
        interview = await self.db.get_interview(interview_id)
        messages = await self.db.get_interview_messages(interview_id)

        # Build transcript
        transcript = self.format_transcript(messages)

        # Get evaluation prompt
        prompt = await self.prompts.get_active('evaluation')

        # Call Claude for evaluation
        response = await self.claude.evaluate(
            prompt=prompt.template_content,
            transcript=transcript
        )

        # Store evaluation
        evaluation = await self.db.create_evaluation(
            interview_id=interview.id,
            reliability_score=response.reliability,
            accountability_score=response.accountability,
            professionalism_score=response.professionalism,
            communication_score=response.communication,
            technical_score=response.technical,
            growth_potential_score=response.growth_potential,
            overall_score=self.compute_overall(response),
            summary=response.summary,
            strengths=response.strengths,
            weaknesses=response.weaknesses,
            red_flags=response.red_flags,
            recommendation=response.recommendation,
            transcript=transcript
        )

        # Update application
        app = await self.db.get_application(interview.application_id)
        await self.db.update_application(app.id, status='interview_complete')

        # Queue report generation
        await self.queue.enqueue('generate_report', app.id)
```

---

### 5. GenerateReportProcessor

Generates PDF candidate report.

**Input:** Application ID
**Output:** PDF report in S3

```python
class GenerateReportProcessor:
    async def process(self, application_id: int):
        app = await self.db.get_application(application_id)
        analysis = await self.db.get_analysis(app.id)
        interview = await self.db.get_interview_for_application(app.id)
        evaluation = await self.db.get_evaluation(interview.id) if interview else None

        # Generate PDF
        pdf_bytes = await self.pdf_generator.generate(
            application=app,
            analysis=analysis,
            evaluation=evaluation
        )

        # Upload to S3
        s3_key = await self.s3.upload_report(app.id, pdf_bytes)

        # Create report record
        report = await self.db.create_report(
            application_id=app.id,
            s3_key=s3_key,
            includes_analysis=True,
            includes_interview=evaluation is not None
        )

        # Update application status
        await self.db.update_application(app.id, status='report_pending')

        # Queue Workday upload
        await self.queue.enqueue('upload_report', app.id)
```

---

### 6. UploadReportProcessor

Uploads report to Workday as candidate attachment.

**Input:** Application ID
**Output:** Report uploaded, application complete

```python
class UploadReportProcessor:
    async def process(self, application_id: int):
        app = await self.db.get_application(application_id)
        report = await self.db.get_report(app.id)

        # Download from S3
        pdf_bytes = await self.s3.download(report.s3_key)

        # Upload to Workday
        doc_id = await self.workday.upload_attachment(
            candidate_id=app.external_candidate_id,
            filename=f"CandidateReport_{app.id}.pdf",
            content=pdf_bytes,
            content_type="application/pdf"
        )

        # Update report record
        await self.db.update_report(
            report.id,
            uploaded_to_workday=True,
            workday_document_id=doc_id
        )

        # Mark application complete
        await self.db.update_application(app.id, status='complete')
```

---

## Pipeline Flow

Complete flow for a single application:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        APPLICATION PIPELINE                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐│
│  │  sync   │───▶│ analyze │───▶│  send   │───▶│evaluate │───▶│ report  ││
│  │         │    │         │    │interview│    │         │    │         ││
│  └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘│
│       │              │              │              │              │      │
│       ▼              ▼              ▼              ▼              ▼      │
│    new           analyzed      interview     interview      complete    │
│                               _pending       _complete                   │
│                                    │                                     │
│                                    ▼                                     │
│                              [Candidate takes                            │
│                               interview via                              │
│                               self-service UI]                           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Error Handling

### Retry Strategy

| Error Type | Retry | Backoff | Max Attempts |
|------------|-------|---------|--------------|
| Network/API timeout | Yes | Exponential | 5 |
| Workday rate limit | Yes | Fixed 60s | 10 |
| Claude API error | Yes | Exponential | 3 |
| S3 upload failure | Yes | Exponential | 5 |
| Parse/extraction error | No | - | 1 |
| Validation error | No | - | 1 |

### Dead Letter Handling

Jobs that fail max attempts go to dead letter:
- Admin can view in UI
- Manual retry option
- Mark as skipped option

---

## Configuration

### Environment Variables

```bash
# Scheduler
SCHEDULER_INTERVAL=60           # Seconds between checks
LOOKBACK_HOURS_DEFAULT=24       # Default lookback window

# Queue
QUEUE_MAX_CONCURRENCY=3         # Parallel job limit
QUEUE_MAX_ATTEMPTS=3            # Default retry limit

# Workday
WORKDAY_TENANT_URL=https://services1.wd503.myworkday.com
WORKDAY_TENANT_ID=ccfs
WORKDAY_CLIENT_ID=...
WORKDAY_CLIENT_SECRET=...       # Encrypted
WORKDAY_REFRESH_TOKEN=...       # Encrypted

# Claude AI
ANTHROPIC_API_KEY=...
CLAUDE_MODEL=claude-3-opus-20240229

# S3
S3_BUCKET=airecruiter-artifacts
AWS_REGION=us-east-1

# Email
SES_FROM_EMAIL=noreply@example.com
SES_FROM_NAME=AIRecruiter

# Frontend
FRONTEND_URL=https://recruiter.example.com
```

---

## Monitoring

### Health Check Endpoint

`GET /health/processor`

```json
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "queue": {
    "pending": 5,
    "running": 2,
    "failed": 0,
    "dead": 0
  },
  "last_successful_job": "2025-01-15T10:30:00Z",
  "workday_connected": true
}
```

### Heartbeat File

Processor writes heartbeat to `/tmp/airecruiter_heartbeat` every 30 seconds:

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "pid": 12345,
  "status": "running",
  "last_activity": "Processed 3 candidates for Req-123"
}
```

---

## Differences from v1

| Aspect | v1 | v2 |
|--------|----|----|
| Provider support | UltiPro + Workday | Workday only |
| Browser automation | Playwright for UltiPro | None (API only) |
| MFA handling | WebSocket flow | N/A (OAuth2) |
| Queue | Simple in-memory | PostgreSQL-backed |
| Job types | Monolithic callback | Discrete processors |
| Error handling | Mixed | Explicit retry policies |
| Monitoring | Basic logging | Health endpoints + heartbeat |
# API Design

RESTful API design for AIRecruiter v2. Built with FastAPI.

---

## Design Principles

1. **RESTful** - Resources as nouns, HTTP verbs for actions
2. **Consistent** - Uniform response format, error handling
3. **Paginated** - All list endpoints paginated by default
4. **Documented** - OpenAPI/Swagger auto-generated
5. **Versioned** - `/api/v1/` prefix

---

## Authentication

### JWT Authentication

All endpoints except public interview require JWT authentication.

```
Authorization: Bearer <jwt_token>
```

Token obtained via `/api/v1/auth/login` (implementation depends on SSO strategy).

### Public Interview Token

Self-service interview endpoints use token-based auth:

```
GET /api/v1/public/interviews/{token}
POST /api/v1/public/interviews/{token}/messages
```

---

## Response Format

### Success Response

```json
{
  "data": { ... },
  "meta": {
    "page": 1,
    "perPage": 20,
    "total": 100,
    "totalPages": 5
  }
}
```

### Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid requisition ID",
    "details": {
      "field": "requisition_id",
      "reason": "must be a positive integer"
    }
  }
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (successful delete) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict (duplicate) |
| 422 | Unprocessable Entity |
| 500 | Internal Server Error |

---

## Endpoints

### Requisitions

#### List Requisitions
```
GET /api/v1/requisitions
```

Query Parameters:
- `page` (int, default: 1)
- `perPage` (int, default: 20, max: 100)
- `search` (string) - Search name/description
- `recruiter_id` (int) - Filter by recruiter
- `is_active` (bool) - Filter by active status
- `sort` (string) - Field to sort by
- `order` (asc|desc)

Response:
```json
{
  "data": [
    {
      "id": 1,
      "externalId": "REQ-2025-001",
      "name": "Senior Software Engineer",
      "location": "Remote",
      "recruiterId": 5,
      "recruiterName": "Jane Smith",
      "isActive": true,
      "autoSendInterview": true,
      "applicationCount": 45,
      "pendingCount": 12,
      "lastSyncedAt": "2025-01-15T10:00:00Z",
      "createdAt": "2025-01-01T00:00:00Z"
    }
  ],
  "meta": { "page": 1, "perPage": 20, "total": 50 }
}
```

#### Get Requisition
```
GET /api/v1/requisitions/{id}
```

Response:
```json
{
  "data": {
    "id": 1,
    "externalId": "REQ-2025-001",
    "name": "Senior Software Engineer",
    "description": "We're looking for...",
    "detailedDescription": "Full job description...",
    "location": "Remote",
    "recruiterId": 5,
    "isActive": true,
    "minCheckInterval": 15,
    "lookbackHours": null,
    "interviewInstructions": "Focus on system design...",
    "autoSendInterview": true,
    "autoSendOnStatus": null,
    "lastSyncedAt": "2025-01-15T10:00:00Z",
    "workdayData": { ... },
    "createdAt": "2025-01-01T00:00:00Z",
    "updatedAt": "2025-01-15T10:00:00Z"
  }
}
```

#### Update Requisition
```
PATCH /api/v1/requisitions/{id}
```

Body:
```json
{
  "isActive": true,
  "recruiterId": 5,
  "minCheckInterval": 30,
  "interviewInstructions": "Updated instructions...",
  "autoSendInterview": true
}
```

#### Sync Requisition
```
POST /api/v1/requisitions/{id}/sync
```

Triggers manual sync from Workday.

Response:
```json
{
  "data": {
    "status": "queued",
    "queueItemId": 123
  }
}
```

---

### Applications

#### List Applications
```
GET /api/v1/applications
```

Query Parameters:
- `page`, `perPage`
- `requisition_id` (int)
- `status` (string) - Filter by status
- `search` (string) - Search candidate name
- `date_from`, `date_to` (ISO date)

Response:
```json
{
  "data": [
    {
      "id": 100,
      "requisitionId": 1,
      "requisitionName": "Senior Software Engineer",
      "externalApplicationId": "APP-12345",
      "candidateName": "John Doe",
      "candidateEmail": "john@example.com",
      "status": "analyzed",
      "workdayStatus": "Screen",
      "hasAnalysis": true,
      "hasInterview": false,
      "hasReport": false,
      "riskScore": 0.25,
      "humanRequested": false,
      "complianceReview": false,
      "createdAt": "2025-01-14T08:00:00Z"
    }
  ],
  "meta": { ... }
}
```

#### Get Application
```
GET /api/v1/applications/{id}
```

Response includes full analysis and interview data.

#### Get Application Analysis
```
GET /api/v1/applications/{id}/analysis
```

Response:
```json
{
  "data": {
    "id": 50,
    "applicationId": 100,
    "riskScore": 0.25,
    "relevanceSummary": "Strong match for role...",
    "pros": ["5+ years Python", "System design experience"],
    "cons": ["No management experience"],
    "redFlags": [],
    "suggestedQuestions": ["Tell me about a complex system you designed"],
    "complianceFlags": [],
    "createdAt": "2025-01-14T08:30:00Z"
  }
}
```

#### Reprocess Application
```
POST /api/v1/applications/{id}/reprocess
```

Re-runs analysis pipeline.

---

### Interviews

#### List Interviews
```
GET /api/v1/interviews
```

Query Parameters:
- `status` (scheduled|in_progress|completed|abandoned|expired)
- `requisition_id`
- `date_from`, `date_to`

#### Get Interview
```
GET /api/v1/interviews/{id}
```

Response:
```json
{
  "data": {
    "id": 75,
    "applicationId": 100,
    "candidateName": "John Doe",
    "requisitionName": "Senior Software Engineer",
    "interviewType": "self_service",
    "status": "completed",
    "token": "abc123...",
    "tokenExpiresAt": "2025-01-21T08:00:00Z",
    "humanRequested": false,
    "createdAt": "2025-01-14T09:00:00Z",
    "startedAt": "2025-01-14T10:00:00Z",
    "completedAt": "2025-01-14T10:45:00Z",
    "messageCount": 24
  }
}
```

#### Get Interview Messages
```
GET /api/v1/interviews/{id}/messages
```

Response:
```json
{
  "data": [
    {
      "id": 1,
      "role": "assistant",
      "content": "Hello! Let's start the interview...",
      "createdAt": "2025-01-14T10:00:00Z"
    },
    {
      "id": 2,
      "role": "user",
      "content": "Hi, I'm excited to be here.",
      "createdAt": "2025-01-14T10:00:30Z"
    }
  ]
}
```

#### Get Interview Evaluation
```
GET /api/v1/interviews/{id}/evaluation
```

Response:
```json
{
  "data": {
    "id": 30,
    "interviewId": 75,
    "reliabilityScore": 8,
    "accountabilityScore": 7,
    "professionalismScore": 9,
    "communicationScore": 8,
    "technicalScore": 7,
    "growthPotentialScore": 8,
    "overallScore": 78,
    "summary": "Strong candidate with...",
    "strengths": ["Clear communication", "Problem-solving"],
    "weaknesses": ["Limited leadership experience"],
    "redFlags": [],
    "recommendation": "hire",
    "nextInterviewFocus": ["Leadership scenarios"],
    "createdAt": "2025-01-14T11:00:00Z"
  }
}
```

#### Create Interview (Manual)
```
POST /api/v1/interviews
```

Body:
```json
{
  "applicationId": 100,
  "personaId": 1
}
```

Creates and sends interview invite.

#### Send Interview Invite
```
POST /api/v1/interviews/{id}/send-invite
```

Resends interview invitation email.

---

### Public Interview (No Auth)

#### Get Interview Info
```
GET /api/v1/public/interviews/{token}
```

Returns interview context for candidate.

Response:
```json
{
  "data": {
    "candidateName": "John",
    "positionTitle": "Senior Software Engineer",
    "companyName": "ACME Corp",
    "status": "scheduled",
    "expiresAt": "2025-01-21T08:00:00Z"
  }
}
```

#### Start Interview
```
POST /api/v1/public/interviews/{token}/start
```

#### Send Message
```
POST /api/v1/public/interviews/{token}/messages
```

Body:
```json
{
  "content": "My answer to your question..."
}
```

Response (streaming or complete):
```json
{
  "data": {
    "userMessage": {
      "id": 100,
      "role": "user",
      "content": "My answer..."
    },
    "assistantMessage": {
      "id": 101,
      "role": "assistant",
      "content": "Thank you for that answer..."
    },
    "isComplete": false
  }
}
```

#### Request Human Contact
```
POST /api/v1/public/interviews/{token}/request-human
```

---

### Recruiters

#### List Recruiters
```
GET /api/v1/recruiters
```

#### Create Recruiter
```
POST /api/v1/recruiters
```

Body:
```json
{
  "name": "Jane Smith",
  "email": "jane@company.com",
  "phone": "555-1234",
  "title": "Senior Recruiter",
  "publicContactInfo": "Jane Smith\nSenior Recruiter\n555-1234"
}
```

#### Update Recruiter
```
PATCH /api/v1/recruiters/{id}
```

#### Delete Recruiter
```
DELETE /api/v1/recruiters/{id}
```

---

### Prompts

#### List Prompts
```
GET /api/v1/prompts
```

Query Parameters:
- `prompt_type` (resume_analysis|interview|evaluation|interview_email)
- `requisition_id` (int, optional)

#### Get Prompt
```
GET /api/v1/prompts/{id}
```

#### Create Prompt
```
POST /api/v1/prompts
```

Body:
```json
{
  "name": "Technical Resume Analysis",
  "promptType": "resume_analysis",
  "templateContent": "You are an AI recruiter...",
  "schemaContent": "{ \"type\": \"object\" ... }",
  "requisitionId": null,
  "isDefault": true
}
```

#### Update Prompt
```
PATCH /api/v1/prompts/{id}
```

#### Delete Prompt
```
DELETE /api/v1/prompts/{id}
```

---

### Interview Personas

#### List Personas
```
GET /api/v1/personas
```

#### Create Persona
```
POST /api/v1/personas
```

Body:
```json
{
  "name": "Friendly Interviewer",
  "description": "A warm, encouraging interview style",
  "systemPromptTemplate": "You are a friendly AI interviewer...",
  "isDefault": false
}
```

#### Update Persona
```
PATCH /api/v1/personas/{id}
```

#### Delete Persona
```
DELETE /api/v1/personas/{id}
```

---

### Credentials

#### Get Credential Status
```
GET /api/v1/credentials/status
```

Response:
```json
{
  "data": {
    "hasCredentials": true,
    "isValid": true,
    "tenantId": "ccfs",
    "lastValidated": "2025-01-15T10:00:00Z",
    "expiresAt": "2025-01-15T11:00:00Z"
  }
}
```

#### Save Credentials
```
POST /api/v1/credentials
```

Body:
```json
{
  "tenantUrl": "https://services1.wd503.myworkday.com",
  "tenantId": "ccfs",
  "clientId": "...",
  "clientSecret": "...",
  "refreshToken": "..."
}
```

#### Test Credentials
```
POST /api/v1/credentials/test
```

Tests connection to Workday.

#### Delete Credentials
```
DELETE /api/v1/credentials
```

---

### Settings

#### Get All Settings
```
GET /api/v1/settings
```

Response:
```json
{
  "data": {
    "lookbackHoursDefault": 24,
    "lookbackHoursMin": 1,
    "lookbackHoursMax": 168,
    "interviewTokenExpiryDays": 7,
    "emailFromAddress": "noreply@company.com",
    "emailFromName": "AIRecruiter",
    "defaultRecruiterId": 1
  }
}
```

#### Update Settings
```
PATCH /api/v1/settings
```

Body:
```json
{
  "lookbackHoursDefault": 48,
  "defaultRecruiterId": 2
}
```

---

### Queue

#### Get Queue Status
```
GET /api/v1/queue
```

Response:
```json
{
  "data": {
    "pending": 5,
    "running": 2,
    "failed": 1,
    "dead": 0,
    "items": [
      {
        "id": 100,
        "jobType": "analyze",
        "applicationId": 500,
        "requisitionName": "Senior Engineer",
        "status": "running",
        "priority": 0,
        "attempts": 1,
        "createdAt": "2025-01-15T10:00:00Z",
        "startedAt": "2025-01-15T10:01:00Z"
      }
    ]
  }
}
```

#### Add to Queue (Manual)
```
POST /api/v1/queue
```

Body:
```json
{
  "jobType": "sync",
  "requisitionId": 1,
  "priority": 10
}
```

#### Retry Failed Item
```
POST /api/v1/queue/{id}/retry
```

#### Clear Completed
```
DELETE /api/v1/queue/completed
```

#### Clear All
```
DELETE /api/v1/queue
```

---

### Logs

#### Get Logs
```
GET /api/v1/logs
```

Query Parameters:
- `page`, `perPage`
- `level` (DEBUG|INFO|WARNING|ERROR)
- `requisition_id`
- `application_id`
- `date_from`, `date_to`
- `search` (string)

Response:
```json
{
  "data": [
    {
      "id": 1000,
      "level": "INFO",
      "message": "Successfully processed candidate John Doe",
      "source": "processor",
      "requisitionId": 1,
      "applicationId": 100,
      "extra": { "duration_ms": 1500 },
      "createdAt": "2025-01-15T10:05:00Z"
    }
  ],
  "meta": { ... }
}
```

---

### Health & Metrics

#### Health Check
```
GET /api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "database": "connected",
  "workday": "connected",
  "processor": "running"
}
```

#### Metrics
```
GET /api/v1/metrics
```

Response:
```json
{
  "data": {
    "applications": {
      "total": 1500,
      "last24h": 45,
      "last7d": 320,
      "byStatus": {
        "new": 12,
        "analyzing": 3,
        "analyzed": 89,
        "complete": 1350
      }
    },
    "interviews": {
      "total": 800,
      "completed": 750,
      "abandoned": 30,
      "pending": 20
    },
    "lastProcessed": "2025-01-15T10:30:00Z"
  }
}
```

---

## WebSocket Endpoints

### Interview Chat (Real-time)

```
WS /api/v1/ws/interviews/{token}
```

Messages:
```json
// Client -> Server
{"type": "message", "content": "My answer..."}
{"type": "request_human"}

// Server -> Client
{"type": "message", "role": "assistant", "content": "...", "isComplete": false}
{"type": "interview_complete"}
{"type": "error", "message": "..."}
```

---

## Rate Limiting

| Endpoint Pattern | Limit |
|-----------------|-------|
| `/api/v1/public/*` | 60/min per IP |
| `/api/v1/*` | 300/min per user |
| `/api/v1/credentials/*` | 10/min per user |

---

## API Versioning

Current version: `v1`

Breaking changes will increment version. Old versions deprecated with 6-month notice.
# ADR 001: Workday-Only TMS Support

**Status:** Accepted
**Date:** 2025-01-15

## Context

AIRecruiter v1 supported multiple TMS providers (UltiPro and Workday) through an abstraction layer. This introduced:

- Complex multi-provider architecture with unified/legacy modes
- Browser automation (Playwright) for UltiPro due to lack of clean API
- MFA session management via WebSockets
- Significant code complexity

The organization has migrated to Workday as the primary TMS.

## Decision

AIRecruiter v2 will support **Workday only**.

## Consequences

### Positive

1. **Simplified Architecture**: No provider abstraction layer needed
2. **Clean API Integration**: Workday SOAP API only, no browser automation
3. **Reduced Complexity**: Single code path for all TMS operations
4. **Easier Maintenance**: Less code to maintain and test
5. **Better Reliability**: No MFA/session management issues

### Negative

1. **Not Extensible**: Adding another TMS would require significant work
2. **Vendor Lock-in**: Tightly coupled to Workday

### Mitigations

- Design internal interfaces cleanly so future provider support is possible
- Keep Workday-specific code isolated in `integrations/workday/` module
# ADR 002: Microsoft SQL Server Database

**Status:** Accepted
**Date:** 2025-01-15

## Context

v1 used PostgreSQL. The organization has standardized on Microsoft SQL Server for enterprise applications.

## Decision

AIRecruiter v2 will use **Microsoft SQL Server** as the database.

## Consequences

### Positive

1. **Enterprise Standards**: Aligns with organization's database standards
2. **Support**: Existing DBA support and tooling
3. **Integration**: Easier integration with other enterprise systems
4. **Familiar**: Development team has SQL Server expertise

### Negative

1. **JSON Handling**: Less elegant than PostgreSQL's native JSONB
2. **ORM Differences**: SQLAlchemy has some PostgreSQL-specific features
3. **Licensing**: SQL Server requires licenses (organization has them)

### Implementation Notes

- Use `NVARCHAR(MAX)` for JSON storage
- Use SQL Server 2016+ for JSON functions
- SQLAlchemy dialect: `mssql+pyodbc`
- Use `DATETIME2` for timestamps (higher precision than `DATETIME`)
# ADR 003: Shared S3 Storage with v1

**Status:** Accepted
**Date:** 2025-01-15

## Context

AIRecruiter v1 stores artifacts (resumes, analyses, reports) in S3. Creating a new bucket would require data migration and increased costs.

## Decision

v2 will **share the same S3 bucket** as v1, using a different prefix.

## Implementation

- v1 prefix: `requisitions/{req_id}/applicants/{app_id}/`
- v2 prefix: `airecruiter2/{req_id}/applications/{app_id}/`

## Consequences

### Positive

1. **No Migration**: Existing artifacts remain accessible
2. **Cost Efficient**: Single bucket, single set of policies
3. **Parallel Operation**: v1 and v2 can run simultaneously during transition

### Negative

1. **Collision Risk**: Must ensure prefixes don't overlap
2. **Cleanup Complexity**: Need to track which artifacts belong to which version
3. **Permissions**: Both versions need access to same bucket

### Mitigations

- Clear prefix separation (`airecruiter2/`)
- Document artifact paths in database
- Consider lifecycle policies for old v1 artifacts after migration
# ADR 004: Domain Terminology Cleanup

**Status:** Accepted
**Date:** 2025-01-15

## Context

v1 had inconsistent terminology that caused confusion:

- `ProcessingRecord` (implementation-focused, not domain-correct)
- `ATSCredentials` (should be TMS, not ATS)
- `requisition_id` and `requisition_pk` (confusing dual identifiers)
- `applicant_id` vs `candidate_id` (Workday uses these differently)
- `overall_score` used in both resume analysis and interview evaluation

## Decision

Establish clear terminology documented in `docs/architecture/terminology.md`.

Key renames:

| v1 Term | v2 Term |
|---------|---------|
| `ProcessingRecord` | `Application` |
| `ATSCredentials` | `Credential` |
| `requisition_pk` | `id` |
| `requisition_id` (external) | `external_id` |
| `applicant_id` | `external_application_id` |
| `overall_score` (resume) | `risk_score` |

## Consequences

### Positive

1. **Clarity**: Domain-aligned naming
2. **Consistency**: Single term per concept
3. **Workday Alignment**: Matches Workday's own terminology
4. **Easier Onboarding**: New developers understand quickly

### Negative

1. **Migration Effort**: Must map old terms to new in migration
2. **Documentation Updates**: All docs need new terms
# ADR 005: Queue-Based Processing Pipeline

**Status:** Accepted
**Date:** 2025-01-15

## Context

v1 used a monolithic processor with a single callback function that handled all stages. This made:

- Error handling difficult
- Retry logic complex
- Pipeline stages tightly coupled
- Monitoring challenging

## Decision

v2 uses a **queue-based pipeline** with discrete job processors:

1. `sync` - Fetch from Workday
2. `analyze` - AI resume analysis
3. `send_interview` - Create and email interview
4. `evaluate` - Score completed interview
5. `generate_report` - Create PDF
6. `upload_report` - Push to Workday

Each job is independent and queued separately.

## Implementation

- **Queue**: Database table (`jobs`)
  - Worker polls for `status = 'pending'` with `UPDLOCK, READPAST` to avoid contention
  - Simple, no extra dependencies
  - UI can view/prioritize queue directly
- **Retry**: Configurable max attempts with exponential backoff
- **Dead letter**: Jobs with `status = 'failed'` after max retries

## Consequences

### Positive

1. **Resilience**: Failed jobs don't block others
2. **Visibility**: Clear queue status in UI
3. **Retry Logic**: Per-job-type retry configuration
4. **Monitoring**: Easy to track job success/failure rates
5. **Scalability**: Could add more workers in future

### Negative

1. **Complexity**: More moving parts than monolithic
2. **Latency**: Jobs wait in queue vs immediate processing
3. **State Management**: Must track progress across jobs

### Mitigations

- Simple single-worker implementation initially
- Clear job state transitions
- Comprehensive logging per job
# ADR 006: API-Only Integration (No Browser Automation)

**Status:** Accepted
**Date:** 2025-01-15

## Context

v1 used Playwright browser automation for UltiPro because:
- UltiPro lacked a clean API
- Required MFA session management
- Needed to scrape certain data

This was fragile and maintenance-intensive.

## Decision

v2 will use **API-only integration** with Workday. No browser automation.

Workday provides:
- SOAP API for Recruiting (requisitions, candidates, applications)
- OAuth 2.0 authentication with refresh tokens
- Document upload via API

## Consequences

### Positive

1. **Reliability**: APIs are stable, UIs change frequently
2. **Performance**: API calls faster than browser automation
3. **Simpler Deployment**: No headless browser dependencies
4. **No MFA Issues**: OAuth handles authentication cleanly
5. **Testable**: APIs easy to mock in tests

### Negative

1. **API Limitations**: Some data may not be available via API
2. **SOAP Complexity**: Workday uses SOAP, not REST, for Recruiting

### Dependencies

- `zeep` library for SOAP
- `httpx` for HTTP client
- Workday Integration System User (ISU) with proper permissions
# ADR 007: Logging Strategy

**Status:** Accepted
**Date:** 2025-01-15

## Context

v1 stored logs in the PostgreSQL database. This caused:

- Database growth (logs are high volume)
- Query performance degradation
- Latency on every operation
- Mixed concerns (operational logs vs. business data)

## Decision

v2 uses **structured logging to CloudWatch**, not database tables.

### Log Types

| Type | Destination | Purpose |
|------|-------------|---------|
| Application logs | CloudWatch Logs | Debugging, operations |
| Error tracking | CloudWatch + alerts | Incident response |
| Audit trail | `activities` table | Business-relevant events |

### What Goes Where

**CloudWatch Logs** (high volume, operational):
- Debug/info messages
- API request logs
- Worker job execution logs
- Performance metrics
- Errors with stack traces

**Activities Table** (low volume, business):
- "Application status changed to X"
- "Interview sent to candidate"
- "Report uploaded to Workday"
- User actions (recruiter marked as reviewed)

## Implementation

```python
# Structured logging to CloudWatch
import structlog

log = structlog.get_logger()
log.info("processing_application",
         application_id=123,
         requisition_id=456,
         stage="analyze")

# Business activity tracking (goes to DB)
await ActivityService.record(
    application_id=123,
    action="status_changed",
    details={"from": "new", "to": "analyzed"}
)
```

## Consequences

### Positive

1. **Database stays lean**: No unbounded log growth
2. **Better tooling**: CloudWatch has search, dashboards, alerts
3. **Separation of concerns**: Ops logs vs. business audit
4. **Cost effective**: CloudWatch is cheaper than DB storage

### Negative

1. **Two places to look**: CloudWatch + DB for full picture
2. **AWS dependency**: Requires CloudWatch access

### Mitigations

- Clear conventions on what goes where
- CloudWatch Logs Insights for searching
- Activities table for user-visible history
