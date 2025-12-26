#!/usr/bin/env python3
"""Inspect WSDL types to understand Resume_Attachment_Data structure."""

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

    # Access the zeep client's type factory
    print("=" * 60)
    print("LOOKING FOR RESUME/ATTACHMENT TYPES IN WSDL")
    print("=" * 60)

    # Use zeep's type factory to get types
    factory = client._client.type_factory('ns0')

    # Try to get specific types we're interested in
    print("\nTrying to access specific types:")

    resume_types = []
    attachment_types = []

    # Try accessing Resume_Attachment types
    type_names = [
        "Job_Application_Resume_Attachment_DataType",
        "Resume_Attachment_DataType",
        "Candidate_Attachment_DataType",
        "Candidate_AttachmentType",
        "Attachment_DataType",
    ]

    for type_name in type_names:
        try:
            t = getattr(factory, type_name, None)
            if t:
                print(f"\nFound: {type_name}")
                resume_types.append((type_name, t))
        except Exception as e:
            print(f"  {type_name}: error - {e}")

    print(f"\nFound {len(resume_types)} Resume types:")
    for name, t in resume_types[:20]:
        print(f"  {name}")

    print(f"\nFound {len(attachment_types)} Attachment types:")
    for name, t in attachment_types[:20]:
        print(f"  {name}")

    # Look at Job_Application_Resume_Attachment_DataType specifically
    print("\n" + "=" * 60)
    print("LOOKING FOR RESUME DATA TYPE STRUCTURE")
    print("=" * 60)

    for name, type_obj in resume_types:
        if 'Resume_Attachment_Data' in str(name):
            print(f"\nType: {name}")
            if hasattr(type_obj, 'elements'):
                for elem_name, elem in type_obj.elements:
                    print(f"  .{elem_name}: {elem.type}")
            # Try elements_nested for complex types
            if hasattr(type_obj, 'elements_nested'):
                print("  Nested elements:")
                for item in type_obj.elements_nested:
                    print(f"    {item}")

    # Look at Candidate_Attachment type
    print("\n" + "=" * 60)
    print("CANDIDATE_ATTACHMENT TYPE STRUCTURE")
    print("=" * 60)

    for name, type_obj in attachment_types:
        if 'Candidate_AttachmentType' in str(name) or 'Candidate_Attachment_Data' in str(name):
            print(f"\nType: {name}")
            if hasattr(type_obj, 'elements'):
                for elem_name, elem in type_obj.elements:
                    print(f"  .{elem_name}: {elem.type}")

    await client.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
