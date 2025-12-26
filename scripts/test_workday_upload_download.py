#!/usr/bin/env python3
"""Test script for Workday attachment upload AND download.

This script:
1. Uploads a test PDF to a candidate
2. Retrieves the attachment to verify it works
3. Cleans up (optional)

Run from project root:
    PYTHONPATH=. ./venv/bin/python scripts/test_workday_upload_download.py
"""

import asyncio
import os
import sys

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


# Create a minimal test PDF (valid PDF structure)
TEST_PDF_CONTENT = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Test Resume) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF
"""


async def test_upload_download():
    """Test uploading and downloading attachments."""
    from processor.tms.providers.workday.config import WorkdayConfig
    from processor.tms.providers.workday.soap_client import WorkdaySOAPClient
    from processor.tms.providers.workday.auth import WorkdayAuth

    # Get credentials
    client_id = os.getenv("WORKDAY_CLIENT_ID")
    client_secret = os.getenv("WORKDAY_CLIENT_SECRET")
    refresh_token = os.getenv("WORKDAY_REFRESH_TOKEN")
    tenant = os.getenv("WORKDAY_TENANT", "ccfs")

    if not all([client_id, client_secret, refresh_token]):
        print("ERROR: Missing credentials in environment")
        sys.exit(1)

    print_section("Configuration")
    print(f"Tenant: {tenant}")

    config = WorkdayConfig(
        tenant_url="https://services1.wd503.myworkday.com",
        tenant_id=tenant,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        api_version="v42.0",
    )

    print_section("1. Initialize")
    auth = WorkdayAuth(config)
    client = WorkdaySOAPClient(config)
    await client.initialize()
    print("SUCCESS: Client initialized")

    # Get a candidate to test with
    print_section("2. Find Test Candidate")
    service = client._client.service
    access_token = await auth.get_token()
    client._auth_plugin.set_token(access_token)

    params = {
        "Response_Filter": {"Page": 1, "Count": 1},
        "Response_Group": {"Include_Reference": True},
    }
    response = await service.Get_Candidates(**params)

    candidate_id = None
    if response and hasattr(response, "Response_Data") and response.Response_Data:
        raw_candidates = getattr(response.Response_Data, "Candidate", None) or []
        if raw_candidates:
            cand_ref = getattr(raw_candidates[0], "Candidate_Reference", None)
            if cand_ref:
                for id_obj in getattr(cand_ref, "ID", []) or []:
                    if getattr(id_obj, "type", "") == "Candidate_ID":
                        candidate_id = getattr(id_obj, "_value_1", "")
                        break

    if not candidate_id:
        print("ERROR: No candidates found to test with")
        await client.close()
        return

    print(f"Using candidate: {candidate_id}")

    # Upload test attachment
    print_section("3. Upload Test Attachment")
    try:
        doc_id = await client.put_candidate_attachment(
            candidate_id=candidate_id,
            filename="test_resume.pdf",
            content=TEST_PDF_CONTENT,
            content_type="application/pdf",
            category="Resume",
            comment="Test upload from script",
        )
        print(f"SUCCESS: Uploaded, document ID = {doc_id}")
    except Exception as e:
        print(f"FAILED to upload: {e}")
        import traceback
        traceback.print_exc()
        await client.close()
        return

    # Wait a moment for Workday to process
    print("\nWaiting 3 seconds for Workday to process...")
    await asyncio.sleep(3)

    # Try to retrieve the attachment
    print_section("4. Retrieve Attachments")
    try:
        attachments = await client.get_candidate_attachments(candidate_id)
        print(f"Found {len(attachments)} attachments")

        for i, att in enumerate(attachments):
            print(f"\n  Attachment {i+1}:")
            print(f"    filename: {att.get('filename')}")
            print(f"    content_type: {att.get('content_type')}")
            if att.get('content'):
                print(f"    content: {len(att['content'])} bytes")
                # Verify it's valid PDF
                if att['content'][:4] == b'%PDF':
                    print("    ✓ Content is valid PDF")
                else:
                    print(f"    ✗ Content starts with: {att['content'][:20]}")
            else:
                print("    ✗ NO CONTENT RETURNED")
    except Exception as e:
        print(f"FAILED to retrieve: {e}")
        import traceback
        traceback.print_exc()

    # Also show raw response
    print_section("5. Raw SOAP Response")
    try:
        access_token = await auth.get_token()
        client._auth_plugin.set_token(access_token)

        params = {
            "Request_Criteria": {
                "Candidate_Reference": {
                    "ID": [{"type": "Candidate_ID", "_value_1": candidate_id}]
                }
            },
            "Response_Filter": {"Page": 1, "Count": 10},
            "Response_Group": {"Include_Reference": True},
        }

        response = await service.Get_Candidate_Attachments(**params)

        if response and hasattr(response, "Response_Data") and response.Response_Data:
            attachments = getattr(response.Response_Data, "Candidate_Attachment", None) or []
            print(f"Raw response has {len(attachments)} attachments")

            for att in attachments:
                print("\n  Attachment object attributes:")
                for attr in sorted(dir(att)):
                    if attr.startswith('_'):
                        continue
                    try:
                        val = getattr(att, attr)
                        if callable(val):
                            continue
                        if isinstance(val, bytes):
                            print(f"    {attr}: {len(val)} bytes")
                        elif val is not None:
                            val_str = str(val)
                            if len(val_str) > 100:
                                val_str = val_str[:100] + "..."
                            print(f"    {attr}: {val_str}")
                    except:
                        pass
        else:
            print("No attachments in response")

            # Check total results
            results = getattr(response, "Response_Results", None)
            if results:
                print(f"Total_Results: {getattr(results, 'Total_Results', 'N/A')}")
    except Exception as e:
        print(f"Raw response error: {e}")

    await client.close()
    print_section("Done")


if __name__ == "__main__":
    asyncio.run(test_upload_download())
