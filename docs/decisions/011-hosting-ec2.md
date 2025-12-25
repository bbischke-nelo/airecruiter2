# ADR 011: EC2 Hosting

**Status:** Accepted
**Date:** 2025-01-15

## Context

Need to choose hosting platform for airecruiter2 services (API, Processor, Web).

Options considered:
- AWS Lambda (serverless)
- AWS ECS (containers)
- AWS EC2 (VMs)

## Decision

Use **EC2** for hosting, consistent with v1 and other internal applications.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         VPC                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   ALB       │  │   ALB       │  │   ALB       │         │
│  │  (API)      │  │  (Web)      │  │  (Public)   │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                  │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐         │
│  │   EC2       │  │   EC2       │  │   EC2       │         │
│  │  API x2     │  │  Web x2     │  │  Interview  │         │
│  │  (t3.small) │  │  (t3.small) │  │  (t3.micro) │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐                          │
│  │   EC2       │  │   RDS       │                          │
│  │  Processor  │  │  SQL Server │                          │
│  │  (t3.small) │  │             │                          │
│  └─────────────┘  └─────────────┘                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Instance Types

| Service | Instance | Count | Notes |
|---------|----------|-------|-------|
| API | t3.small | 2 | Behind ALB, auto-scaling |
| Processor | t3.small | 1 | Single worker, can scale |
| Web | t3.small | 2 | Next.js, behind ALB |
| Public Interview | t3.micro | 1 | Light traffic |

## Deployment

### Docker + Docker Compose

Each EC2 instance runs Docker:

```yaml
# docker-compose.yml (API server)
version: '3.8'
services:
  api:
    image: airecruiter2-api:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SSO_URL=${SSO_URL}
    restart: always
```

### Deployment Process

1. Build Docker image in CI (GitHub Actions)
2. Push to ECR
3. SSH to EC2, pull new image
4. `docker-compose up -d`

### Alternative: Systemd Services

For simpler deployments without Docker:

```ini
# /etc/systemd/system/airecruiter2-api.service
[Unit]
Description=AIRecruiter2 API
After=network.target

[Service]
User=airecruiter
WorkingDirectory=/opt/airecruiter2/api
ExecStart=/opt/airecruiter2/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
EnvironmentFile=/opt/airecruiter2/.env

[Install]
WantedBy=multi-user.target
```

## Load Balancing

- **Application Load Balancer** (ALB) for API and Web
- Health check: `GET /health`
- SSL termination at ALB
- Sticky sessions not required (stateless API)

## Scaling

- **Horizontal**: Add more EC2 instances behind ALB
- **Vertical**: Upgrade instance type
- **Auto-scaling**: Based on CPU utilization (target 70%)

## Monitoring

- CloudWatch metrics (CPU, memory, disk)
- CloudWatch Logs (application logs)
- ALB access logs to S3
- Health check alarms

## Consequences

### Positive

1. **Familiar**: Team knows EC2
2. **Simple**: No container orchestration complexity
3. **Consistent**: Same as v1 and other apps
4. **Flexible**: Easy to SSH and debug

### Negative

1. **Manual scaling**: Not as automatic as ECS/Lambda
2. **Patching**: Must maintain OS updates
3. **Cost**: Paying for idle capacity

## Security

- EC2 instances in private subnets
- ALB in public subnets
- Security groups restrict traffic
- IAM roles for AWS service access
- SSM for secure shell access (no SSH keys)
