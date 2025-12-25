# ADR 003: Shared S3 Storage with v1

**Status:** Accepted
**Date:** 2025-01-15

## Context

AIRecruiter v1 stores artifacts (resumes, analyses, reports) in S3. Creating a new bucket would require data migration and increased costs.

## Decision

v2 will **share the same S3 bucket** as v1, using a different prefix.

## Implementation

- v1 prefix: `requisitions/{req_id}/applicants/{app_id}/`
- v2 prefix: `airecruiter2/{req_id}/applications/{app_id}/`

## Consequences

### Positive

1. **No Migration**: Existing artifacts remain accessible
2. **Cost Efficient**: Single bucket, single set of policies
3. **Parallel Operation**: v1 and v2 can run simultaneously during transition

### Negative

1. **Collision Risk**: Must ensure prefixes don't overlap
2. **Cleanup Complexity**: Need to track which artifacts belong to which version
3. **Permissions**: Both versions need access to same bucket

### Mitigations

- Clear prefix separation (`airecruiter2/`)
- Document artifact paths in database
- Consider lifecycle policies for old v1 artifacts after migration

## Security: IAM Policy

**CRITICAL**: v2's IAM role MUST be restricted to only its prefix to prevent accidental deletion of v1 data.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowV2PrefixOnly",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::airecruiter-artifacts/airecruiter2/*"
        },
        {
            "Sid": "AllowListBucket",
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::airecruiter-artifacts",
            "Condition": {
                "StringLike": {
                    "s3:prefix": "airecruiter2/*"
                }
            }
        }
    ]
}
```

This ensures v2 cannot read, modify, or delete v1 artifacts (`requisitions/*`).
