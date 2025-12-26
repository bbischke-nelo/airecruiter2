"""Workday SOAP client using zeep."""

import asyncio
import base64
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import structlog
import xml.etree.ElementTree as ET
from zeep import AsyncClient, Settings, Plugin
from zeep.plugins import HistoryPlugin
from zeep.transports import AsyncTransport
from zeep.exceptions import Fault

from .config import WorkdayConfig
from .auth import WorkdayAuth

logger = structlog.get_logger()

# Constants
ID_TYPE_WID = "WID"
ID_TYPE_JOB_REQ = "Job_Requisition_ID"
ID_TYPE_CANDIDATE = "Candidate_ID"
ID_TYPE_ATTACHMENT_CATEGORY = "Attachment_Category_ID"


class WorkdayAuthPlugin(Plugin):
    """Zeep plugin to add Bearer token authentication to SOAP requests."""

    def __init__(self, auth: WorkdayAuth):
        self.auth = auth
        self._token: Optional[str] = None

    def set_token(self, token: str) -> None:
        """Update the token to use for subsequent requests."""
        self._token = token

    def egress(self, envelope, http_headers, operation, binding_options):
        """Add Authorization header to outgoing requests."""
        if self._token:
            http_headers["Authorization"] = f"Bearer {self._token}"
        return envelope, http_headers


class WorkdaySOAPClient:
    """Async SOAP client for Workday Recruiting API."""

    def __init__(self, config: WorkdayConfig):
        self.config = config
        self.auth = WorkdayAuth(config)
        self._client: Optional[AsyncClient] = None
        self._transport: Optional[AsyncTransport] = None
        self._auth_plugin: Optional[WorkdayAuthPlugin] = None
        self._history = HistoryPlugin()
        self._last_call_time: float = 0.0

    async def initialize(self) -> None:
        """Initialize the SOAP client with WSDL."""
        logger.info("Initializing Workday SOAP client", wsdl=self.config.recruiting_wsdl_url)

        # Configure zeep settings
        settings = Settings(
            strict=False,  # Workday responses may not be strictly schema-compliant
            xml_huge_tree=True,  # Allow large responses
        )

        # Create async transport
        self._transport = AsyncTransport(timeout=self.config.read_timeout)

        # Create auth plugin for Bearer token
        self._auth_plugin = WorkdayAuthPlugin(self.auth)

        # Load the WSDL
        self._client = AsyncClient(
            self.config.recruiting_wsdl_url,
            transport=self._transport,
            settings=settings,
            plugins=[self._auth_plugin, self._history],
        )

        logger.info("Workday SOAP client initialized")

    async def close(self) -> None:
        """Close the SOAP client."""
        if self._client and hasattr(self._client.transport, "session"):
            await self._client.transport.session.close()
        self._client = None

    async def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting between API calls using monotonic clock."""
        if self.config.rate_limit_delay <= 0:
            return

        now = time.monotonic()
        elapsed = now - self._last_call_time
        if elapsed < self.config.rate_limit_delay:
            await asyncio.sleep(self.config.rate_limit_delay - elapsed)
        self._last_call_time = time.monotonic()

    async def _call_service(
        self,
        operation: str,
        params: Dict[str, Any],
    ) -> Any:
        """Call a SOAP service operation with iterative retry logic.

        Args:
            operation: The SOAP operation name
            params: Parameters for the operation

        Returns:
            Parsed response

        Raises:
            WorkdaySOAPError: If the call fails after retries
        """
        if not self._client or not self._transport:
            raise WorkdaySOAPError("Client not initialized. Call initialize() first.")

        total_attempts = self.config.max_retries + 1
        last_exception = None

        for attempt in range(total_attempts):
            await self._enforce_rate_limit()

            try:
                # Get access token and set on auth plugin
                access_token = await self.auth.get_token()
                self._auth_plugin.set_token(access_token)

                # Get the service and call the operation
                service = self._client.service
                op = getattr(service, operation)
                response = await op(**params)

                return response

            except Fault as e:
                fault_code = getattr(e, "code", "UNKNOWN")
                fault_message = str(e)
                last_exception = e

                logger.error(
                    "Workday SOAP fault",
                    operation=operation,
                    fault_code=fault_code,
                    attempt=attempt + 1,
                    fault_message=fault_message[:500],
                )

                # Check if retryable
                if fault_code == "PROCESSING_FAULT" and attempt < total_attempts - 1:
                    delay = self.config.retry_backoff ** attempt
                    logger.info(f"Retrying in {delay}s", attempt=attempt + 1)
                    await asyncio.sleep(delay)
                    continue

                raise WorkdaySOAPError(f"SOAP fault: {fault_message}") from e

            except Exception as e:
                last_exception = e
                logger.error(
                    "Workday SOAP error",
                    operation=operation,
                    error=str(e),
                    attempt=attempt + 1,
                    exc_info=True,
                )

                # Retry on connection/unknown errors
                if attempt < total_attempts - 1:
                    delay = self.config.retry_backoff ** attempt
                    logger.info(f"Retrying in {delay}s", attempt=attempt + 1)
                    await asyncio.sleep(delay)
                    continue

        raise WorkdaySOAPError(f"SOAP call failed after {total_attempts} attempts: {str(last_exception)}") from last_exception

    async def get_job_requisitions(
        self,
        status: str = "Open",
        page: int = 1,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch job requisitions from Workday.

        Args:
            status: Requisition status filter (Open, Filled, Closed)
            page: Page number
            count: Items per page

        Returns:
            List of requisition data dictionaries
        """
        logger.info("Fetching job requisitions", status=status, page=page, count=count)

        params = {
            "Request_Criteria": {
                "Job_Requisition_Status_Reference": {
                    "ID": [{"type": "Job_Requisition_Status_ID", "_value_1": status}]
                }
            },
            "Response_Filter": {
                "Page": page,
                "Count": count,
            },
            "Response_Group": {
                "Include_Reference": True,
                "Include_Job_Requisition_Definition_Data": True,
            },
        }

        response = await self._call_service("Get_Job_Requisitions", params)

        requisitions = []
        if response and hasattr(response, "Response_Data"):
            # Debug: log the first raw requisition
            reqs = response.Response_Data.Job_Requisition or []
            if reqs:
                logger.debug("Raw requisition sample", raw=str(reqs[0])[:500])
            for req in reqs:
                requisitions.append(self._parse_requisition(req))

        logger.info("Fetched requisitions", count=len(requisitions))
        return requisitions

    async def get_job_applications(
        self,
        requisition_id: str,
        wid: Optional[str] = None,
        page: int = 1,
        count: int = 100,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch candidates for a requisition.

        Args:
            requisition_id: The Job_Requisition_ID
            wid: Optional Workday ID (WID) - preferred for filtering
            page: Page number
            count: Items per page
            since: Only return candidates applied after this time

        Returns:
            List of application data dictionaries
        """
        logger.info(
            "Fetching candidates",
            requisition_id=requisition_id,
            wid=wid,
            since=str(since) if since else "all",
            page=page
        )

        # Build Request Criteria
        # NOTE: Job_Requisition_Reference filter doesn't work in Request_Criteria
        # (causes validation error), so we fetch by date and filter in memory.
        # Also, empty Request_Criteria returns 0 results, so we always need Applied_From.
        request_criteria: Dict[str, Any] = {}

        # Add date filter - required for Get_Candidates to return results
        # Use provided date or default to 2020-01-01 to get all candidates
        filter_date = since if since else datetime(2020, 1, 1)
        applied_from = filter_date.isoformat()
        if not applied_from.endswith("Z") and "+" not in applied_from:
            applied_from += "Z"
        request_criteria["Applied_From"] = applied_from

        params = {
            "Request_Criteria": request_criteria,
            "Response_Filter": {
                "Page": page,
                "Count": count,
            },
            "Response_Group": {
                "Include_Reference": True,
            },
        }

        response = await self._call_service("Get_Candidates", params)

        applications = []
        if response and hasattr(response, "Response_Data") and response.Response_Data:
            for candidate in getattr(response.Response_Data, "Candidate", None) or []:
                # Parse candidate and filter by requisition in memory
                parsed = self._parse_candidate(candidate, requisition_id, wid)
                if parsed:
                    applications.append(parsed)

        logger.info("Fetched candidates", count=len(applications))
        return applications

    def _parse_candidate(
        self, candidate: Any, requisition_id: str, requisition_wid: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Parse a SOAP candidate response into a dictionary.

        Filters to only return candidates with applications for the target requisition.
        """
        data = {}

        # Check if this candidate has an application for the target requisition
        target_application = None
        target_jat = None  # Job Applied To Data

        if hasattr(candidate, "Candidate_Data") and candidate.Candidate_Data:
            cd = candidate.Candidate_Data

            # Find the specific job application
            if hasattr(cd, "Job_Application_Data"):
                apps = cd.Job_Application_Data
                if not isinstance(apps, list):
                    apps = [apps]

                for app in apps:
                    # Check Job Applied To -> Requisition Reference
                    jat_list = getattr(app, "Job_Applied_To_Data", None)
                    if jat_list:
                        if not isinstance(jat_list, list):
                            jat_list = [jat_list]
                        for jat in jat_list:
                            req_ref = getattr(jat, "Job_Requisition_Reference", None)
                            if req_ref:
                                for id_item in getattr(req_ref, "ID", None) or []:
                                    id_value = getattr(id_item, "_value_1", "")
                                    id_type = getattr(id_item, "type", "")
                                    # Match by Job_Requisition_ID or WID
                                    if (id_type == "Job_Requisition_ID" and id_value == requisition_id) or \
                                       (id_type == "WID" and requisition_wid and id_value == requisition_wid):
                                        target_application = app
                                        target_jat = jat
                                        break
                            if target_application:
                                break
                    if target_application:
                        break

        # If we didn't find an application for this requisition, skip this candidate
        if not target_application:
            return None

        data["external_requisition_id"] = requisition_id

        # Extract Candidate Reference
        if hasattr(candidate, "Candidate_Reference") and candidate.Candidate_Reference:
            for id_item in getattr(candidate.Candidate_Reference, "ID", None) or []:
                id_type = getattr(id_item, "type", "")
                id_value = getattr(id_item, "_value_1", "")
                if id_type == ID_TYPE_CANDIDATE:
                    data["external_candidate_id"] = id_value
                elif id_type == ID_TYPE_WID:
                    data["candidate_wid"] = id_value

        # Get application ID from target_jat (the matched Job_Applied_To_Data)
        if target_jat and hasattr(target_jat, "Job_Application_ID"):
            data["external_application_id"] = target_jat.Job_Application_ID
        elif target_application:
            # Try Job_Application_Reference
            app_ref = getattr(target_application, "Job_Application_Reference", None)
            if app_ref:
                for id_item in getattr(app_ref, "ID", None) or []:
                    if getattr(id_item, "type", "") == "Job_Application_ID":
                        data["external_application_id"] = getattr(id_item, "_value_1", "")
                        break

        # Fallback to candidate ID if application ID missing
        if "external_application_id" not in data and "external_candidate_id" in data:
            data["external_application_id"] = data["external_candidate_id"]

        # Extract Candidate Data
        if hasattr(candidate, "Candidate_Data") and candidate.Candidate_Data:
            cd = candidate.Candidate_Data

            # Name Data (directly on Candidate_Data, or via Legal_Name)
            if hasattr(cd, "Name_Data") and cd.Name_Data:
                name_data = cd.Name_Data
                # Try Legal_Name first
                if hasattr(name_data, "Legal_Name") and name_data.Legal_Name:
                    legal = name_data.Legal_Name
                    if hasattr(legal, "Name_Detail_Data") and legal.Name_Detail_Data:
                        nd = legal.Name_Detail_Data
                        first = getattr(nd, "First_Name", "") or ""
                        last = getattr(nd, "Last_Name", "") or ""
                        data["candidate_name"] = f"{first} {last}".strip()
                # Fallback to direct First_Name/Last_Name
                if "candidate_name" not in data:
                    first = getattr(name_data, "First_Name", "") or ""
                    last = getattr(name_data, "Last_Name", "") or ""
                    if first or last:
                        data["candidate_name"] = f"{first} {last}".strip()

            # Email from Contact Data (directly on Candidate_Data)
            if hasattr(cd, "Contact_Data") and cd.Contact_Data:
                contact = cd.Contact_Data
                # Direct Email_Address field
                if hasattr(contact, "Email_Address") and contact.Email_Address:
                    data["candidate_email"] = contact.Email_Address
                # Or Email_Address_Data list
                elif hasattr(contact, "Email_Address_Data"):
                    for email in getattr(contact, "Email_Address_Data", None) or []:
                        if hasattr(email, "Email_Address"):
                            data["candidate_email"] = email.Email_Address
                            break

            # Recruiting Status - Use target_jat we already found
            if target_jat:
                # Try Disposition (e.g. "Screen", "Interview")
                if hasattr(target_jat, "Disposition_Reference") and target_jat.Disposition_Reference:
                    data["workday_status"] = getattr(target_jat.Disposition_Reference, "Descriptor", None)

                # Try Stage if Disposition missing
                if not data.get("workday_status") and hasattr(target_jat, "Stage_Reference") and target_jat.Stage_Reference:
                    # Use Descriptor if available, else try ID value
                    stage_ref = target_jat.Stage_Reference
                    descriptor = getattr(stage_ref, "Descriptor", None)
                    if descriptor:
                        data["workday_status"] = descriptor
                    else:
                        for id_item in getattr(stage_ref, "ID", None) or []:
                            if getattr(id_item, "type", "") == "Recruiting_Stage_ID":
                                data["workday_status"] = getattr(id_item, "_value_1", "")
                                break

            # Fallback to top-level status if application status not found
            if "workday_status" not in data and hasattr(cd, "Status_Reference") and cd.Status_Reference:
                for id_item in getattr(cd.Status_Reference, "ID", None) or []:
                    if getattr(id_item, "type", "") in ("Candidate_Status_ID", "Recruiting_Status_ID"):
                        data["workday_status"] = id_item._value_1
                        break

            # Try alternate status location
            if "workday_status" not in data and hasattr(cd, "Candidate_Status_Data"):
                csd = cd.Candidate_Status_Data
                if hasattr(csd, "Status"):
                    data["workday_status"] = csd.Status

        # Default status if not found
        if "workday_status" not in data:
            data["workday_status"] = "Unknown"

        # Extract applied_at from target_jat
        if target_jat:
            job_app_date = getattr(target_jat, "Job_Application_Date", None)
            if job_app_date:
                # Convert to string if it's a datetime object
                if hasattr(job_app_date, "isoformat"):
                    data["applied_at"] = job_app_date.isoformat()
                else:
                    data["applied_at"] = str(job_app_date)

        # If we don't have a candidate ID, skip this record
        if "external_candidate_id" not in data:
            return None

        return data

    async def get_candidate_attachments(
        self,
        candidate_id: str,
        page: int = 1,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch attachments for a candidate.

        Args:
            candidate_id: The candidate external ID
            page: Page number
            count: Items per page

        Returns:
            List of attachment data dictionaries
        """
        logger.info("Fetching candidate attachments", candidate_id=candidate_id, page=page)

        # Use Request_Criteria to filter by candidate, not Request_References
        # Request_References is for fetching specific attachments by attachment ID
        params = {
            "Request_Criteria": {
                "Candidate_Reference": {
                    "ID": [{"type": ID_TYPE_CANDIDATE, "_value_1": candidate_id}]
                }
            },
            "Response_Filter": {
                "Page": page,
                "Count": count,
            },
        }

        response = await self._call_service("Get_Candidate_Attachments", params)

        attachments = []
        if response and hasattr(response, "Response_Data") and response.Response_Data:
            # Get_Candidate_Attachments returns Candidate_Attachment objects
            for attachment in getattr(response.Response_Data, "Candidate_Attachment", None) or []:
                attachments.append(self._parse_attachment(attachment))

        logger.info("Fetched attachments", count=len(attachments))
        return attachments

    async def put_candidate_attachment(
        self,
        candidate_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/pdf",
        category: str = "Other",
        comment: Optional[str] = None,
    ) -> str:
        """Upload an attachment to a candidate profile.

        Args:
            candidate_id: The candidate external ID
            filename: Name for the file
            content: File content as bytes
            content_type: MIME type
            category: Attachment category
            comment: Optional comment

        Returns:
            Document ID from Workday
        """
        logger.info(
            "Uploading candidate attachment",
            candidate_id=candidate_id,
            filename=filename,
            size=len(content),
        )

        # Base64 encode the content
        encoded_content = base64.b64encode(content).decode("utf-8")

        params = {
            "Candidate_Attachment_Data": {
                "Candidate_Reference": {
                    "ID": [{"type": ID_TYPE_CANDIDATE, "_value_1": candidate_id}]
                },
                "Attachment_Data": {
                    "File_Name": filename,
                    "File": encoded_content,
                    "Category_Reference": {
                        "ID": [{"type": ID_TYPE_ATTACHMENT_CATEGORY, "_value_1": category}]
                    },
                    "Comment": comment or "",
                },
            }
        }

        response = await self._call_service("Put_Candidate_Attachment", params)

        # Extract document ID from response
        doc_id = None
        if response and hasattr(response, "Candidate_Attachment_Reference"):
            ref = response.Candidate_Attachment_Reference
            if hasattr(ref, "ID"):
                for id_item in ref.ID or []:
                    if hasattr(id_item, "_value_1"):
                        doc_id = id_item._value_1
                        break

        logger.info("Attachment uploaded", document_id=doc_id)
        return doc_id or ""

    def _parse_requisition(self, req: Any) -> Dict[str, Any]:
        """Parse a SOAP requisition response into a dictionary."""
        data = {}

        # Extract IDs from reference - we need both Job_Requisition_ID and WID
        if hasattr(req, "Job_Requisition_Reference") and req.Job_Requisition_Reference:
            for id_item in req.Job_Requisition_Reference.ID or []:
                id_type = getattr(id_item, "type", "")
                id_value = getattr(id_item, "_value_1", "")
                if id_type == ID_TYPE_JOB_REQ:
                    data["external_id"] = id_value
                elif id_type == ID_TYPE_WID:
                    data["wid"] = id_value
            logger.debug("Requisition IDs", external_id=data.get("external_id"), wid=data.get("wid"))

        # Extract data fields
        if hasattr(req, "Job_Requisition_Data") and req.Job_Requisition_Data:
            rd = req.Job_Requisition_Data

            # Job details are nested under Job_Requisition_Detail_Data
            if hasattr(rd, "Job_Requisition_Detail_Data") and rd.Job_Requisition_Detail_Data:
                detail = rd.Job_Requisition_Detail_Data
                data["name"] = getattr(detail, "Job_Posting_Title", None)
                data["description"] = getattr(detail, "Job_Description", None)
                # Job_Description contains HTML, we keep it as is.

            # Status - extract from Job_Requisition_Status_Reference
            if hasattr(rd, "Job_Requisition_Status_Reference") and rd.Job_Requisition_Status_Reference:
                status_ref = rd.Job_Requisition_Status_Reference
                # Try Descriptor first, then look in ID array
                status = getattr(status_ref, "Descriptor", None)
                if not status and hasattr(status_ref, "ID"):
                    for id_item in status_ref.ID or []:
                        if getattr(id_item, "type", "") == "Job_Requisition_Status_ID":
                            status = id_item._value_1
                            break
                data["is_active"] = (status or "").upper() == "OPEN"

            # Location - check Position_Data array
            if hasattr(rd, "Position_Data") and rd.Position_Data:
                positions = rd.Position_Data if isinstance(rd.Position_Data, list) else [rd.Position_Data]
                for pos in positions:
                    if hasattr(pos, "Location_Reference") and pos.Location_Reference:
                        loc_ref = pos.Location_Reference
                        if isinstance(loc_ref, list):
                            loc_ref = loc_ref[0] if loc_ref else None
                        if loc_ref:
                            data["location"] = getattr(loc_ref, "Descriptor", None)
                            break

        return data

    async def put_candidate(
        self,
        first_name: str,
        last_name: str,
        email: str,
        phone: Optional[str] = None,
        requisition_id: Optional[str] = None,
        requisition_wid: Optional[str] = None,
        stage: str = "Review",
        resume_content: Optional[bytes] = None,
        resume_filename: Optional[str] = None,
        source: str = "Agency",
        country_code: str = "USA",
    ) -> Dict[str, Any]:
        """Create a new candidate in Workday with optional job application.

        Note: Uses httpx directly instead of zeep due to authentication issues
        with zeep's async transport for write operations.

        Args:
            first_name: Candidate's first name
            last_name: Candidate's last name
            email: Candidate's email address
            phone: Candidate's phone number (optional if email provided)
            requisition_id: Job_Requisition_ID to apply to (optional)
            requisition_wid: Workday ID of requisition (preferred over requisition_id)
            stage: Initial recruiting stage (e.g., "Review", "Screen")
            resume_content: Resume file content as bytes
            resume_filename: Resume filename
            source: Candidate source (e.g., "Agency", "Employee Referral")
            country_code: ISO country code for address/phone

        Returns:
            Dict with candidate_id, candidate_wid, and job_application_id if applicable
        """
        logger.info(
            "Creating candidate in Workday",
            name=f"{first_name} {last_name}",
            email=email,
            requisition_id=requisition_id,
        )

        # Build SOAP envelope directly - zeep has auth issues with Put_Candidate
        # Build Contact_Data section - phone handling is complex (requires country code reference)
        # so we only include email for now
        contact_xml = f"<ns0:Email_Address>{email}</ns0:Email_Address>"

        # Build Job_Application_Data section
        job_app_xml = ""
        if requisition_id or requisition_wid:
            ref_type = "WID" if requisition_wid else "Job_Requisition_ID"
            ref_value = requisition_wid or requisition_id

            # NOTE: Resume upload via Put_Candidate requires additional permissions
            # that may not be enabled for this API client. Skip resume for now.
            # TODO: Use Put_Candidate_Attachment after candidate creation if resume needed
            resume_xml = ""

            job_app_xml = f"""<ns0:Job_Application_Data>
          <ns0:Job_Applied_To_Data>
            <ns0:Job_Requisition_Reference>
              <ns0:ID ns0:type="{ref_type}">{ref_value}</ns0:ID>
            </ns0:Job_Requisition_Reference>
            <ns0:Stage_Reference>
              <ns0:ID ns0:type="Recruiting_Stage_ID">{stage}</ns0:ID>
            </ns0:Stage_Reference>
          </ns0:Job_Applied_To_Data>
          {resume_xml}
        </ns0:Job_Application_Data>"""

        soap_envelope = f'''<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">
  <soap-env:Body>
    <ns0:Put_Candidate_Request xmlns:ns0="urn:com.workday/bsvc">
      <ns0:Candidate_Data>
        <ns0:Name_Data>
          <ns0:Legal_Name>
            <ns0:Name_Detail_Data>
              <ns0:First_Name>{first_name}</ns0:First_Name>
              <ns0:Last_Name>{last_name}</ns0:Last_Name>
            </ns0:Name_Detail_Data>
          </ns0:Legal_Name>
        </ns0:Name_Data>
        <ns0:Contact_Data>
          {contact_xml}
        </ns0:Contact_Data>
        {job_app_xml}
      </ns0:Candidate_Data>
    </ns0:Put_Candidate_Request>
  </soap-env:Body>
</soap-env:Envelope>'''

        # Get access token
        access_token = await self.auth.get_token()

        url = self.config.recruiting_service_url
        headers = {
            "SOAPAction": '""',
            "Content-Type": "text/xml; charset=utf-8",
            "Authorization": f"Bearer {access_token}",
        }

        async with httpx.AsyncClient(timeout=self.config.read_timeout) as client:
            response = await client.post(url, content=soap_envelope, headers=headers)

            if response.status_code != 200:
                logger.error(
                    "Put_Candidate failed",
                    status=response.status_code,
                    response=response.text[:500],
                )
                raise WorkdaySOAPError(f"Put_Candidate failed: {response.text[:500]}")

        # Parse XML response
        root = ET.fromstring(response.text)

        # Define namespaces
        ns = {"wd": "urn:com.workday/bsvc"}

        result = {
            "candidate_id": None,
            "candidate_wid": None,
            "job_application_ids": [],
        }

        # Extract Candidate_Reference IDs
        for id_elem in root.findall(".//wd:Candidate_Reference/wd:ID", ns):
            id_type = id_elem.get(f"{{{ns['wd']}}}type")
            id_value = id_elem.text
            if id_type == "Candidate_ID":
                result["candidate_id"] = id_value
            elif id_type == "WID":
                result["candidate_wid"] = id_value

        # Extract Job_Application IDs
        for id_elem in root.findall(".//wd:Job_Application_Reference/wd:ID", ns):
            id_type = id_elem.get(f"{{{ns['wd']}}}type")
            if id_type == "Job_Application_ID":
                result["job_application_ids"].append(id_elem.text)

        logger.info(
            "Candidate created in Workday",
            candidate_id=result["candidate_id"],
            candidate_wid=result["candidate_wid"],
            job_applications=result["job_application_ids"],
        )

        return result

    async def get_recruiting_stages(self) -> List[Dict[str, Any]]:
        """Fetch available recruiting stages.

        Returns:
            List of stage dictionaries with id and name
        """
        logger.info("Fetching recruiting stages")

        # Try to get stages - this may require a different service or may not be directly available
        # For now, return common default stages
        # TODO: Implement actual stage fetching if the API supports it
        return [
            {"id": "Review", "name": "Review"},
            {"id": "Screen", "name": "Screen"},
            {"id": "Interview", "name": "Interview"},
            {"id": "Offer", "name": "Offer"},
            {"id": "Background_Check", "name": "Background Check"},
        ]

    def _parse_attachment(self, attachment: Any) -> Dict[str, Any]:
        """Parse a SOAP attachment response into a dictionary."""
        data = {}

        data["filename"] = getattr(attachment, "Filename", None)
        data["content_type"] = getattr(attachment, "Content_Type", "application/octet-stream")

        # Decode base64 content
        if hasattr(attachment, "File_Content") and attachment.File_Content:
            try:
                data["content"] = base64.b64decode(attachment.File_Content)
            except Exception as e:
                logger.error("Failed to decode attachment", error=str(e), filename=data["filename"])
                raise WorkdaySOAPError(f"Failed to decode attachment {data['filename']}") from e

        return data


class WorkdaySOAPError(Exception):
    """Raised when a Workday SOAP call fails."""

    pass