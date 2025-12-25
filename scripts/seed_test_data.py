#!/usr/bin/env python3
"""Seed test data from local files.

Usage:
    python scripts/seed_test_data.py [application.json] [resume.docx]

If no arguments provided, uses files from test_data/ directory.

Examples:
    python scripts/seed_test_data.py
    python scripts/seed_test_data.py test_data/REGIO004114-application.json test_data/REGIO004114-resume.docx
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path so we can import from api and processor
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from api.config.database import SessionLocal
from api.models import Requisition, Application, Job
from processor.integrations.s3 import S3Service


def create_requisition(db, app_data: dict) -> Requisition:
    """Create or get requisition from application data."""
    job_req = app_data.get("job_requisition", {})
    external_id = job_req.get("requisition_number", "UNKNOWN")

    # Check if requisition exists
    existing = db.query(Requisition).filter(Requisition.external_id == external_id).first()
    if existing:
        print(f"  Requisition {external_id} already exists (id={existing.id})")
        return existing

    # Create new requisition
    requisition = Requisition(
        external_id=external_id,
        name=job_req.get("title", f"Job {external_id}"),
        description=job_req.get("brief_description"),
        detailed_description=job_req.get("detailed_description"),
        is_active=True,
        sync_enabled=False,  # Don't auto-sync test data
        auto_send_interview=False,
    )
    db.add(requisition)
    db.commit()
    db.refresh(requisition)

    print(f"  Created requisition: {requisition.external_id} (id={requisition.id})")
    return requisition


def create_application(db, requisition: Requisition, app_data: dict) -> Application:
    """Create application from application data."""
    external_app_id = app_data.get("application_id", "unknown")
    external_candidate_id = app_data.get("candidate_id")

    # Check if application exists
    existing = db.query(Application).filter(
        Application.requisition_id == requisition.id,
        Application.external_application_id == external_app_id
    ).first()
    if existing:
        print(f"  Application {external_app_id} already exists (id={existing.id})")
        return existing

    # Build candidate name
    first_name = app_data.get("first_name", "")
    last_name = app_data.get("last_name", "")
    candidate_name = f"{first_name} {last_name}".strip() or "Unknown"

    # Create application
    application = Application(
        requisition_id=requisition.id,
        external_application_id=external_app_id,
        external_candidate_id=external_candidate_id,
        candidate_name=candidate_name,
        candidate_email=app_data.get("email"),
        status="new",
        workday_status=app_data.get("current_state", "NEW"),
        artifacts="{}",  # Will be updated after resume upload
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    print(f"  Created application: {application.candidate_name} (id={application.id})")
    return application


async def upload_resume(application: Application, resume_path: Path) -> str:
    """Upload resume to S3 and return the key."""
    s3 = S3Service()

    content = resume_path.read_bytes()
    filename = resume_path.name

    key = await s3.upload_resume(
        application_id=application.id,
        content=content,
        filename=filename,
    )

    print(f"  Uploaded resume to S3: {key}")
    return key


def update_application_artifacts(db, application: Application, resume_key: str):
    """Update application with artifact references."""
    artifacts = {"resume": resume_key}
    application.artifacts = json.dumps(artifacts)
    db.commit()
    print(f"  Updated application artifacts")


def queue_analysis_job(db, application: Application) -> Job:
    """Queue an analysis job for the application."""
    # Check if job already exists
    existing = db.query(Job).filter(
        Job.application_id == application.id,
        Job.job_type == "analyze",
        Job.status.in_(["pending", "running"])
    ).first()
    if existing:
        print(f"  Analysis job already exists (id={existing.id})")
        return existing

    job = Job(
        application_id=application.id,
        requisition_id=application.requisition_id,
        job_type="analyze",
        status="pending",
        priority=5,  # Medium priority for test data
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    print(f"  Queued analysis job (id={job.id})")
    return job


async def main():
    # Default to test_data directory if no args provided
    project_root = Path(__file__).parent.parent
    test_data_dir = project_root / "test_data"

    if len(sys.argv) >= 3:
        app_json_path = Path(sys.argv[1]).expanduser()
        resume_path = Path(sys.argv[2]).expanduser()
    else:
        # Find first .json and .docx in test_data
        json_files = list(test_data_dir.glob("*.json"))
        docx_files = list(test_data_dir.glob("*.docx"))

        if not json_files or not docx_files:
            print("Usage: python scripts/seed_test_data.py [application.json] [resume.docx]")
            print("\nNo test data found in test_data/ directory.")
            print("Either provide file paths or add files to test_data/")
            sys.exit(1)

        app_json_path = json_files[0]
        resume_path = docx_files[0]
        print(f"Using test data from: {test_data_dir}")

    if not app_json_path.exists():
        print(f"Error: Application JSON not found: {app_json_path}")
        sys.exit(1)

    if not resume_path.exists():
        print(f"Error: Resume not found: {resume_path}")
        sys.exit(1)

    print(f"Loading application data from: {app_json_path}")
    app_data = json.loads(app_json_path.read_text())

    print(f"Resume file: {resume_path}")

    db = SessionLocal()
    try:
        print("\n1. Creating requisition...")
        requisition = create_requisition(db, app_data)

        print("\n2. Creating application...")
        application = create_application(db, requisition, app_data)

        print("\n3. Uploading resume to S3...")
        try:
            resume_key = await upload_resume(application, resume_path)
            update_application_artifacts(db, application, resume_key)
        except Exception as e:
            print(f"  Warning: S3 upload failed: {e}")
            print("  Storing local path reference instead...")
            # Store local path as fallback for testing
            artifacts = {"resume_local": str(resume_path)}
            application.artifacts = json.dumps(artifacts)
            db.commit()

        print("\n4. Queueing analysis job...")
        job = queue_analysis_job(db, application)

        print("\n" + "="*50)
        print("Test data seeded successfully!")
        print("="*50)
        print(f"  Requisition ID: {requisition.id} ({requisition.external_id})")
        print(f"  Application ID: {application.id}")
        print(f"  Candidate: {application.candidate_name}")
        print(f"  Status: {application.status}")
        print(f"  Analysis Job ID: {job.id}")
        print("\nTo process, start the processor service or manually run the job.")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
