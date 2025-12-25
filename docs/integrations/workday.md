# Workday Integration

Technical documentation for Workday TMS integration.

---

## Overview

AIRecruiter integrates with Workday Recruiting via the **SOAP API** (not REST).

**Important**: The Workday REST API (`/ccx/api/v1/{tenant}/`) is only for HCM/Workers data. The Recruiting module (candidates, requisitions, applications) requires SOAP.

---

## Authentication

### OAuth 2.0 (Recommended)

Workday uses OAuth 2.0 with refresh tokens:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ AIRecruiter │────▶│  Workday    │────▶│   Access    │
│             │     │  OAuth      │     │   Token     │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                       │
       │         Refresh Token Flow            │
       └───────────────────────────────────────┘
```

**Configuration Required:**
- `tenant_url`: Base URL (e.g., `https://services1.wd503.myworkday.com`)
- `tenant_id`: Tenant identifier (e.g., `ccfs`)
- `client_id`: OAuth client ID (API client created in Workday)
- `client_secret`: OAuth client secret
- `refresh_token`: Long-lived refresh token

**Token Flow:**
1. Use refresh token to get access token
2. Access token expires after ~60 minutes
3. Auto-refresh before expiry
4. Refresh token valid for extended period (configurable in Workday)

```python
# OAuth token request
POST https://{tenant_url}/ccx/oauth2/{tenant_id}/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
refresh_token={refresh_token}
client_id={client_id}
client_secret={client_secret}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "..."
}
```

---

## SOAP API

### WSDL Endpoints

Workday publishes WSDLs per service. For Recruiting:

```
https://{tenant_url}/ccx/service/{tenant_id}/Recruiting/v42.0
```

WSDL URL:
```
https://{tenant_url}/ccx/service/{tenant_id}/Recruiting/v42.0?wsdl
```

### API Version

Current: `v42.0` (as of 2024)

Update via configuration if Workday upgrades.

### Authentication Header

```xml
<soapenv:Header>
  <wsse:Security>
    <wsse:BinarySecurityToken>
      Bearer {access_token}
    </wsse:BinarySecurityToken>
  </wsse:Security>
</soapenv:Header>
```

---

## Key Operations

### Get_Job_Requisitions

Fetches job requisitions.

**Request:**
```xml
<bsvc:Get_Job_Requisitions_Request>
  <bsvc:Request_Criteria>
    <bsvc:Job_Requisition_Status_Reference>
      <bsvc:ID bsvc:type="Job_Requisition_Status_ID">Open</bsvc:ID>
    </bsvc:Job_Requisition_Status_Reference>
  </bsvc:Request_Criteria>
  <bsvc:Response_Filter>
    <bsvc:Page>1</bsvc:Page>
    <bsvc:Count>100</bsvc:Count>
  </bsvc:Response_Filter>
  <bsvc:Response_Group>
    <bsvc:Include_Reference>true</bsvc:Include_Reference>
    <bsvc:Include_Job_Requisition_Definition_Data>true</bsvc:Include_Job_Requisition_Definition_Data>
  </bsvc:Response_Group>
</bsvc:Get_Job_Requisitions_Request>
```

**Response Data:**
```python
{
    "Job_Requisition_Reference": {
        "ID": [{"_value_1": "REQ-2025-001", "_type": "Job_Requisition_ID"}]
    },
    "Job_Requisition_Data": {
        "Job_Requisition_ID": "REQ-2025-001",
        "Job_Posting_Title": "Senior Software Engineer",
        "Job_Description": "...",
        "Position_Data": {
            "Location_Reference": {...},
            "Supervisory_Organization_Reference": {...}
        },
        "Recruiting_Data": {
            "Primary_Recruiter_Reference": {...},
            "Hiring_Manager_Reference": {...}
        }
    }
}
```

### Get_Candidates

Fetches candidate profiles.

**Request:**
```xml
<bsvc:Get_Candidates_Request>
  <bsvc:Request_Criteria>
    <!-- Optional: filter by job requisition -->
  </bsvc:Request_Criteria>
  <bsvc:Response_Filter>
    <bsvc:Page>1</bsvc:Page>
    <bsvc:Count>100</bsvc:Count>
  </bsvc:Response_Filter>
  <bsvc:Response_Group>
    <bsvc:Include_Reference>true</bsvc:Include_Reference>
    <bsvc:Include_Recruiting_Information>true</bsvc:Include_Recruiting_Information>
  </bsvc:Response_Group>
</bsvc:Get_Candidates_Request>
```

### Get_Job_Applications

Fetches applications for a requisition (preferred for our use case).

**Request:**
```xml
<bsvc:Get_Job_Applications_Request>
  <bsvc:Request_Criteria>
    <bsvc:Job_Requisition_Reference>
      <bsvc:ID bsvc:type="Job_Requisition_ID">REQ-2025-001</bsvc:ID>
    </bsvc:Job_Requisition_Reference>
  </bsvc:Request_Criteria>
  <bsvc:Response_Group>
    <bsvc:Include_Reference>true</bsvc:Include_Reference>
    <bsvc:Include_Job_Application_Data>true</bsvc:Include_Job_Application_Data>
  </bsvc:Response_Group>
</bsvc:Get_Job_Applications_Request>
```

**Response Data:**
```python
{
    "Job_Application_Reference": {
        "ID": [{"_value_1": "APP-12345"}]
    },
    "Job_Application_Data": {
        "Candidate_Reference": {...},
        "Job_Requisition_Reference": {...},
        "Application_Date": "2025-01-15",
        "Status_Reference": {
            "ID": [{"_value_1": "Screen"}],
            "Descriptor": "Screen"
        },
        "Personal_Data": {
            "Name_Data": {...},
            "Contact_Data": {...}
        }
    }
}
```

### Put_Candidate_Attachment

Uploads a document to a candidate profile.

**Request:**
```xml
<bsvc:Put_Candidate_Attachment_Request>
  <bsvc:Candidate_Attachment_Data>
    <bsvc:Candidate_Reference>
      <bsvc:ID bsvc:type="Candidate_ID">CAND-12345</bsvc:ID>
    </bsvc:Candidate_Reference>
    <bsvc:Attachment_Data>
      <bsvc:File_Name>CandidateReport.pdf</bsvc:File_Name>
      <bsvc:File>{base64_encoded_content}</bsvc:File>
      <bsvc:Category_Reference>
        <bsvc:ID bsvc:type="Attachment_Category_ID">Other</bsvc:ID>
      </bsvc:Category_Reference>
      <bsvc:Comment>AI-generated candidate report</bsvc:Comment>
    </bsvc:Attachment_Data>
  </bsvc:Candidate_Attachment_Data>
</bsvc:Put_Candidate_Attachment_Request>
```

### Get_Candidate_Attachments

Downloads candidate documents (resume, etc.).

**Response includes base64-encoded file content.**

---

## Data Mapping

### Requisition Fields

| Workday Field | AIRecruiter Field | Notes |
|--------------|-------------------|-------|
| `Job_Requisition_ID` | `external_id` | Unique identifier |
| `Job_Posting_Title` | `name` | Display title |
| `Job_Description` | `description` | Brief description |
| `Job_Qualifications` | `detailed_description` | Full JD for AI |
| `Location_Reference.Descriptor` | `location` | Location name |
| `Primary_Recruiter_Reference` | `recruiter` | Assigned recruiter |
| `Job_Requisition_Status` | `is_active` | Open = active |
| `Last_Updated` | `last_synced_at` | Sync timestamp |

### Application Fields

| Workday Field | AIRecruiter Field | Notes |
|--------------|-------------------|-------|
| `Job_Application_ID` | `external_application_id` | Application ID |
| `Candidate_ID` | `external_candidate_id` | Candidate ID |
| `First_Name` / `Last_Name` | `candidate_name` | Combined name |
| `Email_Address` | `candidate_email` | Primary email |
| `Status_Reference` | `workday_status` | Current status |
| `Application_Date` | `created_at` | Apply date |

### Application Status Mapping

| Workday Status | AIRecruiter Status | Description |
|----------------|-------------------|-------------|
| `Review` | `new` | New application |
| `Screen` | `analyzed` | After resume analysis |
| `Interview` | `interview_complete` | After AI interview |

---

## Rate Limiting

Workday enforces rate limits:

- **10 calls per second** (typical)
- Configurable per tenant

Implementation:
```python
async def _check_rate_limit(self) -> None:
    """Enforce 100ms between calls = max 10/second"""
    await asyncio.sleep(0.1)
```

For bulk operations, use batch endpoints where available.

---

## Error Handling

### Common SOAP Faults

| Fault | Meaning | Action |
|-------|---------|--------|
| `INVALID_ID_TYPE` | Wrong ID type in reference | Check ID format |
| `INVALID_REFERENCE` | Object not found | Skip or log |
| `PROCESSING_FAULT` | General processing error | Retry |
| `VALIDATION_FAULT` | Invalid data | Fix and retry |
| `PERMISSION_DENIED` | Auth/permissions issue | Check ISU config |

### Retry Strategy

```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "backoff_factor": 2,  # Exponential backoff
    "retryable_faults": [
        "PROCESSING_FAULT",
        "CONNECTION_ERROR",
        "TIMEOUT"
    ]
}
```

---

## Security Configuration

### Workday Side

1. **Create API Client**
   - Workday > Administration > Register API Client
   - Set scopes: Recruiting, Staffing

2. **Create Integration System User (ISU)**
   - Workday > Integration > Integration Security
   - Assign to security groups with Recruiting access

3. **Configure Domain Security**
   - Grant ISU access to Recruiting functional areas
   - Enable: Get, Put for required objects

4. **Generate Refresh Token**
   - Use OAuth flow to generate long-lived refresh token
   - Store securely (encrypted in AIRecruiter)

### AIRecruiter Side

1. **Store Credentials Encrypted**
   - Use Fernet encryption for `client_secret` and `refresh_token`
   - Never log credentials

2. **Validate SSL**
   - Always verify Workday certificates
   - Use production endpoints only

3. **Rotate Tokens**
   - Monitor token expiry
   - Implement graceful refresh

---

## Sync Strategy

### Initial Sync

1. Fetch all open requisitions
2. For each requisition, fetch all applications
3. Store in database with `status='new'`
4. Queue for processing

### Incremental Sync

1. Check `last_synced_at` for each active requisition
2. Fetch applications modified since last sync
3. Upsert new/updated applications
4. Queue new applications for processing

### Lookback Window

- Default: 24 hours
- Configurable per requisition
- Prevents missing applications during outages

```python
# Calculate effective since date
last_sync = requisition.last_synced_at or (now - timedelta(hours=48))
since = max(last_sync, now - timedelta(hours=lookback_hours))
```

---

## Resume Handling

### Download Flow

1. Call `Get_Candidates` with `Include_Resume_Data=true`
2. Extract base64-encoded resume from response
3. Decode and store in S3
4. Update `artifacts.resume` with S3 key

### Supported Formats

| Format | Handling |
|--------|----------|
| PDF | Direct extraction |
| DOCX | Convert with python-docx |
| DOC | Convert via LibreOffice (if needed) |
| TXT | Direct read |

---

## Report Upload

### Process

1. Generate PDF report (WeasyPrint)
2. Base64-encode content
3. Call `Put_Candidate_Attachment`
4. Verify success via response
5. Store `workday_document_id` in database

### Attachment Categories

Configure in Workday:
- `AIRecruiter_Report` - Custom category for our reports
- `Other` - Fallback category

---

## Testing

### Test Connection

```python
async def test_workday_connection():
    """Verify Workday connectivity and permissions."""
    provider = WorkdayTMSProvider(config)
    await provider.initialize()

    # Test: fetch 1 requisition
    reqs = await provider.get_requisitions(limit=1)
    assert len(reqs) >= 0

    # Test: health check
    health = await provider.health_check()
    assert health["healthy"]

    await provider.close()
```

### Mock for Development

Use recorded SOAP responses for local development:

```python
@pytest.fixture
def mock_workday_client(mocker):
    mock = mocker.patch('workday.soap_client.WorkdaySOAPClient')
    mock.return_value.get_job_requisitions.return_value = [
        {"Job_Requisition_Reference": {"ID": [{"_value_1": "REQ-001"}]}}
    ]
    return mock
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `PERMISSION_DENIED` | ISU lacks permissions | Check Workday security groups |
| Empty responses | Wrong tenant or environment | Verify `tenant_url` and `tenant_id` |
| `INVALID_REFERENCE` | Object doesn't exist | Verify IDs in Workday UI |
| Token refresh fails | Refresh token expired | Re-generate via OAuth flow |
| Status not updating | Wrong status ID | Query valid statuses first |

### Debug Logging

Enable verbose SOAP logging:

```python
import logging
logging.getLogger('zeep').setLevel(logging.DEBUG)
```

### Workday Admin Access

For troubleshooting, access Workday admin:
1. Integration > Launch / Manage Integrations
2. View integration logs
3. Check security group assignments
