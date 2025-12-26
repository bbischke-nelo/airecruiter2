#!/usr/bin/env python3
"""Inspect raw Workday SOAP responses without any parsing assumptions."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


def dump_object(obj, indent=0, seen=None):
    """Recursively dump an object's structure."""
    if seen is None:
        seen = set()

    prefix = "  " * indent
    obj_id = id(obj)

    if obj_id in seen:
        print(f"{prefix}<circular reference>")
        return
    seen.add(obj_id)

    if obj is None:
        print(f"{prefix}None")
        return

    if isinstance(obj, (str, int, float, bool, bytes)):
        if isinstance(obj, str) and len(obj) > 100:
            print(f"{prefix}{type(obj).__name__}: {obj[:100]}... (len={len(obj)})")
        elif isinstance(obj, bytes) and len(obj) > 100:
            print(f"{prefix}bytes: {len(obj)} bytes")
        else:
            print(f"{prefix}{type(obj).__name__}: {repr(obj)}")
        return

    if isinstance(obj, (list, tuple)):
        print(f"{prefix}{type(obj).__name__} ({len(obj)} items):")
        for i, item in enumerate(obj[:10]):  # Limit to first 10
            print(f"{prefix}  [{i}]:")
            dump_object(item, indent + 2, seen.copy())
        if len(obj) > 10:
            print(f"{prefix}  ... and {len(obj) - 10} more items")
        return

    if isinstance(obj, dict):
        print(f"{prefix}dict ({len(obj)} keys):")
        for key, value in list(obj.items())[:20]:
            print(f"{prefix}  {key}:")
            dump_object(value, indent + 2, seen.copy())
        return

    # Object with attributes
    print(f"{prefix}{type(obj).__name__}:")

    # Try to get all attributes
    attrs = []
    if hasattr(obj, '__dict__'):
        attrs.extend(obj.__dict__.keys())

    # Also check for zeep-style attributes
    for attr in dir(obj):
        if not attr.startswith('_') and attr not in attrs:
            attrs.append(attr)

    for attr in sorted(set(attrs))[:30]:
        if attr.startswith('_'):
            continue
        try:
            value = getattr(obj, attr)
            if callable(value):
                continue
            print(f"{prefix}  .{attr}:")
            dump_object(value, indent + 2, seen.copy())
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

    # 1. Get candidates first
    print("=" * 60)
    print("1. GETTING CANDIDATES")
    print("=" * 60)

    params = {
        "Response_Filter": {"Page": 1, "Count": 5},
        "Response_Group": {"Include_Reference": True},
    }

    response = await service.Get_Candidates(**params)

    # Extract candidate IDs
    candidate_ids = []
    if response and hasattr(response, "Response_Data") and response.Response_Data:
        raw_candidates = getattr(response.Response_Data, "Candidate", None) or []
        print(f"Found {len(raw_candidates)} candidates")

        for cand in raw_candidates:
            cand_ref = getattr(cand, "Candidate_Reference", None)
            if cand_ref:
                ids = getattr(cand_ref, "ID", []) or []
                for id_obj in ids:
                    id_type = getattr(id_obj, "type", "")
                    id_val = getattr(id_obj, "_value_1", "")
                    if id_type == "Candidate_ID":
                        candidate_ids.append(id_val)
                        print(f"  - {id_val}")
                        break

    # 2. Get attachments (no filter - get all)
    print("\n" + "=" * 60)
    print("2. GET ALL ATTACHMENTS (NO FILTER)")
    print("=" * 60)

    params = {
        "Response_Filter": {"Page": 1, "Count": 50},
        "Response_Group": {"Include_Reference": True},
    }

    response = await service.Get_Candidate_Attachments(**params)

    print("\nFull Response Structure:")
    dump_object(response)

    # 3. Check Response_Results
    print("\n" + "=" * 60)
    print("3. RESPONSE RESULTS")
    print("=" * 60)

    if hasattr(response, "Response_Results"):
        results = response.Response_Results
        print(f"Total_Results: {getattr(results, 'Total_Results', 'N/A')}")
        print(f"Total_Pages: {getattr(results, 'Total_Pages', 'N/A')}")
        print(f"Page_Results: {getattr(results, 'Page_Results', 'N/A')}")
        print(f"Page: {getattr(results, 'Page', 'N/A')}")

    # 4. Check Response_Data more carefully
    print("\n" + "=" * 60)
    print("4. RESPONSE DATA DETAILS")
    print("=" * 60)

    if hasattr(response, "Response_Data"):
        data = response.Response_Data
        print(f"Response_Data type: {type(data)}")
        print(f"Response_Data is None: {data is None}")

        if data is not None:
            print("\nAll attributes of Response_Data:")
            for attr in dir(data):
                if not attr.startswith('_'):
                    try:
                        val = getattr(data, attr)
                        if not callable(val):
                            print(f"  .{attr} = {type(val).__name__}")
                            if val:
                                print(f"    Value: {val}")
                    except Exception as e:
                        print(f"  .{attr} = <error: {e}>")

    # 5. Try getting attachments for each candidate
    print("\n" + "=" * 60)
    print("5. ATTACHMENTS PER CANDIDATE")
    print("=" * 60)

    for cid in candidate_ids[:5]:
        print(f"\nCandidate {cid}:")

        params = {
            "Request_Criteria": {
                "Candidate_Reference": {
                    "ID": [{"type": "Candidate_ID", "_value_1": cid}]
                }
            },
            "Response_Filter": {"Page": 1, "Count": 20},
            "Response_Group": {"Include_Reference": True},
        }

        try:
            response = await service.Get_Candidate_Attachments(**params)

            results = getattr(response, "Response_Results", None)
            if results:
                total = getattr(results, "Total_Results", 0)
                print(f"  Total_Results: {total}")

            data = getattr(response, "Response_Data", None)
            if data:
                # Try different attribute names
                for attr in ["Candidate_Attachment", "Attachment", "Candidate_Attachment_Data"]:
                    val = getattr(data, attr, None)
                    if val:
                        print(f"  Found {attr}: {len(val) if hasattr(val, '__len__') else val}")
                        if hasattr(val, '__iter__') and not isinstance(val, str):
                            for i, item in enumerate(list(val)[:2]):
                                print(f"    [{i}]: {type(item).__name__}")
                                dump_object(item, indent=3)
        except Exception as e:
            print(f"  Error: {e}")

    await client.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
