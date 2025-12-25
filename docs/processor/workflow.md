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
4. For each application from Workday:
   - **New**: Create application record (status: `new`), download resume, queue analysis
   - **Existing**: Update `workday_status` if changed (for auto-send trigger)
   - Download resume attachment (new only)
   - Store resume in S3 (new only)

```python
class SyncProcessor:
    async def process(self, requisition_id: int):
        req = await self.db.get_requisition(requisition_id)

        # Get applications from Workday
        apps = await self.workday.get_candidates(req.external_id)

        for app in apps:
            existing = await self.db.get_application_by_external_id(
                app.external_application_id
            )

            if existing:
                # UPDATE existing application if Workday status changed
                if existing.workday_status != app.workday_status:
                    await self.db.update_application(
                        existing.id,
                        workday_status=app.workday_status,
                        workday_status_changed=datetime.now(UTC)
                    )
                    # Log activity
                    await self.activity.record(
                        application_id=existing.id,
                        action='workday_status_changed',
                        details={'from': existing.workday_status, 'to': app.workday_status}
                    )
                    # Check if auto-send interview should trigger
                    if (req.auto_send_interview and
                        req.auto_send_on_status == app.workday_status and
                        existing.status == 'analyzed'):
                        await self.queue.enqueue('send_interview', existing.id)
                continue

            # CREATE new application
            new_app = await self.db.create_application(
                requisition_id=req.id,
                external_application_id=app.external_application_id,
                external_candidate_id=app.external_candidate_id,
                candidate_name=app.candidate_name,
                candidate_email=app.candidate_email,
                workday_status=app.workday_status,
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
