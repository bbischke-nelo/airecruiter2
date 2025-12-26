#!/usr/bin/env python3
"""Inspect candidate data to see where attachments might be."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


def dump_object(obj, indent=0, max_depth=10, seen=None):
    """Recursively dump an object's structure."""
    if seen is None:
        seen = set()

    if indent > max_depth:
        print("  " * indent + "... (max depth)")
        return

    prefix = "  " * indent
    obj_id = id(obj)

    if obj_id in seen:
        print(f"{prefix}<circular reference>")
        return
    seen.add(obj_id)

    if obj is None:
        print(f"{prefix}None")
        return

    if isinstance(obj, (str, int, float, bool)):
        if isinstance(obj, str) and len(obj) > 200:
            print(f"{prefix}str: '{obj[:200]}...' (len={len(obj)})")
        else:
            print(f"{prefix}{type(obj).__name__}: {repr(obj)}")
        return

    if isinstance(obj, bytes):
        print(f"{prefix}bytes: {len(obj)} bytes")
        return

    if isinstance(obj, (list, tuple)):
        print(f"{prefix}{type(obj).__name__} ({len(obj)} items):")
        for i, item in enumerate(obj[:5]):
            print(f"{prefix}  [{i}]:")
            dump_object(item, indent + 2, max_depth, seen.copy())
        if len(obj) > 5:
            print(f"{prefix}  ... and {len(obj) - 5} more items")
        return

    if isinstance(obj, dict):
        print(f"{prefix}dict ({len(obj)} keys):")
        for key, value in list(obj.items())[:20]:
            print(f"{prefix}  {key}:")
            dump_object(value, indent + 2, max_depth, seen.copy())
        return

    # Skip Decimal to avoid infinite recursion
    if "Decimal" in type(obj).__name__:
        print(f"{prefix}Decimal: {obj}")
        return

    # Object with attributes
    print(f"{prefix}{type(obj).__name__}:")

    # Get zeep-style attributes
    attrs = []
    for attr in dir(obj):
        if not attr.startswith('_'):
            try:
                val = getattr(obj, attr)
                if not callable(val):
                    attrs.append(attr)
            except:
                pass

    for attr in sorted(set(attrs))[:30]:
        try:
            value = getattr(obj, attr)
            print(f"{prefix}  .{attr}:")
            dump_object(value, indent + 2, max_depth, seen.copy())
        except Exception as e:
            print(f"{prefix}  .{attr}: <error: {e}>")


async def main():
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

    # Get a single candidate with FULL data
    print("=" * 60)
    print("1. GETTING SINGLE CANDIDATE WITH FULL DATA")
    print("=" * 60)

    # Try different Response_Group options to get attachments
    params = {
        "Request_References": {
            "Candidate_Reference": [
                {"ID": [{"type": "Candidate_ID", "_value_1": "C100002"}]}
            ]
        },
        "Response_Group": {
            "Include_Reference": True,
        },
    }

    response = await service.Get_Candidates(**params)

    if response and hasattr(response, "Response_Data") and response.Response_Data:
        candidates = getattr(response.Response_Data, "Candidate", None) or []
        if candidates:
            print(f"\nCandidate data for C100002:")
            dump_object(candidates[0], max_depth=6)

    # Check what operations are available
    print("\n" + "=" * 60)
    print("2. AVAILABLE OPERATIONS")
    print("=" * 60)

    for op_name in sorted(dir(service)):
        if not op_name.startswith('_') and 'Attach' in op_name:
            print(f"  {op_name}")

    # Get job applications to see if attachments are there
    print("\n" + "=" * 60)
    print("3. GET JOB APPLICATIONS")
    print("=" * 60)

    # First get a requisition
    req_params = {
        "Response_Filter": {"Page": 1, "Count": 1},
        "Request_Criteria": {"Job_Requisition_Status": "Open"},
    }
    req_response = await service.Get_Job_Requisitions(**req_params)

    req_id = None
    if req_response and hasattr(req_response, "Response_Data") and req_response.Response_Data:
        reqs = getattr(req_response.Response_Data, "Job_Requisition", None) or []
        if reqs:
            req_ref = getattr(reqs[0], "Job_Requisition_Reference", None)
            if req_ref:
                ids = getattr(req_ref, "ID", []) or []
                for id_obj in ids:
                    if getattr(id_obj, "type", "") == "Job_Requisition_ID":
                        req_id = getattr(id_obj, "_value_1", "")
                        print(f"Found requisition: {req_id}")
                        break

    if req_id:
        app_params = {
            "Request_Criteria": {
                "Job_Requisition_Reference": {
                    "ID": [{"type": "Job_Requisition_ID", "_value_1": req_id}]
                }
            },
            "Response_Filter": {"Page": 1, "Count": 5},
        }

        app_response = await service.Get_Evergreen_Requisition_Job_Applications(**app_params)

        print("\nJob Applications Response:")
        if app_response and hasattr(app_response, "Response_Data") and app_response.Response_Data:
            apps = getattr(app_response.Response_Data, "Evergreen_Job_Application", None) or []
            print(f"Found {len(apps)} applications")
            if apps:
                print("\nFirst application structure:")
                dump_object(apps[0], max_depth=6)
        else:
            print("No applications found")
            # Try regular Get_Job_Applications
            print("\nTrying Get_Job_Applications...")
            try:
                app_response2 = await service.Get_Job_Applications(**app_params)
                if app_response2:
                    dump_object(app_response2, max_depth=4)
            except Exception as e:
                print(f"Error: {e}")

    await client.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
