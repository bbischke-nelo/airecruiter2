"""Base interface for TMS providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class TMSRequisition:
    """Standardized requisition data from TMS."""

    external_id: str
    name: str
    description: Optional[str] = None
    detailed_description: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    hiring_manager: Optional[str] = None
    is_active: bool = True
    external_data: Optional[dict] = None  # Raw data from TMS for reference


@dataclass
class TMSApplication:
    """Standardized application data from TMS."""

    external_application_id: str
    external_candidate_id: str
    external_requisition_id: str
    candidate_name: str
    candidate_email: str
    workday_status: str
    applied_at: Optional[datetime] = None
    resume_content: Optional[bytes] = None  # Resume file content if available
    resume_filename: Optional[str] = None
    resume_content_type: Optional[str] = None
    external_data: Optional[dict] = None  # Raw data from TMS for reference


@dataclass
class TMSHealthStatus:
    """Health status from TMS."""

    healthy: bool
    message: str
    details: dict = field(default_factory=dict)


class TMSProvider(ABC):
    """Abstract base class for TMS providers."""

    provider_name: str = "base"

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider (authenticate, load WSDL, etc.)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connections and clean up resources."""
        pass

    @abstractmethod
    async def health_check(self) -> TMSHealthStatus:
        """Check if the TMS connection is healthy."""
        pass

    @abstractmethod
    async def get_requisitions(
        self,
        active_only: bool = True,
        limit: Optional[int] = None,
    ) -> List[TMSRequisition]:
        """Fetch requisitions from TMS.

        Args:
            active_only: Only return active/open requisitions
            limit: Maximum number to return

        Returns:
            List of TMSRequisition objects
        """
        pass

    @abstractmethod
    async def get_requisition(self, external_id: str) -> Optional[TMSRequisition]:
        """Fetch a single requisition by external ID.

        Args:
            external_id: The TMS requisition ID

        Returns:
            TMSRequisition or None if not found
        """
        pass

    @abstractmethod
    async def get_applications(
        self,
        requisition_external_id: str,
        since: Optional[datetime] = None,
    ) -> List[TMSApplication]:
        """Fetch applications for a requisition.

        Args:
            requisition_external_id: The TMS requisition ID
            since: Only return applications modified since this time

        Returns:
            List of TMSApplication objects
        """
        pass

    @abstractmethod
    async def get_resume(
        self,
        candidate_external_id: str,
    ) -> Optional[tuple[bytes, str, str]]:
        """Fetch resume for a candidate.

        Args:
            candidate_external_id: The TMS candidate ID

        Returns:
            Tuple of (content, filename, content_type) or None if not found
        """
        pass

    @abstractmethod
    async def upload_attachment(
        self,
        candidate_external_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/pdf",
        category: str = "Other",
        comment: Optional[str] = None,
    ) -> str:
        """Upload an attachment to a candidate profile.

        Args:
            candidate_external_id: The TMS candidate ID
            filename: Name for the file
            content: File content as bytes
            content_type: MIME type
            category: Attachment category
            comment: Optional comment

        Returns:
            Document ID from TMS
        """
        pass
