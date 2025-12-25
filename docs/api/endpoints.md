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

## Naming Conventions

### Casing Strategy

| Layer | Convention | Example |
|-------|------------|---------|
| Database columns | `snake_case` | `external_application_id` |
| API JSON fields | `camelCase` | `externalApplicationId` |
| Query parameters | `snake_case` | `?requisition_id=123` |
| URL paths | `kebab-case` | `/api/v1/public/interviews` |

**Implementation**: FastAPI response models use `alias_generator = to_camel` to automatically convert snake_case Python fields to camelCase JSON.

```python
from pydantic import BaseModel
from humps import camelize

class ApplicationResponse(BaseModel):
    external_application_id: str  # DB: external_application_id
    candidate_name: str           # DB: candidate_name

    class Config:
        alias_generator = camelize
        populate_by_name = True
```

**Result**:
```json
{
  "externalApplicationId": "APP-123",
  "candidateName": "John Doe"
}
```

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

## Authorization (RBAC)

### Roles

| Role | Description |
|------|-------------|
| `admin` | Full access to all endpoints |
| `recruiter` | Standard recruiter access |
| `readonly` | View-only access (future) |

### Permission Matrix

| Endpoint Group | Admin | Recruiter |
|---------------|-------|-----------|
| Requisitions (CRUD) | ✓ | ✓ |
| Applications (Read) | ✓ | ✓ |
| Applications (Reprocess) | ✓ | ✓ |
| Interviews (Read/Create) | ✓ | ✓ |
| Prompts (CRUD) | ✓ | Read only |
| Personas (CRUD) | ✓ | Read only |
| Credentials (CRUD) | ✓ | ✗ |
| Settings (CRUD) | ✓ | Read only |
| Queue (View) | ✓ | ✓ |
| Queue (Modify/Clear) | ✓ | ✗ |
| Logs/Activities | ✓ | ✓ (filtered) |
| Recruiters (CRUD) | ✓ | Read only |

### Implementation

```python
from fastapi import Depends, HTTPException

def require_role(allowed_roles: list[str]):
    def checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(403, "Insufficient permissions")
        return current_user
    return checker

# Usage
@router.post("/credentials")
async def save_credentials(
    data: CredentialCreate,
    user: User = Depends(require_role(["admin"]))
):
    ...
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
