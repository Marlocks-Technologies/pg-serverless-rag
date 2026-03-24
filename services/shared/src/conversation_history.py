"""
Conversation History - Manages chat session storage in DynamoDB.

Stores and retrieves conversation turns with session context.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key


class ConversationHistory:
    """Manages conversation history in DynamoDB."""

    def __init__(self, table_name: str, region: str = "us-east-1"):
        """
        Initialize conversation history manager.

        Args:
            table_name: DynamoDB table name
            region: AWS region
        """
        self.table_name = table_name
        self.region = region
        dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = dynamodb.Table(table_name)

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Save a message to conversation history.

        Args:
            session_id: Session identifier
            role: Message role (user, assistant)
            content: Message content
            metadata: Optional metadata (citations, etc.)

        Returns:
            Saved message item
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        item = {
            'SessionId': session_id,
            'Timestamp': timestamp,
            'Role': role,
            'Content': content,
            'TTL': self._calculate_ttl(days=90)  # Auto-expire after 90 days
        }

        if metadata:
            # Convert floats to Decimal for DynamoDB
            item['Metadata'] = self._convert_floats_to_decimal(metadata)

        self.table.put_item(Item=item)

        return item

    def get_conversation(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages in chronological order
        """
        response = self.table.query(
            KeyConditionExpression=Key('SessionId').eq(session_id),
            ScanIndexForward=True,  # Chronological order
            Limit=limit
        )

        messages = response.get('Items', [])

        # Convert Decimal back to float
        messages = [self._convert_decimal_to_float(msg) for msg in messages]

        return messages

    def get_recent_context(
        self,
        session_id: str,
        max_turns: int = 5
    ) -> List[Dict[str, str]]:
        """
        Get recent conversation context for RAG.

        Args:
            session_id: Session identifier
            max_turns: Maximum number of turns to retrieve

        Returns:
            List of messages formatted for RAG engine
        """
        # Get recent messages
        messages = self.get_conversation(session_id, limit=max_turns * 2)

        # Format for RAG engine (last N turns)
        context = []
        for msg in messages[-(max_turns * 2):]:
            context.append({
                'role': msg['Role'],
                'content': msg['Content']
            })

        return context

    def delete_session(self, session_id: str) -> int:
        """
        Delete all messages for a session.

        Args:
            session_id: Session identifier

        Returns:
            Number of messages deleted
        """
        messages = self.get_conversation(session_id)

        count = 0
        for msg in messages:
            self.table.delete_item(
                Key={
                    'SessionId': session_id,
                    'Timestamp': msg['Timestamp']
                }
            )
            count += 1

        return count

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get summary statistics for a session.

        Args:
            session_id: Session identifier

        Returns:
            Summary with message count, first/last timestamps
        """
        messages = self.get_conversation(session_id)

        if not messages:
            return {
                'session_id': session_id,
                'message_count': 0,
                'exists': False
            }

        return {
            'session_id': session_id,
            'message_count': len(messages),
            'first_message': messages[0]['Timestamp'],
            'last_message': messages[-1]['Timestamp'],
            'exists': True
        }

    def list_sessions(
        self,
        limit: int = 100
    ) -> List[str]:
        """
        List recent session IDs.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session IDs
        """
        # Scan table and collect unique session IDs
        # Note: This is not efficient for large datasets
        # In production, consider using GSI on SessionId
        response = self.table.scan(
            ProjectionExpression='SessionId',
            Limit=limit
        )

        session_ids = set()
        for item in response.get('Items', []):
            session_ids.add(item['SessionId'])

        return sorted(list(session_ids))

    def _calculate_ttl(self, days: int) -> int:
        """
        Calculate TTL timestamp for DynamoDB.

        Args:
            days: Number of days until expiration

        Returns:
            Unix timestamp
        """
        from datetime import timedelta
        expiry = datetime.now(timezone.utc) + timedelta(days=days)
        return int(expiry.timestamp())

    def _convert_floats_to_decimal(self, obj: Any) -> Any:
        """
        Convert floats to Decimal for DynamoDB storage.

        Args:
            obj: Object to convert

        Returns:
            Converted object
        """
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(item) for item in obj]
        return obj

    def _convert_decimal_to_float(self, obj: Any) -> Any:
        """
        Convert Decimal back to float after DynamoDB retrieval.

        Args:
            obj: Object to convert

        Returns:
            Converted object
        """
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimal_to_float(item) for item in obj]
        return obj

    def format_conversation_context(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 2000
    ) -> str:
        """
        Format conversation history as text context.

        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens for context

        Returns:
            Formatted conversation string
        """
        if not messages:
            return ""

        context = "Previous conversation:\n\n"
        total_chars = len(context)
        max_chars = max_tokens * 4  # Rough approximation

        for msg in messages:
            role = msg['Role'].title()
            content = msg['Content']
            line = f"{role}: {content}\n\n"

            if total_chars + len(line) > max_chars:
                break

            context += line
            total_chars += len(line)

        return context.strip()
