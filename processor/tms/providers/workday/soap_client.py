"""Workday SOAP client using zeep."""

import asyncio
import base64
from typing import Any, Dict, List, Optional

import structlog
from zeep import AsyncClient, Settings, Plugin
from zeep.plugins import HistoryPlugin
from zeep.transports import AsyncTransport
from zeep.exceptions import Fault

from .config import WorkdayConfig
from .auth import WorkdayAuth

logger = structlog.get_logger()


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
        self._last_call_time: float = 0

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

        # Create auth plugin
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
        """Enforce rate limiting between API calls."""
        import time

        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < self.config.rate_limit_delay:
            await asyncio.sleep(self.config.rate_limit_delay - elapsed)
        self._last_call_time = time.time()

    async def _call_service(
        self,
        operation: str,
        params: Dict[str, Any],
        retry_count: int = 0,
    ) -> Any:
        """Call a SOAP service operation with retry logic.

        Args:
            operation: The SOAP operation name
            params: Parameters for the operation
            retry_count: Current retry attempt

        Returns:
            Parsed response

        Raises:
            WorkdaySOAPError: If the call fails after retries
        """
        if not self._client or not self._transport:
            raise WorkdaySOAPError("Client not initialized. Call initialize() first.")

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

            logger.error(
                "Workday SOAP fault",
                operation=operation,
                fault_code=fault_code,
                fault_message=fault_message[:500],
            )

            # Check if retryable
            if fault_code in ("PROCESSING_FAULT",) and retry_count < self.config.max_retries:
                delay = self.config.retry_backoff ** retry_count
                logger.info(f"Retrying in {delay}s", attempt=retry_count + 1)
                await asyncio.sleep(delay)
                return await self._call_service(operation, params, retry_count + 1)

            raise WorkdaySOAPError(f"SOAP fault: {fault_message}") from e

        except Exception as e:
            logger.error(
                "Workday SOAP error",
                operation=operation,
                error=str(e),
                exc_info=True,
            )

            # Retry on connection errors
            if retry_count < self.config.max_retries:
                delay = self.config.retry_backoff ** retry_count
                logger.info(f"Retrying in {delay}s", attempt=retry_count + 1)
                await asyncio.sleep(delay)
                return await self._call_service(operation, params, retry_count + 1)

            raise WorkdaySOAPError(f"SOAP call failed: {str(e)}") from e

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
            for req in response.Response_Data.Job_Requisition or []:
                requisitions.append(self._parse_requisition(req))

        logger.info("Fetched requisitions", count=len(requisitions))
        return requisitions

    async def get_job_applications(
        self,
        requisition_id: str,
        page: int = 1,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch job applications for a requisition.

        Args:
            requisition_id: The requisition external ID
            page: Page number
            count: Items per page

        Returns:
            List of application data dictionaries
        """
        logger.info("Fetching job applications", requisition_id=requisition_id, page=page)

        params = {
            "Request_Criteria": {
                "Job_Requisition_Reference": {
                    "ID": [{"type": "Job_Requisition_ID", "_value_1": requisition_id}]
                }
            },
            "Response_Filter": {
                "Page": page,
                "Count": count,
            },
            "Response_Group": {
                "Include_Reference": True,
                "Include_Job_Application_Data": True,
            },
        }

        response = await self._call_service("Get_Job_Applications", params)

        applications = []
        if response and hasattr(response, "Response_Data"):
            for app in response.Response_Data.Job_Application or []:
                applications.append(self._parse_application(app))

        logger.info("Fetched applications", count=len(applications))
        return applications

    async def get_candidate_attachments(
        self,
        candidate_id: str,
    ) -> List[Dict[str, Any]]:
        """Fetch attachments for a candidate.

        Args:
            candidate_id: The candidate external ID

        Returns:
            List of attachment data dictionaries
        """
        logger.info("Fetching candidate attachments", candidate_id=candidate_id)

        params = {
            "Request_References": {
                "Candidate_Reference": {
                    "ID": [{"type": "Candidate_ID", "_value_1": candidate_id}]
                }
            },
            "Response_Group": {
                "Include_Attachment_Data": True,
            },
        }

        response = await self._call_service("Get_Candidates", params)

        attachments = []
        if response and hasattr(response, "Response_Data"):
            for candidate in response.Response_Data.Candidate or []:
                if hasattr(candidate, "Candidate_Data") and candidate.Candidate_Data:
                    if hasattr(candidate.Candidate_Data, "Resume") and candidate.Candidate_Data.Resume:
                        for resume in candidate.Candidate_Data.Resume or []:
                            attachments.append(self._parse_attachment(resume))

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
                    "ID": [{"type": "Candidate_ID", "_value_1": candidate_id}]
                },
                "Attachment_Data": {
                    "File_Name": filename,
                    "File": encoded_content,
                    "Category_Reference": {
                        "ID": [{"type": "Attachment_Category_ID", "_value_1": category}]
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

        # Extract ID from reference
        if hasattr(req, "Job_Requisition_Reference") and req.Job_Requisition_Reference:
            for id_item in req.Job_Requisition_Reference.ID or []:
                if getattr(id_item, "type", "") == "Job_Requisition_ID":
                    data["external_id"] = id_item._value_1

        # Extract data fields
        if hasattr(req, "Job_Requisition_Data") and req.Job_Requisition_Data:
            rd = req.Job_Requisition_Data
            data["name"] = getattr(rd, "Job_Posting_Title", None)
            data["description"] = getattr(rd, "Job_Description_Summary", None)
            data["detailed_description"] = getattr(rd, "Job_Qualifications", None)

            # Location
            if hasattr(rd, "Position_Data") and rd.Position_Data:
                if hasattr(rd.Position_Data, "Location_Reference") and rd.Position_Data.Location_Reference:
                    data["location"] = getattr(rd.Position_Data.Location_Reference, "Descriptor", None)

            # Recruiter
            if hasattr(rd, "Recruiting_Data") and rd.Recruiting_Data:
                if hasattr(rd.Recruiting_Data, "Primary_Recruiter_Reference") and rd.Recruiting_Data.Primary_Recruiter_Reference:
                    data["recruiter_name"] = getattr(rd.Recruiting_Data.Primary_Recruiter_Reference, "Descriptor", None)

            # Status
            if hasattr(rd, "Job_Requisition_Status_Reference") and rd.Job_Requisition_Status_Reference:
                status = getattr(rd.Job_Requisition_Status_Reference, "Descriptor", "Unknown")
                data["is_active"] = status.lower() == "open"

        return data

    def _parse_application(self, app: Any) -> Dict[str, Any]:
        """Parse a SOAP application response into a dictionary."""
        data = {}

        # Extract application ID from reference
        if hasattr(app, "Job_Application_Reference") and app.Job_Application_Reference:
            for id_item in app.Job_Application_Reference.ID or []:
                if hasattr(id_item, "_value_1"):
                    data["external_application_id"] = id_item._value_1
                    break

        # Extract data fields
        if hasattr(app, "Job_Application_Data") and app.Job_Application_Data:
            ad = app.Job_Application_Data

            # Candidate reference
            if hasattr(ad, "Candidate_Reference") and ad.Candidate_Reference:
                for id_item in ad.Candidate_Reference.ID or []:
                    if hasattr(id_item, "_value_1"):
                        data["external_candidate_id"] = id_item._value_1
                        break

            # Requisition reference
            if hasattr(ad, "Job_Requisition_Reference") and ad.Job_Requisition_Reference:
                for id_item in ad.Job_Requisition_Reference.ID or []:
                    if getattr(id_item, "type", "") == "Job_Requisition_ID":
                        data["external_requisition_id"] = id_item._value_1

            # Status
            if hasattr(ad, "Status_Reference") and ad.Status_Reference:
                data["workday_status"] = getattr(ad.Status_Reference, "Descriptor", "Unknown")

            # Application date
            data["applied_at"] = getattr(ad, "Application_Date", None)

            # Personal data
            if hasattr(ad, "Personal_Data") and ad.Personal_Data:
                pd = ad.Personal_Data

                # Name
                if hasattr(pd, "Name_Data") and pd.Name_Data:
                    first = getattr(pd.Name_Data, "First_Name", "") or ""
                    last = getattr(pd.Name_Data, "Last_Name", "") or ""
                    data["candidate_name"] = f"{first} {last}".strip()

                # Email
                if hasattr(pd, "Contact_Data") and pd.Contact_Data:
                    if hasattr(pd.Contact_Data, "Email_Address_Data") and pd.Contact_Data.Email_Address_Data:
                        for email in pd.Contact_Data.Email_Address_Data or []:
                            if hasattr(email, "Email_Address"):
                                data["candidate_email"] = email.Email_Address
                                break

        return data

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
                logger.error("Failed to decode attachment", error=str(e))
                data["content"] = None

        return data


class WorkdaySOAPError(Exception):
    """Raised when a Workday SOAP call fails."""

    pass
