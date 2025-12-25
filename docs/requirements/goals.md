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
