"""
SIMS Plus - S3 File Storage Service

Handles file uploads to AWS S3 with automatic bucket creation.

SECURITY:
- Student and staff photos are NOT publicly accessible (PII of minors).
  Use generate_presigned_url() to serve them via authenticated API calls.
- Only school logos and user avatars have public read access.
- CORS is restricted to known application origins.
"""

import json
import uuid
from typing import Optional

import boto3
import structlog
from botocore.exceptions import ClientError

from app.config import settings

logger = structlog.get_logger()

# Allowed CORS origins for browser-based S3 requests
_CORS_ALLOWED_ORIGINS = [
    "https://*.simsplus.io",
    "http://localhost:3000",
    "http://localhost:3001",
]


class S3Service:
    """Service for managing file uploads to AWS S3."""

    def __init__(self):
        """Initialize S3 client with credentials from settings."""
        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            raise ValueError("AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")

        # endpoint_url allows connecting to MinIO or other S3-compatible stores in local dev
        client_kwargs = {
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "region_name": settings.AWS_REGION,
        }
        if settings.S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

        self.client = boto3.client("s3", **client_kwargs)
        self.bucket = settings.AWS_S3_BUCKET
        self.region = settings.AWS_REGION
        self._endpoint_url = settings.S3_ENDPOINT_URL
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Create the S3 bucket if it doesn't exist, and ensure policy is correct."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
            # Bucket exists, ensure policy is up to date
            self._ensure_bucket_policy()
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchBucket"):
                self._create_bucket()
            else:
                raise

    def _create_bucket(self) -> None:
        """Create the S3 bucket with appropriate configuration."""
        try:
            # us-east-1 doesn't require LocationConstraint
            if self.region == "us-east-1":
                self.client.create_bucket(Bucket=self.bucket)
            else:
                self.client.create_bucket(
                    Bucket=self.bucket,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )

            # Disable block public access for the logos and avatars folders only
            self.client.put_public_access_block(
                Bucket=self.bucket,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": False,
                    "IgnorePublicAcls": False,
                    "BlockPublicPolicy": False,
                    "RestrictPublicBuckets": False,
                },
            )

            # Only logos and avatars get public read access
            self._set_public_read_policy()

            # Restrict CORS to known application origins (not wildcard)
            cors_configuration = {
                "CORSRules": [
                    {
                        "AllowedHeaders": ["*"],
                        "AllowedMethods": ["GET", "PUT", "POST"],
                        "AllowedOrigins": _CORS_ALLOWED_ORIGINS,
                        "ExposeHeaders": ["ETag"],
                        "MaxAgeSeconds": 3600,
                    }
                ]
            }
            self.client.put_bucket_cors(
                Bucket=self.bucket,
                CORSConfiguration=cors_configuration,
            )

        except ClientError as e:
            raise RuntimeError(f"Failed to create S3 bucket: {e}")

    def _set_public_read_policy(self) -> None:
        """Set bucket policy to allow public read for logos and avatars only.

        SECURITY: Student and staff photos are excluded because they contain
        PII (photos of minors). Those are served via presigned URLs instead.
        """
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadLogos",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{self.bucket}/logos/*",
                },
                {
                    "Sid": "PublicReadAvatars",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{self.bucket}/avatars/*",
                },
            ],
        }
        self.client.put_bucket_policy(
            Bucket=self.bucket,
            Policy=json.dumps(policy),
        )

    def _ensure_bucket_policy(self) -> None:
        """Ensure the bucket policy includes required public read permissions.

        Only logos and avatars need public access. If stale PublicReadStudents
        or PublicReadStaff statements exist, the policy is overwritten to
        remove them.
        """
        try:
            response = self.client.get_bucket_policy(Bucket=self.bucket)
            current_policy = json.loads(response["Policy"])
            statements = current_policy.get("Statement", [])

            has_logos = any(stmt.get("Sid") == "PublicReadLogos" for stmt in statements)
            has_avatars = any(stmt.get("Sid") == "PublicReadAvatars" for stmt in statements)

            # Check for stale public read policies on sensitive paths
            has_students = any(stmt.get("Sid") == "PublicReadStudents" for stmt in statements)
            has_staff = any(stmt.get("Sid") == "PublicReadStaff" for stmt in statements)

            # Rewrite policy if any required statement is missing OR if stale
            # student/staff public read policies exist (security remediation)
            if not has_logos or not has_avatars or has_students or has_staff:
                logger.info(
                    "s3.bucket_policy.updating",
                    logos=has_logos,
                    avatars=has_avatars,
                    removing_students=has_students,
                    removing_staff=has_staff,
                )
                self._set_public_read_policy()
                logger.info("s3.bucket_policy.updated")
            else:
                logger.debug("s3.bucket_policy.up_to_date")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchBucketPolicy":
                logger.info("s3.bucket_policy.creating")
                self._set_public_read_policy()
                logger.info("s3.bucket_policy.created")
            else:
                logger.error("s3.bucket_policy.check_failed", error_code=error_code)
                # Try to set policy anyway
                try:
                    self._set_public_read_policy()
                    logger.info("s3.bucket_policy.set_after_error")
                except Exception:
                    logger.exception("s3.bucket_policy.set_failed")

    def upload_file(
        self,
        file_content: bytes,
        key: str,
        content_type: str,
    ) -> str:
        """
        Upload a file to S3.

        Args:
            file_content: The file content as bytes
            key: The S3 object key (path)
            content_type: MIME type of the file

        Returns:
            The public URL of the uploaded file
        """
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_content,
            ContentType=content_type,
        )
        return self.get_public_url(key)

    def get_public_url(self, key: str) -> str:
        """Get the public URL for an S3 object.

        Only valid for objects with public read access (logos, avatars).
        For student/staff photos, use generate_presigned_url() instead.

        Returns MinIO-style URL when S3_ENDPOINT_URL is configured,
        otherwise returns standard AWS S3 URL.
        """
        if self._endpoint_url:
            return f"{self._endpoint_url}/{self.bucket}/{key}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a time-limited presigned URL for private S3 objects.

        Used for student and staff photos which must not be publicly
        accessible. The URL expires after the specified duration, ensuring
        photos can only be accessed via authenticated API calls.

        Args:
            key: The S3 object key (e.g., "students/{tenant_id}/{uuid}.jpg")
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            A presigned URL that grants temporary read access
        """
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_file(self, key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            key: The S3 object key to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def generate_unique_key(
        self,
        folder: str,
        tenant_id: str,
        original_filename: str,
    ) -> str:
        """
        Generate a unique S3 key for a file.

        Args:
            folder: The folder prefix (e.g., 'logos')
            tenant_id: The tenant UUID
            original_filename: Original filename to extract extension

        Returns:
            A unique S3 key like 'logos/{tenant_id}/{uuid}.{ext}'
        """
        ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "png"
        unique_id = uuid.uuid4().hex
        return f"{folder}/{tenant_id}/{unique_id}.{ext}"


# Singleton instance
_s3_service: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    """Get or create the S3 service singleton."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service
