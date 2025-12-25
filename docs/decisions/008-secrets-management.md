# ADR 008: Secrets Management

**Status:** Accepted
**Date:** 2025-01-15

## Context

AIRecruiter stores sensitive credentials:
- Workday OAuth client_secret and refresh_token
- Anthropic API key
- Database connection string
- AWS credentials

These need secure storage and rotation support.

## Decision

Use a **layered approach**:

1. **Application secrets** (API keys, DB passwords): AWS Secrets Manager or environment variables
2. **Credential encryption** (Workday tokens in DB): Fernet symmetric encryption with key from Secrets Manager

## Implementation

### Environment Variables (Runtime)

```bash
# Core secrets - from AWS Secrets Manager or env
ANTHROPIC_API_KEY=sk-...
DATABASE_URL=mssql+pyodbc://...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Encryption key for DB-stored credentials
FERNET_KEY=base64-encoded-32-byte-key
```

### Fernet Key Management

The `FERNET_KEY` encrypts Workday credentials stored in the `credentials` table.

**Generation**:
```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()  # Store this securely!
```

**Storage options** (choose one):
1. **AWS Secrets Manager** (recommended for production)
   - Store key in Secrets Manager
   - Fetch at application startup
   - Supports rotation

2. **Environment variable** (simpler for dev)
   - Set `FERNET_KEY` env var
   - Loaded at startup

### Credential Encryption Flow

```python
from cryptography.fernet import Fernet
import os

fernet = Fernet(os.environ['FERNET_KEY'])

# Encrypt before storing
encrypted_secret = fernet.encrypt(client_secret.encode())

# Decrypt when using
client_secret = fernet.decrypt(encrypted_secret).decode()
```

### Key Rotation

If rotating the Fernet key:
1. Generate new key
2. Decrypt all credentials with old key
3. Re-encrypt with new key
4. Update key in Secrets Manager
5. Restart applications

## Consequences

### Positive

1. **Secrets not in code**: No hardcoded credentials
2. **Encrypted at rest**: DB compromise doesn't expose Workday tokens
3. **Rotation ready**: Can rotate keys without schema changes

### Negative

1. **Key management**: Must securely store/rotate the Fernet key
2. **Startup dependency**: Must have key available at startup

## Security Checklist

- [ ] Fernet key stored in AWS Secrets Manager (not in code/repo)
- [ ] Database credentials use separate IAM role or secrets
- [ ] API keys rotated periodically
- [ ] No secrets in git history
- [ ] Secrets Manager access logged via CloudTrail
