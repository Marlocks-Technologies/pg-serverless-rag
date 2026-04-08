"""
Document Manager Lambda - Document upload, listing, and management.

Handles:
- Document upload with multipart/form-data
- List documents with filtering and pagination
- Get document details and status
- Update document metadata
- Delete documents
"""

import json
import os
import sys
import uuid
import base64
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import unquote

# Add Lambda layer path
sys.path.insert(0, '/opt/python')

import boto3
from shared.logger import get_logger
from shared.validation import sanitize_filename
from shared.s3_helpers import upload_object

logger = get_logger(__name__)


def _decode_base64_file_content(content_base64) -> bytes:
    """Decode upload payload; base64 strings must be ASCII-only (Python base64 requirement)."""
    if content_base64 is None:
        raise ValueError("Missing required field: content")
    if not isinstance(content_base64, str):
        raise ValueError("content must be a string (base64-encoded file bytes)")
    # Ignore whitespace often added by clients (line wrapping)
    cleaned = "".join(content_base64.split())
    if not cleaned:
        raise ValueError("content is empty")
    try:
        cleaned.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "content must be standard base64 using only ASCII characters; "
            "re-encode the file as base64 or remove non-ASCII characters from the payload"
        ) from exc
    try:
        return base64.b64decode(cleaned, validate=False)
    except Exception as exc:
        raise ValueError(f"Invalid base64 content: {exc}") from exc


class DocumentManager:
    """Manages document uploads and metadata."""

    def __init__(self):
        """Initialize with AWS clients and configuration."""
        self.s3 = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')

        # Configuration from environment
        self.ingestion_bucket = os.environ['INGESTION_BUCKET']
        self.staging_bucket = os.environ['STAGING_BUCKET']
        self.vectors_bucket = os.environ['VECTORS_BUCKET']
        self.documents_table_name = os.environ.get('DOCUMENTS_TABLE', 'rag-dev-documents')

        # DynamoDB table for document metadata
        try:
            self.documents_table = self.dynamodb.Table(self.documents_table_name)
        except Exception as e:
            logger.warning("documents_table_not_found", error=str(e))
            self.documents_table = None

    def upload_document(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Upload a document to S3 ingestion bucket.

        Args:
            filename: Original filename
            content: File content bytes
            content_type: MIME type
            metadata: Additional metadata

        Returns:
            Upload result with document ID
        """
        log = logger.bind(
            filename=filename,
            content_type=content_type,
            size_bytes=len(content)
        )

        log.info("uploading_document")

        # Sanitize filename
        safe_filename = sanitize_filename(filename)

        # Generate document ID
        document_id = str(uuid.uuid4())

        # S3 key
        s3_key = f"uploads/{safe_filename}"

        # Upload to S3 ingestion bucket (triggers Lambda processing)
        try:
            upload_object(
                bucket=self.ingestion_bucket,
                key=s3_key,
                body=content,
                content_type=content_type,
                metadata={
                    'document-id': document_id,
                    'original-filename': filename,
                    'upload-timestamp': datetime.utcnow().isoformat() + 'Z',
                    **metadata
                },
                client=self.s3
            )

            log.info("document_uploaded", document_id=document_id, s3_key=s3_key)

            # Store metadata in DynamoDB
            if self.documents_table:
                self._save_document_metadata(
                    document_id=document_id,
                    filename=filename,
                    s3_key=s3_key,
                    content_type=content_type,
                    size_bytes=len(content),
                    status='processing',
                    metadata=metadata
                )

            return {
                'success': True,
                'documentId': document_id,
                'filename': filename,
                's3Key': s3_key,
                'status': 'processing',
                'message': 'Document uploaded successfully and is being processed'
            }

        except Exception as e:
            log.error("upload_failed", error=str(e), error_type=type(e).__name__)
            raise

    def list_documents(
        self,
        limit: int = 50,
        status: Optional[str] = None,
        category: Optional[str] = None,
        next_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List documents with optional filtering.

        Args:
            limit: Maximum number of documents to return
            status: Filter by status (processing, completed, failed)
            category: Filter by category
            next_token: Pagination token

        Returns:
            List of documents with metadata
        """
        log = logger.bind(limit=limit, status=status, category=category)
        log.info("listing_documents")

        try:
            # List from staging bucket (processed documents)
            paginator = self.s3.get_paginator('list_objects_v2')

            # Build prefix based on category filter
            prefix = f"grouped/{category}/" if category else "grouped/"

            pages = paginator.paginate(
                Bucket=self.staging_bucket,
                Prefix=prefix,
                MaxKeys=limit
            )

            documents = []

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    # Only process PDF files (not metadata files)
                    if not obj['Key'].endswith('.pdf'):
                        continue

                    # Get metadata
                    try:
                        metadata_key = obj['Key'].replace('.pdf', '.metadata.json')
                        metadata_obj = self.s3.get_object(
                            Bucket=self.staging_bucket,
                            Key=metadata_key
                        )
                        metadata = json.loads(metadata_obj['Body'].read())

                        # Apply status filter if specified
                        if status:
                            # Status is inferred from presence in staging bucket
                            doc_status = 'completed'  # If in staging, it's completed
                            if status != doc_status:
                                continue

                        documents.append({
                            'documentId': metadata['documentId'],
                            'filename': metadata['source']['filename'],
                            'category': metadata['classification']['primaryTag'],
                            'status': 'completed',
                            'uploadedAt': metadata['source']['uploadTimestamp'],
                            'processedAt': metadata['processing']['timestamp'],
                            'sizeBytes': metadata['source']['sizeBytes'],
                            's3Uri': f"s3://{self.staging_bucket}/{obj['Key']}"
                        })

                    except Exception as e:
                        log.warning("failed_to_load_metadata", key=obj['Key'], error=str(e))
                        continue

                # Respect limit
                if len(documents) >= limit:
                    break

            log.info("documents_listed", count=len(documents))

            return {
                'success': True,
                'documents': documents[:limit],
                'count': len(documents[:limit]),
                'nextToken': None  # Implement pagination if needed
            }

        except Exception as e:
            log.error("list_failed", error=str(e))
            raise

    def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific document.

        Args:
            document_id: Document identifier

        Returns:
            Document details with metadata
        """
        log = logger.bind(document_id=document_id)
        log.info("getting_document")

        try:
            # Search for document in staging bucket
            # Try all category prefixes
            categories = ['unknown', 'contracts', 'financial', 'technical', 'general']

            metadata = None
            for category in categories:
                metadata_key = f"grouped/{category}/{document_id}.metadata.json"
                try:
                    metadata_obj = self.s3.get_object(
                        Bucket=self.staging_bucket,
                        Key=metadata_key
                    )
                    metadata = json.loads(metadata_obj['Body'].read())
                    break
                except self.s3.exceptions.NoSuchKey:
                    continue

            if not metadata:
                log.warning("document_not_found")
                return {
                    'success': False,
                    'error': 'Document not found'
                }

            # Get vector count
            vector_count = self._count_vectors(document_id)

            # Build response
            result = {
                'success': True,
                'document': {
                    'documentId': metadata['documentId'],
                    'filename': metadata['source']['filename'],
                    'category': metadata['classification']['primaryTag'],
                    'secondaryTags': metadata['classification'].get('secondaryTags', []),
                    'confidence': metadata['classification']['confidence'],
                    'status': 'completed',
                    'uploadedAt': metadata['source']['uploadTimestamp'],
                    'processedAt': metadata['processing']['timestamp'],
                    'sizeBytes': metadata['source']['sizeBytes'],
                    'contentType': metadata['source']['contentType'],
                    'checksum': metadata['source']['checksum'],
                    'processing': {
                        'parser': metadata['processing']['parser'],
                        'ocrUsed': metadata['processing']['ocrUsed'],
                        'textLengthChars': metadata['processing']['textLengthChars'],
                        'pageCount': metadata['processing'].get('pageCount', 1)
                    },
                    'vectors': {
                        'count': vector_count,
                        'bucket': self.vectors_bucket
                    },
                    's3Uri': f"s3://{self.staging_bucket}/grouped/{metadata['classification']['primaryTag']}/{document_id}.pdf"
                }
            }

            log.info("document_retrieved")
            return result

        except Exception as e:
            log.error("get_document_failed", error=str(e))
            raise

    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        Delete a document and its associated data.

        Args:
            document_id: Document identifier

        Returns:
            Deletion result
        """
        log = logger.bind(document_id=document_id)
        log.info("deleting_document")

        try:
            deleted_items = []

            # Delete from staging bucket (PDF and metadata)
            categories = ['unknown', 'contracts', 'financial', 'technical', 'general']

            for category in categories:
                # Delete PDF
                pdf_key = f"grouped/{category}/{document_id}.pdf"
                try:
                    self.s3.delete_object(Bucket=self.staging_bucket, Key=pdf_key)
                    deleted_items.append(pdf_key)
                except Exception:
                    pass

                # Delete metadata
                metadata_key = f"grouped/{category}/{document_id}.metadata.json"
                try:
                    self.s3.delete_object(Bucket=self.staging_bucket, Key=metadata_key)
                    deleted_items.append(metadata_key)
                except Exception:
                    pass

            # Delete vectors
            vector_count = self._delete_vectors(document_id)

            # Delete from DynamoDB
            if self.documents_table:
                try:
                    self.documents_table.delete_item(Key={'documentId': document_id})
                except Exception:
                    pass

            log.info("document_deleted", deleted_items=len(deleted_items), vectors_deleted=vector_count)

            return {
                'success': True,
                'documentId': document_id,
                'deletedFiles': len(deleted_items),
                'vectorsDeleted': vector_count,
                'message': 'Document deleted successfully'
            }

        except Exception as e:
            log.error("delete_failed", error=str(e))
            raise

    def _save_document_metadata(
        self,
        document_id: str,
        filename: str,
        s3_key: str,
        content_type: str,
        size_bytes: int,
        status: str,
        metadata: Dict[str, Any]
    ):
        """Save document metadata to DynamoDB."""
        if not self.documents_table:
            return

        try:
            self.documents_table.put_item(
                Item={
                    'documentId': document_id,
                    'filename': filename,
                    's3Key': s3_key,
                    'contentType': content_type,
                    'sizeBytes': size_bytes,
                    'status': status,
                    'uploadedAt': datetime.utcnow().isoformat() + 'Z',
                    'metadata': metadata,
                    'ttl': int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)  # 90 days
                }
            )
        except Exception as e:
            logger.error("failed_to_save_metadata", error=str(e))

    def _count_vectors(self, document_id: str) -> int:
        """Count vectors for a document."""
        try:
            prefix = f"vectors/{document_id}-chunk-"
            response = self.s3.list_objects_v2(
                Bucket=self.vectors_bucket,
                Prefix=prefix
            )
            return response.get('KeyCount', 0)
        except Exception:
            return 0

    def _delete_vectors(self, document_id: str) -> int:
        """Delete all vectors for a document."""
        try:
            prefix = f"vectors/{document_id}-chunk-"

            # List all vectors
            response = self.s3.list_objects_v2(
                Bucket=self.vectors_bucket,
                Prefix=prefix
            )

            if 'Contents' not in response:
                return 0

            # Delete all vectors
            objects = [{'Key': obj['Key']} for obj in response['Contents']]

            if objects:
                self.s3.delete_objects(
                    Bucket=self.vectors_bucket,
                    Delete={'Objects': objects}
                )

            return len(objects)
        except Exception as e:
            logger.error("failed_to_delete_vectors", error=str(e))
            return 0


# Global instance
_manager_instance = None


def get_manager() -> DocumentManager:
    """Get or create manager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = DocumentManager()
    return _manager_instance


def handler(event, context):
    """
    Lambda entry point for document management operations.
    """
    request_id = context.aws_request_id if context else "local"

    # Get manager instance
    try:
        manager = get_manager()
    except Exception as e:
        logger.error("manager_initialization_failed", error=str(e))
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Service initialization failed"})
        }

    # Route request
    path = event.get("path", "")
    method = event.get("httpMethod", "")

    logger.info("document_request", path=path, method=method, request_id=request_id)

    try:
        # Upload document
        if path == "/documents" and method == "POST":
            return _handle_upload(event, context, manager, request_id)

        # List documents
        elif path == "/documents" and method == "GET":
            return _handle_list(event, context, manager, request_id)

        # Get document details
        elif path.startswith("/documents/") and method == "GET":
            return _handle_get(event, context, manager, request_id)

        # Delete document
        elif path.startswith("/documents/") and method == "DELETE":
            return _handle_delete(event, context, manager, request_id)

        # Not found
        else:
            return {
                "statusCode": 404,
                "headers": _cors_headers(),
                "body": json.dumps({"error": "Endpoint not found"})
            }

    except Exception as e:
        logger.error("request_failed", error=str(e), path=path, method=method)
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Internal server error"})
        }


def _handle_upload(event, context, manager: DocumentManager, request_id: str):
    """Handle document upload."""
    try:
        # Get content type
        headers = event.get("headers", {})
        content_type = headers.get("content-type") or headers.get("Content-Type", "")

        # Parse body
        body = event.get("body", "")
        is_base64 = event.get("isBase64Encoded", False)

        # Try JSON format first (for testing and API clients)
        if content_type.startswith("application/json") or not content_type.startswith("multipart/form-data"):
            try:
                if isinstance(body, bytes):
                    data = json.loads(body.decode('utf-8'))
                else:
                    data = json.loads(body)

                filename = data.get('filename')
                content_base64 = data.get('content')
                file_content_type = data.get('contentType', 'application/octet-stream')
                metadata = data.get('metadata', {})

                if not filename or not content_base64:
                    return {
                        "statusCode": 400,
                        "headers": _cors_headers(),
                        "body": json.dumps({"error": "Missing required fields: filename, content"})
                    }

                try:
                    content = _decode_base64_file_content(content_base64)
                except ValueError as err:
                    return {
                        "statusCode": 400,
                        "headers": _cors_headers(),
                        "body": json.dumps({"error": str(err)}),
                    }

            except (json.JSONDecodeError, KeyError) as e:
                return {
                    "statusCode": 400,
                    "headers": _cors_headers(),
                    "body": json.dumps({"error": f"Invalid JSON format: {str(e)}"})
                }

        # Handle multipart/form-data (for browser uploads)
        else:
            if is_base64:
                body = base64.b64decode(body)
            else:
                body = body.encode('utf-8') if isinstance(body, str) else body

            # For now, just return error for multipart - implement parser if needed
            return {
                "statusCode": 400,
                "headers": _cors_headers(),
                "body": json.dumps({"error": "Multipart uploads not yet implemented. Use JSON with base64-encoded content."})
            }

        # Validate file size (max 10MB)
        if len(content) > 10 * 1024 * 1024:
            return {
                "statusCode": 400,
                "headers": _cors_headers(),
                "body": json.dumps({"error": "File too large (max 10MB)"})
            }

        # Upload document
        result = manager.upload_document(
            filename=filename,
            content=content,
            content_type=file_content_type,
            metadata=metadata
        )

        return {
            "statusCode": 202,  # Accepted (processing)
            "headers": _cors_headers(),
            "body": json.dumps({
                **result,
                "requestId": request_id
            })
        }

    except Exception as e:
        logger.error("upload_handling_failed", error=str(e))
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Upload failed"})
        }


def _handle_list(event, context, manager: DocumentManager, request_id: str):
    """Handle list documents."""
    try:
        params = event.get("queryStringParameters") or {}

        limit = int(params.get("limit", 50))
        status = params.get("status")
        category = params.get("category")
        next_token = params.get("nextToken")

        result = manager.list_documents(
            limit=limit,
            status=status,
            category=category,
            next_token=next_token
        )

        return {
            "statusCode": 200,
            "headers": _cors_headers(),
            "body": json.dumps({
                **result,
                "requestId": request_id
            })
        }

    except Exception as e:
        logger.error("list_handling_failed", error=str(e))
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Failed to list documents"})
        }


def _handle_get(event, context, manager: DocumentManager, request_id: str):
    """Handle get document details."""
    try:
        document_id = event.get("pathParameters", {}).get("documentId")

        if not document_id:
            document_id = event.get("path", "").split("/")[-1]

        result = manager.get_document(document_id)

        if not result.get('success'):
            return {
                "statusCode": 404,
                "headers": _cors_headers(),
                "body": json.dumps(result)
            }

        return {
            "statusCode": 200,
            "headers": _cors_headers(),
            "body": json.dumps({
                **result,
                "requestId": request_id
            })
        }

    except Exception as e:
        logger.error("get_handling_failed", error=str(e))
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Failed to get document"})
        }


def _handle_delete(event, context, manager: DocumentManager, request_id: str):
    """Handle delete document."""
    try:
        document_id = event.get("pathParameters", {}).get("documentId")

        if not document_id:
            document_id = event.get("path", "").split("/")[-1]

        result = manager.delete_document(document_id)

        return {
            "statusCode": 200,
            "headers": _cors_headers(),
            "body": json.dumps({
                **result,
                "requestId": request_id
            })
        }

    except Exception as e:
        logger.error("delete_handling_failed", error=str(e))
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Failed to delete document"})
        }


def _cors_headers() -> Dict[str, str]:
    """Get CORS headers."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
