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
