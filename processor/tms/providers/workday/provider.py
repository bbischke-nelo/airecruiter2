"""Workday TMS provider implementation."""

from datetime import datetime
from typing import List, Optional

import structlog

from processor.tms.base import (
    TMSProvider,
    TMSRequisition,
    TMSApplication,
    TMSHealthStatus,
)
from .config import WorkdayConfig
from .soap_client import WorkdaySOAPClient, WorkdaySOAPError

logger = structlog.get_logger()


class WorkdayProvider(TMSProvider):
    """Workday TMS provider using SOAP API."""

    provider_name = "workday"

    def __init__(self, config: WorkdayConfig):
        """Initialize Workday provider.

        Args:
            config: Workday configuration
        """
        self.config = config
        self._client = WorkdaySOAPClient(config)

    async def initialize(self) -> None:
        """Initialize the SOAP client."""
        await self._client.initialize()
        logger.info("Workday provider initialized")

    async def close(self) -> None:
        """Close the SOAP client."""
        await self._client.close()
        logger.info("Workday provider closed")

    async def health_check(self) -> TMSHealthStatus:
        """Check if Workday connection is healthy."""
        try:
            # Try to fetch one requisition as a health check
            await self._client.get_job_requisitions(status="Open", page=1, count=1)
            return TMSHealthStatus(
                healthy=True,
                message="Workday connection is healthy",
                details={
                    "tenant_url": self.config.tenant_url,
                    "tenant_id": self.config.tenant_id,
                    "api_version": self.config.api_version,
                },
            )
        except Exception as e:
            logger.error("Workday health check failed", error=str(e))
            return TMSHealthStatus(
                healthy=False,
                message=f"Workday connection failed: {str(e)}",
                details={"error": str(e)},
            )

    async def get_requisitions(
        self,
        active_only: bool = True,
        limit: Optional[int] = None,
    ) -> List[TMSRequisition]:
        """Fetch requisitions from Workday."""
        status = "Open" if active_only else None
        page = 1
        count = min(limit or 100, 100)  # Max 100 per page
        all_requisitions = []

        while True:
            raw_reqs = await self._client.get_job_requisitions(
                status=status or "Open",
                page=page,
                count=count,
            )

            if not raw_reqs:
                break

            for raw in raw_reqs:
                req = TMSRequisition(
                    external_id=raw.get("external_id", ""),
                    name=raw.get("name", ""),
                    description=raw.get("description"),
                    detailed_description=raw.get("detailed_description"),
                    location=raw.get("location"),
                    recruiter_name=raw.get("recruiter_name"),
                    is_active=raw.get("is_active", True),
                    workday_data=raw,
                )
                all_requisitions.append(req)

            # Check if we've hit the limit
            if limit and len(all_requisitions) >= limit:
                all_requisitions = all_requisitions[:limit]
                break

            # Check if we got a full page (more might exist)
            if len(raw_reqs) < count:
                break

            page += 1

        logger.info("Fetched requisitions from Workday", count=len(all_requisitions))
        return all_requisitions

    async def get_requisition(self, external_id: str) -> Optional[TMSRequisition]:
        """Fetch a single requisition by external ID."""
        # Workday doesn't have a direct get-by-ID, so we fetch all and filter
        # In a real implementation, you'd want to use a more efficient query
        requisitions = await self.get_requisitions(active_only=False, limit=500)

        for req in requisitions:
            if req.external_id == external_id:
                return req

        return None

    async def get_applications(
        self,
        requisition_external_id: str,
        since: Optional[datetime] = None,
        wid: Optional[str] = None,
    ) -> List[TMSApplication]:
        """Fetch applications for a requisition.

        Args:
            requisition_external_id: The Job_Requisition_ID
            since: Only return applications after this date
            wid: Optional Workday ID (WID) - preferred for Get_Candidates query
        """
        page = 1
        count = 100
        all_applications = []

        while True:
            raw_apps = await self._client.get_job_applications(
                requisition_id=requisition_external_id,
                wid=wid,
                page=page,
                count=count,
            )

            if not raw_apps:
                break

            for raw in raw_apps:
                # Parse applied_at for filtering
                applied_at = raw.get("applied_at")
                if isinstance(applied_at, str):
                    try:
                        applied_at = datetime.fromisoformat(applied_at.replace("Z", "+00:00"))
                    except ValueError:
                        applied_at = None

                # Filter by since date if provided
                if since and applied_at and applied_at < since:
                    continue

                app = TMSApplication(
                    external_application_id=raw.get("external_application_id", ""),
                    external_candidate_id=raw.get("external_candidate_id", ""),
                    external_requisition_id=raw.get("external_requisition_id", requisition_external_id),
                    candidate_name=raw.get("candidate_name", ""),
                    candidate_email=raw.get("candidate_email", ""),
                    workday_status=raw.get("workday_status", "Unknown"),
                    applied_at=applied_at,
                    workday_data=raw,
                )
                all_applications.append(app)

            # Check if we got a full page
            if len(raw_apps) < count:
                break

            page += 1

        logger.info(
            "Fetched applications from Workday",
            requisition_id=requisition_external_id,
            count=len(all_applications),
        )
        return all_applications

    async def get_resume(
        self,
        candidate_external_id: str,
    ) -> Optional[tuple[bytes, str, str]]:
        """Fetch resume for a candidate."""
        attachments = await self._client.get_candidate_attachments(candidate_external_id)

        for attachment in attachments:
            content = attachment.get("content")
            filename = attachment.get("filename", "resume.pdf")
            content_type = attachment.get("content_type", "application/pdf")

            # Filter for resume-like files
            if content and self._is_resume(filename, content_type):
                logger.info(
                    "Found resume",
                    candidate_id=candidate_external_id,
                    filename=filename,
                )
                return content, filename, content_type

        logger.warning("No resume found", candidate_id=candidate_external_id)
        return None

    async def upload_attachment(
        self,
        candidate_external_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/pdf",
        category: str = "Other",
        comment: Optional[str] = None,
    ) -> str:
        """Upload an attachment to a candidate profile."""
        doc_id = await self._client.put_candidate_attachment(
            candidate_id=candidate_external_id,
            filename=filename,
            content=content,
            content_type=content_type,
            category=category,
            comment=comment,
        )

        logger.info(
            "Attachment uploaded to Workday",
            candidate_id=candidate_external_id,
            filename=filename,
            document_id=doc_id,
        )
        return doc_id

    def _is_resume(self, filename: str, content_type: str) -> bool:
        """Check if a file is likely a resume."""
        filename_lower = filename.lower()
        resume_keywords = ["resume", "cv", "curriculum"]

        # Check by filename
        if any(kw in filename_lower for kw in resume_keywords):
            return True

        # Check by extension/content type
        resume_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]
        resume_extensions = [".pdf", ".doc", ".docx"]

        if content_type in resume_types:
            return True

        if any(filename_lower.endswith(ext) for ext in resume_extensions):
            return True

        return False
