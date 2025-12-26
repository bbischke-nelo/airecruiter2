#!/usr/bin/env python3
"""Debug script to test candidate attachment retrieval from Workday.

Run from project root:
    PYTHONPATH=. python scripts/debug_attachments.py [candidate_id]

Example:
    PYTHONPATH=. python scripts/debug_attachments.py 5f6a7b8c-9d0e-1234-5678-9abcdef01234
"""

import asyncio
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


async def debug_attachments(candidate_id: str = None):
    """Debug attachment retrieval for a candidate."""
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
        sys.exit(1)

    # Create config
    config = WorkdayConfig(
        tenant_url="https://services1.wd503.myworkday.com",
        tenant_id=tenant,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        api_version="v42.0",
    )

    print(f"Initializing Workday SOAP client...")
    client = WorkdaySOAPClient(config)
    await client.initialize()

    try:
        if candidate_id:
            # Test specific candidate
            print(f"\n=== Testing attachments for candidate: {candidate_id} ===\n")
            await test_candidate_attachments(client, candidate_id)
        else:
            # Get first few candidates and test each
            print(f"\n=== Finding candidates to test ===\n")

            # Get candidates
            service = client._client.service
            auth = WorkdayAuth(config)
            access_token = await auth.get_token()
            client._auth_plugin.set_token(access_token)

            params = {
                "Response_Filter": {
                    "Page": 1,
                    "Count": 5,
                },
                "Response_Group": {
                    "Include_Reference": True,
                },
            }
            response = await service.Get_Candidates(**params)

            if response and hasattr(response, "Response_Data") and response.Response_Data:
                candidates = getattr(response.Response_Data, "Candidate", None) or []
                print(f"Found {len(candidates)} candidates\n")

                for cand in candidates[:3]:
                    # Extract candidate ID (use Candidate_ID, not WID)
                    cand_id = None
                    if hasattr(cand, "Candidate_Reference") and cand.Candidate_Reference:
                        for id_obj in (cand.Candidate_Reference.ID or []):
                            if id_obj.type == "Candidate_ID":
                                cand_id = id_obj._value_1
                                break

                    if cand_id:
                        print(f"--- Candidate: {cand_id} ---")
                        await test_candidate_attachments(client, cand_id)
                        print()
    finally:
        await client.close()


async def test_candidate_attachments(client, candidate_id: str):
    """Test getting attachments for a specific candidate."""
    from processor.tms.providers.workday.soap_client import ID_TYPE_CANDIDATE
    from processor.tms.providers.workday.auth import WorkdayAuth

    service = client._client.service

    # Refresh token
    auth = WorkdayAuth(client.config)
    access_token = await auth.get_token()
    client._auth_plugin.set_token(access_token)

    print(f"Calling Get_Candidate_Attachments for: {candidate_id}")

    # Build request with Request_Criteria
    params = {
        "Request_Criteria": {
            "Candidate_Reference": {
                "ID": [{"type": ID_TYPE_CANDIDATE, "_value_1": candidate_id}]
            }
        },
        "Response_Filter": {
            "Page": 1,
            "Count": 100,
        },
    }

    try:
        response = await service.Get_Candidate_Attachments(**params)

        print(f"Response type: {type(response)}")
        print(f"Response attrs: {[a for a in dir(response) if not a.startswith('_')]}")

        if response and hasattr(response, "Response_Data") and response.Response_Data:
            resp_data = response.Response_Data
            print(f"Response_Data attrs: {[a for a in dir(resp_data) if not a.startswith('_')]}")

            # Try different possible attribute names for attachments
            attachments = None
            for attr_name in ["Candidate_Attachment", "Attachment", "Attachments", "Candidate_Attachments"]:
                if hasattr(resp_data, attr_name):
                    attachments = getattr(resp_data, attr_name)
                    print(f"Found attachments under: {attr_name}")
                    break

            if attachments:
                print(f"Found {len(attachments)} attachments")

                for i, att in enumerate(attachments[:3]):
                    print(f"\n  Attachment {i+1}:")
                    print(f"    Attributes: {[a for a in dir(att) if not a.startswith('_')]}")

                    # Print common attachment properties
                    for prop in ["Filename", "File_Name", "filename", "Content_Type", "content_type",
                                 "File_Content", "file_content", "Content", "content",
                                 "Category", "category", "Document_Category"]:
                        if hasattr(att, prop):
                            val = getattr(att, prop)
                            if prop in ["File_Content", "file_content", "Content", "content"] and val:
                                print(f"    {prop}: <binary data, len={len(val) if isinstance(val, (bytes, str)) else 'unknown'}>")
                            else:
                                print(f"    {prop}: {val}")
            else:
                print("No attachments found in response")

        else:
            print("No Response_Data in response")

            # Check for Results element
            if hasattr(response, "Response_Results") and response.Response_Results:
                results = response.Response_Results
                print(f"Response_Results: total={getattr(results, 'Total_Results', 0)}, pages={getattr(results, 'Total_Pages', 0)}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    candidate_id = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(debug_attachments(candidate_id))
