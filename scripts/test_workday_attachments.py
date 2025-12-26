#!/usr/bin/env python3
"""Test script for Workday attachment fetching.

Run from project root:
    PYTHONPATH=. python scripts/test_workday_attachments.py

Or with venv:
    PYTHONPATH=. ./venv/bin/python scripts/test_workday_attachments.py

This script tests:
1. OAuth token refresh
2. SOAP client initialization
3. Fetching candidates
4. Fetching attachments for a candidate
5. Parsing attachment data structure
"""

import asyncio
import os
import sys
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


def print_object_structure(obj, prefix="", max_depth=3, current_depth=0):
    """Recursively print object structure for debugging."""
    if current_depth >= max_depth:
        print(f"{prefix}... (max depth reached)")
        return

    if obj is None:
        print(f"{prefix}None")
        return

    if isinstance(obj, (str, int, float, bool)):
        val = str(obj)
        if len(val) > 100:
            val = val[:100] + "..."
        print(f"{prefix}{type(obj).__name__}: {val}")
        return

    if isinstance(obj, bytes):
        print(f"{prefix}bytes: {len(obj)} bytes")
        return

    if isinstance(obj, list):
        print(f"{prefix}list[{len(obj)}]:")
        for i, item in enumerate(obj[:3]):  # Only first 3
            print_object_structure(item, prefix + f"  [{i}] ", max_depth, current_depth + 1)
        if len(obj) > 3:
            print(f"{prefix}  ... and {len(obj) - 3} more")
        return

    # Object with attributes
    attrs = [a for a in dir(obj) if not a.startswith('_')]
    print(f"{prefix}{type(obj).__name__}:")
    for attr in attrs[:20]:  # Limit attributes shown
        try:
            val = getattr(obj, attr)
            if callable(val):
                continue
            print_object_structure(val, prefix + f"  .{attr} = ", max_depth, current_depth + 1)
        except Exception as e:
            print(f"{prefix}  .{attr} = <error: {e}>")


async def test_workday_attachments(test_candidate_id: str = None):
    """Test Workday attachment fetching.

    Args:
        test_candidate_id: Optional specific candidate ID to test (from prod logs)
    """
    from processor.tms.providers.workday.config import WorkdayConfig
    from processor.tms.providers.workday.soap_client import WorkdaySOAPClient
    from processor.tms.providers.workday.auth import WorkdayAuth

    # Get credentials
    client_id = os.getenv("WORKDAY_CLIENT_ID")
    client_secret = os.getenv("WORKDAY_CLIENT_SECRET")
    refresh_token = os.getenv("WORKDAY_REFRESH_TOKEN")
    tenant = os.getenv("WORKDAY_TENANT", "ccfs")

    if not all([client_id, client_secret, refresh_token]):
        print("ERROR: Missing WORKDAY_CLIENT_ID, WORKDAY_CLIENT_SECRET, or WORKDAY_REFRESH_TOKEN")
        print("Set these in .env file or environment variables")
        sys.exit(1)

    print_section("Configuration")
    print(f"Tenant: {tenant}")
    print(f"Client ID: {client_id[:20]}...")

    # Create config
    config = WorkdayConfig(
        tenant_url="https://services1.wd503.myworkday.com",
        tenant_id=tenant,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        api_version="v42.0",
    )

    # Test 1: OAuth
    print_section("1. Testing OAuth Token")
    auth = WorkdayAuth(config)
    try:
        token = await auth.get_token()
        print(f"SUCCESS: Got token: {token[:40]}...")
    except Exception as e:
        print(f"FAILED: {e}")
        return

    # Test 2: Initialize SOAP client
    print_section("2. Initializing SOAP Client")
    client = WorkdaySOAPClient(config)
    try:
        await client.initialize()
        print("SUCCESS: SOAP client initialized")
    except Exception as e:
        print(f"FAILED: {e}")
        return

    # Test 3: Fetch requisitions first
    print_section("3. Fetching Requisitions")
    try:
        requisitions = await client.get_job_requisitions(status="Open", count=5)
        print(f"SUCCESS: Got {len(requisitions)} requisitions")
        for req in requisitions[:3]:
            print(f"  - {req.get('external_id')}: {req.get('name')}")
    except Exception as e:
        print(f"FAILED: {e}")
        requisitions = []

    # Test 4: Fetch candidates (try without requisition filter first)
    print_section("4. Fetching Candidates")
    candidates = []
    try:
        # Try fetching all candidates
        service = client._client.service
        access_token = await auth.get_token()
        client._auth_plugin.set_token(access_token)

        params = {
            "Response_Filter": {
                "Page": 1,
                "Count": 10,
            },
            "Response_Group": {
                "Include_Reference": True,
            },
        }

        response = await service.Get_Candidates(**params)

        if response and hasattr(response, "Response_Data") and response.Response_Data:
            raw_candidates = getattr(response.Response_Data, "Candidate", None) or []
            print(f"SUCCESS: Got {len(raw_candidates)} candidates")

            for cand in raw_candidates[:5]:
                cand_ref = getattr(cand, "Candidate_Reference", None)
                if cand_ref:
                    ids = getattr(cand_ref, "ID", []) or []
                    for id_obj in ids:
                        id_type = getattr(id_obj, "type", "")
                        id_val = getattr(id_obj, "_value_1", "")
                        if id_type == "Candidate_ID":
                            candidates.append({"external_candidate_id": id_val})
                            print(f"  - Candidate ID: {id_val}")
                            break
        else:
            print("No candidates in response")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

    # If a specific candidate ID was provided, test that first
    if test_candidate_id:
        print_section(f"5. Testing Specific Candidate: {test_candidate_id}")
        try:
            attachments = await client.get_candidate_attachments(test_candidate_id)
            print(f"Result: {len(attachments)} attachments")

            for i, att in enumerate(attachments):
                print(f"\n  Attachment {i+1}:")
                for key, value in att.items():
                    if key == 'content' and value:
                        print(f"    {key}: {len(value)} bytes")
                    elif isinstance(value, str) and len(value) > 50:
                        print(f"    {key}: {value[:50]}...")
                    else:
                        print(f"    {key}: {value}")

            # If no attachments, do a raw SOAP call to see what's returned
            if not attachments:
                print("\nRaw SOAP response for this candidate:")
                service = client._client.service
                access_token = await auth.get_token()
                client._auth_plugin.set_token(access_token)

                params = {
                    "Request_Criteria": {
                        "Candidate_Reference": {
                            "ID": [{"type": "Candidate_ID", "_value_1": test_candidate_id}]
                        }
                    },
                    "Response_Filter": {"Page": 1, "Count": 20},
                    "Response_Group": {"Include_Reference": True},
                }

                response = await service.Get_Candidate_Attachments(**params)
                print_object_structure(response, "  ", max_depth=4)
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()

    # Test 5b: Find a candidate with attachments from the list
    print_section("5b. Searching Candidates for Attachments")
    found_attachments = False
    candidate_with_attachments = None

    for cand in candidates:
        candidate_id = cand.get('external_candidate_id')
        try:
            attachments = await client.get_candidate_attachments(candidate_id)
            if attachments:
                print(f"FOUND: Candidate {candidate_id} has {len(attachments)} attachments!")
                candidate_with_attachments = candidate_id
                found_attachments = True

                for i, att in enumerate(attachments):
                    print(f"\n  Attachment {i+1}:")
                    for key, value in att.items():
                        if key == 'content' and value:
                            print(f"    {key}: {len(value)} bytes")
                        elif isinstance(value, str) and len(value) > 50:
                            print(f"    {key}: {value[:50]}...")
                        else:
                            print(f"    {key}: {value}")
                break
            else:
                print(f"  {candidate_id}: no attachments")
        except Exception as e:
            print(f"  {candidate_id}: error - {e}")

    if not found_attachments:
        print("\nNo candidates with attachments found in first 10 candidates")

    # Test 5b: Try fetching ALL attachments (no candidate filter)
    print_section("5b. Fetching ALL Attachments (no filter)")
    try:
        service = client._client.service
        access_token = await auth.get_token()
        client._auth_plugin.set_token(access_token)

        params = {
            "Response_Filter": {
                "Page": 1,
                "Count": 20,
            },
            "Response_Group": {
                "Include_Reference": True,
            },
        }

        response = await service.Get_Candidate_Attachments(**params)

        if response and hasattr(response, "Response_Data") and response.Response_Data:
            attachments = getattr(response.Response_Data, "Candidate_Attachment", None) or []
            print(f"SUCCESS: Found {len(attachments)} attachments total")

            for i, att in enumerate(attachments[:5]):
                print(f"\n  Attachment {i+1}:")
                print_object_structure(att, "    ", max_depth=3)
        else:
            results = getattr(response, "Response_Results", None)
            if results:
                total = getattr(results, "Total_Results", 0)
                print(f"No Response_Data, but Total_Results = {total}")
            else:
                print("No attachments found (empty Response_Data)")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Test 6: Raw SOAP call to see full response structure
    print_section("6. Raw SOAP Response Structure")
    if candidates:
        candidate_id = candidates[0].get('external_candidate_id')
        try:
            service = client._client.service
            access_token = await auth.get_token()
            client._auth_plugin.set_token(access_token)

            params = {
                "Request_Criteria": {
                    "Candidate_Reference": {
                        "ID": [{"type": "Candidate_ID", "_value_1": candidate_id}]
                    }
                },
                "Response_Filter": {
                    "Page": 1,
                    "Count": 5,
                },
                "Response_Group": {
                    "Include_Reference": True,
                },
            }

            response = await service.Get_Candidate_Attachments(**params)

            print("Response structure:")
            print_object_structure(response, "  ", max_depth=4)

            # Check for attachment content specifically
            if response and hasattr(response, "Response_Data") and response.Response_Data:
                attachments = getattr(response.Response_Data, "Candidate_Attachment", None) or []
                print(f"\nFound {len(attachments)} Candidate_Attachment objects")

                for i, att in enumerate(attachments[:2]):
                    print(f"\n  Attachment {i+1} detailed structure:")
                    # Look for file content
                    for attr in dir(att):
                        if attr.startswith('_'):
                            continue
                        try:
                            val = getattr(att, attr)
                            if callable(val):
                                continue
                            if 'content' in attr.lower() or 'data' in attr.lower() or 'file' in attr.lower():
                                if isinstance(val, bytes):
                                    print(f"    {attr}: {len(val)} bytes (FOUND CONTENT!)")
                                elif val:
                                    print(f"    {attr}: {type(val).__name__} = {str(val)[:100]}")
                        except:
                            pass

        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()

    # Cleanup
    print_section("Cleanup")
    await client.close()
    print("Done!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Workday attachment fetching")
    parser.add_argument("--candidate", "-c", help="Specific candidate ID to test")
    args = parser.parse_args()

    asyncio.run(test_workday_attachments(test_candidate_id=args.candidate))
