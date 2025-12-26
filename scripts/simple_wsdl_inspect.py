#!/usr/bin/env python3
"""Simple script to inspect zeep type structure."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


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

    # Get a candidate and look at the resume attachment data structure
    service = client._client.service
    access_token = await client.auth.get_token()
    client._auth_plugin.set_token(access_token)

    print("Fetching candidate C100002...")
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
            cand = candidates[0]
            cand_data = getattr(cand, "Candidate_Data", None)

            if cand_data:
                job_apps = getattr(cand_data, "Job_Application_Data", None) or []
                if job_apps:
                    app = job_apps[0]
                    print(f"\nJob Application attributes:")
                    for attr in dir(app):
                        if not attr.startswith('_'):
                            val = getattr(app, attr, None)
                            if val is not None and not callable(val):
                                print(f"  .{attr} = {type(val).__name__}")
                                if 'Resume' in attr or 'Attachment' in attr:
                                    print(f"    Value: {val}")
                                    # Dig deeper if it's a list or object
                                    if isinstance(val, list):
                                        print(f"    List length: {len(val)}")
                                        if val:
                                            item = val[0]
                                            print(f"    Item type: {type(item).__name__}")
                                            for item_attr in dir(item):
                                                if not item_attr.startswith('_'):
                                                    item_val = getattr(item, item_attr, None)
                                                    if item_val is not None and not callable(item_val):
                                                        print(f"      .{item_attr}: {item_val}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
