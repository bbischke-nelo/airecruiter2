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
