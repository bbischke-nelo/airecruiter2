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
