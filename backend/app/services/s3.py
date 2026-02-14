"""
SIMS Plus - S3 File Storage Service

Handles file uploads to AWS S3 with automatic bucket creation.
"""

import json
import uuid
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.config import settings


class S3Service:
    """Service for managing file uploads to AWS S3."""

    def __init__(self):
        """Initialize S3 client with credentials from settings."""
        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            raise ValueError("AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")

        self.client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.bucket = settings.AWS_S3_BUCKET
        self.region = settings.AWS_REGION
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

            # Disable block public access for the logos folder
            self.client.put_public_access_block(
                Bucket=self.bucket,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": False,
                    "IgnorePublicAcls": False,
                    "BlockPublicPolicy": False,
                    "RestrictPublicBuckets": False,
                },
            )

            # Set bucket policy to allow public read for logos and avatars
            self._set_public_read_policy()

            # Enable CORS for browser uploads
            cors_configuration = {
                "CORSRules": [
                    {
                        "AllowedHeaders": ["*"],
                        "AllowedMethods": ["GET", "PUT", "POST"],
                        "AllowedOrigins": ["*"],
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
        """Set bucket policy to allow public read for logos, avatars, student photos, and staff photos."""
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
                {
                    "Sid": "PublicReadStudents",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{self.bucket}/students/*",
                },
                {
                    "Sid": "PublicReadStaff",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{self.bucket}/staff/*",
                },
            ],
        }
        self.client.put_bucket_policy(
            Bucket=self.bucket,
            Policy=json.dumps(policy),
        )

    def _ensure_bucket_policy(self) -> None:
        """Ensure the bucket policy includes all required public read permissions."""
        try:
            response = self.client.get_bucket_policy(Bucket=self.bucket)
            current_policy = json.loads(response["Policy"])
            statements = current_policy.get("Statement", [])

            # Check if all required policies exist
            has_logos = any(stmt.get("Sid") == "PublicReadLogos" for stmt in statements)
            has_avatars = any(stmt.get("Sid") == "PublicReadAvatars" for stmt in statements)
            has_students = any(stmt.get("Sid") == "PublicReadStudents" for stmt in statements)
            has_staff = any(stmt.get("Sid") == "PublicReadStaff" for stmt in statements)

            # Update policy if any statement is missing
            if not has_logos or not has_avatars or not has_students or not has_staff:
                print(f"S3: Updating bucket policy - logos={has_logos}, avatars={has_avatars}, students={has_students}, staff={has_staff}")
                self._set_public_read_policy()
                print("S3: Bucket policy updated successfully")
            else:
                print("S3: Bucket policy already has all required permissions")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchBucketPolicy":
                print("S3: No bucket policy exists, creating one...")
                self._set_public_read_policy()
                print("S3: Bucket policy created successfully")
            else:
                print(f"S3: Error checking bucket policy: {error_code} - {e}")
                # Try to set policy anyway
                try:
                    self._set_public_read_policy()
                    print("S3: Bucket policy set after error")
                except Exception as e2:
                    print(f"S3: Failed to set bucket policy: {e2}")

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
        """Get the public URL for an S3 object."""
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

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
