"""
OCR service using Amazon Textract.

Handles both synchronous and asynchronous text extraction from images and scanned PDFs.
"""

import time
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError


class TextractOCR:
    """Amazon Textract OCR service wrapper."""

    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize Textract client.

        Args:
            region: AWS region for Textract service
        """
        self.textract = boto3.client('textract', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)

    def extract_text_from_bytes(self, document_bytes: bytes, document_type: str = 'image') -> Dict[str, Any]:
        """
        Extract text from document bytes using synchronous Textract.

        Args:
            document_bytes: Document content as bytes
            document_type: Type of document ('image' or 'pdf')

        Returns:
            Dictionary with:
                - text: Extracted text
                - confidence: Average confidence score
                - blocks: Raw Textract blocks
                - page_count: Number of pages processed
        """
        # Check size limit for synchronous detection (5 MB)
        if len(document_bytes) > 5 * 1024 * 1024:
            raise ValueError(
                "Document too large for synchronous processing. "
                "Use extract_text_from_s3() for documents > 5MB"
            )

        try:
            # Call Textract DetectDocumentText for simple text extraction
            response = self.textract.detect_document_text(
                Document={'Bytes': document_bytes}
            )

            return self._parse_textract_response(response)

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            raise RuntimeError(f"Textract error ({error_code}): {error_msg}")

    def extract_text_from_s3(
        self,
        bucket: str,
        key: str,
        use_async: bool = True
    ) -> Dict[str, Any]:
        """
        Extract text from document stored in S3.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            use_async: Whether to use asynchronous processing (for large documents)

        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            if use_async:
                return self._extract_text_async(bucket, key)
            else:
                return self._extract_text_sync(bucket, key)

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            raise RuntimeError(f"Textract S3 error ({error_code}): {error_msg}")

    def _extract_text_sync(self, bucket: str, key: str) -> Dict[str, Any]:
        """Synchronous text extraction from S3 (documents < 5MB)."""
        response = self.textract.detect_document_text(
            Document={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            }
        )

        return self._parse_textract_response(response)

    def _extract_text_async(self, bucket: str, key: str, max_wait_seconds: int = 300) -> Dict[str, Any]:
        """
        Asynchronous text extraction from S3 (for large documents).

        Starts a Textract job and polls until completion.
        """
        # Start async job
        response = self.textract.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            }
        )

        job_id = response['JobId']

        # Poll for completion
        start_time = time.time()
        while True:
            if time.time() - start_time > max_wait_seconds:
                raise TimeoutError(f"Textract job {job_id} timed out after {max_wait_seconds}s")

            time.sleep(2)  # Wait 2 seconds between polls

            result = self.textract.get_document_text_detection(JobId=job_id)
            status = result['JobStatus']

            if status == 'SUCCEEDED':
                # Collect all pages
                all_blocks = result.get('Blocks', [])

                # Handle pagination
                next_token = result.get('NextToken')
                while next_token:
                    result = self.textract.get_document_text_detection(
                        JobId=job_id,
                        NextToken=next_token
                    )
                    all_blocks.extend(result.get('Blocks', []))
                    next_token = result.get('NextToken')

                # Parse blocks
                return self._parse_textract_blocks(all_blocks)

            elif status == 'FAILED':
                error_msg = result.get('StatusMessage', 'Unknown error')
                raise RuntimeError(f"Textract job {job_id} failed: {error_msg}")

            elif status in ['IN_PROGRESS', 'PARTIAL_SUCCESS']:
                continue  # Keep waiting

            else:
                raise RuntimeError(f"Unexpected Textract job status: {status}")

    def _parse_textract_response(self, response: Dict) -> Dict[str, Any]:
        """Parse synchronous Textract response."""
        blocks = response.get('Blocks', [])
        return self._parse_textract_blocks(blocks)

    def _parse_textract_blocks(self, blocks: list) -> Dict[str, Any]:
        """
        Parse Textract blocks and extract text.

        Args:
            blocks: List of Textract block objects

        Returns:
            Dictionary with extracted text and metadata
        """
        # Extract LINE blocks (preserve line structure)
        lines = []
        confidences = []
        page_numbers = set()

        for block in blocks:
            if block['BlockType'] == 'LINE':
                text = block.get('Text', '')
                confidence = block.get('Confidence', 0)
                page = block.get('Page', 1)

                if text.strip():
                    lines.append(text)
                    confidences.append(confidence)
                    page_numbers.add(page)

        # Join lines with newlines
        full_text = '\n'.join(lines)

        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            'text': full_text,
            'confidence': avg_confidence,
            'blocks': blocks,
            'page_count': len(page_numbers),
            'line_count': len(lines),
            'method': 'textract_ocr'
        }

    def extract_text_with_layout(self, document_bytes: bytes) -> Dict[str, Any]:
        """
        Extract text while preserving layout information.

        Uses AnalyzeDocument API with LAYOUT feature.

        Args:
            document_bytes: Document content as bytes

        Returns:
            Dictionary with text and layout information
        """
        try:
            response = self.textract.analyze_document(
                Document={'Bytes': document_bytes},
                FeatureTypes=['LAYOUT']
            )

            # Parse blocks and organize by layout
            text_by_section = {}
            current_section = 'body'

            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LAYOUT_TEXT':
                    text = self._extract_text_from_block(block, response['Blocks'])
                    if text:
                        if current_section not in text_by_section:
                            text_by_section[current_section] = []
                        text_by_section[current_section].append(text)

            # Combine sections
            full_text = '\n\n'.join([
                '\n'.join(text_by_section.get('body', []))
            ])

            return {
                'text': full_text,
                'sections': text_by_section,
                'method': 'textract_layout'
            }

        except ClientError as e:
            # Fall back to simple text detection
            return self.extract_text_from_bytes(document_bytes)

    def _extract_text_from_block(self, block: Dict, all_blocks: list) -> str:
        """Extract text from a layout block by following relationships."""
        if 'Relationships' not in block:
            return ''

        text_parts = []
        for relationship in block['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    child_block = next(
                        (b for b in all_blocks if b['Id'] == child_id),
                        None
                    )
                    if child_block and 'Text' in child_block:
                        text_parts.append(child_block['Text'])

        return ' '.join(text_parts)


def clean_ocr_text(text: str) -> str:
    """
    Clean OCR text by removing common artifacts.

    Args:
        text: Raw OCR text

    Returns:
        Cleaned text
    """
    if not text:
        return text

    # Remove excessive whitespace
    lines = []
    for line in text.split('\n'):
        cleaned_line = ' '.join(line.split())
        if cleaned_line:
            lines.append(cleaned_line)

    # Join with single newlines
    cleaned = '\n'.join(lines)

    # Remove common OCR artifacts
    # (This can be expanded based on observed patterns)
    cleaned = cleaned.replace('|', 'I')  # Common OCR mistake
    cleaned = cleaned.replace('¢', 'c')  # Currency symbols

    return cleaned
