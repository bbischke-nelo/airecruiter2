#!/usr/bin/env python3
"""Test script for Workday SOAP client.

Run from project root:
    cd /path/to/airecruiter2
    PYTHONPATH=. python processor/test_workday_soap.py

Or with explicit env vars:
    WORKDAY_CLIENT_ID=xxx WORKDAY_CLIENT_SECRET=xxx WORKDAY_REFRESH_TOKEN=xxx \
    PYTHONPATH=. python processor/test_workday_soap.py
"""

import asyncio
import os
import sys

# Try to load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Use environment variables directly


async def test_workday():
    """Test Workday SOAP connection and operations."""
    from processor.tms.providers.workday.config import WorkdayConfig
    from processor.tms.providers.workday.soap_client import WorkdaySOAPClient
    from processor.tms.providers.workday.auth import WorkdayAuth

    # Get credentials from environment
    client_id = os.getenv("WORKDAY_CLIENT_ID")
    client_secret = os.getenv("WORKDAY_CLIENT_SECRET")
    refresh_token = os.getenv("WORKDAY_REFRESH_TOKEN")
    tenant = os.getenv("WORKDAY_TENANT", "ccfs")

    if not all([client_id, client_secret, refresh_token]):
        print("ERROR: Missing WORKDAY_CLIENT_ID, WORKDAY_CLIENT_SECRET, or WORKDAY_REFRESH_TOKEN")
        sys.exit(1)

    print(f"Testing Workday SOAP client...")
    print(f"  Tenant: {tenant}")
    print(f"  Client ID: {client_id[:20]}...")

    # Create config
    config = WorkdayConfig(
        tenant_url="https://services1.wd503.myworkday.com",
        tenant_id=tenant,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        api_version="v42.0",
    )

    print(f"\n1. Testing OAuth token refresh...")
    auth = WorkdayAuth(config)
    try:
        token = await auth.get_token()
        print(f"   SUCCESS: Got access token: {token[:30]}...")
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    print(f"\n2. Initializing SOAP client...")
    client = WorkdaySOAPClient(config)
    try:
        await client.initialize()
        print(f"   SUCCESS: SOAP client initialized")
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    # Test 3: Get Requisitions
    print(f"\n3. Fetching job requisitions (Get_Job_Requisitions)...")
    try:
        requisitions = await client.get_job_requisitions(status="Open", count=5)
        print(f"   SUCCESS: Got {len(requisitions)} requisitions")

        for req in requisitions[:2]:
            print(f"\n      === Requisition: {req.get('external_id')} ===")
            print(f"      Name: {req.get('name')}")
            print(f"      Description: {(req.get('description') or '')[:80]}...")
            print(f"      Is Active: {req.get('is_active')}")
    except Exception as e:
        print(f"   FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Test 4: Get Candidates
    print(f"\n4. Fetching candidates (Get_Candidates)...")
    try:
        candidates = await client.get_job_applications("dummy", count=5)
        print(f"   SUCCESS: Got {len(candidates)} candidates")

        for cand in candidates[:3]:
            print(f"\n      === Candidate: {cand.get('external_candidate_id')} ===")
            print(f"      Name: {cand.get('candidate_name')}")
            print(f"      Email: {cand.get('candidate_email')}")
    except Exception as e:
        print(f"   FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Test 5: Get Candidate Attachments (for first candidate if found)
    print(f"\n5. Fetching candidate attachments (Get_Candidate_Attachments)...")
    try:
        # Try to get attachments for a test candidate
        # We'll test with a dummy ID first to see the API structure
        service = client._client.service
        access_token = await auth.get_token()
        client._auth_plugin.set_token(access_token)

        # First, let's see what operations are available for attachments
        print(f"   Testing Get_Candidate_Attachments operation...")

        params = {
            "Response_Filter": {
                "Page": 1,
                "Count": 1,
            },
        }
        response = await service.Get_Candidate_Attachments(**params)
        print(f"   SUCCESS: Get_Candidate_Attachments works")
        print(f"   Response type: {type(response)}")
        if response and hasattr(response, "Response_Data"):
            print(f"   Has Response_Data: Yes")
    except Exception as e:
        print(f"   FAILED: {e}")
        # Don't print full traceback for expected failures

    # Test 6: Check Put_Candidate_Attachment structure (without actually uploading)
    print(f"\n6. Checking Put_Candidate_Attachment operation structure...")
    try:
        service = client._client.service
        # Just check if the operation exists
        if hasattr(service, "Put_Candidate_Attachment"):
            print(f"   SUCCESS: Put_Candidate_Attachment operation exists")
        else:
            print(f"   FAILED: Operation not found")
    except Exception as e:
        print(f"   FAILED: {e}")

    # Test 7: Explore Get_Candidates response structure
    print(f"\n7. Exploring Get_Candidates response structure...")
    try:
        service = client._client.service
        access_token = await auth.get_token()
        client._auth_plugin.set_token(access_token)

        # Correct Response_Group params: Include_Reference, Exclude_All_Attachments
        params = {
            "Response_Filter": {
                "Page": 1,
                "Count": 2,
            },
            "Response_Group": {
                "Include_Reference": True,
                "Exclude_All_Attachments": False,
            },
        }
        response = await service.Get_Candidates(**params)

        if response and hasattr(response, "Response_Data") and response.Response_Data:
            candidates = getattr(response.Response_Data, "Candidate", None) or []
            print(f"   SUCCESS: Got {len(candidates)} candidates")

            if candidates:
                cand = candidates[0]
                print(f"\n   Candidate structure:")
                print(f"   - Top level: {[a for a in dir(cand) if not a.startswith('_')]}")

                if hasattr(cand, "Candidate_Reference") and cand.Candidate_Reference:
                    ref = cand.Candidate_Reference
                    print(f"   - Reference IDs: {[{'type': id.type, 'value': id._value_1} for id in (ref.ID or [])]}")
        else:
            print(f"   SUCCESS: API call worked but returned no candidates")
    except Exception as e:
        print(f"   FAILED: {e}")

    print(f"\n8. Closing client...")
    await client.close()
    print(f"   Done!")


if __name__ == "__main__":
    asyncio.run(test_workday())
