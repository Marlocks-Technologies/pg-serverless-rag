"""
DocumentProcessorLambda - Full Implementation

Processes uploaded documents through complete pipeline:
1. Download from S3
2. Extract text (parsers + OCR)
3. Normalize text
4. Classify with LLM
5. Generate normalized PDF
6. Generate embeddings
7. Store in S3 Vectors
8. Write metadata to staging bucket
"""

import json
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, Any

# Add Lambda layer path
sys.path.insert(0, '/opt/python')

import boto3
from shared.document_parsers import DocumentParser
from shared.ocr_service import TextractOCR, clean_ocr_text
from shared.text_processing import (
    normalize_text,
    chunk_text,
    extract_classification_snippet,
    compute_text_hash
)
from shared.document_classifier import DocumentClassifier, get_prefix_for_category
from shared.pdf_generator import generate_pdf
from shared.s3_vectors import S3VectorStore
from shared.bedrock_wrappers import generate_embeddings
from shared.s3_helpers import download_object, upload_object
from shared.logger import get_logger
from shared.validation import sanitize_filename

logger = get_logger(__name__)


class DocumentProcessor:
    """Main document processing orchestrator."""

    def __init__(self):
        """Initialize processor with AWS clients and configuration."""
        self.s3 = boto3.client('s3')
        self.region = os.environ.get('AWS_REGION', 'us-east-1')

        # Configuration from environment
        self.ingestion_bucket = os.environ['INGESTION_BUCKET']
        self.staging_bucket = os.environ['STAGING_BUCKET']
        self.vectors_bucket = os.environ['VECTORS_BUCKET']
        self.embedding_model_id = os.environ['EMBEDDING_MODEL_ID']
        self.haiku_model_id = os.environ['HAIKU_MODEL_ID']

        # Initialize services
        self.ocr = TextractOCR(region=self.region)
        self.classifier = DocumentClassifier(
            model_id=self.haiku_model_id,
            region=self.region
        )
        self.vector_store = S3VectorStore(
            bucket_name=self.vectors_bucket,
            region=self.region
        )

    def process_s3_event(self, record: Dict[str, Any], request_id: str) -> Dict[str, Any]:
        """
        Process a single S3 event record.

        Args:
            record: S3 event notification record
            request_id: Lambda request ID for tracking

        Returns:
            Processing result dictionary
        """
        # Extract S3 details
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        size = record['s3']['object'].get('size', 0)

        log = logger.bind(
            request_id=request_id,
            bucket=bucket,
            key=key,
            size_bytes=size
        )

        log.info("processing_document_started")

        try:
            # Step 1: Download document
            log.info("downloading_document")
            file_content = download_object(bucket, key, self.s3)
            filename = os.path.basename(key)

            # Step 2: Parse document
            log.info("parsing_document", filename=filename)
            parsed = DocumentParser.parse(file_content, filename)

            text = parsed['text']
            requires_ocr = parsed.get('requires_ocr', False)

            # Step 3: OCR if needed
            if requires_ocr and not text.strip():
                log.info("running_ocr")
                ocr_result = self.ocr.extract_text_from_bytes(file_content)
                text = clean_ocr_text(ocr_result['text'])
                parsed['ocr_confidence'] = ocr_result.get('confidence', 0)

            if not text or len(text.strip()) < 50:
                log.warning("insufficient_text_extracted", text_length=len(text))
                return self._handle_failed_document(
                    bucket, key, filename, "Insufficient text extracted"
                )

            # Step 4: Normalize text
            log.info("normalizing_text")
            normalized_text = normalize_text(text, source_metadata={
                'filename': filename,
                'upload_timestamp': datetime.utcnow().isoformat() + 'Z',
                'source_bucket': bucket,
                'source_key': key
            })

            # Step 5: Classify document
            log.info("classifying_document")
            classification_snippet = extract_classification_snippet(normalized_text, max_length=2000)
            classification = self.classifier.classify(classification_snippet, filename)

            log.info("classification_result",
                category=classification['primary_tag'],
                confidence=classification['confidence']
            )

            # Step 6: Generate document ID and metadata
            document_id = str(uuid.uuid4())
            text_hash = compute_text_hash(normalized_text)

            # Step 7: Generate normalized PDF
            log.info("generating_pdf", document_id=document_id)
            pdf_bytes = generate_pdf(
                title=filename,
                source_filename=filename,
                category=classification['primary_tag'],
                extraction_timestamp=datetime.utcnow().isoformat() + 'Z',
                body_text=normalized_text,
                document_id=document_id
            )

            # Step 8: Upload PDF to staging bucket
            category_prefix = get_prefix_for_category(classification['primary_tag'])
            pdf_key = f"grouped/{category_prefix}/{document_id}.pdf"

            log.info("uploading_pdf", staging_key=pdf_key)
            upload_object(
                self.staging_bucket,
                pdf_key,
                pdf_bytes,
                content_type='application/pdf',
                metadata={
                    'document-id': document_id,
                    'source-filename': sanitize_filename(filename),
                    'category': classification['primary_tag']
                },
                client=self.s3
            )

            # Step 9: Create and upload metadata
            metadata = self._build_metadata(
                document_id=document_id,
                source_bucket=bucket,
                source_key=key,
                filename=filename,
                size=size,
                classification=classification,
                parsed=parsed,
                text_hash=text_hash,
                normalized_text_length=len(normalized_text),
                category_prefix=category_prefix
            )

            metadata_key = f"grouped/{category_prefix}/{document_id}.metadata.json"

            log.info("uploading_metadata", metadata_key=metadata_key)
            upload_object(
                self.staging_bucket,
                metadata_key,
                json.dumps(metadata, indent=2).encode('utf-8'),
                content_type='application/json',
                metadata={},
                client=self.s3
            )

            # Step 10: Chunk text for embeddings
            log.info("chunking_text")
            chunks = chunk_text(
                normalized_text,
                chunk_size=800,
                overlap_percentage=0.15,
                preserve_sentences=True
            )

            log.info("chunks_created", chunk_count=len(chunks))

            # Step 11: Generate embeddings and store in S3 Vectors
            log.info("generating_embeddings_start", chunk_count=len(chunks))

            # Create bedrock client with explicit region
            log.info("creating_bedrock_client", region=self.region)
            try:
                bedrock_runtime = boto3.client('bedrock-runtime', region_name=self.region)
                log.info("bedrock_client_created")
            except Exception as e:
                log.error("bedrock_client_failed", error=str(e), error_type=type(e).__name__)
                raise

            for i, chunk in enumerate(chunks):
                log.info("processing_chunk", chunk_index=i, chunk_size=len(chunk['text']))

                # Generate embedding
                try:
                    log.info("calling_generate_embeddings", chunk_index=i, model=self.embedding_model_id)
                    embedding = generate_embeddings(
                        text=chunk['text'],
                        model_id=self.embedding_model_id,
                        client=bedrock_runtime
                    )
                    log.info("embedding_generated", chunk_index=i, dimension=len(embedding))
                except Exception as e:
                    log.error("embedding_generation_failed",
                        chunk_index=i,
                        error=str(e),
                        error_type=type(e).__name__,
                        traceback=str(e.__traceback__)
                    )
                    raise

                # Store in S3 Vectors
                vector_id = f"{document_id}-chunk-{chunk['chunk_index']}"

                try:
                    log.info("storing_vector", vector_id=vector_id, chunk_index=i)
                    self.vector_store.store_vector(
                        vector_id=vector_id,
                        embedding=embedding,
                        text=chunk['text'],
                        metadata={
                            'documentId': document_id,
                            'filename': filename,
                            'category': classification['primary_tag'],
                            'chunkIndex': chunk['chunk_index'],
                            'sourceUri': f"s3://{self.staging_bucket}/{pdf_key}",
                            'timestamp': datetime.utcnow().isoformat() + 'Z',
                            'tokenCount': chunk['token_count']
                        }
                    )
                    log.info("vector_stored", vector_id=vector_id, chunk_index=i)
                except Exception as e:
                    log.error("vector_storage_failed",
                        chunk_index=i,
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    raise

            log.info("vectors_stored", vector_count=len(chunks))

            # Success!
            log.info("processing_completed",
                document_id=document_id,
                category=classification['primary_tag'],
                chunks=len(chunks),
                status="success"
            )

            return {
                'status': 'success',
                'document_id': document_id,
                'category': classification['primary_tag'],
                'chunks': len(chunks),
                'staging_pdf': f"s3://{self.staging_bucket}/{pdf_key}"
            }

        except Exception as e:
            log.error("processing_failed",
                error=str(e),
                error_type=type(e).__name__,
                status="error"
            )
            return self._handle_failed_document(bucket, key, filename, str(e))

    def _build_metadata(
        self,
        document_id: str,
        source_bucket: str,
        source_key: str,
        filename: str,
        size: int,
        classification: Dict[str, Any],
        parsed: Dict[str, Any],
        text_hash: str,
        normalized_text_length: int,
        category_prefix: str
    ) -> Dict[str, Any]:
        """Build complete metadata document."""
        return {
            'documentId': document_id,
            'source': {
                'bucket': source_bucket,
                'key': source_key,
                'filename': filename,
                'contentType': parsed.get('parser_used', 'unknown'),
                'sizeBytes': size,
                'uploadTimestamp': datetime.utcnow().isoformat() + 'Z',
                'checksum': text_hash
            },
            'classification': {
                'primaryTag': classification['primary_tag'],
                'secondaryTags': classification.get('secondary_tags', []),
                'confidence': classification['confidence']
            },
            'grouping': {
                'prefix': category_prefix,
                'reason': classification.get('grouping_reason', '')
            },
            'processing': {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'parser': parsed.get('parser_used', 'unknown'),
                'ocrUsed': parsed.get('requires_ocr', False),
                'ocrConfidence': parsed.get('ocr_confidence'),
                'textLengthChars': normalized_text_length,
                'pageCount': parsed.get('page_count', 1)
            }
        }

    def _handle_failed_document(
        self,
        bucket: str,
        key: str,
        filename: str,
        error_message: str
    ) -> Dict[str, Any]:
        """Handle failed document processing."""
        # Write error manifest to failed/ prefix
        error_manifest = {
            'source': {
                'bucket': bucket,
                'key': key,
                'filename': filename
            },
            'error': error_message,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

        error_key = f"failed/{datetime.utcnow().strftime('%Y%m%d')}/{os.path.basename(key)}.error.json"

        try:
            upload_object(
                self.staging_bucket,
                error_key,
                json.dumps(error_manifest, indent=2).encode('utf-8'),
                content_type='application/json',
                metadata={},
                client=self.s3
            )
        except Exception as e:
            logger.error("failed_to_write_error_manifest", error=str(e))

        return {
            'status': 'failed',
            'error': error_message,
            'error_manifest': f"s3://{self.staging_bucket}/{error_key}"
        }


def handler(event, context):
    """
    Lambda handler entry point.

    Processes S3 event notifications for document uploads.
    """
    request_id = context.aws_request_id if context else 'local'

    logger.info("lambda_invoked",
        request_id=request_id,
        record_count=len(event.get('Records', []))
    )

    processor = DocumentProcessor()
    results = []

    for record in event.get('Records', []):
        result = processor.process_s3_event(record, request_id)
        results.append(result)

    # Summary
    success_count = sum(1 for r in results if r.get('status') == 'success')
    failed_count = len(results) - success_count

    logger.info("lambda_completed",
        request_id=request_id,
        total=len(results),
        success=success_count,
        failed=failed_count
    )

    return {
        'statusCode': 200 if failed_count == 0 else 207,  # 207 = Multi-Status
        'body': json.dumps({
            'message': f"Processed {len(results)} documents",
            'success': success_count,
            'failed': failed_count,
            'results': results
        })
    }
