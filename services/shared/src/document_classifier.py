"""
Document classification using Amazon Bedrock Claude 3 Haiku.
"""

import json
import boto3
from typing import Dict, Any
from pathlib import Path
from botocore.exceptions import ClientError


class DocumentClassifier:
    """LLM-based document classifier using Bedrock."""

    VALID_CATEGORIES = {
        'invoice', 'hr', 'technical-spec', 'legal',
        'finance', 'operations', 'unknown'
    }

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-5-haiku-20241022-v1:0",
        region: str = 'us-east-1',
        system_prompt_path: str = None
    ):
        """
        Initialize document classifier.

        Args:
            model_id: Bedrock model ID for classification
            region: AWS region
            system_prompt_path: Path to system prompt file (optional)
        """
        self.model_id = model_id
        self.bedrock = boto3.client('bedrock-runtime', region_name=region)
        self.system_prompt = self._load_system_prompt(system_prompt_path)

    def _load_system_prompt(self, prompt_path: str = None) -> str:
        """Load system prompt from file or use default."""
        if prompt_path and Path(prompt_path).exists():
            with open(prompt_path, 'r') as f:
                return f.read()

        # Default system prompt (fallback)
        return """You are a document classification assistant. Analyze the provided document excerpt and classify it into one of these categories:

- invoice: Invoices, bills, payment requests, purchase orders
- hr: Human resources documents, employee records, policies, benefits
- technical-spec: Technical specifications, architecture docs, API docs, system designs
- legal: Contracts, agreements, terms of service, legal notices
- finance: Financial reports, budgets, forecasts, financial analysis
- operations: Operational procedures, workflows, process documentation
- unknown: Document type cannot be determined with confidence

Output ONLY valid JSON in this exact format:
{
  "primaryTag": "<category>",
  "secondaryTags": ["<tag1>", "<tag2>"],
  "confidence": 0.95,
  "groupingReason": "<brief explanation>"
}

Base classification ONLY on the provided text. Do not hallucinate details."""

    def classify(self, text_excerpt: str, filename: str = None) -> Dict[str, Any]:
        """
        Classify document based on text excerpt.

        Args:
            text_excerpt: Sample text from document
            filename: Optional filename for additional context

        Returns:
            Dictionary with:
                - primary_tag: Main category
                - secondary_tags: Additional tags
                - confidence: Confidence score (0.0 to 1.0)
                - grouping_reason: Explanation for classification
        """
        if not text_excerpt or not text_excerpt.strip():
            return self._unknown_classification("Empty document")

        # Build prompt
        user_prompt = f"Classify this document excerpt:\n\n{text_excerpt}"

        if filename:
            user_prompt = f"Filename: {filename}\n\n{user_prompt}"

        # Call Bedrock
        try:
            response = self._invoke_bedrock(user_prompt)
            classification = self._parse_classification_response(response)

            # Validate and return
            return self._validate_classification(classification)

        except Exception as e:
            print(f"Classification error: {e}")
            return self._unknown_classification(f"Classification failed: {str(e)}")

    def _invoke_bedrock(self, user_prompt: str, max_retries: int = 3) -> str:
        """
        Invoke Bedrock model with retry logic.

        Args:
            user_prompt: User message
            max_retries: Maximum number of retries for failed calls

        Returns:
            Model response text
        """
        for attempt in range(max_retries):
            try:
                # Claude 3 Messages API format
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "system": self.system_prompt,
                    "messages": [
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ],
                    "temperature": 0.0,  # Deterministic for classification
                })

                response = self.bedrock.invoke_model(
                    modelId=self.model_id,
                    body=body,
                    contentType='application/json',
                    accept='application/json'
                )

                response_body = json.loads(response['body'].read())

                # Extract text from response
                content = response_body.get('content', [])
                if content and len(content) > 0:
                    return content[0].get('text', '')

                raise ValueError("Empty response from Bedrock")

            except ClientError as e:
                error_code = e.response['Error']['Code']

                # Retry on throttling
                if error_code == 'ThrottlingException' and attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue

                # Log ResourceNotFoundException (legacy model) but don't crash
                if error_code == 'ResourceNotFoundException':
                    print(f"Model {self.model_id} not available: {e}")
                    raise RuntimeError(f"Model not available: {self.model_id}")

                raise RuntimeError(f"Bedrock error ({error_code}): {e}")

            except Exception as e:
                if attempt < max_retries - 1:
                    continue
                raise

        raise RuntimeError("Max retries exceeded for Bedrock invocation")

    def _parse_classification_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON response from model.

        Args:
            response_text: Raw model response

        Returns:
            Parsed classification dictionary
        """
        # Try to extract JSON from response
        # Model might include some explanation before/after JSON

        # Find JSON block
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in model response")

        json_str = response_text[json_start:json_end]

        try:
            classification = json.loads(json_str)
            return classification
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in model response: {e}")

    def _validate_classification(self, classification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate classification response schema.

        Args:
            classification: Raw classification from model

        Returns:
            Validated and normalized classification
        """
        # Required fields
        if 'primaryTag' not in classification:
            raise ValueError("Missing primaryTag in classification")
        if 'confidence' not in classification:
            raise ValueError("Missing confidence in classification")

        primary_tag = classification['primaryTag']
        confidence = classification['confidence']
        secondary_tags = classification.get('secondaryTags', [])
        grouping_reason = classification.get('groupingReason', '')

        # Validate primary tag
        if primary_tag not in self.VALID_CATEGORIES:
            print(f"Invalid category '{primary_tag}', defaulting to 'unknown'")
            primary_tag = 'unknown'
            confidence = 0.1

        # Validate confidence
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, float(confidence)))

        # Validate secondary tags
        if not isinstance(secondary_tags, list):
            secondary_tags = []

        # Normalize
        return {
            'primary_tag': primary_tag,
            'secondary_tags': secondary_tags,
            'confidence': confidence,
            'grouping_reason': grouping_reason
        }

    def _unknown_classification(self, reason: str) -> Dict[str, Any]:
        """Return a default 'unknown' classification."""
        return {
            'primary_tag': 'unknown',
            'secondary_tags': [],
            'confidence': 0.0,
            'grouping_reason': reason
        }

    def classify_batch(self, documents: list) -> list:
        """
        Classify multiple documents.

        Args:
            documents: List of dicts with 'text' and optional 'filename'

        Returns:
            List of classification results
        """
        results = []
        for doc in documents:
            text = doc.get('text', '')
            filename = doc.get('filename')

            classification = self.classify(text, filename)
            results.append({
                'filename': filename,
                'classification': classification
            })

        return results


def get_prefix_for_category(category: str) -> str:
    """
    Get S3 prefix for a document category.

    Args:
        category: Document category

    Returns:
        S3 prefix string (e.g., 'technical-spec')
    """
    # Map category to prefix (can be customized)
    category_to_prefix = {
        'invoice': 'invoice',
        'hr': 'hr',
        'technical-spec': 'technical-spec',
        'legal': 'legal',
        'finance': 'finance',
        'operations': 'operations',
        'unknown': 'unknown'
    }

    return category_to_prefix.get(category, 'unknown')
