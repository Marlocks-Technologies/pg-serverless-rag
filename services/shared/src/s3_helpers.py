"""S3 helper functions for the RAG Platform.

All functions accept an optional boto3 S3 client for testability (dependency injection).
If no client is provided, one is created using the default session.
"""

import hashlib
from typing import Optional

import boto3
from botocore.exceptions import ClientError


def _get_client(client: Optional[object] = None) -> object:
    """Return provided client or create a new S3 client."""
    if client is not None:
        return client
    return boto3.client("s3")


def download_object(bucket: str, key: str, client=None) -> bytes:
    """Download an object from S3 and return its content as bytes.

    Args:
        bucket: S3 bucket name.
        key: S3 object key.
        client: Optional boto3 S3 client.

    Returns:
        Raw bytes content of the object.

    Raises:
        ClientError: If the object cannot be retrieved.
    """
    s3 = _get_client(client)
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def upload_object(
    bucket: str,
    key: str,
    body: bytes,
    content_type: str,
    metadata: Optional[dict] = None,
    client=None,
) -> None:
    """Upload bytes to an S3 object.

    Args:
        bucket: S3 bucket name.
        key: S3 object key.
        body: Raw bytes to upload.
        content_type: MIME type of the object (e.g. "application/pdf").
        metadata: Optional dict of user-defined S3 metadata (string values only).
        client: Optional boto3 S3 client.
    """
    s3 = _get_client(client)
    put_kwargs: dict = {
        "Bucket": bucket,
        "Key": key,
        "Body": body,
        "ContentType": content_type,
    }
    if metadata:
        # S3 metadata values must be strings
        put_kwargs["Metadata"] = {k: str(v) for k, v in metadata.items()}

    s3.put_object(**put_kwargs)


def object_exists(bucket: str, key: str, client=None) -> bool:
    """Check whether an S3 object exists without downloading it.

    Args:
        bucket: S3 bucket name.
        key: S3 object key.
        client: Optional boto3 S3 client.

    Returns:
        True if the object exists, False otherwise.
    """
    s3 = _get_client(client)
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("404", "NoSuchKey"):
            return False
        raise


def get_object_metadata(bucket: str, key: str, client=None) -> dict:
    """Retrieve S3 object metadata (user-defined and system metadata).

    Args:
        bucket: S3 bucket name.
        key: S3 object key.
        client: Optional boto3 S3 client.

    Returns:
        Dict containing:
          - "user_metadata": dict of user-defined metadata tags
          - "content_type": MIME type string
          - "content_length": size in bytes
          - "last_modified": datetime object
          - "etag": ETag string

    Raises:
        ClientError: If the object does not exist or cannot be accessed.
    """
    s3 = _get_client(client)
    response = s3.head_object(Bucket=bucket, Key=key)
    return {
        "user_metadata": response.get("Metadata", {}),
        "content_type": response.get("ContentType", ""),
        "content_length": response.get("ContentLength", 0),
        "last_modified": response.get("LastModified"),
        "etag": response.get("ETag", "").strip('"'),
    }


def compute_checksum(data: bytes) -> str:
    """Compute a SHA-256 hex digest of the provided bytes.

    Args:
        data: Raw bytes to hash.

    Returns:
        Lowercase hex-encoded SHA-256 digest string.
    """
    return hashlib.sha256(data).hexdigest()
