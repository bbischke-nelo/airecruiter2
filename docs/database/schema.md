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
             ┌──────────┐          ┌─────────────┐
             │ messages │          │ evaluations │
             └──────────┘          └─────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     prompts     │     │    personas     │     │      jobs       │
└─────────────────┘     └─────────────────┘     └─────────────────┘

┌─────────────────┐     ┌─────────────────┐
│    settings     │     │   activities    │
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
    id                  INT IDENTITY(1,1) PRIMARY KEY,
    application_id      INT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    -- Scores (0-100 scale, consistent with evaluations)
    risk_score          INT CHECK (risk_score BETWEEN 0 AND 100),

    -- Structured output
    relevance_summary   NVARCHAR(MAX),                      -- Job fit assessment
    pros                NVARCHAR(MAX) DEFAULT '[]',         -- JSON: ["Strong Python", ...]
    cons                NVARCHAR(MAX) DEFAULT '[]',         -- JSON: ["No management exp", ...]
    red_flags           NVARCHAR(MAX) DEFAULT '[]',         -- JSON: ["Employment gap", ...]

    -- AI-generated content
    suggested_questions NVARCHAR(MAX) DEFAULT '[]',         -- JSON: Interview questions
    compliance_flags    NVARCHAR(MAX) DEFAULT '[]',         -- JSON: Legal/ethical concerns

    -- Raw AI response
    raw_response        NVARCHAR(MAX),                      -- JSON: Full AI output for debugging

    -- Prompt used
    prompt_id           INT REFERENCES prompts(id),

    -- Metadata
    model_version       VARCHAR(50),                        -- claude-3-opus, etc.
    created_at          DATETIME2 DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_analyses_application UNIQUE (application_id)
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
    id                  INT IDENTITY(1,1) PRIMARY KEY,
    application_id      INT NOT NULL REFERENCES applications(id),

    -- Type
    interview_type      VARCHAR(20) DEFAULT 'self_service',  -- self_service, admin

    -- Self-service access
    token               VARCHAR(64) UNIQUE,
    token_expires_at    DATETIME2,

    -- Status
    status              VARCHAR(50) DEFAULT 'scheduled',
    -- scheduled, in_progress, completed, abandoned, expired

    -- Configuration
    persona_id          INT REFERENCES personas(id),

    -- Flags
    human_requested     BIT DEFAULT 0,
    human_requested_at  DATETIME2,

    -- Timestamps
    created_at          DATETIME2 DEFAULT GETUTCDATE(),
    started_at          DATETIME2,
    completed_at        DATETIME2,

    -- Extra context
    metadata            NVARCHAR(MAX)                        -- JSON
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
    id              INT IDENTITY(1,1) PRIMARY KEY,
    interview_id    INT NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,

    -- Message
    role            VARCHAR(20) NOT NULL,                   -- system, assistant, user
    content         NVARCHAR(MAX),

    -- Optional per-message analysis
    sentiment       DECIMAL(3,2),                           -- -1.00 to 1.00
    topics          NVARCHAR(MAX),                          -- JSON: ["salary", "remote"]

    -- Timestamp
    created_at      DATETIME2 DEFAULT GETUTCDATE()
);

CREATE INDEX idx_messages_interview ON messages(interview_id);
```

---

### evaluations

AI-generated interview evaluation scores.

```sql
CREATE TABLE evaluations (
    id                      INT IDENTITY(1,1) PRIMARY KEY,
    interview_id            INT NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,

    -- Granular scores (0-10 scale)
    reliability_score       INT CHECK (reliability_score BETWEEN 0 AND 10),
    accountability_score    INT CHECK (accountability_score BETWEEN 0 AND 10),
    professionalism_score   INT CHECK (professionalism_score BETWEEN 0 AND 10),
    communication_score     INT CHECK (communication_score BETWEEN 0 AND 10),
    technical_score         INT CHECK (technical_score BETWEEN 0 AND 10),
    growth_potential_score  INT CHECK (growth_potential_score BETWEEN 0 AND 10),

    -- Computed overall (0-100 scale)
    overall_score           INT CHECK (overall_score BETWEEN 0 AND 100),

    -- Textual analysis
    summary                 NVARCHAR(MAX),
    strengths               NVARCHAR(MAX) DEFAULT '[]',     -- JSON
    weaknesses              NVARCHAR(MAX) DEFAULT '[]',     -- JSON
    red_flags               NVARCHAR(MAX) DEFAULT '[]',     -- JSON

    -- Recommendation
    recommendation          VARCHAR(50),                    -- hire, strong_hire, no_hire, review
    next_interview_focus    NVARCHAR(MAX) DEFAULT '[]',     -- JSON: Focus areas for next round

    -- Raw AI response
    raw_response            NVARCHAR(MAX),                  -- JSON

    -- Prompt used
    prompt_id               INT REFERENCES prompts(id),

    -- Metadata
    model_version           VARCHAR(50),
    created_at              DATETIME2 DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_evaluations_interview UNIQUE (interview_id)
);

CREATE INDEX idx_evaluations_interview ON evaluations(interview_id);
CREATE INDEX idx_evaluations_recommendation ON evaluations(recommendation);
```

**Notes:**
- Transcript is NOT stored here - query `messages` table joined to `interviews`
- CHECK constraints on scores enforce valid ranges
- `raw_response` stores full AI output for debugging

---

### reports

Generated PDF reports.

```sql
CREATE TABLE reports (
    id                  INT IDENTITY(1,1) PRIMARY KEY,
    application_id      INT NOT NULL REFERENCES applications(id),

    -- Storage
    s3_key              VARCHAR(500) NOT NULL,
    file_name           VARCHAR(255),
    file_size           INT,

    -- Upload status
    uploaded_to_workday BIT DEFAULT 0,
    workday_document_id VARCHAR(255),                       -- Workday attachment ID
    uploaded_at         DATETIME2,

    -- Content included
    includes_analysis   BIT DEFAULT 1,
    includes_interview  BIT DEFAULT 1,

    -- Metadata
    created_at          DATETIME2 DEFAULT GETUTCDATE()
);

CREATE INDEX idx_reports_application ON reports(application_id);
```

---

## Configuration Tables

### prompts

AI prompt templates.

```sql
CREATE TABLE prompts (
    id                  INT IDENTITY(1,1) PRIMARY KEY,

    -- Identity
    name                VARCHAR(255) NOT NULL,
    prompt_type         VARCHAR(50) NOT NULL,
    -- resume_analysis, interview, self_service_interview, evaluation, interview_email

    -- Content
    template_content    NVARCHAR(MAX) NOT NULL,
    schema_content      NVARCHAR(MAX),                      -- JSON schema for structured output

    -- Scope
    requisition_id      INT REFERENCES requisitions(id) ON DELETE CASCADE,
    -- NULL = global, otherwise requisition-specific override

    -- Status
    is_active           BIT DEFAULT 1,
    is_default          BIT DEFAULT 0,                      -- One default per type

    -- Versioning
    version             INT DEFAULT 1,
    description         NVARCHAR(MAX),

    -- Metadata
    created_at          DATETIME2 DEFAULT GETUTCDATE(),
    updated_at          DATETIME2,
    created_by          VARCHAR(255),
    updated_by          VARCHAR(255)
);

CREATE INDEX idx_prompts_type ON prompts(prompt_type);
CREATE INDEX idx_prompts_requisition ON prompts(requisition_id);
CREATE UNIQUE INDEX idx_prompts_default ON prompts(prompt_type)
    WHERE is_default = 1 AND requisition_id IS NULL;
```

---

### personas

AI interviewer personalities.

```sql
CREATE TABLE personas (
    id                      INT IDENTITY(1,1) PRIMARY KEY,

    name                    VARCHAR(100) NOT NULL,
    description             NVARCHAR(MAX),

    -- The AI personality/system prompt
    system_prompt_template  NVARCHAR(MAX) NOT NULL,

    -- Status
    is_active               BIT DEFAULT 1,
    is_default              BIT DEFAULT 0,

    -- Metadata
    created_at              DATETIME2 DEFAULT GETUTCDATE(),
    updated_at              DATETIME2
);

CREATE UNIQUE INDEX idx_personas_default ON personas(is_default)
    WHERE is_default = 1;
```

---

### settings

System configuration key-value store.

```sql
CREATE TABLE settings (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    [key]           VARCHAR(100) NOT NULL UNIQUE,           -- 'key' is reserved in SQL Server
    value           NVARCHAR(MAX) NOT NULL,
    description     NVARCHAR(MAX),

    created_at      DATETIME2 DEFAULT GETUTCDATE(),
    updated_at      DATETIME2
);

CREATE INDEX idx_settings_key ON settings([key]);
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
    id              INT IDENTITY(1,1) PRIMARY KEY,

    name            VARCHAR(100) NOT NULL,
    template_type   VARCHAR(50) NOT NULL,                   -- interview_invite, alert

    subject         VARCHAR(500) NOT NULL,
    body_html       NVARCHAR(MAX) NOT NULL,
    body_text       NVARCHAR(MAX),

    is_active       BIT DEFAULT 1,
    is_default      BIT DEFAULT 0,

    created_at      DATETIME2 DEFAULT GETUTCDATE(),
    updated_at      DATETIME2
);
```

### email_log

```sql
CREATE TABLE email_log (
    id              INT IDENTITY(1,1) PRIMARY KEY,

    -- Recipient
    to_email        VARCHAR(255) NOT NULL,

    -- Content
    template_id     INT REFERENCES email_templates(id),
    subject         VARCHAR(500),

    -- Context
    application_id  INT REFERENCES applications(id),

    -- Status
    status          VARCHAR(50) DEFAULT 'sent',             -- sent, failed, bounced
    error           NVARCHAR(MAX),

    -- Tracking
    sent_at         DATETIME2 DEFAULT GETUTCDATE(),
    opened_at       DATETIME2,
    clicked_at      DATETIME2
);
```

---

## Migration Strategy

### Approach: Clean Break

v2 is a **clean break**, not a data migration. Reasons:
- Schema changes are substantial (field renames, new tables, removed columns)
- v1 data quality issues would carry forward
- Parallel operation allows gradual transition
- Shared S3 bucket preserves artifact access if needed

### Transition Plan

1. **Deploy v2** alongside v1 (separate database)
2. **Configure v2** with same Workday credentials
3. **Run parallel** for 1-2 weeks to validate
4. **Cut over** by disabling v1 requisitions
5. **Decommission v1** after validation period

### What Migrates

| Data | Migrate? | Method |
|------|----------|--------|
| Requisitions | No | Re-sync from Workday |
| Active applications | No | Re-sync, reprocess if needed |
| Completed applications | No | Stay in v1 DB for reference |
| Prompts/Personas | Optional | Manual copy if customized |
| Credentials | Yes | Re-enter in v2 UI |
| S3 artifacts | Shared | Both versions access same bucket |

### Field Mapping Reference (If Migration Needed)

For reference if partial data migration is ever required:

| v1 Field | v2 Field |
|----------|----------|
| `requisition_pk` | `id` |
| `requisition_id` (string) | `external_id` |
| `min_check_interval` | `sync_interval_minutes` |
| `processing_records` | `applications` |
| `applicant_id` | `external_application_id` |
| `candidate_id` | `external_candidate_id` |
| `overall_score` (resume) | `risk_score` (in `analyses`) |
| `interview_score` | `overall_score` (in `evaluations`) |

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
