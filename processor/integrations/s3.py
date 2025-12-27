"""S3 integration for artifact storage."""

import io
from typing import Optional

import boto3
import structlog
from botocore.exceptions import ClientError

from processor.config import settings

logger = structlog.get_logger()


class S3Service:
    """Service for S3 file operations."""

    def __init__(self):
        """Initialize S3 client with S3-specific credentials."""
        client_kwargs = {"region_name": settings.S3_REGION}
        if settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = settings.S3_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = settings.S3_SECRET_ACCESS_KEY
        self.client = boto3.client("s3", **client_kwargs)
        self.bucket = settings.S3_BUCKET
        self.prefix = settings.S3_PREFIX

    def _get_key(self, path: str) -> str:
        """Get full S3 key with prefix."""
        return f"{self.prefix.rstrip('/')}/{path.lstrip('/')}"

    async def upload(
        self,
        content: bytes,
        path: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None,
    ) -> str:
        """Upload content to S3.

        Args:
            content: File content as bytes
            path: Path within the bucket (without prefix)
            content_type: MIME type
            metadata: Optional metadata

        Returns:
            Full S3 key
        """
        key = self._get_key(path)

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                Metadata=metadata or {},
            )

            logger.info(
                "File uploaded to S3",
                bucket=self.bucket,
                key=key,
                size=len(content),
            )

            return key

        except ClientError as e:
            logger.error("S3 upload failed", error=str(e))
            raise S3Error(f"Upload failed: {str(e)}") from e

    async def download(self, key: str) -> bytes:
        """Download content from S3.

        Args:
            key: Full S3 key

        Returns:
            File content as bytes
        """
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read()

            logger.info(
                "File downloaded from S3",
                bucket=self.bucket,
                key=key,
                size=len(content),
            )

            return content

        except ClientError as e:
            logger.error("S3 download failed", error=str(e))
            raise S3Error(f"Download failed: {str(e)}") from e

    async def exists(self, key: str) -> bool:
        """Check if an object exists in S3.

        Args:
            key: Full S3 key

        Returns:
            True if exists
        """
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise S3Error(f"Existence check failed: {str(e)}") from e

    async def delete(self, key: str) -> None:
        """Delete an object from S3.

        Args:
            key: Full S3 key
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            logger.info("File deleted from S3", bucket=self.bucket, key=key)
        except ClientError as e:
            logger.error("S3 delete failed", error=str(e))
            raise S3Error(f"Delete failed: {str(e)}") from e

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned URL for download.

        Args:
            key: Full S3 key
            expires_in: URL validity in seconds

        Returns:
            Presigned URL
        """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error("Presigned URL generation failed", error=str(e))
            raise S3Error(f"Presigned URL failed: {str(e)}") from e

    # Convenience methods for specific artifact types

    async def upload_resume(
        self,
        application_id: int,
        content: bytes,
        filename: str,
    ) -> str:
        """Upload a resume file.

        Args:
            application_id: Application ID
            content: Resume content
            filename: Original filename

        Returns:
            S3 key
        """
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "pdf"
        path = f"resumes/{application_id}/resume.{ext}"

        content_type = self._get_content_type(filename)

        return await self.upload(
            content=content,
            path=path,
            content_type=content_type,
            metadata={"original_filename": filename},
        )

    async def upload_report(
        self,
        application_id: int,
        content: bytes,
    ) -> str:
        """Upload a generated report.

        Args:
            application_id: Application ID
            content: PDF content

        Returns:
            S3 key
        """
        path = f"reports/{application_id}/candidate_report.pdf"

        return await self.upload(
            content=content,
            path=path,
            content_type="application/pdf",
        )

    def _get_content_type(self, filename: str) -> str:
        """Get content type from filename."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        content_types = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
        }

        return content_types.get(ext, "application/octet-stream")


class S3Error(Exception):
    """Raised when S3 operations fail."""

    pass
