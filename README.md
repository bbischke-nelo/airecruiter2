# AIRecruiter v2

AI-powered candidate screening and interview system with Talent Management System (TMS) integration.

## Overview

AIRecruiter automates the initial stages of recruitment by:
1. Syncing job requisitions and candidates from your TMS (Workday)
2. Analyzing resumes using AI to score and evaluate candidates
3. Conducting self-service AI interviews
4. Generating comprehensive candidate reports
5. Uploading results back to the TMS

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Workday   │◄───►│  Processor  │◄───►│  SQL Server │
│    TMS      │     │   Worker    │     │  + Job Queue│
└─────────────┘     └──────┬──────┘     └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   Claude    │
                   │     AI      │
                   └─────────────┘

┌─────────────┐     ┌─────────────┐
│  Candidate  │◄───►│   Web API   │
│   Web UI    │     │  (FastAPI)  │
└─────────────┘     └─────────────┘
```

## Project Structure

```
airecruiter2/
├── docs/                    # Design documentation
│   ├── architecture/        # System architecture
│   ├── database/           # Schema design
│   ├── api/                # API specifications
│   ├── processor/          # Processing pipeline
│   └── decisions/          # Architecture Decision Records
├── api/                    # FastAPI backend
├── processor/              # Background processing service
└── web/                    # Next.js frontend
```

## Key Design Principles

1. **Clean Separation** - API, Processor, and Web are independent services
2. **Provider Extensibility** - TMS provider interface designed for extension
3. **Clear Terminology** - Consistent naming across codebase
4. **API-First** - No browser automation; clean API integrations only
5. **Observable** - Comprehensive logging and monitoring

## Documentation

### Requirements
- [Project Goals](docs/requirements/goals.md) - Problem statement, MVP scope
- [Feature Requirements](docs/requirements/features.md) - Complete feature list

### Architecture
- [Terminology](docs/architecture/terminology.md) - Domain terms and naming conventions
- [Database Schema](docs/database/schema.md) - SQL Server table definitions
- [Processor Workflow](docs/processor/workflow.md) - Background processing pipeline
- [API Design](docs/api/endpoints.md) - REST API specification
- [Web UI](docs/ui/pages.md) - Frontend page specifications

### Integrations
- [Workday Integration](docs/integrations/workday.md) - SOAP API details

### Decisions
- [ADR 001: Workday Only](docs/decisions/001-workday-only.md)
- [ADR 002: SQL Server](docs/decisions/002-sql-server-database.md)
- [ADR 003: Shared S3](docs/decisions/003-shared-s3-storage.md)
- [ADR 004: Terminology](docs/decisions/004-terminology-cleanup.md)
- [ADR 005: Queue Processing](docs/decisions/005-queue-based-processing.md)
- [ADR 006: API Only](docs/decisions/006-api-only-integration.md)
- [ADR 007: Logging Strategy](docs/decisions/007-logging-strategy.md)
- [ADR 008: Secrets Management](docs/decisions/008-secrets-management.md)
- [ADR 009: Data Retention](docs/decisions/009-data-retention.md)
- [ADR 010: Authentication](docs/decisions/010-authentication.md)
- [ADR 011: EC2 Hosting](docs/decisions/011-hosting-ec2.md)
- [ADR 012: SES Email](docs/decisions/012-email-ses.md)

## Tech Stack

- **API**: Python, FastAPI, SQLAlchemy
- **Processor**: Python, async/await
- **Database**: Microsoft SQL Server (RDS)
- **Web**: Next.js, TypeScript, Tailwind
- **AI**: Claude API (Anthropic)
- **TMS**: Workday SOAP API
- **Storage**: AWS S3 (shared with v1)
- **Email**: AWS SES
- **Auth**: centralized-auth (Azure AD SSO)
- **Hosting**: AWS EC2

## Development

```bash
# Setup (TBD)
```

## License

Proprietary
