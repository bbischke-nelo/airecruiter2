"""S3 service for presigned URL generation."""

import boto3
import structlog
from botocore.exceptions import ClientError

from api.config.settings import settings

logger = structlog.get_logger()


class S3Service:
    """Service for S3 presigned URL operations."""

    def __init__(self):
        """Initialize S3 client with S3-specific credentials."""
        client_kwargs = {"region_name": settings.S3_REGION}
        if settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = settings.S3_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = settings.S3_SECRET_ACCESS_KEY
        self.client = boto3.client("s3", **client_kwargs)
        self.bucket = settings.S3_BUCKET

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: str | None = None,
    ) -> str:
        """Generate a presigned URL for download.

        Args:
            key: Full S3 key
            expires_in: URL validity in seconds
            filename: Optional filename for Content-Disposition header

        Returns:
            Presigned URL
        """
        try:
            params = {"Bucket": self.bucket, "Key": key}

            # Add Content-Disposition to suggest filename on download
            if filename:
                params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

            url = self.client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error("Presigned URL generation failed", error=str(e), key=key)
            raise S3Error(f"Presigned URL failed: {str(e)}") from e

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


class S3Error(Exception):
    """Raised when S3 operations fail."""

    pass
