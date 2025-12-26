#!/usr/bin/env python3
"""Test script for resume fetching - checks both attachment paths.

Workday has two places resumes can exist:
1. Candidate-level attachments via Get_Candidate_Attachments
2. Job application resumes via Get_Candidates -> Resume_Attachment_Data

This script tests both paths.

Usage:
    PYTHONPATH=. ./venv/bin/python scripts/test_resume_fetch.py
    PYTHONPATH=. ./venv/bin/python scripts/test_resume_fetch.py --candidate C100002
"""

import asyncio
import base64
import os
from dotenv import load_dotenv

load_dotenv()


async def main(candidate_id: str = None):
    from processor.tms.providers.workday.config import WorkdayConfig
    from processor.tms.providers.workday.soap_client import WorkdaySOAPClient

    config = WorkdayConfig(
        tenant_url=os.environ.get("WORKDAY_TENANT_URL", ""),
        tenant_id=os.environ.get("WORKDAY_TENANT_ID", ""),
        client_id=os.environ.get("WORKDAY_CLIENT_ID", ""),
        client_secret=os.environ.get("WORKDAY_CLIENT_SECRET", ""),
        refresh_token=os.environ.get("WORKDAY_REFRESH_TOKEN", ""),
    )

    client = WorkdaySOAPClient(config)
    await client.initialize()

    service = client._client.service
    access_token = await client.auth.get_token()
    client._auth_plugin.set_token(access_token)

    # Get candidate IDs to test
    if candidate_id:
        candidate_ids = [candidate_id]
    else:
        # Fetch some candidates
        print("Fetching candidates...")
        params = {
            "Response_Filter": {"Page": 1, "Count": 10},
            "Response_Group": {"Include_Reference": True},
        }
        response = await service.Get_Candidates(**params)

        candidate_ids = []
        if response and hasattr(response, "Response_Data") and response.Response_Data:
            for cand in getattr(response.Response_Data, "Candidate", None) or []:
                cand_ref = getattr(cand, "Candidate_Reference", None)
                if cand_ref:
                    for id_obj in getattr(cand_ref, "ID", []) or []:
                        if getattr(id_obj, "type", "") == "Candidate_ID":
                            candidate_ids.append(getattr(id_obj, "_value_1", ""))
                            break
        print(f"Found {len(candidate_ids)} candidates: {candidate_ids}")

    # Test each candidate
    for cid in candidate_ids:
        print(f"\n{'='*60}")
        print(f"TESTING CANDIDATE: {cid}")
        print("=" * 60)

        # PATH 1: Get_Candidate_Attachments
        print("\n1. Via Get_Candidate_Attachments API:")
        try:
            attachments = await client.get_candidate_attachments(cid)
            print(f"   Found {len(attachments)} attachments")
            for i, att in enumerate(attachments):
                filename = att.get("filename", "unknown")
                content = att.get("content")
                content_type = att.get("content_type", "unknown")
                print(f"   [{i+1}] {filename} ({content_type})")
                if content:
                    print(f"       Size: {len(content)} bytes")
                else:
                    print("       No content (might need to fetch separately)")
        except Exception as e:
            print(f"   ERROR: {e}")

        # PATH 2: Resume_Attachment_Data from Get_Candidates
        print("\n2. Via Get_Candidates -> Resume_Attachment_Data:")
        try:
            params = {
                "Request_References": {
                    "Candidate_Reference": [
                        {"ID": [{"type": "Candidate_ID", "_value_1": cid}]}
                    ]
                },
                "Response_Group": {
                    "Include_Reference": True,
                    # Don't exclude attachments
                },
            }
            response = await service.Get_Candidates(**params)

            if response and hasattr(response, "Response_Data") and response.Response_Data:
                candidates = getattr(response.Response_Data, "Candidate", None) or []
                if candidates:
                    cand = candidates[0]
                    cand_data = getattr(cand, "Candidate_Data", None)

                    if cand_data:
                        # Check Candidate_Attachment_Data
                        cand_attachments = getattr(cand_data, "Candidate_Attachment_Data", None) or []
                        print(f"   Candidate_Attachment_Data: {len(cand_attachments)} items")
                        for i, att in enumerate(cand_attachments):
                            print(f"   [{i+1}] Candidate attachment:")
                            for attr in ["Filename", "File_Content", "Mime_Type"]:
                                val = getattr(att, attr, None)
                                if val:
                                    if attr == "File_Content":
                                        print(f"       {attr}: {len(val)} chars (base64)")
                                    else:
                                        print(f"       {attr}: {val}")

                        # Check Job_Application_Data -> Resume_Attachment_Data
                        job_apps = getattr(cand_data, "Job_Application_Data", None) or []
                        print(f"   Job_Application_Data: {len(job_apps)} applications")

                        for j, app in enumerate(job_apps):
                            resume_attachments = getattr(app, "Resume_Attachment_Data", None) or []
                            print(f"   Application [{j+1}] Resume_Attachment_Data: {len(resume_attachments)} items")

                            for i, att in enumerate(resume_attachments):
                                print(f"     Resume [{i+1}]:")

                                # Try to find file content and metadata
                                for attr in dir(att):
                                    if not attr.startswith('_'):
                                        val = getattr(att, attr, None)
                                        if val is not None and not callable(val):
                                            if 'content' in attr.lower() or 'file' in attr.lower() or 'data' in attr.lower():
                                                if isinstance(val, (str, bytes)) and len(str(val)) > 100:
                                                    print(f"       .{attr}: {len(str(val))} chars/bytes")
                                                else:
                                                    print(f"       .{attr}: {val}")
                                            elif 'name' in attr.lower() or 'type' in attr.lower() or 'mime' in attr.lower():
                                                print(f"       .{attr}: {val}")

                                # Also dump all attributes for debugging
                                print("       All attributes:")
                                for attr in sorted(dir(att)):
                                    if not attr.startswith('_'):
                                        val = getattr(att, attr, None)
                                        if val is not None and not callable(val):
                                            val_str = str(val)
                                            if len(val_str) > 100:
                                                val_str = f"{val_str[:100]}... ({len(val_str)} chars)"
                                            print(f"         .{attr} = {val_str}")
                else:
                    print("   No candidate data returned")
            else:
                print("   No response data")
        except Exception as e:
            print(f"   ERROR: {e}")
            import traceback
            traceback.print_exc()

    await client.close()
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("""
If you see 0 attachments in both paths, the sandbox has no resume data.
To test with real data:
1. Upload a resume to a candidate via Workday UI
2. Re-run this script with that candidate ID

The production code (soap_client.py:get_candidate_attachments) uses Path 1.
If resumes are in Path 2 (Resume_Attachment_Data), the code needs updating.
""")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", "-c", help="Specific candidate ID to test")
    args = parser.parse_args()

    asyncio.run(main(args.candidate))
