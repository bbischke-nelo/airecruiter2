"""Workday SOAP client using zeep."""

import asyncio
import base64
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import structlog
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
                # Note: Get_Candidates only supports Include_Reference and Exclude_All_Attachments
                # Candidate profile data (work history, education, skills) comes from the resume parsing
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

    async def get_applicant_profile(
        self,
        candidate_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch detailed applicant profile using Get_Applicants API.

        Get_Applicants has richer Response_Group options than Get_Candidates,
        including personal info (phone, address) and qualification profile
        (work experience, education, skills).

        Args:
            candidate_id: The Candidate_ID (not WID)

        Returns:
            Dictionary with profile data or None if not found
        """
        logger.info("Fetching applicant profile", candidate_id=candidate_id)

        params = {
            "Request_References": {
                "Applicant_Reference": [
                    {"ID": [{"type": ID_TYPE_CANDIDATE, "_value_1": candidate_id}]}
                ]
            },
            "Response_Group": {
                "Include_Reference": True,
                "Include_Personal_Information": True,
                "Include_Qualification_Profile": True,
            },
        }

        try:
            response = await self._call_service("Get_Applicants", params)
        except Exception as e:
            # Get_Applicants fails for non-pre-hires - this is expected
            # Only log at debug level to avoid spam
            logger.debug(
                "Get_Applicants returned no data (candidate not a pre-hire)",
                candidate_id=candidate_id,
            )
            return None

        if not response or not hasattr(response, "Response_Data") or not response.Response_Data:
            return None

        applicants = getattr(response.Response_Data, "Applicant", None) or []
        if not applicants:
            return None

        applicant = applicants[0] if isinstance(applicants, list) else applicants
        return self._parse_applicant_profile(applicant)

    def _parse_applicant_profile(self, applicant: Any) -> Dict[str, Any]:
        """Parse applicant profile data from Get_Applicants response."""
        data = {}

        # Get Applicant_Data (Pre-Hire_Data_WWSType in WSDL)
        app_data = getattr(applicant, "Applicant_Data", None)
        if not app_data:
            return data

        # Parse Personal_Data for contact info
        personal = getattr(app_data, "Personal_Data", None)
        if personal:
            # Contact Data
            contact = getattr(personal, "Contact_Data", None)
            if contact:
                # Phone numbers
                phone_list = getattr(contact, "Phone_Data", None)
                if phone_list:
                    if not isinstance(phone_list, list):
                        phone_list = [phone_list]
                    for phone in phone_list:
                        phone_num = (
                            getattr(phone, "Phone_Number", None) or
                            getattr(phone, "Complete_Phone_Number", None) or
                            getattr(phone, "Formatted_Phone", None)
                        )
                        if phone_num:
                            data["phone_number"] = str(phone_num)
                            break

                # Email addresses (may have multiple)
                email_list = getattr(contact, "Email_Address_Data", None)
                if email_list:
                    if not isinstance(email_list, list):
                        email_list = [email_list]
                    emails = []
                    for email_item in email_list:
                        email_addr = getattr(email_item, "Email_Address", None)
                        if email_addr:
                            emails.append(email_addr)
                    if emails:
                        data["primary_email"] = emails[0]
                        if len(emails) > 1:
                            data["secondary_email"] = emails[1]

                # Address data
                addr_list = getattr(contact, "Address_Data", None)
                if addr_list:
                    if not isinstance(addr_list, list):
                        addr_list = [addr_list]
                    for addr in addr_list:
                        # City
                        city = getattr(addr, "Municipality", None) or getattr(addr, "City_Subdivision_1", None)
                        if city:
                            data["city"] = city

                        # State/Region
                        region = getattr(addr, "Country_Region_Descriptor", None)
                        if not region:
                            region_ref = getattr(addr, "Region_Reference", None) or getattr(addr, "Country_Region_Reference", None)
                            if region_ref:
                                region = getattr(region_ref, "Descriptor", None)
                        if region:
                            data["state"] = region

                        if data.get("city") or data.get("state"):
                            break

        # Parse Qualification_Data for work history, education, skills
        qual = getattr(app_data, "Qualification_Data", None)
        if qual:
            # Work Experience
            work_exp = getattr(qual, "Experience", None) or getattr(qual, "Work_Experience", None)
            if work_exp:
                if not isinstance(work_exp, list):
                    work_exp = [work_exp]
                work_history = []
                for job in work_exp[:10]:
                    job_entry = {}
                    job_entry["company"] = (
                        getattr(job, "Company_Name", None) or
                        getattr(job, "Company", None) or
                        getattr(job, "Employer", None)
                    )
                    job_entry["title"] = (
                        getattr(job, "Job_Title", None) or
                        getattr(job, "Title", None) or
                        getattr(job, "Position", None)
                    )
                    start_year = getattr(job, "Start_Year", None)
                    start_month = getattr(job, "Start_Month", None)
                    if start_year:
                        job_entry["start_date"] = f"{start_year}-{start_month or 1:02d}-01"
                    end_year = getattr(job, "End_Year", None)
                    end_month = getattr(job, "End_Month", None)
                    if end_year:
                        job_entry["end_date"] = f"{end_year}-{end_month or 1:02d}-01"
                    job_entry["description"] = getattr(job, "Responsibilities", None) or getattr(job, "Description", None)
                    if job_entry.get("company") or job_entry.get("title"):
                        work_history.append(job_entry)
                if work_history:
                    data["work_history"] = work_history

            # Education
            edu_data = getattr(qual, "Education", None)
            if edu_data:
                if not isinstance(edu_data, list):
                    edu_data = [edu_data]
                education = []
                for edu in edu_data[:5]:
                    edu_entry = {}
                    edu_entry["school"] = getattr(edu, "School_Name", None) or getattr(edu, "School", None)
                    edu_entry["degree"] = getattr(edu, "Degree", None)
                    degree_ref = getattr(edu, "Degree_Reference", None)
                    if degree_ref and not edu_entry.get("degree"):
                        edu_entry["degree"] = getattr(degree_ref, "Descriptor", None)
                    edu_entry["field"] = getattr(edu, "Field_Of_Study", None) or getattr(edu, "Major", None)
                    grad_year = getattr(edu, "Graduation_Year", None) or getattr(edu, "Last_Year_Attended", None)
                    if grad_year:
                        edu_entry["graduation_date"] = f"{grad_year}-01-01"
                    if edu_entry.get("school") or edu_entry.get("degree"):
                        education.append(edu_entry)
                if education:
                    data["education"] = education

            # Skills/Competencies
            skills_data = getattr(qual, "Competency", None) or getattr(qual, "Skills", None)
            if skills_data:
                if not isinstance(skills_data, list):
                    skills_data = [skills_data]
                skills = []
                for skill in skills_data[:20]:
                    skill_name = (
                        getattr(skill, "Competency_Descriptor", None) or
                        getattr(skill, "Skill_Descriptor", None) or
                        getattr(skill, "Name", None)
                    )
                    if not skill_name:
                        skill_ref = getattr(skill, "Competency_Reference", None) or getattr(skill, "Skill_Reference", None)
                        if skill_ref:
                            skill_name = getattr(skill_ref, "Descriptor", None)
                    if skill_name:
                        skills.append(skill_name)
                if skills:
                    data["skills"] = skills

        logger.info(
            "Parsed applicant profile",
            has_phone=bool(data.get("phone_number")),
            has_city=bool(data.get("city")),
            has_work_history=bool(data.get("work_history")),
            has_education=bool(data.get("education")),
            has_skills=bool(data.get("skills")),
        )
        return data

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
                    emails = []
                    for email in getattr(contact, "Email_Address_Data", None) or []:
                        if hasattr(email, "Email_Address"):
                            emails.append(email.Email_Address)
                    if emails:
                        data["candidate_email"] = emails[0]
                        if len(emails) > 1:
                            data["secondary_email"] = emails[1]

                # Phone number from Contact Data
                if hasattr(contact, "Phone_Data"):
                    phone_list = getattr(contact, "Phone_Data", None)
                    if phone_list:
                        if not isinstance(phone_list, list):
                            phone_list = [phone_list]
                        for phone in phone_list:
                            phone_num = getattr(phone, "Phone_Number", None) or getattr(phone, "Complete_Phone_Number", None)
                            if phone_num:
                                data["phone_number"] = str(phone_num)
                                break

                # Address from Contact Data
                if hasattr(contact, "Address_Data"):
                    addr_list = getattr(contact, "Address_Data", None)
                    if addr_list:
                        if not isinstance(addr_list, list):
                            addr_list = [addr_list]
                        for addr in addr_list:
                            if hasattr(addr, "Municipality"):
                                data["city"] = getattr(addr, "Municipality", None)
                            if hasattr(addr, "Region_Reference"):
                                region = getattr(addr, "Region_Reference", None)
                                if region and hasattr(region, "Descriptor"):
                                    data["state"] = region.Descriptor
                            # Only take first address
                            if data.get("city") or data.get("state"):
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

        # Extract application source from Job_Application_Data
        if target_application:
            source_ref = getattr(target_application, "Source_Reference", None)
            if source_ref:
                data["application_source"] = getattr(source_ref, "Descriptor", None)
            # Try alternate location
            if not data.get("application_source"):
                source_data = getattr(target_application, "Source_Data", None)
                if source_data:
                    data["application_source"] = getattr(source_data, "Source", None)

        # Extract work history, education, skills from Candidate_Data or Candidate_Profile_Data
        # The data can be in different locations depending on Workday configuration
        profile_sources = []
        if hasattr(candidate, "Candidate_Data") and candidate.Candidate_Data:
            profile_sources.append(candidate.Candidate_Data)
        if hasattr(candidate, "Candidate_Profile_Data") and candidate.Candidate_Profile_Data:
            profile_sources.append(candidate.Candidate_Profile_Data)
        if hasattr(candidate, "Profile_Data") and candidate.Profile_Data:
            profile_sources.append(candidate.Profile_Data)

        work_history = []
        education = []
        skills = []

        for cd in profile_sources:
            # Work history - check multiple possible field names
            if not work_history:
                emp_history = (
                    getattr(cd, "Employment_History", None) or
                    getattr(cd, "Employment_History_Data", None) or
                    getattr(cd, "Work_Experience_Data", None) or
                    getattr(cd, "Job_History_Data", None)
                )
                if emp_history:
                    if not isinstance(emp_history, list):
                        emp_history = [emp_history]
                    for job in emp_history[:10]:  # Limit to 10 entries
                        job_entry = {}
                        job_entry["company"] = getattr(job, "Company_Name", None) or getattr(job, "Employer_Name", None) or getattr(job, "Company", None)
                        job_entry["title"] = getattr(job, "Job_Title", None) or getattr(job, "Position_Title", None) or getattr(job, "Title", None)
                        start = getattr(job, "Start_Date", None)
                        end = getattr(job, "End_Date", None)
                        if start:
                            job_entry["start_date"] = start.isoformat() if hasattr(start, "isoformat") else str(start)
                        if end:
                            job_entry["end_date"] = end.isoformat() if hasattr(end, "isoformat") else str(end)
                        job_entry["description"] = getattr(job, "Job_Description", None) or getattr(job, "Responsibilities", None) or getattr(job, "Description", None)
                        if job_entry.get("company") or job_entry.get("title"):
                            work_history.append(job_entry)

            # Education history
            if not education:
                edu_history = (
                    getattr(cd, "Education_History", None) or
                    getattr(cd, "Education_Data", None) or
                    getattr(cd, "Education", None)
                )
                if edu_history:
                    if not isinstance(edu_history, list):
                        edu_history = [edu_history]
                    for edu in edu_history[:5]:  # Limit to 5 entries
                        edu_entry = {}
                        edu_entry["school"] = getattr(edu, "School_Name", None) or getattr(edu, "School", None) or getattr(edu, "Institution", None)
                        edu_entry["degree"] = getattr(edu, "Degree", None) or getattr(edu, "Degree_Name", None)
                        degree_ref = getattr(edu, "Degree_Reference", None)
                        if degree_ref and not edu_entry.get("degree"):
                            edu_entry["degree"] = getattr(degree_ref, "Descriptor", None)
                        edu_entry["field"] = getattr(edu, "Field_of_Study", None) or getattr(edu, "Major", None) or getattr(edu, "Area_of_Study", None)
                        grad_date = getattr(edu, "Graduation_Date", None) or getattr(edu, "End_Date", None) or getattr(edu, "Completion_Date", None)
                        if grad_date:
                            edu_entry["graduation_date"] = grad_date.isoformat() if hasattr(grad_date, "isoformat") else str(grad_date)
                        if edu_entry.get("school") or edu_entry.get("degree"):
                            education.append(edu_entry)

            # Skills
            if not skills:
                skills_data = (
                    getattr(cd, "Skills_Data", None) or
                    getattr(cd, "Skill_Data", None) or
                    getattr(cd, "Skills", None) or
                    getattr(cd, "Competency_Data", None)
                )
                if skills_data:
                    if not isinstance(skills_data, list):
                        skills_data = [skills_data]
                    for skill in skills_data[:20]:  # Limit to 20 skills
                        skill_name = (
                            getattr(skill, "Skill_Name", None) or
                            getattr(skill, "Skill", None) or
                            getattr(skill, "Name", None) or
                            getattr(skill, "Competency_Name", None)
                        )
                        if not skill_name:
                            skill_ref = getattr(skill, "Skill_Reference", None) or getattr(skill, "Competency_Reference", None)
                            if skill_ref:
                                skill_name = getattr(skill_ref, "Descriptor", None)
                        if skill_name:
                            skills.append(skill_name)

        if work_history:
            data["work_history"] = work_history
        if education:
            data["education"] = education
        if skills:
            data["skills"] = skills

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
            "Response_Group": {
                "Include_Reference": True,
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

    async def get_candidate_resume_from_application(
        self,
        candidate_id: str,
    ) -> List[Dict[str, Any]]:
        """Fetch resume attachments from a candidate's job applications.

        This is an alternative path to get_candidate_attachments - resumes can be
        attached either at the candidate level or at the job application level.

        Args:
            candidate_id: The candidate external ID

        Returns:
            List of attachment data dictionaries from Resume_Attachment_Data
        """
        logger.info("Fetching resume from candidate job applications", candidate_id=candidate_id)

        params = {
            "Request_References": {
                "Candidate_Reference": [
                    {"ID": [{"type": ID_TYPE_CANDIDATE, "_value_1": candidate_id}]}
                ]
            },
            "Response_Group": {
                "Include_Reference": True,
                # Don't exclude attachments - we want Resume_Attachment_Data
            },
        }

        response = await self._call_service("Get_Candidates", params)

        attachments = []
        if response and hasattr(response, "Response_Data") and response.Response_Data:
            candidates = getattr(response.Response_Data, "Candidate", None) or []
            for candidate in candidates:
                cand_data = getattr(candidate, "Candidate_Data", None)
                if not cand_data:
                    continue

                # Check Job_Application_Data for Resume_Attachment_Data
                job_apps = getattr(cand_data, "Job_Application_Data", None) or []
                if not isinstance(job_apps, list):
                    job_apps = [job_apps]

                for app in job_apps:
                    resume_attachments = getattr(app, "Resume_Attachment_Data", None) or []
                    if not isinstance(resume_attachments, list):
                        resume_attachments = [resume_attachments]

                    for att in resume_attachments:
                        parsed = self._parse_resume_attachment(att)
                        if parsed:
                            attachments.append(parsed)

        logger.info("Fetched resume attachments from applications", count=len(attachments))
        return attachments

    def _parse_resume_attachment(self, attachment: Any) -> Optional[Dict[str, Any]]:
        """Parse a Resume_Attachment_Data object."""
        if attachment is None:
            return None

        data = {}

        # Log available attributes for debugging
        attrs = [a for a in dir(attachment) if not a.startswith('_')]
        logger.debug("Resume attachment attributes", attrs=attrs[:20])

        # Try various attribute names for filename
        data["filename"] = (
            getattr(attachment, "Filename", None)
            or getattr(attachment, "File_Name", None)
            or getattr(attachment, "Resume_Filename", None)
            or getattr(attachment, "Document_Name", None)
        )

        # Try various attribute names for content type
        mime_ref = getattr(attachment, "Mime_Type_Reference", None)
        if mime_ref:
            data["content_type"] = getattr(mime_ref, "Descriptor", None)
        if not data.get("content_type"):
            data["content_type"] = (
                getattr(attachment, "Content_Type", None)
                or getattr(attachment, "Mime_Type", None)
                or "application/octet-stream"
            )

        # Try to get file content - could be in various places
        file_content = (
            getattr(attachment, "File_Content", None)
            or getattr(attachment, "File", None)
            or getattr(attachment, "Resume_Content", None)
            or getattr(attachment, "Content", None)
        )

        # Check nested Attachment_Data structure
        attachment_data = getattr(attachment, "Attachment_Data", None)
        if attachment_data and not file_content:
            if not data["filename"]:
                data["filename"] = getattr(attachment_data, "Filename", None)
            file_content = (
                getattr(attachment_data, "File_Content", None)
                or getattr(attachment_data, "File", None)
            )

        if file_content:
            try:
                data["content"] = base64.b64decode(file_content)
                logger.debug("Decoded resume content", size=len(data["content"]))
            except Exception as e:
                logger.error("Failed to decode resume attachment", error=str(e))

        # Mark as resume type
        data["category"] = "Resume"

        logger.info(
            "Parsed resume attachment",
            filename=data.get("filename"),
            content_type=data.get("content_type"),
            has_content=("content" in data),
            content_size=len(data["content"]) if "content" in data else 0,
        )

        return data if data.get("filename") or data.get("content") else None

    async def put_candidate_attachment(
        self,
        candidate_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/pdf",
        category: str = "OTHER_DOCUMENTS",
        comment: Optional[str] = None,
    ) -> str:
        """Upload an attachment to a candidate profile.

        Note: Uses raw httpx instead of zeep due to authentication issues
        with zeep's async transport for write operations.

        Args:
            candidate_id: The candidate external ID
            filename: Name for the file
            content: File content as bytes
            content_type: MIME type
            category: Document category - valid values:
                - OTHER_DOCUMENTS (default, for analysis reports)
                - CANDIDATE_RESUME_AND_COVER_LETTER
                - EDUCATION
            comment: Optional comment

        Returns:
            Document ID from Workday
        """
        logger.info(
            "Uploading candidate attachment",
            candidate_id=candidate_id,
            filename=filename,
            category=category,
            size=len(content),
        )

        # Base64 encode the content
        encoded_content = base64.b64encode(content).decode("utf-8")

        # Use zeep client directly with correct structure
        # Candidate_Reference is at request level, Add_Only=True for new attachments
        params = {
            "Add_Only": True,
            "Candidate_Reference": {
                "ID": [{"type": ID_TYPE_CANDIDATE, "_value_1": candidate_id}]
            },
            "Candidate_Attachment_Data": {
                "Attachment_Data": {
                    "Filename": filename,
                    "File_Content": encoded_content,
                    "Comment": comment,
                },
                "Document_Category_Reference": {
                    "ID": [{"type": "Document_Category__Workday_Owned__ID", "_value_1": category}]
                },
            },
        }

        # Get access token and set on auth plugin
        access_token = await self.auth.get_token()
        self._auth_plugin.set_token(access_token)

        try:
            response = await self._client.service.Put_Candidate_Attachment(**params)
        except Exception as e:
            logger.error(
                "Put_Candidate_Attachment failed",
                error=str(e),
                candidate_id=candidate_id,
            )
            raise WorkdaySOAPError(f"Put_Candidate_Attachment failed: {str(e)}") from e

        # Extract attachment ID from zeep response object
        doc_id = None
        if response:
            # Response should have Candidate_Attachment_Reference
            att_ref = getattr(response, "Candidate_Attachment_Reference", None)
            if att_ref:
                for id_item in getattr(att_ref, "ID", None) or []:
                    id_type = getattr(id_item, "type", "")
                    if id_type == "Candidate_Attachment_ID" or id_type == "File_ID":
                        doc_id = getattr(id_item, "_value_1", "")
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

    async def move_candidate(
        self,
        application_id: str,
        stage_id: Optional[str] = None,
        disposition_id: Optional[str] = None,
    ) -> bool:
        """Move a candidate to a new recruiting stage or disposition.

        Uses the Workday Move_Candidate SOAP operation to transition
        a job application to a new stage (for advancing) or disposition
        (for rejecting).

        Args:
            application_id: The Job_Application_ID (external application ID)
            stage_id: Target Recruiting_Stage_ID (e.g., "Screen", "Interview")
            disposition_id: Target Disposition_ID (e.g., "Experience/Skills")

        Returns:
            True if successful

        Raises:
            ValueError: If neither or both stage_id and disposition_id provided
            WorkdaySOAPError: If the API call fails
        """
        if (stage_id is None) == (disposition_id is None):
            raise ValueError("Exactly one of stage_id or disposition_id must be provided")

        # Get authentication token
        access_token = await self.auth.get_token()

        logger.info(
            "Moving candidate",
            application_id=application_id,
            stage_id=stage_id,
            disposition_id=disposition_id,
        )

        # Build the Move_Candidate SOAP request manually
        # The structure is based on Workday Recruiting v42+ API
        # Dispositions use Dynamic_Business_Process_Parameters, not direct Disposition_Reference
        wd = "wd"

        if stage_id:
            # Moving to a new stage (advancing)
            # Stage reference goes directly in Move_Candidate_Data
            xml = f'''<?xml version="1.0" encoding="utf-8"?>
<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">
  <soap-env:Body>
    <{wd}:Move_Candidate_Request xmlns:{wd}="urn:com.workday/bsvc" {wd}:version="{self.config.api_version}">
      <{wd}:Move_Candidate_Data>
        <{wd}:Job_Application_Reference>
          <{wd}:ID {wd}:type="Job_Application_ID">{application_id}</{wd}:ID>
        </{wd}:Job_Application_Reference>
        <{wd}:Recruiting_Stage_Reference>
          <{wd}:ID {wd}:type="Recruiting_Stage_ID">{stage_id}</{wd}:ID>
        </{wd}:Recruiting_Stage_Reference>
      </{wd}:Move_Candidate_Data>
    </{wd}:Move_Candidate_Request>
  </soap-env:Body>
</soap-env:Envelope>'''
        else:
            # Moving to disposition (rejecting)
            # Disposition uses Dynamic_Business_Process_Parameters with Disposition_Step_Reference
            xml = f'''<?xml version="1.0" encoding="utf-8"?>
<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">
  <soap-env:Body>
    <{wd}:Move_Candidate_Request xmlns:{wd}="urn:com.workday/bsvc" {wd}:version="{self.config.api_version}">
      <{wd}:Move_Candidate_Data>
        <{wd}:Job_Application_Reference>
          <{wd}:ID {wd}:type="Job_Application_ID">{application_id}</{wd}:ID>
        </{wd}:Job_Application_Reference>
        <{wd}:Dynamic_Business_Process_Parameters>
          <{wd}:Disposition_Step_Reference>
            <{wd}:ID {wd}:type="Disposition_ID">{disposition_id}</{wd}:ID>
          </{wd}:Disposition_Step_Reference>
        </{wd}:Dynamic_Business_Process_Parameters>
      </{wd}:Move_Candidate_Data>
    </{wd}:Move_Candidate_Request>
  </soap-env:Body>
</soap-env:Envelope>'''

        headers = {
            "SOAPAction": '""',
            "Content-Type": "text/xml; charset=utf-8",
            "Authorization": f"Bearer {access_token}",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.config.recruiting_service_url,
                    content=xml,
                    headers=headers,
                )

            if "authenticationError" in response.text:
                logger.error(
                    "Move_Candidate auth error",
                    application_id=application_id,
                    response_snippet=response.text[:500],
                )
                raise WorkdaySOAPError(f"Authentication error moving candidate {application_id}")

            if response.status_code != 200 or "Fault" in response.text:
                logger.error(
                    "Move_Candidate failed",
                    application_id=application_id,
                    status=response.status_code,
                    response_snippet=response.text[:500],
                )
                raise WorkdaySOAPError(f"Failed to move candidate {application_id}: {response.text[:200]}")

            logger.info(
                "Candidate moved successfully",
                application_id=application_id,
                stage_id=stage_id,
                disposition_id=disposition_id,
            )
            return True

        except httpx.HTTPError as e:
            logger.error(
                "Move_Candidate HTTP error",
                application_id=application_id,
                error=str(e),
            )
            raise WorkdaySOAPError(f"HTTP error moving candidate {application_id}: {e}") from e

    def _parse_attachment(self, attachment: Any) -> Dict[str, Any]:
        """Parse a SOAP attachment response into a dictionary.

        Workday returns attachments in this structure:
        attachment.Candidate_Attachment_Data.Attachment_Data = {
            'Filename': 'file.pdf',
            'File_Content': b'...',  # Already decoded bytes
            'Mime_Type_Reference': {'ID': [...], 'Descriptor': None}
        }
        attachment.Candidate_Attachment_Data.Document_Category_Reference = {
            'ID': [{'type': 'Document_Category__Workday_Owned__ID', '_value_1': 'RESUME'}]
        }
        """
        data = {}

        # Log available attributes for debugging
        attrs = [a for a in dir(attachment) if not a.startswith('_')]
        logger.debug("Attachment attributes", attrs=attrs[:20])

        # Check for Candidate_Attachment_Data wrapper (Workday's actual structure)
        cand_att_data = getattr(attachment, "Candidate_Attachment_Data", None)
        if cand_att_data:
            # Get Attachment_Data - it's a zeep object (Attachment_WWS_DataType)
            att_data = getattr(cand_att_data, "Attachment_Data", None)
            if att_data:
                # Access as object attributes (zeep objects look like dicts when printed but aren't)
                data["filename"] = getattr(att_data, "Filename", None)

                # File_Content is already bytes (not base64)
                file_content = getattr(att_data, "File_Content", None)
                if file_content:
                    if isinstance(file_content, bytes):
                        data["content"] = file_content
                    else:
                        # Try base64 decode if it's a string
                        try:
                            data["content"] = base64.b64decode(file_content)
                        except Exception:
                            data["content"] = file_content.encode() if isinstance(file_content, str) else None

                # Get content type from Mime_Type_Reference
                mime_ref = getattr(att_data, "Mime_Type_Reference", None)
                if mime_ref:
                    for id_item in getattr(mime_ref, "ID", None) or []:
                        id_type = getattr(id_item, "type", "") if hasattr(id_item, "type") else id_item.get("type", "")
                        if id_type == "Content_Type_ID":
                            data["content_type"] = getattr(id_item, "_value_1", "") if hasattr(id_item, "_value_1") else id_item.get("_value_1", "")
                            break

            # Get Document Category
            doc_cat_ref = getattr(cand_att_data, "Document_Category_Reference", None)
            if doc_cat_ref:
                # Get category from ID list
                for id_item in getattr(doc_cat_ref, "ID", None) or []:
                    id_type = getattr(id_item, "type", "") if hasattr(id_item, "type") else id_item.get("type", "")
                    if "Document_Category" in id_type:
                        cat_id = getattr(id_item, "_value_1", "") if hasattr(id_item, "_value_1") else id_item.get("_value_1", "")
                        data["category_id"] = cat_id
                        # Map common category IDs to readable names
                        if cat_id:
                            cat_lower = cat_id.lower()
                            if "resume" in cat_lower or "cv" in cat_lower:
                                data["category"] = "Candidate Resume and Cover Letter"
                            elif "education" in cat_lower:
                                data["category"] = "Education"
                            else:
                                data["category"] = cat_id
                        break

        # Fallback: Try to find filename directly on attachment
        if not data.get("filename"):
            data["filename"] = (
                getattr(attachment, "Filename", None)
                or getattr(attachment, "File_Name", None)
                or getattr(attachment, "Document_Name", None)
            )

        # Fallback: Try to find content type directly
        if not data.get("content_type"):
            data["content_type"] = (
                getattr(attachment, "Content_Type", None)
                or getattr(attachment, "Mime_Type", None)
                or "application/octet-stream"
            )

        # Fallback: Check for nested Attachment_Data as object (not dict)
        if "content" not in data:
            attachment_data = getattr(attachment, "Attachment_Data", None)
            if attachment_data and not isinstance(attachment_data, dict):
                logger.debug("Found Attachment_Data as object, checking for content")
                if not data.get("filename"):
                    data["filename"] = getattr(attachment_data, "Filename", None)
                file_content = getattr(attachment_data, "File_Content", None) or getattr(attachment_data, "File", None)
                if file_content:
                    if isinstance(file_content, bytes):
                        data["content"] = file_content
                    else:
                        try:
                            data["content"] = base64.b64decode(file_content)
                        except Exception as e:
                            logger.error("Failed to decode attachment from Attachment_Data", error=str(e))

        # Fallback: Direct File_Content on attachment
        if "content" not in data:
            file_content = (
                getattr(attachment, "File_Content", None)
                or getattr(attachment, "File", None)
                or getattr(attachment, "Content", None)
            )
            if file_content:
                if isinstance(file_content, bytes):
                    data["content"] = file_content
                else:
                    try:
                        data["content"] = base64.b64decode(file_content)
                    except Exception as e:
                        logger.error("Failed to decode attachment", error=str(e), filename=data.get("filename"))

        # Log what we found
        logger.info(
            "Parsed attachment",
            filename=data.get("filename"),
            content_type=data.get("content_type"),
            category=data.get("category"),
            has_content=("content" in data),
            content_size=len(data["content"]) if "content" in data else 0,
        )

        return data


class WorkdaySOAPError(Exception):
    """Raised when a Workday SOAP call fails."""

    pass