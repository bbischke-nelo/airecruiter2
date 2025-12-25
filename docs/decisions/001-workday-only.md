# ADR 001: Workday-Only TMS Support

**Status:** Accepted
**Date:** 2025-01-15

## Context

AIRecruiter v1 supported multiple TMS providers (UltiPro and Workday) through an abstraction layer. This introduced:

- Complex multi-provider architecture with unified/legacy modes
- Browser automation (Playwright) for UltiPro due to lack of clean API
- MFA session management via WebSockets
- Significant code complexity

The organization has migrated to Workday as the primary TMS.

## Decision

AIRecruiter v2 will support **Workday only**.

## Consequences

### Positive

1. **Simplified Architecture**: No provider abstraction layer needed
2. **Clean API Integration**: Workday SOAP API only, no browser automation
3. **Reduced Complexity**: Single code path for all TMS operations
4. **Easier Maintenance**: Less code to maintain and test
5. **Better Reliability**: No MFA/session management issues

### Negative

1. **Not Extensible**: Adding another TMS would require significant work
2. **Vendor Lock-in**: Tightly coupled to Workday

### Mitigations

- Design internal interfaces cleanly so future provider support is possible
- Keep Workday-specific code isolated in `integrations/workday/` module
