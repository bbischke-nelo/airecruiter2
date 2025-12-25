# ADR 006: API-Only Integration (No Browser Automation)

**Status:** Accepted
**Date:** 2025-01-15

## Context

v1 used Playwright browser automation for UltiPro because:
- UltiPro lacked a clean API
- Required MFA session management
- Needed to scrape certain data

This was fragile and maintenance-intensive.

## Decision

v2 will use **API-only integration** with Workday. No browser automation.

Workday provides:
- SOAP API for Recruiting (requisitions, candidates, applications)
- OAuth 2.0 authentication with refresh tokens
- Document upload via API

## Consequences

### Positive

1. **Reliability**: APIs are stable, UIs change frequently
2. **Performance**: API calls faster than browser automation
3. **Simpler Deployment**: No headless browser dependencies
4. **No MFA Issues**: OAuth handles authentication cleanly
5. **Testable**: APIs easy to mock in tests

### Negative

1. **API Limitations**: Some data may not be available via API
2. **SOAP Complexity**: Workday uses SOAP, not REST, for Recruiting

### Dependencies

- `zeep` library for SOAP
- `httpx` for HTTP client
- Workday Integration System User (ISU) with proper permissions
