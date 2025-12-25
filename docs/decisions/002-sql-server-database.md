# ADR 002: Microsoft SQL Server Database

**Status:** Accepted
**Date:** 2025-01-15

## Context

v1 used PostgreSQL. The organization has standardized on Microsoft SQL Server for enterprise applications.

## Decision

AIRecruiter v2 will use **Microsoft SQL Server** as the database.

## Consequences

### Positive

1. **Enterprise Standards**: Aligns with organization's database standards
2. **Support**: Existing DBA support and tooling
3. **Integration**: Easier integration with other enterprise systems
4. **Familiar**: Development team has SQL Server expertise

### Negative

1. **JSON Handling**: Less elegant than PostgreSQL's native JSONB
2. **ORM Differences**: SQLAlchemy has some PostgreSQL-specific features
3. **Licensing**: SQL Server requires licenses (organization has them)

### Implementation Notes

- Use `NVARCHAR(MAX)` for JSON storage
- Use SQL Server 2016+ for JSON functions
- SQLAlchemy dialect: `mssql+pyodbc`
- Use `DATETIME2` for timestamps (higher precision than `DATETIME`)
