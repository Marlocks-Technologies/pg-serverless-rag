"""DynamoDB access functions for the RAG Platform chat history table.

The chat history table schema:
  - Partition key: SessionId (S)
  - Sort key:      Timestamp (S)  — ISO-8601 UTC string
  - Attributes:    Role, Message, Citations (optional), Metadata (optional)
  - TTL:           ExpiresAt (N)  — Unix epoch seconds
"""

import time
from decimal import Decimal
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key


def put_history_item(
    table: Any,
    session_id: str,
    timestamp: str,
    role: str,
    message: str,
    citations: Optional[list[dict]] = None,
    metadata: Optional[dict] = None,
    ttl_seconds: int = 60 * 60 * 24 * 30,  # 30 days default
) -> None:
    """Write a chat history item to the DynamoDB table.

    Args:
        table: boto3 DynamoDB Table resource.
        session_id: Unique session identifier.
        timestamp: ISO-8601 UTC timestamp string (e.g. "2024-01-15T12:34:56.789Z").
        role: Message author — "user" or "assistant".
        message: The text content of the message.
        citations: Optional list of citation dicts (document references).
        metadata: Optional additional metadata dict.
        ttl_seconds: Seconds until the record expires (default 30 days).
    """
    item: dict[str, Any] = {
        "SessionId": session_id,
        "Timestamp": timestamp,
        "Role": role,
        "Message": message,
        "ExpiresAt": int(time.time()) + ttl_seconds,
    }
    if citations is not None:
        item["Citations"] = citations
    if metadata is not None:
        item["Metadata"] = metadata

    table.put_item(Item=item)


def get_history(
    table: Any,
    session_id: str,
    limit: int = 20,
) -> list[dict]:
    """Retrieve the most recent chat history items for a session.

    Results are ordered by Timestamp ascending (oldest first).

    Args:
        table: boto3 DynamoDB Table resource.
        session_id: Unique session identifier.
        limit: Maximum number of items to return.

    Returns:
        List of item dicts ordered by Timestamp ascending.
    """
    response = table.query(
        KeyConditionExpression=Key("SessionId").eq(session_id),
        ScanIndexForward=True,   # ascending by sort key (oldest first)
        Limit=limit,
    )
    return response.get("Items", [])


def build_conversation_context(history_items: list[dict]) -> list[dict]:
    """Format DynamoDB history items into Bedrock Converse API message format.

    Args:
        history_items: List of history item dicts from ``get_history()``.
            Each must have "Role" and "Message" fields.

    Returns:
        List of message dicts in Bedrock Converse format:
        [{"role": "user", "content": [{"text": "..."}]}, ...]

        Only "user" and "assistant" roles are included; any unknown roles
        are skipped.
    """
    messages = []
    for item in history_items:
        role = item.get("Role", "").lower()
        if role not in ("user", "assistant"):
            continue
        message_text = item.get("Message", "")
        if not message_text:
            continue
        messages.append(
            {
                "role": role,
                "content": [{"text": message_text}],
            }
        )
    return messages
