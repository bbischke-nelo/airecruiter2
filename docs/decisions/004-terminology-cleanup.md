# ADR 004: Domain Terminology Cleanup

**Status:** Accepted
**Date:** 2025-01-15

## Context

v1 had inconsistent terminology that caused confusion:

- `ProcessingRecord` (implementation-focused, not domain-correct)
- `ATSCredentials` (should be TMS, not ATS)
- `requisition_id` and `requisition_pk` (confusing dual identifiers)
- `applicant_id` vs `candidate_id` (Workday uses these differently)
- `overall_score` used in both resume analysis and interview evaluation

## Decision

Establish clear terminology documented in `docs/architecture/terminology.md`.

Key renames:

| v1 Term | v2 Term |
|---------|---------|
| `ProcessingRecord` | `Application` |
| `ATSCredentials` | `Credential` |
| `requisition_pk` | `id` |
| `requisition_id` (external) | `external_id` |
| `applicant_id` | `external_application_id` |
| `overall_score` (resume) | `risk_score` |

## Consequences

### Positive

1. **Clarity**: Domain-aligned naming
2. **Consistency**: Single term per concept
3. **Workday Alignment**: Matches Workday's own terminology
4. **Easier Onboarding**: New developers understand quickly

### Negative

1. **Migration Effort**: Must map old terms to new in migration
2. **Documentation Updates**: All docs need new terms
