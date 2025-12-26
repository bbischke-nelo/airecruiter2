#!/usr/bin/env python3
"""Inspect Resume_Attachment_Data in candidate responses."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


def dump_object(obj, indent=0, max_depth=15, seen=None):
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
        for i, item in enumerate(obj[:10]):
            print(f"{prefix}  [{i}]:")
            dump_object(item, indent + 2, max_depth, seen.copy())
        if len(obj) > 10:
            print(f"{prefix}  ... and {len(obj) - 10} more items")
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

    # Get candidates with full data
    print("=" * 60)
    print("INSPECTING RESUME_ATTACHMENT_DATA")
    print("=" * 60)

    # Get several candidates
    candidates_to_check = ["C100002", "C100003", "C100004", "C100005", "C100006", "C100007", "C100008", "C100009", "C100010"]

    for cand_id in candidates_to_check:
        print(f"\n{'='*60}")
        print(f"Candidate: {cand_id}")
        print("=" * 60)

        params = {
            "Request_References": {
                "Candidate_Reference": [
                    {"ID": [{"type": "Candidate_ID", "_value_1": cand_id}]}
                ]
            },
            "Response_Group": {
                "Include_Reference": True,
            },
        }

        try:
            response = await service.Get_Candidates(**params)

            if response and hasattr(response, "Response_Data") and response.Response_Data:
                candidates = getattr(response.Response_Data, "Candidate", None) or []
                if candidates:
                    cand = candidates[0]
                    cand_data = getattr(cand, "Candidate_Data", None)

                    if cand_data:
                        # Check Candidate_Attachment_Data
                        att_data = getattr(cand_data, "Candidate_Attachment_Data", None)
                        print(f"\n  Candidate_Attachment_Data: {len(att_data) if att_data else 0} items")
                        if att_data:
                            for i, att in enumerate(att_data[:3]):
                                print(f"\n  Attachment {i+1}:")
                                dump_object(att, indent=2, max_depth=10)

                        # Check Job_Application_Data
                        job_apps = getattr(cand_data, "Job_Application_Data", None)
                        print(f"\n  Job_Application_Data: {len(job_apps) if job_apps else 0} items")

                        if job_apps:
                            for i, app in enumerate(job_apps[:3]):
                                print(f"\n  Application {i+1}:")

                                # Resume_Attachment_Data
                                resume_att = getattr(app, "Resume_Attachment_Data", None)
                                print(f"    Resume_Attachment_Data: {type(resume_att).__name__}")
                                dump_object(resume_att, indent=3, max_depth=10)

                                # Resume_Data
                                resume_data = getattr(app, "Resume_Data", None)
                                print(f"    Resume_Data: {resume_data is not None}")
                                if resume_data:
                                    dump_object(resume_data, indent=3, max_depth=10)
                else:
                    print("  No candidate data returned")
            else:
                print("  No response data")
        except Exception as e:
            print(f"  Error: {e}")

    await client.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
