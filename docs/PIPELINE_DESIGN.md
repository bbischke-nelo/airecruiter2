# Application Processing Pipeline Design

## Overview

This document describes the application processing pipeline for the AIRecruiter system. The pipeline syncs candidates from Workday and uses AI to **extract and tabulate factual information only**. All hiring decisions are made by human recruiters.

## Legal Compliance Context

### Why Human-in-the-Loop?

Following legal developments (e.g., Mobley v. Workday class action), AI-based auto-screening presents disparate impact liability risk. Our approach:

1. **AI extracts facts** - Tabulates data from resumes (tenure, skills, gaps, certifications)
2. **AI does NOT score or rank** - No resume_score, no auto-rejection
3. **Human makes all decisions** - Recruiters use UI to advance/reject with reason codes
4. **Audit trail** - Every decision has a documented reason code

### "Glass Box" Approach

We expose extracted data transparently:
- Recruiter sees exactly what AI extracted
- Recruiter makes decision based on visible facts
- Decision + reason code logged for audit

### Safe Matching Criteria (Factual Extraction Only)

| Category | What We Extract | What We DON'T Do |
|----------|-----------------|------------------|
| **Experience** | Years at each employer, job titles, industries | Score or rank experience |
| **Skills** | Technologies, certifications, licenses mentioned | Infer skills not stated |
| **Education** | Degrees, institutions, certifications | Weight prestige |
| **Timeline** | Employment gaps, tenure at each job | Penalize gaps automatically |
| **Logistics** | Location mentioned, remote/onsite preferences | Auto-filter by location |

## LTL Industry Skills Taxonomy

For Less-Than-Truckload (LTL) freight companies, we extract these job-relevant facts:

### Driver/Operations Roles
- **Licenses**: CDL-A, CDL-B, endorsements (Hazmat, Tanker, Doubles/Triples)
- **Equipment**: Tractor-trailer, straight truck, forklift, pallet jack
- **Experience**: OTR, regional, local, dock work, P&D
- **Compliance**: DOT medical card, clean MVR, years accident-free
- **Technology**: ELD/E-Log systems, GPS/routing, TMS familiarity

### Warehouse/Dock Roles
- **Certifications**: Forklift certified, OSHA training
- **Systems**: WMS experience, RF scanner, barcode systems
- **Physical**: Ability to lift (stated in resume), standing/walking requirements
- **Environment**: Dock work, cross-dock, temperature-controlled

### Office/Administrative Roles
- **Software**: TMS (specific systems), ERP, MS Office, industry-specific
- **Functions**: Billing, claims, dispatch, customer service, sales
- **Industry**: LTL experience, 3PL experience, freight brokerage

### Management/Supervisory Roles
- **Scale**: Team size managed, budget responsibility, P&L
- **Functions**: Operations, safety, fleet, terminal management
- **Compliance**: DOT regulations, FMCSA, OSHA familiarity

## Rejection Reason Codes

Human-selected reason codes for audit trail:

| Code | Description | Notes |
|------|-------------|-------|
| `QUAL_LICENSE` | Missing required license/certification | e.g., CDL-A required |
| `QUAL_EXPERIENCE` | Does not meet minimum experience requirement | Years/type as stated in JD |
| `QUAL_SKILLS` | Missing required technical skills | Specific skill from JD |
| `QUAL_EDUCATION` | Does not meet education requirement | If explicitly required |
| `LOCATION_MISMATCH` | Unable to work at job location | Candidate indicated |
| `SCHEDULE_MISMATCH` | Unable to work required schedule | Shift/hours incompatibility |
| `SALARY_MISMATCH` | Compensation expectations misaligned | If candidate stated |
| `WITHDREW` | Candidate withdrew application | Candidate-initiated |
| `NO_RESPONSE` | No response to interview invitation | After configured days |
| `INTERVIEW_INCOMPLETE` | Did not complete AI interview | Started but abandoned |
| `INTERVIEW_PERFORMANCE` | Did not meet standards in interview | Communication, vague answers |
| `WORK_AUTHORIZATION` | Cannot provide required work authorization | Visa/sponsorship issue |
| `DID_NOT_SHOW` | Candidate did not attend scheduled interview | Live interview no-show |
| `POSITION_FILLED` | Position filled by another candidate | Role closed |
| `DUPLICATE` | Duplicate application | Same person applied again |
| `OTHER` | Other reason (requires comment) | Freeform explanation |

## Proposed Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. SYNC (intake from Workday)                                               │
│    • Fetch applications from Workday (with 1-hour lookback overlap)         │
│    • Deduplicate by external_application_id                                 │
│    • Save application to DB immediately (status='new')                      │
│    • Queue → download_resume                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. DOWNLOAD_RESUME                                                          │
│    • Set status='downloading'                                               │
│    • Download resume from Workday                                           │
│    • Save resume to S3                                                      │
│    • ATOMIC: Set status='downloaded' + queue extract_facts                  │
│    • If no resume: status='no_resume', still queue extract_facts            │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. EXTRACT_FACTS (AI tabulation - NO SCORING)                               │
│    • Set status='extracting'                                                │
│    • Claude AI extracts factual data from resume:                           │
│      - Employment history (employer, title, dates, tenure)                  │
│      - Skills mentioned (matched against taxonomy)                          │
│      - Certifications/licenses                                              │
│      - Education                                                            │
│      - Location/logistics preferences stated                                │
│    • Save extracted facts JSON to DB + S3                                   │
│    • ATOMIC: Set status='extracted' + queue generate_summary                │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. GENERATE_SUMMARY (Human-readable extraction summary)                     │
│    • Set status='generating_summary'                                        │
│    • Generate PDF summary of extracted facts (NOT a scoring report)         │
│    • Highlights: JD requirements vs extracted facts (match/gap table)       │
│    • Save summary PDF to S3                                                 │
│    • Upload summary to Workday (as candidate attachment)                    │
│    • ATOMIC: Set status='ready_for_review'                                  │
│    • [WAIT FOR HUMAN DECISION]                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. HUMAN DECISION (via UI - NOT automated)                                  │
│    Recruiter reviews application and chooses:                               │
│                                                                             │
│    [ADVANCE] → status='advancing', queue send_interview (if enabled)        │
│                or status='advanced' (if interview not enabled)              │
│                                                                             │
│    [REJECT]  → status='rejected', reason_code required                      │
│                                                                             │
│    [HOLD]    → status='on_hold', optional comment                           │
│                                                                             │
│    All actions logged with user_id, timestamp, reason_code                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓ (if advanced + interview enabled)
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. SEND_INTERVIEW (if interview enabled for requisition)                    │
│    • Set status='interview_sending'                                         │
│    • Generate interview link                                                │
│    • Send email to candidate via SES                                        │
│    • Set status='interview_sent'                                            │
│    • [Wait for candidate to complete via webhook...]                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. INTERVIEW_COMPLETED (triggered by webhook)                               │
│    • Set status='interview_received'                                        │
│    • Queue → transcribe_interview                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 8. TRANSCRIBE_INTERVIEW                                                     │
│    • Set status='transcribing'                                              │
│    • Extract interview responses and transcription                          │
│    • Claude AI summarizes responses factually (NOT scored)                  │
│    • Generate interview summary PDF                                         │
│    • Save to S3 + upload to Workday                                         │
│    • Set status='interview_ready_for_review'                                │
│    • [WAIT FOR HUMAN DECISION]                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 9. FINAL HUMAN DECISION (via UI)                                            │
│    Recruiter reviews interview and chooses:                                 │
│                                                                             │
│    [ADVANCE TO NEXT STAGE] → status='advanced', optional Workday stage update│
│                                                                             │
│    [REJECT] → status='rejected', reason_code required                       │
│                                                                             │
│    [SCHEDULE LIVE INTERVIEW] → status='live_interview_pending'              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## State Machine

### Application Status Values

| Status | Description | Auto-Queued | Human Action Required |
|--------|-------------|-------------|----------------------|
| `new` | Just synced from Workday | Yes → download_resume | No |
| `downloading` | Resume download in progress | - | No |
| `downloaded` | Resume saved to S3 | Yes → extract_facts | No |
| `no_resume` | No resume in Workday | Yes → extract_facts | No |
| `extraction_failed` | AI could not parse resume | Yes → generate_summary | No (manual review) |
| `extracting` | AI fact extraction running | - | No |
| `extracted` | Facts extracted | Yes → generate_summary | No |
| `generating_summary` | Summary PDF being created | - | No |
| `ready_for_review` | **WAITING FOR RECRUITER** | No | **YES** |
| `on_hold` | Recruiter placed on hold | No | Yes (to change) |
| `advancing` | Queued for interview send | Yes → send_interview | No |
| `advanced` | Advanced (no interview) | No | Terminal |
| `rejected` | Rejected by recruiter | No | Terminal |
| `interview_sending` | Sending interview email | - | No |
| `interview_sent` | Interview email sent | No (webhook) | No |
| `interview_expired` | Candidate didn't respond | No | Yes (retry/reject) |
| `interview_received` | Candidate completed | Yes → transcribe | No |
| `transcribing` | Processing interview | - | No |
| `interview_ready_for_review` | **WAITING FOR RECRUITER** | No | **YES** |
| `live_interview_pending` | Scheduled for live interview | No | External |
| `error` | Failed after max retries | No | Manual intervention |

### State Transition Diagram

```
new ──► downloading ──► downloaded ──► extracting ──► extracted ──► generating_summary
              │              │                                              │
              ▼              ▼                                              ▼
         [retry/error]   no_resume ─────────────────────────────►   ready_for_review
                                                                            │
                          ┌─────────────────────────────────────────────────┼─────────────────┐
                          │                                                 │                 │
                          ▼                                                 ▼                 ▼
                      on_hold                                           advancing          rejected
                                                                            │             (terminal)
                                                                            ▼
                                          ┌─────────────────► interview_sending ──► interview_sent
                                          │                                               │
                                          │                         ┌─────────────────────┼─────────────┐
                                          │                         ▼                     ▼             ▼
                                          │                   interview_expired    interview_received  (retry)
                                          │                                               │
                                          │                                               ▼
                                          │                                         transcribing
                                          │                                               │
                                          │                                               ▼
                                          │                               interview_ready_for_review
                                          │                                               │
                                          │               ┌───────────────┬───────────────┼───────────────┐
                                          │               ▼               ▼               ▼               ▼
                         (interview not enabled)     advanced         rejected    live_interview_pending
                                          │          (terminal)       (terminal)
                                          ▼
                                       advanced
                                      (terminal)
```

## Human Decision Actions

### UI Pattern: Table + Slide-Over Drawer

**Why Slide-Over instead of Modal:**
- Maintains list context (see which candidate is selected)
- Click next row without closing anything
- Enables power-review workflow with Prev/Next navigation
- Auto-advance to next candidate after action

### 1. Table View (List Screen)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Applications - Software Engineer (12 pending)     [All ▼] [Needs Review] [High Match] [Rejected]  [Search...] │
├─────┬────────────────┬─────────────┬─────────┬───────────┬──────────┬────────────┬───────────┬─────────────────┤
│ ☐   │ Candidate      │ Current Role│ Location│ Experience│ JD Match │ Avg Tenure │ Certs     │ Status          │
├─────┼────────────────┼─────────────┼─────────┼───────────┼──────────┼────────────┼───────────┼─────────────────┤
│ ☐   │ John Smith     │ Sr Dev @ XYZ│ Chicago │ 5 yrs     │ ████░░ 75%│ 2.5 yrs   │ 🔧        │ ⏳ Review       │
│ ☐   │ Sarah Johnson  │ Mgr @ ABC   │ Dallas  │ 8 yrs     │ ██████ 95%│ 4.1 yrs   │ 🚛 +2     │ ⏳ Review       │
│ ☐   │ Mike Davis     │ Dev @ Acme  │ Remote  │ 2 yrs     │ ██░░░░ 25%│ 0.7 yrs   │ —         │ ⏳ Review       │
└─────┴────────────────┴─────────────┴─────────┴───────────┴──────────┴────────────┴───────────┴─────────────────┘
                                                    ↑                      ↑
                                        Color-coded progress bar    Icon badges (🚛=CDL, 🔧=Tech, +N=more)

[Bulk Actions: ☐ Select All]  [Bulk Reject ▼]  [Bulk Hold]
```

**Table Columns:**
| Column | Data | Notes |
|--------|------|-------|
| ☐ | Checkbox | For bulk actions |
| Candidate | Name (or hash if blind) | Click to open drawer |
| Current Role | Title @ Company | Pedigree at a glance |
| Location | City or "Remote" | Time zone / commute |
| Experience | Total years | |
| JD Match | Visual progress bar + % | Color: Green >80%, Yellow 50-80%, Red <50% |
| Avg Tenure | Years | Flag if < threshold |
| Certs | Icon badges | 🚛 CDL, 🔧 Tech, ⚠️ Hazmat, +N for overflow |
| Status | Current state | |

**Quick Filters (Tabs):**
- `All` | `Needs Review` | `High Match (>80%)` | `On Hold` | `Rejected`

**Hover Peek:** Hover on JD Match shows tooltip with top 3 missing requirements

### 2. Slide-Over Drawer (Click Row)

Opens from right side. List stays visible on left. Auto-advances after action.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ [< Prev]  John Smith - Software Engineer  [Next >]                                      [X] │
│ ───────────────────────────────────────────────────────────────────────────────────────────  │
│ Applied: Dec 24 │ Sr Dev @ XYZ Logistics │ Chicago, IL                                      │
│                                                                                              │
│ [📄 Resume]  [🔗 LinkedIn]  [Activity Log]                              ← Tabs at top       │
├──────────────────────────────────┬───────────────────────────────────────────────────────────┤
│ EXTRACTED FACTS                  │ JD MATCH                                                 │
│ ────────────────                 │ ─────────                                                │
│ Experience: 5 years              │ ✓ 3+ years Python → 5 yrs found                         │
│ Current: Sr Dev @ XYZ (2.5 yrs)  │ ✓ TMS experience → McLeod, TMW                          │
│ Employers (5 yr): 2              │ ? SQL Server → "SQL" mentioned                          │
│ Avg Tenure: 2.5 years            │ ✗ AWS certification → Not found                         │
│ Location: Chicago, IL            │                                                          │
│ Certs: None listed               │ Match: 75% (3/4 required)                               │
├──────────────────────────────────┴───────────────────────────────────────────────────────────┤
│ PROS (AI-Extracted)                    │ CONS (AI-Extracted)                                │
│ • 5 yrs Python (exceeds 3yr req)       │ • AWS cert required, not found                    │
│ • TMS experience (McLeod, TMW)         │ • SQL Server not confirmed                        │
│ • Stable tenure (2.5 yr avg)           │                                                    │
├────────────────────────────────────────┴────────────────────────────────────────────────────┤
│ SUGGESTED QUESTIONS                                                                         │
│ • "You mentioned SQL - was this SQL Server specifically?"                                  │
│ • "Are you currently pursuing AWS certification?"                                          │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ INTERVIEW (if completed)                                                   [View Transcript]│
│ Key points: Discussed 3 yrs TMS integrations, mentioned Python REST APIs                   │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│ ┌───────────────┐ ┌─────────────────────┐ ┌───────────────┐ ┌────────────────────────────┐ │
│ │ ✓ ADVANCE     │ │ 📞 LIVE INTERVIEW   │ │ ⏸ HOLD       │ │ ✗ REJECT                   │ │
│ └───────────────┘ └─────────────────────┘ └───────────────┘ └────────────────────────────┘ │
│                                                                                             │
│ ⚠️ AI-Generated - Verify against resume                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3. Action Flows with Auto-Advance

**After ANY action → Auto-advance to next pending candidate**

**[✓ ADVANCE] Flow:**
```
Click [ADVANCE]
    ↓
Brief confirmation toast: "John Smith advanced ✓"
    ↓
Drawer auto-loads NEXT candidate in queue
    ↓
(Recruiter keeps reviewing without extra clicks)
```

**[✗ REJECT] Flow (Two-Step to prevent accidents):**
```
Click [REJECT]
    ↓
Action bar transforms:
┌─────────────────────────────────────────────────────────────────────────┐
│ [Select Reason ▼ ] ________________________  [Confirm] [Cancel]         │
│                    Comment (optional)                                    │
└─────────────────────────────────────────────────────────────────────────┘
    ↓
Select reason + optional comment → Click [Confirm]
    ↓
Toast: "John Smith rejected - Missing required skills"
    ↓
Auto-advance to NEXT candidate
```

**[📞 LIVE INTERVIEW] Flow:**
```
Click [LIVE INTERVIEW]
    ↓
"Skip AI interview and schedule live interview?"
    ↓
[Confirm] → Status = 'live_interview_pending', auto-advance to next
```

**[⏸ HOLD] Flow:**
```
Click [HOLD]
    ↓
Optional note field appears inline
    ↓
[Confirm] → Status = 'on_hold', auto-advance to next
```

### 4. Power User Features

**Keyboard Shortcuts:**
| Key | Action |
|-----|--------|
| `j` / `↓` | Next candidate in list |
| `k` / `↑` | Previous candidate in list |
| `Space` / `Enter` | Open drawer for selected |
| `Esc` | Close drawer |
| `a` | Advance (then confirm) |
| `r` | Reject (opens reason picker) |
| `h` | Hold |

**Bulk Actions:**
- Select multiple with checkboxes
- [Bulk Reject ▼] → Select reason → Applies to all selected
- [Bulk Hold] → Applies to all selected

### 5. Responsive Behavior

| Screen | Layout |
|--------|--------|
| Desktop (≥1024px) | Table + slide-over drawer |
| Tablet (768-1023px) | Compact table + full-screen drawer |
| Mobile (<768px) | Card list + swipe actions (left=reject, right=advance) |

## Settings & Configuration UX

### Settings Architecture

**Two-Level Configuration:**
1. **Global Settings** → System-wide defaults
2. **Requisition Overrides** → Per-job customization (null = use global)

### 1. Global Settings Page (`/settings`)

Replace card grid with organized sections:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Settings                                                                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ [Pipeline] [Interview] [Email] [Prompts] [Reports] [Recruiters] [Compliance]           │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│ PIPELINE SETTINGS                                                      [Save Changes]  │
│ ─────────────────                                                                       │
│                                                                                         │
│ Sync & Lookback                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Default lookback hours        [24    ] ▼   Hours to look back when syncing         │ │
│ │ Lookback overlap hours        [1     ] ▼   Overlap for deduplication safety        │ │
│ │ Sync interval (minutes)       [15    ] ▼   How often to sync from Workday          │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│ Interview Defaults                                                                      │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ AI Interview enabled          [○ Off  ● On]   Send AI interview by default         │ │
│ │ Interview expiry (days)       [7     ] ▼      Days before invitation expires       │ │
│ │ Auto-update Workday stage     [○ Off  ● On]   Update stage when advanced           │ │
│ │ Advance to stage              [Screen    ] ▼  Workday stage to set                 │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│ Retention Risk Thresholds (avg tenure in months)                                        │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Entry-level                   [6     ] ▼                                            │ │
│ │ Individual contributor        [9     ] ▼                                            │ │
│ │ Manager                       [12    ] ▼                                            │ │
│ │ Director+                     [18    ] ▼                                            │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Interview Tab:**
```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ INTERVIEW SETTINGS                                                     [Save Changes]  │
│ ─────────────────                                                                       │
│                                                                                         │
│ Question Bank                                                                           │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ [+ Add Question]                                                                    │ │
│ │                                                                                     │ │
│ │ ☑ exp_001  "Describe your experience with TMS systems..."        [Edit] [Delete]  │ │
│ │ ☑ exp_002  "Tell me about a time you handled a difficult..."     [Edit] [Delete]  │ │
│ │ ☑ exp_003  "What specific certifications do you hold?"           [Edit] [Delete]  │ │
│ │ ☐ exp_004  "Why are you interested in this role?" (disabled)     [Edit] [Delete]  │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│ Redirect Triggers (when to change subject)                                              │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Medical: my disability, my illness, medical leave, health issues...                │ │
│ │ Family: childcare, eldercare, maternity leave, paternity leave...                  │ │
│ │ Legal: lawsuit, discrimination, harassment, whistleblower...                       │ │
│ │                                                            [Edit Triggers]         │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│ Accommodations Text                                                                     │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Need an accommodation? We offer:                                                    │ │
│ │ • Extended time (no time limit)                                                     │ │
│ │ • Voice-to-text option                                                              │ │
│ │ • ...                                                              [Edit Text]     │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Compliance Tab:**
```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ COMPLIANCE SETTINGS                                                    [Save Changes]  │
│ ─────────────────                                                                       │
│                                                                                         │
│ Blind Hiring                                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Enable by default             [○ Off  ● On]   Redact PII from summaries            │ │
│ │                                                                                     │ │
│ │ When enabled, AI summaries redact:                                                  │ │
│ │   ☑ Candidate name → "Candidate #[hash]"                                           │ │
│ │   ☑ Address/location → "[Location withheld]"                                       │ │
│ │   ☑ School names → "[Degree] in [Field]"                                           │ │
│ │   ☑ Photo → Not included                                                           │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│ Disparate Impact Monitoring                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Enable monitoring             [○ Off  ● On]                                         │ │
│ │ Alert threshold               [80    ] %     4/5ths rule (alert if below)          │ │
│ │ Report frequency              [Quarterly] ▼                                         │ │
│ │ Send alerts to                [hr-compliance@company.com]                           │ │
│ │                                                                                     │ │
│ │ Last Report: Dec 15, 2024                              [View Report] [Run Now]     │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│ Audit Trail                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Retain decision logs          [7     ] years                                        │ │
│ │ Export format                 [CSV   ] ▼                                            │ │
│ │                                                    [Export All Decisions]          │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2. Requisition Settings (Per-Job Overrides)

On requisition detail page, Settings tab shows overrides with "Use Global" option:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Requisition Settings - Software Engineer                              [Save Changes]   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│ ℹ️ Settings override global defaults. "Use Global" inherits from system settings.      │
│                                                                                         │
│ Interview                                                                               │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ AI Interview enabled          [● Use Global (On)] [○ On] [○ Off]                    │ │
│ │ Interview expiry (days)       [● Use Global (7) ] [○ Custom: ___]                   │ │
│ │ Auto-update Workday stage     [● Use Global (On)] [○ On] [○ Off]                    │ │
│ │ Advance to stage              [● Use Global (Screen)] [○ Custom: ___]               │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│ Compliance                                                                              │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Blind hiring                  [● Use Global (Off)] [○ On] [○ Off]                   │ │
│ │ Role level (for retention)    [Individual Contributor] ▼                            │ │
│ │   → Retention threshold: 9 months (from global settings)                            │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│ Sync                                                                                    │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Sync enabled                  [● On] [○ Off]                                        │ │
│ │ Sync interval (minutes)       [● Use Global (15)] [○ Custom: ___]                   │ │
│ │ Lookback hours                [● Use Global (24)] [○ Custom: ___]                   │ │
│ │                                                                                     │ │
│ │ Last synced: Dec 24, 2024 3:45 PM                           [Sync Now]             │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│ Interview Questions (Override Global Bank)                                              │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ [● Use Global Question Bank] [○ Custom Questions]                                   │ │
│ │                                                                                     │ │
│ │ Additional Instructions for AI Interviewer:                                         │ │
│ │ ┌─────────────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ Focus on TMS experience. This role requires heavy McLeod usage.                 │ │ │
│ │ │ Ask about multi-stop routing if they mention delivery experience.               │ │ │
│ │ └─────────────────────────────────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│ JD Requirements (for matching)                                         [Auto-Extract]  │
│ ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Required:                                                                           │ │
│ │   [+ Add]  CDL-A [x]  3+ years TMS [x]  Python [x]                                 │ │
│ │                                                                                     │ │
│ │ Preferred:                                                                          │ │
│ │   [+ Add]  Hazmat endorsement [x]  AWS certification [x]                           │ │
│ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3. Settings UX Patterns

**Inline Editing:**
- No separate "Edit" mode - fields are always editable
- Changes auto-save with debounce (500ms) or explicit [Save] button
- Toast confirmation: "Settings saved ✓"

**Global vs Override Visual:**
```
[● Use Global (On)]  ← Radio selected, shows inherited value
[○ On]               ← Override options
[○ Off]

When override selected, "Use Global" label updates to show you're overriding:
[○ Use Global (On)]  ← Not selected, grayed out
[● On]               ← Override active, highlighted
[○ Off]
```

**Validation:**
- Immediate inline validation (red border + message)
- Prevent save if invalid
- Example: "Retention threshold must be > 0"

**Settings Search:**
- Global search across all settings tabs
- Highlights matching settings
- "No results for 'blind'" shows empty state with suggestions

### 4. Database Schema for Settings

```sql
-- Global settings (key-value with typed values)
CREATE TABLE global_settings (
    key VARCHAR(100) PRIMARY KEY,
    value NVARCHAR(MAX) NOT NULL,
    value_type VARCHAR(20) DEFAULT 'string',  -- string, int, bool, json
    category VARCHAR(50),                      -- pipeline, interview, compliance, email
    description NVARCHAR(500),
    updated_at DATETIME DEFAULT GETUTCDATE(),
    updated_by INT
);

-- Requisition overrides (nullable = use global)
ALTER TABLE requisitions ADD
    interview_enabled BIT NULL,
    interview_expiry_days INT NULL,
    auto_update_stage BIT NULL,
    advance_to_stage VARCHAR(50) NULL,
    blind_hiring_enabled BIT NULL,
    role_level VARCHAR(50) DEFAULT 'individual_contributor',
    custom_interview_instructions NVARCHAR(MAX) NULL,
    jd_requirements_json NVARCHAR(MAX) NULL;  -- Extracted/manual JD requirements
```

### 5. Config Resolution Logic

```python
def get_config(requisition_id: int, key: str) -> Any:
    """Get config with requisition override > global > default."""

    # Check requisition override
    req = get_requisition(requisition_id)
    override_value = getattr(req, key, None)
    if override_value is not None:
        return override_value

    # Check global setting
    global_setting = db.query(GlobalSetting).filter_by(key=key).first()
    if global_setting:
        return parse_typed_value(global_setting.value, global_setting.value_type)

    # Return default
    return DEFAULTS.get(key)

DEFAULTS = {
    'interview_enabled': False,
    'interview_expiry_days': 7,
    'auto_update_stage': False,
    'blind_hiring_enabled': False,
    'lookback_hours': 24,
    'lookback_overlap_hours': 1,
    'retention_threshold_entry': 6,
    'retention_threshold_ic': 9,
    'retention_threshold_manager': 12,
    'retention_threshold_director': 18,
}
```

### Rejection Reasons (Legally Defensible Only)

The dropdown ONLY shows job-related reasons. These are the allowed values:

| Code | Display Text | When to Use |
|------|--------------|-------------|
| `QUAL_LICENSE` | Missing required license/certification | CDL, forklift cert, etc. required by JD |
| `QUAL_EXPERIENCE` | Does not meet experience requirement | Years/type below JD minimum |
| `RETENTION_RISK` | Objective retention concern | Average tenure < 9 months over last 3 roles (math, not characterization) |
| `RECENCY_OF_SKILLS` | Skills are outdated | "Has 5 yrs Java but none in last 4 years" - factual, not gap penalty |
| `QUAL_SKILLS` | Missing required technical skills | Specific skill from JD not found |
| `QUAL_EDUCATION` | Does not meet education requirement | If JD explicitly requires degree |
| `LOCATION_MISMATCH` | Unable to work at job location | Candidate stated they can't work there |
| `SCHEDULE_MISMATCH` | Unable to work required schedule | Shift/hours incompatibility |
| `WITHDREW` | Candidate withdrew application | Candidate-initiated |
| `NO_RESPONSE` | No response to interview invitation | After expiry period |
| `INTERVIEW_INCOMPLETE` | Did not complete interview | Started but abandoned |
| `INTERVIEW_PERFORMANCE` | Did not meet interview standards | Post-interview only |
| `WORK_AUTHORIZATION` | Work authorization issue | Cannot provide required auth |
| `DID_NOT_SHOW` | Did not attend scheduled interview | Live interview no-show |
| `POSITION_FILLED` | Position filled | Role closed |
| `DUPLICATE` | Duplicate application | Same person applied again |
| `OVERQUALIFIED` | Overqualified (requires comment) | Retention concern - explain why they'll leave |
| `OTHER` | Other (requires comment) | Must explain in comment |

**NOT in dropdown (legally risky):**
- ~~Poor culture fit~~ (subjective, means nothing)
- ~~Job hopper~~ (characterization - use QUAL_EXPERIENCE if they don't meet minimum)
- ~~Employment gaps~~ (caregiving, disability proxy - present timeline, don't judge)

**USE WITH SPECIFICITY (not banned, just be precise):**
- "Overqualified" → Add as `OVERQUALIFIED` with required comment explaining retention concern. It's legitimate if a VP applies for entry-level and will leave in 3 months.
- "Communication issues" → Use `QUAL_SKILLS` + specify: "Role requires client presentations; candidate could not articulate experience clearly." Job-relevant for sales, trainers, customer-facing.
- "Salary mismatch" → Fine to discuss expectations (not history). If they want $200k for a $80k role, that's `SALARY_MISMATCH`.

### Advance Action
```python
def advance_application(application_id: int, user_id: int):
    """Human advances application to next stage."""
    app = get_application(application_id)

    if app.status not in ('ready_for_review', 'interview_ready_for_review', 'on_hold'):
        raise InvalidStateError(f"Cannot advance from {app.status}")

    # Log the decision
    log_decision(
        application_id=application_id,
        action='advance',
        user_id=user_id,
        from_status=app.status,
        timestamp=utcnow(),
    )

    # Determine next step based on config
    req = get_requisition(app.requisition_id)

    if app.status == 'ready_for_review':
        if get_config(req, 'interview_enabled', False):
            # Queue interview
            update_status(application_id, 'advancing')
            enqueue_job('send_interview', application_id)
        else:
            # No interview, mark advanced directly
            update_status(application_id, 'advanced')
            # Optionally update Workday stage
            if get_config(req, 'auto_update_stage', False):
                enqueue_job('update_workday_stage', application_id)

    elif app.status == 'interview_ready_for_review':
        # After interview, mark advanced
        update_status(application_id, 'advanced')
        # Optionally update Workday stage
        if get_config(req, 'auto_update_stage', False):
            enqueue_job('update_workday_stage', application_id)

    db.commit()
```

### Reject Action
```python
def reject_application(
    application_id: int,
    user_id: int,
    reason_code: str,
    comment: Optional[str] = None,
):
    """Human rejects application with required reason code."""
    app = get_application(application_id)

    # Validate reason code
    if reason_code not in VALID_REASON_CODES:
        raise ValueError(f"Invalid reason code: {reason_code}")

    if reason_code == 'OTHER' and not comment:
        raise ValueError("Comment required for OTHER reason code")

    # Log the decision with full audit trail
    log_decision(
        application_id=application_id,
        action='reject',
        user_id=user_id,
        from_status=app.status,
        reason_code=reason_code,
        comment=comment,
        timestamp=utcnow(),
    )

    # Update status
    update_status(application_id, 'rejected')
    app.rejection_reason_code = reason_code
    app.rejection_comment = comment
    app.rejected_by = user_id
    app.rejected_at = utcnow()

    db.commit()
```

## AI Fact Extraction (No Scoring)

### What AI Does

```python
EXTRACTION_PROMPT = """
Extract factual information from this resume. DO NOT score, rank, or make
recommendations. Only extract facts that are explicitly stated.

For each category, extract ONLY what the candidate has written:

1. EMPLOYMENT HISTORY
   For each position:
   - Employer name
   - Job title
   - Start date (if stated)
   - End date (if stated) or "Present"
   - Duration in months/years
   - Key responsibilities (as stated)

2. SKILLS & TECHNOLOGIES
   List ONLY skills explicitly mentioned:
   - Technical skills
   - Software/systems
   - Industry-specific skills

3. CERTIFICATIONS & LICENSES
   List ONLY certifications/licenses explicitly stated:
   - Name of certification
   - Issuing body (if stated)
   - Date/expiration (if stated)

4. EDUCATION
   For each entry:
   - Institution
   - Degree/program
   - Field of study
   - Graduation date (if stated)

5. LOGISTICS/LOCATION
   ONLY if explicitly stated by candidate:
   - Current location
   - Willingness to relocate
   - Remote/onsite preference

Return as structured JSON. Use null for anything not explicitly stated.
Do not infer, assume, or extrapolate.
"""
```

### What AI Does NOT Do

- Does NOT assign scores or rankings
- Does NOT compare candidates to each other
- Does NOT recommend advance/reject decisions
- Does NOT infer skills not explicitly stated
- Does NOT penalize employment gaps or job changes
- Does NOT evaluate "culture fit" or personality
- Does NOT assess writing quality, grammar, or tone
- Does NOT consider school prestige or graduation dates
- Does NOT make character judgments

### What AI DOES Do (Within Constraints)

- Extracts factual information from resumes
- Identifies JD requirements found/not found in resume
- Notes factual pros (JD match) and cons (JD gaps)
- Suggests clarifying questions about unclear facts
- Calculates tenure, experience totals, timelines
- Flags parsing issues or missing information

### Extracted Facts Schema

```json
{
  "extraction_version": "1.0",
  "extracted_at": "2025-12-25T10:30:00Z",
  "employment_history": [
    {
      "employer": "ABC Logistics",
      "title": "Senior Developer",
      "start_date": "2022-06",
      "end_date": null,
      "is_current": true,
      "duration_months": 30,
      "responsibilities": ["TMS development", "API integrations"]
    }
  ],
  "skills": {
    "technical": ["Python", "SQL", "REST APIs"],
    "software": ["TMW", "McLeod", "SAP"],
    "industry": ["LTL operations", "freight billing"]
  },
  "certifications": [
    {
      "name": "AWS Solutions Architect",
      "issuer": "Amazon",
      "date": "2023-01",
      "expiration": null
    }
  ],
  "education": [
    {
      "institution": "State University",
      "degree": "BS",
      "field": "Computer Science",
      "graduation_date": "2018-05"
    }
  ],
  "logistics": {
    "location_stated": "Chicago, IL",
    "relocation_stated": null,
    "remote_preference_stated": "hybrid"
  },
  "summary_stats": {
    "total_experience_months": 84,
    "employers_count": 3,
    "average_tenure_months": 28
  },
  "timeline": [
    {"type": "employment", "employer": "ABC Logistics", "from": "2022-06", "to": null},
    {"type": "gap", "from": "2020-03", "to": "2020-09", "months": 6},
    {"type": "employment", "employer": "XYZ Corp", "from": "2018-05", "to": "2020-03"}
  ]
}
```

**Note on Gap Presentation:** Employment gaps are presented neutrally in the timeline (not highlighted or flagged). This avoids "priming" reviewers to penalize gaps, which can disproportionately affect caregivers, those with medical leave, or other protected groups. The timeline shows facts; the human decides relevance.

## AI Interview Defensibility

### Why AI Interviews Can Be Defensible

1. **Consistency** - Every candidate gets the same questions in the same format
2. **Experience-focused** - Questions about specific job-related experiences (not personality)
3. **No AI decision** - AI summarizes, human decides
4. **Documented** - Full transcript preserved for audit
5. **Job-related** - Questions derived from JD requirements

### Potential Legal Risks & Mitigations

| Risk | Concern | Mitigation |
|------|---------|------------|
| **Accessibility (ADA)** | Text-based interview may disadvantage candidates with dyslexia, visual impairments, or cognitive disabilities | Offer accommodations: voice option, extended time, screen reader compatibility, human alternative |
| **Language Bias** | Non-native English speakers may be disadvantaged | Focus questions on WHAT they did, not HOW they describe it; don't penalize grammar/style |
| **Communication Scoring** | "Communication skills" is vague and can mask bias | Don't score communication; only extract factual content from responses |
| **Time Pressure** | Time limits can disadvantage people with certain disabilities | No strict time limits, or generous limits with extension option |
| **Question Content** | Questions could inadvertently reveal protected info | Pre-approved question bank, no questions about gaps/personal life |
| **Technical Barriers** | Platform issues could disproportionately affect certain groups | Multiple device support, low-bandwidth option, tech support available |

### Interview Question Guidelines

**SAFE Questions (Experience-Focused):**
```
✓ "Describe a time when you [specific job task from JD]"
✓ "Tell me about your experience with [specific tool/system from JD]"
✓ "What was your role in [specific type of project relevant to JD]?"
✓ "How have you handled [specific job-related scenario]?"
✓ "What [specific certification] training have you completed?"
```

**AVOID These Questions:**
```
✗ "Tell me about yourself" (too open, can reveal protected info)
✗ "What are your greatest weaknesses?" (subjective, not job-related)
```

**FINE to Ask (Job-Relevant Behavior):**
```
✓ "Describe your leadership style" - Being an asshole is not a protected class
✓ "How do you handle conflict with direct reports?"
✓ "How do you give difficult feedback?"
✓ "Tell me about a time you had to fire someone"
✓ "How do you handle underperformers?"
```
These are legitimate job-related behavioral questions for leadership roles.

**ASK, But Handle Carefully:**
```
? "Why did you leave your last job?"
    → BETTER: Reframe as forward-looking to reduce protected info disclosure:
    → "What are you looking for in your next role that was missing from your last one?"
    → Gets the same signal without inviting medical/legal/family explanations
    → If they volunteer protected info anyway, redirect gracefully

? "Where do you see yourself in 5 years?" - OK to ask for career goals, redirect if:
    → Family planning → "Let's focus on your professional goals"
    → Retirement timeline → "What interests you about this role specifically?"

? "Are you comfortable with [travel/overtime/schedule]?" - OK if JD requires it, but:
    → Frame as: "This role requires X. Does that work for you?" (yes/no)
    → Don't ask WHY if they say no
```

### AI Redirect Behavior

When candidate responses veer into protected territory, the AI should:

```python
# REDIRECT only on clearly protected CONTEXTS, not incidental word mentions
# "I worked in healthcare" = fine
# "I left because of my health condition" = redirect

REDIRECT_TRIGGERS = {
    # Medical - only when it's THEIR condition affecting employment
    "my disability", "my illness", "my surgery", "my treatment",
    "my diagnosis", "my condition", "medical leave", "on disability",
    "health issues", "mental health struggles",

    # Family - only caregiving responsibilities
    "childcare", "eldercare", "family leave", "maternity leave",
    "paternity leave", "had a baby", "pregnant when", "taking care of my",

    # Legal/Protected Activity - these are always redirect
    "lawsuit", "sued them", "discrimination", "harassment complaint",
    "fired for reporting", "retaliation", "whistleblower",
    "union activity", "workers comp claim",

    # Age - only when framed as discrimination
    "too old", "age discrimination", "wanted younger",

    # Religion - only scheduling/practice conflicts
    "can't work saturdays because", "religious holiday", "need time to pray"
}

# DON'T redirect on incidental mentions:
# "healthy work environment" - fine
# "kids programming at the YMCA" - fine
# "healthcare industry" - fine
# "church volunteer coordinator" - fine (it's experience)

REDIRECT_RESPONSE = """
Thanks for sharing that context. Let's focus on [specific job aspect].
[NEXT QUESTION]
"""
```

**Logging approach (balanced, not paranoid):**
- Log that redirect happened + topic category (e.g., "medical", "family")
- Log the question that triggered it
- Summary: "Candidate discussed personal medical situation when asked about job transition; redirected to role requirements"
- Full transcript IS preserved (it's their words, we need the record)

**Question Bank Structure:**
```json
{
  "question_id": "exp_tms_001",
  "category": "experience",
  "jd_requirement": "TMS experience required",
  "question": "Describe your experience using transportation management systems. What specific TMS platforms have you worked with, and what tasks did you perform in them?",
  "follow_up": "Can you give a specific example of a problem you solved using TMS?",
  "what_we_extract": ["systems_used", "tasks_performed", "years_of_use"],
  "what_we_dont_judge": ["communication_style", "enthusiasm", "confidence"]
}
```

### Accommodation Process

**Required accommodation offer (in interview invitation):**
```
Need an accommodation? We offer:
• Extended time (no time limit)
• Voice-to-text option
• Screen reader compatible version
• Alternative interview format (phone/video with human)
• Other accommodations upon request

Contact: accommodations@company.com
```

**Tracking (for audit):**
```sql
CREATE TABLE interview_accommodations (
    id INT IDENTITY(1,1) PRIMARY KEY,
    interview_id INT NOT NULL,
    accommodation_type VARCHAR(50) NOT NULL,
    requested_at DATETIME,
    approved_at DATETIME,
    approved_by INT,
    notes NVARCHAR(500)
);
```

### What AI Interview Summary Should NOT Include

The `interview_summary.md` prompt already excludes scoring, but explicitly:

**DO NOT include in summary:**
- Any assessment of communication "quality" or "clarity"
- Judgments about enthusiasm, confidence, or attitude
- Observations about response length or speed
- Comments on grammar, vocabulary, or articulation
- Authenticity assessments ("seemed rehearsed", "genuine")
- Character assessments ("honest", "evasive", "defensive")
- Red flags based on HOW they answered (only WHAT they said)

**DO include in summary:**
- Factual claims about experience (employer, duration, tasks)
- Specific examples given (project names, numbers, outcomes)
- Skills/tools mentioned
- Questions candidate asked
- Any factual inconsistencies with resume (dates, titles)
- Logistics discussed (availability, location preferences)

### EEOC Compliance Considerations

Per EEOC guidance on AI in employment (2023):

1. **Disparate Impact Testing** - Should periodically analyze whether interview completion rates or advancement rates differ by protected class
2. **Reasonable Accommodation** - Must provide alternatives for candidates who cannot use the AI format
3. **Transparency** - Candidates should know they're interacting with AI
4. **Human Oversight** - Final decisions must be made by humans

**Recommended disclaimer (in invitation):**
```
This is an AI-assisted screening interview. Your responses will be
recorded and summarized by AI, then reviewed by a human recruiter
who makes all hiring decisions. If you need an accommodation or
prefer to speak with a human, please contact us.
```

## New Prompts (Replacing Scoring Prompts)

### Resume Fact Extraction Prompt

**File:** `api/config/prompts/fact_extraction.md`

```markdown
## Resume Fact Extraction

Extract factual information from this resume for the **${requisitionTitle}** position.
Use application date ${applicationDate} as reference for time calculations.
Applicant ID: ${candidateId}

**CRITICAL CONSTRAINTS:**
- Extract ONLY facts explicitly stated in the resume
- DO NOT score, rank, rate, or assess the candidate
- DO NOT infer skills or experience not explicitly mentioned
- DO NOT make recommendations or judgments
- Use null for any field not explicitly stated

### Job Description (for context only - do not score against it)
${requisitionBriefDescription}

### Resume/Application Data
${candidate}

### Required Output (JSON)

Return this exact structure:

{
  "extraction_version": "2.0",
  "extracted_at": "<ISO timestamp>",
  "applicant_id": "${candidateId}",

  "employment_history": [
    {
      "employer": "<company name>",
      "title": "<job title>",
      "start_date": "<YYYY-MM or null>",
      "end_date": "<YYYY-MM or null if current>",
      "is_current": <true/false>,
      "duration_months": <calculated number>,
      "location": "<city, state or null>",
      "responsibilities": ["<as stated>"],
      "industry": "<if discernible from company/role>"
    }
  ],

  "skills": {
    "technical": ["<explicitly listed skills>"],
    "software": ["<systems, tools, platforms mentioned>"],
    "industry_specific": ["<domain skills: CDL, forklift, TMS, etc>"],
    "certifications_mentioned_in_skills": ["<certs listed in skills section>"]
  },

  "certifications": [
    {
      "name": "<certification name>",
      "issuer": "<issuing body or null>",
      "date_obtained": "<YYYY-MM or null>",
      "expiration": "<YYYY-MM or null>",
      "details": "<class, endorsements, etc or null>"
    }
  ],

  "licenses": [
    {
      "type": "<CDL-A, CDL-B, forklift, etc>",
      "class": "<A, B, C, or null>",
      "endorsements": ["<Hazmat, Tanker, Doubles, etc>"],
      "state": "<issuing state or null>",
      "expiration": "<YYYY-MM or null>"
    }
  ],

  "education": [
    {
      "institution": "<school name>",
      "degree": "<degree type or null>",
      "field": "<field of study or null>",
      "graduation_date": "<YYYY-MM or null>",
      "gpa": "<if stated, else null>"
    }
  ],

  "logistics": {
    "location_stated": "<city, state or null>",
    "willing_to_relocate": "<yes/no/not stated>",
    "remote_preference": "<remote/hybrid/onsite/not stated>",
    "travel_willingness": "<percentage or description or null>"
  },

  "timeline": [
    {
      "type": "employment|education|gap",
      "entity": "<employer or school name>",
      "from": "<YYYY-MM>",
      "to": "<YYYY-MM or null>",
      "duration_months": <number>
    }
  ],

  "summary_stats": {
    "total_experience_months": <calculated>,
    "employers_count": <number>,
    "average_tenure_months": <calculated>,
    "most_recent_employer": "<name>",
    "most_recent_title": "<title>",
    "years_since_last_employment": <if gap to present>
  },

  "jd_keyword_matches": {
    "found": ["<keywords from JD found in resume>"],
    "not_found": ["<keywords from JD not found in resume>"]
  },

  "observations": {
    "pros": [
      {
        "category": "<experience|skills|certifications|education|other>",
        "observation": "<factual observation tied to JD requirement>",
        "evidence": "<specific quote or fact from resume>"
      }
    ],
    "cons": [
      {
        "category": "<experience|skills|certifications|education|other>",
        "observation": "<factual gap relative to JD requirement>",
        "evidence": "<what's missing or unclear>"
      }
    ],
    "suggested_questions": [
      {
        "topic": "<what to clarify>",
        "question": "<specific question to ask>",
        "reason": "<why this needs clarification based on resume>"
      }
    ]
  },

  "extraction_notes": "<any parsing issues, unclear data, or flags>"
}

### DO NOT CONSIDER (Off-Limits for Pros/Cons/Questions):

**Protected Characteristics (Federal Law):**
- Race or color
- National origin or ancestry
- Sex, gender, or gender identity
- Sexual orientation
- Religion or religious practices
- Age (40+) - do not infer from graduation dates
- Disability (physical or mental)
- Genetic information or family medical history
- Pregnancy, childbirth, or related conditions
- Veteran or military status
- Citizenship status (beyond work authorization)

**Protected Activities & Status:**
- Union membership or activity
- Workers' compensation history
- Prior lawsuits against employers
- Whistleblower activity
- FMLA leave usage

**Proxy Variables (Handle With Care):**
- Employment gaps → Present timeline factually, don't characterize or penalize
- Number of jobs → Present count, don't label as "job hopper"
- Graduation dates → Don't use to calculate age
- Name patterns → Never consider
- Salary history → Don't ask (illegal in some states). Salary EXPECTATIONS are fine.

**Context-Dependent (Role-Based, Not Blanket Banned):**
- School prestige → Don't weight university *brand* (Harvard vs State), BUT can note program rigor for technical roles (top CS program = higher bar). Never auto-reject based on school.
- Writing style/grammar → Relevant for copywriter, tech writer, executive assistant. Not for warehouse.
- Geographic location → Only if JD specifies location requirement
- Hobbies/extracurriculars → Ignore unless relevant experience ("10 years coaching" = leadership)
- **Verbal communication (tone, clarity, pacing)** → This is a BFOQ for Sales, Support, CSM, Trainer roles. Enable audio analysis ONLY when "verbal communication" is in JD. Analyze for clarity, NOT accent.
- Recency of skills → Factual observation: "Has 5 yrs Java but none in last 4 years" is relevant. This is NOT a gap penalty - it's skill currency.

**Actually Subjective (Avoid):**
- "Culture fit" → Means nothing, often mask for bias
- "Gut feeling" → Not defensible
- "Attitude" → Too vague unless specific behavioral example

**Legitimate Concerns (Not Banned):**
- "Overqualified" → Legitimate retention concern. VP applying for entry-level will leave. Just document the rationale.
- Career trajectory → Can observe pattern, just don't make it the sole factor
- Retention risk → Can consider if based on objective factors (role is clearly below their level)

### DO FOCUS ON (For Pros/Cons/Questions):
- Specific skills/certifications required in JD vs what's in resume
- Years of relevant experience vs JD minimum
- Specific tools/systems mentioned in JD vs resume
- Licenses required vs licenses held
- Concrete accomplishments relevant to the role
- Gaps in information that need clarification (not judgment)

### Rules:
1. Calculate duration_months from dates when possible
2. List timeline entries in reverse chronological order
3. For JD keyword matching, extract key requirements from JD and check resume
4. If resume is unparseable (image, corrupted), return minimal structure with extraction_notes explaining the issue
5. Do not include personal information beyond what's job-relevant (no age, race, gender inference)
6. Pros/cons must tie directly to a JD requirement - not general observations
7. Suggested questions should clarify facts, not probe character or personality
```

### Interview Summary Prompt (No Scoring)

**File:** `api/config/prompts/interview_summary.md`

```markdown
## Interview Summary

Summarize this interview transcript factually. DO NOT score, rate, or recommend.

**Candidate:** ${candidateName}
**Position:** ${requisitionTitle}
**Interview Date:** ${interviewDate}

### Transcript
${transcript}

### Required Output (JSON)

{
  "summary_version": "2.0",
  "summarized_at": "<ISO timestamp>",

  "interview_summary": "<2-3 paragraph factual summary of what the candidate discussed>",

  "key_points": [
    {
      "topic": "<topic discussed>",
      "what_candidate_said": "<factual summary of their response>",
      "specific_examples_given": ["<any concrete examples they provided>"]
    }
  ],

  "experience_discussed": [
    {
      "employer": "<company mentioned>",
      "role": "<role discussed>",
      "context": "<what they said about this experience>"
    }
  ],

  "skills_mentioned": ["<skills candidate claimed during interview>"],

  "questions_candidate_asked": ["<questions they asked us>"],

  "logistics_discussed": {
    "availability": "<what they said about start date, schedule>",
    "location": "<what they said about location, commute, relocation>",
    "compensation": "<what they said about salary expectations, if discussed>"
  },

  "follow_up_items": ["<any items needing verification or follow-up>"],

  "transcript_quality": {
    "completeness": "complete|partial|poor",
    "notes": "<any technical issues, interruptions, unclear sections>"
  }
}

### Rules:
1. Summarize ONLY what the candidate actually said
2. DO NOT evaluate, score, or assess their responses
3. DO NOT make recommendations (interview, review, decline)
4. DO NOT judge authenticity, character, or fit
5. Use direct quotes where relevant
6. Note any factual claims that could be verified (dates, numbers, companies)
7. If transcript is incomplete or unclear, note in transcript_quality
```

### JD Requirements Extraction Prompt

**File:** `api/config/prompts/jd_extraction.md`

```markdown
## Job Description Requirements Extraction

Extract the factual requirements from this job description.

**Position:** ${requisitionTitle}
**Job Description:**
${requisitionDescription}

### Required Output (JSON)

{
  "required_qualifications": {
    "licenses": ["<required licenses: CDL-A, etc>"],
    "certifications": ["<required certs>"],
    "education": "<minimum education if stated>",
    "experience_years": "<minimum years if stated>",
    "skills_required": ["<explicitly required skills>"]
  },

  "preferred_qualifications": {
    "licenses": ["<preferred licenses>"],
    "certifications": ["<preferred certs>"],
    "education": "<preferred education>",
    "experience_years": "<preferred years>",
    "skills_preferred": ["<nice-to-have skills>"]
  },

  "logistics": {
    "location": "<job location>",
    "remote_option": "<yes/no/hybrid>",
    "travel_required": "<percentage or description>",
    "schedule": "<shift, hours if stated>"
  },

  "keywords": ["<key terms for matching>"]
}

### Rules:
1. Distinguish between REQUIRED and PREFERRED qualifications
2. Extract only what is explicitly stated
3. Do not infer or expand requirements
```

## Configuration Schema

### Global Settings Table

```sql
CREATE TABLE global_settings (
    key VARCHAR(100) PRIMARY KEY,
    value NVARCHAR(MAX) NOT NULL,
    description NVARCHAR(500),
    updated_at DATETIME DEFAULT GETUTCDATE(),
    updated_by VARCHAR(100)
);

-- Default values
INSERT INTO global_settings (key, value, description) VALUES
('lookback_overlap_hours', '1', 'Hours of overlap when syncing to catch edge cases'),
('interview_enabled', 'false', 'Enable AI interview for all requisitions by default'),
('interview_expiry_days', '7', 'Days before interview invitation expires'),
('auto_update_stage', 'false', 'Update Workday stage when advanced');
```

### Requisition Overrides

```sql
ALTER TABLE requisitions ADD
    interview_enabled BIT NULL,           -- NULL = use global
    interview_expiry_days INT NULL,       -- NULL = use global
    auto_update_stage BIT NULL,           -- NULL = use global
    advance_to_stage VARCHAR(50) NULL;    -- Workday stage when advanced
```

### Application Decision Log

```sql
CREATE TABLE application_decisions (
    id INT IDENTITY(1,1) PRIMARY KEY,
    application_id INT NOT NULL REFERENCES applications(id),
    action VARCHAR(20) NOT NULL,          -- 'advance', 'reject', 'hold', 'unhold'
    from_status VARCHAR(50) NOT NULL,
    to_status VARCHAR(50) NOT NULL,
    reason_code VARCHAR(50) NULL,         -- Required for reject
    comment NVARCHAR(1000) NULL,
    user_id INT NOT NULL,
    created_at DATETIME DEFAULT GETUTCDATE(),

    INDEX IX_decisions_application (application_id),
    INDEX IX_decisions_user (user_id),
    INDEX IX_decisions_reason (reason_code)
);
```

## Preventing Stuck Applications

### 1. Atomic Transitions

Same as before - update status + queue next job in same transaction.

### 2. Stuck Detection Query

```sql
-- Find applications stuck in processing states (not waiting for human)
SELECT a.id, a.status, a.updated_at
FROM applications a
WHERE a.status IN (
    -- Processing states (job should be running)
    'new',
    'downloading',
    'downloaded',
    'extracting',
    'extracted',
    'generating_summary',
    'advancing',
    'interview_sending',
    'interview_received',
    'transcribing'
)
  AND a.updated_at < DATEADD(hour, -1, GETUTCDATE())
  AND NOT EXISTS (
      SELECT 1 FROM jobs j
      WHERE j.application_id = a.id
        AND (
            j.status = 'pending'
            OR (j.status = 'running' AND j.started_at > DATEADD(hour, -1, GETUTCDATE()))
        )
  );
```

Note: `ready_for_review`, `interview_ready_for_review`, `on_hold` are NOT stuck - they're waiting for human action.

### 4. Extraction Failure Handling

If AI cannot parse the resume (image scan, corrupted PDF, foreign language):

```python
async def extract_facts(application_id: int):
    app = get_application(application_id)
    update_status(app.id, 'extracting')
    db.commit()

    try:
        resume = await get_resume_from_s3(app)
        facts = await claude_extract_facts(resume)

        # Check if extraction was meaningful
        if is_empty_extraction(facts):
            # Go to review with flag - don't fail
            update_status(app.id, 'extraction_failed')
            app.extraction_notes = "AI could not parse resume - manual review required"
            enqueue_job('generate_summary', app.id)  # Still generate summary (empty facts)
        else:
            update_status(app.id, 'extracted')
            save_extracted_facts(app.id, facts)
            enqueue_job('generate_summary', app.id)

        db.commit()

    except Exception as e:
        # Hard failure - retry or error
        db.rollback()
        raise
```

The summary PDF will show "Extraction Failed - Manual Review Required" and the recruiter can view the original resume directly.

### 5. Error State Recovery

Applications in `error` state can be recovered via admin action:

```sql
-- Admin recovers application to restart processing
UPDATE applications
SET status = 'new',
    error_message = NULL,
    updated_at = GETUTCDATE()
WHERE id = @application_id
  AND status = 'error';

-- Queue the restart
INSERT INTO jobs (application_id, job_type, status, created_at)
VALUES (@application_id, 'download_resume', 'pending', GETUTCDATE());
```

Recovery options:
- **Restart from beginning** → Set to `new`, queue `download_resume`
- **Skip to manual review** → Set to `ready_for_review` with flag
- **Mark as skipped** → Set to `rejected` with reason `OTHER` and admin note

### 3. Interview Expiry Check

```sql
-- Find applications where interview expired
UPDATE applications
SET status = 'interview_expired'
WHERE status = 'interview_sent'
  AND interview_sent_at < DATEADD(day, -COALESCE(
      (SELECT interview_expiry_days FROM requisitions r WHERE r.id = requisition_id),
      (SELECT CAST(value AS INT) FROM global_settings WHERE key = 'interview_expiry_days'),
      7
  ), GETUTCDATE());
```

## Job Types Summary

| Job Type | Input Status | Output Status | Next Job | Trigger |
|----------|--------------|---------------|----------|---------|
| `sync` | - | `new` | `download_resume` | Scheduled |
| `download_resume` | `new` | `downloaded`/`no_resume` | `extract_facts` | Auto |
| `extract_facts` | `downloaded`/`no_resume` | `extracted` | `generate_summary` | Auto |
| `generate_summary` | `extracted` | `ready_for_review` | - | **Human** |
| `send_interview` | `advancing` | `interview_sent` | - | Webhook |
| `transcribe_interview` | `interview_received` | `interview_ready_for_review` | - | **Human** |
| `update_workday_stage` | `advanced` | `advanced` | - | Optional |

## Implementation Order

1. **Database migrations**
   - Add `application_decisions` table
   - Add `rejection_reason_code`, `rejection_comment`, `rejected_by`, `rejected_at` to applications
   - Add new status values to enum/check constraint
   - Add requisition config columns

2. **Update sync processor** - Queue download_resume instead of analyze

3. **Create download_resume processor** - New processor

4. **Create extract_facts processor** - Replace analyze (no scoring)

5. **Create generate_summary processor** - Replace generate_report (no scoring)

6. **API endpoints for human actions**
   - `POST /applications/{id}/advance`
   - `POST /applications/{id}/reject`
   - `POST /applications/{id}/hold`

7. **Update interview processors** - Remove scoring, add transcription

8. **UI components**
   - Application review queue
   - Quick action buttons
   - Rejection reason selector
   - Audit trail viewer

## Deprecation & Removal Plan

### Database Fields to REMOVE

**analyses table:**
```sql
-- REMOVE these columns
ALTER TABLE analyses DROP COLUMN risk_score;     -- No scoring
ALTER TABLE analyses DROP COLUMN red_flags;      -- Too judgmental, replaced by cons
ALTER TABLE analyses DROP CONSTRAINT CK_analyses_risk_score;

-- KEEP these columns (reframed with new prompt constraints)
-- pros          -- Now: factual observations tied to JD requirements
-- cons          -- Now: factual gaps relative to JD requirements
-- suggested_questions  -- Now: clarifying questions about facts, not character

-- ADD these columns (for structured extraction)
ALTER TABLE analyses ADD extracted_facts NVARCHAR(MAX);  -- JSON blob with full extraction
ALTER TABLE analyses ADD extraction_version VARCHAR(20);
ALTER TABLE analyses ADD extraction_notes NVARCHAR(500);  -- Manual review flags
```

**evaluations table:**
```sql
-- REMOVE these columns (all scoring)
ALTER TABLE evaluations DROP COLUMN reliability_score;
ALTER TABLE evaluations DROP COLUMN accountability_score;
ALTER TABLE evaluations DROP COLUMN professionalism_score;
ALTER TABLE evaluations DROP COLUMN communication_score;
ALTER TABLE evaluations DROP COLUMN technical_score;
ALTER TABLE evaluations DROP COLUMN growth_potential_score;
ALTER TABLE evaluations DROP COLUMN overall_score;
ALTER TABLE evaluations DROP COLUMN recommendation;        -- AI shouldn't recommend
ALTER TABLE evaluations DROP COLUMN character_passed;      -- AI shouldn't judge
ALTER TABLE evaluations DROP COLUMN retention_risk;        -- AI shouldn't assess
ALTER TABLE evaluations DROP COLUMN authenticity_assessment;  -- AI shouldn't judge
ALTER TABLE evaluations DROP COLUMN readiness;             -- AI shouldn't assess
-- DROP all score constraints

-- KEEP these columns (factual)
-- transcript (factual record)
-- summary (will be rewritten as factual summary)
-- strengths/weaknesses → RENAME to interview_highlights (factual observations)
```

**applications table:**
```sql
-- ADD these columns (for human decisions)
ALTER TABLE applications ADD rejection_reason_code VARCHAR(50);
ALTER TABLE applications ADD rejection_comment NVARCHAR(1000);
ALTER TABLE applications ADD rejected_by INT;
ALTER TABLE applications ADD rejected_at DATETIME;
ALTER TABLE applications ADD advanced_by INT;
ALTER TABLE applications ADD advanced_at DATETIME;
ALTER TABLE applications ADD decision_notes NVARCHAR(1000);
```

### Files to DELETE or REWRITE

| File | Action | Reason |
|------|--------|--------|
| `api/config/prompts/resume_analysis.md` | **REWRITE** | Replace scoring with fact extraction |
| `api/config/prompts/resume_analysis_example.json` | **REWRITE** | New schema for extracted facts |
| `api/config/prompts/evaluation.md` | **REWRITE** | Replace scoring with factual summary |
| `processor/integrations/claude.py` | **REWRITE** | New dataclasses, new parsing |
| `processor/processors/analyze.py` | **RENAME/REWRITE** | Becomes `extract_facts.py` |
| `processor/processors/evaluate.py` | **REWRITE** | Becomes factual summarization |
| `processor/utils/report_generator.py` | **REWRITE** | New templates, no scores |
| `api/schemas/applications.py` | **REWRITE** | Remove score fields, add decision fields |
| `api/schemas/interviews.py` | **REWRITE** | Remove score fields |
| `api/models/analyses.py` | **REWRITE** | New column definitions |
| `api/models/evaluations.py` | **REWRITE** | New column definitions |
| `web/src/types/index.ts` | **REWRITE** | Remove score types |

### Frontend Components to REMOVE/REWRITE

**Applications pages:**
- `web/src/app/(dashboard)/applications/page.tsx`
  - REMOVE: `getRiskColor()` function
  - REMOVE: Risk score display column
  - CHANGE: Card view → **Table view** with sortable columns
  - ADD: Status filter, bulk actions, rejection reason display

- `web/src/app/(dashboard)/applications/[id]/page.tsx`
  - REMOVE: Risk Score card (lines 171-194)
  - REMOVE: Pros/Cons/Red Flags sections
  - ADD: Extracted Facts display (structured)
  - ADD: Quick action buttons (Advance/Reject/Hold)
  - ADD: Decision history/audit trail

**Interviews pages:**
- `web/src/app/(dashboard)/interviews/page.tsx`
  - REMOVE: `evaluation.overallScore` display
  - REMOVE: `formatRecommendation()` function
  - CHANGE: Card view → **Table view**
  - ADD: Transcript preview, status filters

- `web/src/app/(dashboard)/interviews/[id]/page.tsx`
  - REMOVE: Overall Score card (lines 235-252)
  - REMOVE: Score Breakdown card (lines 255-274)
  - REMOVE: Recommendation badge
  - KEEP: Transcript display
  - ADD: Factual summary (key points from interview)
  - ADD: Quick action buttons

**Requisitions page:**
- `web/src/app/(dashboard)/requisitions/page.tsx`
  - CHANGE: Card view → **Table view**
  - ADD: Application count per requisition
  - ADD: Status breakdown (pending review, in progress, etc.)

**Responsive Design:**
- Desktop (≥1024px): Table view with sortable columns, filters, bulk actions
- Tablet (768-1023px): Compact table or list view
- Mobile (<768px): Card view with swipe actions (advance/reject)

### API Endpoints to MODIFY

```python
# REMOVE these response fields from GET /applications/{id}
- analysis.risk_score
- analysis.red_flags  # Replaced by cons with JD context

# KEEP (reframed with new prompt)
~ analysis.pros              # Now: factual observations tied to JD
~ analysis.cons              # Now: factual gaps relative to JD
~ analysis.suggested_questions  # Now: clarifying questions about facts

# ADD these response fields
+ analysis.extracted_facts  # JSON with employment, skills, certs, etc.
+ analysis.jd_keyword_matches  # { found: [], not_found: [] }
+ application.rejection_reason_code
+ application.rejection_comment
+ application.decision_history[]

# REMOVE these response fields from GET /interviews/{id}
- evaluation.reliability_score
- evaluation.accountability_score
- evaluation.professionalism_score
- evaluation.communication_score
- evaluation.technical_score
- evaluation.growth_potential_score
- evaluation.overall_score
- evaluation.recommendation
- evaluation.character_passed
- evaluation.retention_risk
- evaluation.authenticity_assessment
- evaluation.readiness
- evaluation.strengths
- evaluation.weaknesses
- evaluation.red_flags

# ADD these response fields
+ evaluation.interview_summary  # Factual summary
+ evaluation.key_points[]       # Extracted highlights
+ evaluation.transcript         # Full transcript (keep)
```

### Migration Strategy

1. **Phase 1: Add new columns** (non-breaking)
   - Add `extracted_facts`, `extraction_version`, etc.
   - Add decision tracking columns to applications
   - Add `application_decisions` table

2. **Phase 2: Deploy new processors** (parallel)
   - New `extract_facts` processor writes to new columns
   - Old `analyze` processor still works (for existing apps)

3. **Phase 3: Migrate frontend** (feature flag)
   - New table views behind feature flag
   - New fact display replaces score display
   - Quick action buttons for decisions

4. **Phase 4: Remove old columns** (breaking)
   - Drop deprecated columns
   - Remove old prompt files
   - Clean up old processor code

## Questions Resolved

1. **Should AI score resumes?** → No, extract facts only
2. **Should AI auto-reject?** → No, human rejects with reason code
3. **Should interviews go to everyone?** → If enabled, goes to everyone human advances
4. **How to audit decisions?** → Reason codes + decision log table
5. **What's the skills taxonomy?** → LTL-specific categories defined above

## Gemini Review Feedback (2025-12-25)

**Review of Human-in-the-Loop Redesign - APPROVED**

> "This design is solid. It trades automation speed for legal safety, which is the correct tradeoff for the current regulatory environment."

### Issues Identified and Fixed:

1. ✅ **Missing rejection codes** - Added `INTERVIEW_PERFORMANCE`, `WORK_AUTHORIZATION`, `DID_NOT_SHOW`
2. ✅ **update_workday_stage inconsistency** - Now fires on both interview and non-interview advance paths
3. ✅ **Gap presentation concern** - Changed to neutral timeline presentation (not highlighted)
4. ✅ **Error recovery missing** - Added admin recovery options from `error` state
5. ✅ **Extraction failure handling** - Added `extraction_failed` status for unparseable resumes

### Enhancement Suggestions (Future):

- **Blind Hiring Mode**: Redact PII (name, address) from summary PDF so reviewers decide on skills only
- **AI Label**: UI should label extracted data as "AI-Generated Summary" with one-click access to original resume

### Design Strengths Noted:

- "Glass Box" approach removes black-box liability
- Double-touch model (review → advance → interview → review) is high safety
- Stuck detection correctly excludes human-waiting states
- `OTHER` reason code requiring comment is correct

## Gemini Review: Legal Balance Audit (2025-12-25)

**Goal:** 100% compliant, but not operationally crippled. Scale: -5 (reckless) → 0 (balanced) → +5 (paranoid)

**Initial Rating:** +2 (Moderately Paranoid)
**After Adjustments:** 0 (Balanced)

### Under-Protected (Fixed):

| Issue | Risk | Fix Applied |
|-------|------|-------------|
| Using `QUAL_EXPERIENCE` for job hoppers | Pretextual - they DO have experience | Added `RETENTION_RISK` code with objective tenure math |
| "Why did you leave?" invites protected info | Medical/legal/family disclosures | Reframed as forward-looking: "What are you looking for that was missing?" |
| `INTERVIEW_PERFORMANCE` too vague | Black box rejection | Requires specific rubric/example in comment |
| Skills can get stale | Ignoring recency loses signal | Added `RECENCY_OF_SKILLS` code - factual, not gap penalty |

### Over-Protected (Fixed):

| Issue | Was | Now |
|-------|-----|-----|
| Audio/verbal analysis | Banned entirely | Enabled for roles where it's BFOQ (Sales, Support). Analyze clarity, NOT accent. |
| School prestige | Completely flat | Brand ignored, but program rigor noted for technical roles |
| Employment gaps | Total neutrality | Recency of experience is factual observation, not penalty |

### Kept As-Is (Validated):

- Redirect triggers (strongest legal shield)
- Accommodations workflow (perfect)
- Protected characteristics list (comprehensive)
- Human-in-the-loop for all decisions

## Grok Review (2025-12-25)

**Verdict:** "Ready for implementation"

> "This design achieves the stated goal: 100% human-decision authority with AI as a transparent fact-extraction assistant only. It moves from a higher-risk automated screening model to a legally safe, audit-defensible, 'glass box' augmentation tool."

### Refinements to Add:

| Suggestion | Priority | Notes |
|------------|----------|-------|
| **UI Labeling** | High | Label sections as "AI-Generated Fact Extraction" + one-click to original resume |
| **Configurable RETENTION_RISK threshold** | Medium | Entry-level roles have shorter tenures normally. Make threshold role-level aware. |
| **Blind Hiring mode** | Medium | Redact name/address/photo from summary PDF. Low-effort, high-impact for unconscious bias. |
| **Disparate Impact Monitoring** | Medium | Periodic reporting on advance/reject rates by protected class (where self-reported). Proactive EEOC compliance. |

### Implementation Additions:

**1. Role-Level Retention Thresholds:**
```python
RETENTION_RISK_THRESHOLDS = {
    "entry_level": 6,      # 6 months avg tenure OK for entry-level
    "individual_contributor": 9,   # 9 months
    "manager": 12,         # 12 months
    "director_plus": 18,   # 18 months expected
}

def is_retention_risk(avg_tenure_months: int, role_level: str) -> bool:
    threshold = RETENTION_RISK_THRESHOLDS.get(role_level, 9)
    return avg_tenure_months < threshold
```

**2. Disparate Impact Report (Quarterly):**
```sql
-- Advancement rate by self-reported demographic (where available)
SELECT
    demographic_category,
    COUNT(*) as total_applications,
    SUM(CASE WHEN status = 'advanced' THEN 1 ELSE 0 END) as advanced,
    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
    CAST(SUM(CASE WHEN status = 'advanced' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as advance_rate
FROM applications a
LEFT JOIN candidate_demographics d ON a.candidate_id = d.candidate_id
WHERE a.created_at > DATEADD(quarter, -1, GETUTCDATE())
GROUP BY demographic_category;

-- Flag if any group's advance rate is < 80% of highest group (4/5ths rule)
```

**3. Blind Hiring Toggle (per requisition):**
```sql
ALTER TABLE requisitions ADD blind_hiring_enabled BIT DEFAULT 0;
```

When enabled, summary PDF redacts:
- Candidate name → "Candidate #[hash]"
- Address/location → "[Location withheld]"
- Photo → Not included
- School names → "[Degree] in [Field]" (no institution name)
