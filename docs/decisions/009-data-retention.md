# ADR 009: Data Retention and Cleanup

**Status:** Accepted
**Date:** 2025-01-15

## Context

Without retention policies, data grows unbounded:
- `jobs` table accumulates completed/failed job records
- `activities` table grows with every status change
- S3 artifacts (resumes, reports) persist indefinitely
- Old application data may not be needed after hire/rejection

## Decision

Implement **tiered retention policies** based on data sensitivity and utility.

## Retention Periods

| Data Type | Retention | Cleanup Method |
|-----------|-----------|----------------|
| Completed jobs | 30 days | SQL scheduled job |
| Failed jobs | 90 days | SQL scheduled job |
| Activities | 1 year | SQL scheduled job |
| Applications (complete) | 2 years | Manual review |
| Applications (failed) | 90 days | SQL scheduled job |
| S3 artifacts | 2 years | S3 lifecycle policy |
| Interview messages | 2 years | Cascade with application |

## Implementation

### SQL Server Agent Jobs

```sql
-- Clean up completed jobs older than 30 days
CREATE PROCEDURE sp_cleanup_jobs
AS
BEGIN
    DELETE FROM jobs
    WHERE status = 'completed'
      AND completed_at < DATEADD(DAY, -30, GETUTCDATE());

    DELETE FROM jobs
    WHERE status = 'failed'
      AND completed_at < DATEADD(DAY, -90, GETUTCDATE());
END;

-- Schedule to run daily at 2 AM
```

### S3 Lifecycle Policy

```json
{
    "Rules": [
        {
            "ID": "ExpireOldArtifacts",
            "Filter": {
                "Prefix": "airecruiter2/"
            },
            "Status": "Enabled",
            "Expiration": {
                "Days": 730
            }
        }
    ]
}
```

### Application Cleanup (Manual Review)

Applications should not be auto-deleted due to compliance requirements. Instead:
1. Mark applications older than 2 years as `archived`
2. Provide admin UI to review and delete archived records
3. Cascade delete removes: analysis, interviews, messages, evaluations, reports

### Activities Cleanup

```sql
-- Clean up activities older than 1 year
CREATE PROCEDURE sp_cleanup_activities
AS
BEGIN
    DELETE FROM activities
    WHERE created_at < DATEADD(YEAR, -1, GETUTCDATE());
END;
```

## Consequences

### Positive

1. **Controlled growth**: Tables stay manageable size
2. **Cost savings**: Less S3 storage over time
3. **Compliance**: Clear retention windows for audits
4. **Performance**: Smaller tables = faster queries

### Negative

1. **Data loss risk**: Must ensure retention periods meet business needs
2. **Compliance complexity**: Some regulations may require longer retention
3. **Operational overhead**: Must monitor cleanup jobs

## Configuration

Add settings for configurable retention:

```sql
INSERT INTO settings ([key], value, description) VALUES
('retention_jobs_completed_days', '30', 'Days to keep completed jobs'),
('retention_jobs_failed_days', '90', 'Days to keep failed jobs'),
('retention_activities_days', '365', 'Days to keep activity records'),
('retention_applications_days', '730', 'Days before marking applications archived');
```

## Monitoring

- Alert if cleanup jobs fail
- Dashboard showing table sizes over time
- Audit log for deleted records (before deletion)
