#!/usr/bin/env python3
"""Submit a test candidate to Workday.

Usage:
    python scripts/submit_to_workday.py [--requisition REGIO004114]

This script:
1. Loads test application data from test_data/
2. Connects to Workday
3. Fetches the requisition to get its WID
4. Submits the candidate with resume attached
"""

import asyncio
import json
import sys
from pathlib import Path
from argparse import ArgumentParser

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from processor.tms.providers.workday.soap_client import WorkdaySOAPClient
from processor.tms.providers.workday.config import WorkdayConfig
from processor.config import settings

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
)

logger = structlog.get_logger()


async def find_requisition(client: WorkdaySOAPClient, requisition_id: str) -> dict:
    """Find a requisition by ID and return its details including WID."""
    logger.info("Searching for requisition", requisition_id=requisition_id)

    # Fetch open requisitions and find the one we want
    page = 1
    while True:
        requisitions = await client.get_job_requisitions(status="Open", page=page, count=100)

        for req in requisitions:
            if req.get("external_id") == requisition_id:
                logger.info("Found requisition",
                           external_id=req.get("external_id"),
                           wid=req.get("wid"),
                           name=req.get("name"))
                return req

        if len(requisitions) < 100:
            break
        page += 1

    # Try closed/filled requisitions too
    for status in ["Filled", "Closed"]:
        requisitions = await client.get_job_requisitions(status=status, page=1, count=100)
        for req in requisitions:
            if req.get("external_id") == requisition_id:
                logger.info("Found requisition (non-open)",
                           external_id=req.get("external_id"),
                           wid=req.get("wid"),
                           name=req.get("name"),
                           status=status)
                return req

    return None


async def submit_candidate(
    client: WorkdaySOAPClient,
    app_data: dict,
    resume_path: Path,
    requisition_id: str,
    requisition_wid: str = None,
) -> dict:
    """Submit a candidate to Workday."""

    first_name = app_data.get("first_name", "")
    last_name = app_data.get("last_name", "")
    email = app_data.get("email", "")
    phone = app_data.get("primary_phone", "")

    # Read resume
    resume_content = None
    resume_filename = None
    if resume_path and resume_path.exists():
        resume_content = resume_path.read_bytes()
        resume_filename = resume_path.name
        logger.info("Loaded resume", filename=resume_filename, size=len(resume_content))

    logger.info("Submitting candidate to Workday",
               name=f"{first_name} {last_name}",
               email=email,
               requisition_id=requisition_id,
               requisition_wid=requisition_wid)

    result = await client.put_candidate(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        requisition_id=requisition_id,
        requisition_wid=requisition_wid,
        stage="Review",  # Initial stage - may need to adjust for your tenant
        resume_content=resume_content,
        resume_filename=resume_filename,
        source="Agency",  # May need to adjust for your tenant
    )

    return result


async def main():
    parser = ArgumentParser(description="Submit a test candidate to Workday")
    parser.add_argument("--requisition", "-r", default="REGIO004114",
                       help="Requisition ID to apply to (default: REGIO004114)")
    parser.add_argument("--stage", "-s", default="Review",
                       help="Initial recruiting stage (default: Review)")
    parser.add_argument("--dry-run", "-n", action="store_true",
                       help="Don't actually submit, just show what would be sent")
    args = parser.parse_args()

    # Find test data
    project_root = Path(__file__).parent.parent
    test_data_dir = project_root / "test_data"

    json_files = list(test_data_dir.glob("*.json"))
    docx_files = list(test_data_dir.glob("*.docx"))

    if not json_files:
        logger.error("No application JSON found in test_data/")
        sys.exit(1)

    app_json_path = json_files[0]
    resume_path = docx_files[0] if docx_files else None

    logger.info("Loading test data",
               application=app_json_path.name,
               resume=resume_path.name if resume_path else None)

    app_data = json.loads(app_json_path.read_text())

    # Show candidate info
    print("\n" + "="*60)
    print("CANDIDATE INFO")
    print("="*60)
    print(f"  Name:  {app_data.get('first_name')} {app_data.get('last_name')}")
    print(f"  Email: {app_data.get('email')}")
    print(f"  Phone: {app_data.get('primary_phone')}")
    print(f"  City:  {app_data.get('city')}, {app_data.get('state')}")
    print(f"  Resume: {resume_path.name if resume_path else 'None'}")
    print(f"  Target Requisition: {args.requisition}")
    print("="*60 + "\n")

    if args.dry_run:
        logger.info("Dry run mode - not submitting to Workday")
        return

    # Initialize Workday client from processor settings
    if not settings.WORKDAY_CLIENT_ID or not settings.WORKDAY_CLIENT_SECRET:
        logger.error("Workday credentials not configured")
        print("\nError: Workday credentials not found in environment.")
        print("Make sure these are set in .env:")
        print("  WORKDAY_TENANT_URL")
        print("  WORKDAY_TENANT_ID")
        print("  WORKDAY_CLIENT_ID")
        print("  WORKDAY_CLIENT_SECRET")
        print("  WORKDAY_REFRESH_TOKEN")
        sys.exit(1)

    config = WorkdayConfig(
        tenant_url=settings.WORKDAY_TENANT_URL,
        tenant_id=settings.WORKDAY_TENANT_ID,
        client_id=settings.WORKDAY_CLIENT_ID,
        client_secret=settings.WORKDAY_CLIENT_SECRET,
        refresh_token=settings.WORKDAY_REFRESH_TOKEN,
        api_version=settings.WORKDAY_API_VERSION,
    )
    client = WorkdaySOAPClient(config)

    try:
        await client.initialize()

        # Find the requisition to get its WID
        requisition = await find_requisition(client, args.requisition)

        if not requisition:
            logger.error("Requisition not found", requisition_id=args.requisition)
            print(f"\nError: Could not find requisition {args.requisition} in Workday")
            print("Make sure the requisition exists and is accessible with your credentials.")
            sys.exit(1)

        print(f"\nFound requisition: {requisition.get('name')}")
        print(f"  ID:  {requisition.get('external_id')}")
        print(f"  WID: {requisition.get('wid')}")
        print(f"  Active: {requisition.get('is_active')}")
        print()

        # Submit the candidate
        result = await submit_candidate(
            client=client,
            app_data=app_data,
            resume_path=resume_path,
            requisition_id=args.requisition,
            requisition_wid=requisition.get("wid"),
        )

        print("\n" + "="*60)
        print("SUCCESS!")
        print("="*60)
        print(f"  Candidate ID:  {result.get('candidate_id')}")
        print(f"  Candidate WID: {result.get('candidate_wid')}")
        print(f"  Job Applications: {result.get('job_application_ids')}")
        print("="*60 + "\n")

        print("You can now sync this requisition to pull the candidate into the system.")

    except Exception as e:
        logger.exception("Failed to submit candidate")
        print(f"\nError: {e}")
        print("\nThis might be a permissions issue. Check that your Workday credentials have")
        print("access to create candidates via the Put_Candidate operation.")
        sys.exit(1)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
