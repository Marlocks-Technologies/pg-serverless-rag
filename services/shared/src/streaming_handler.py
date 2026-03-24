"""
Streaming Handler - Manages WebSocket streaming responses.

Handles token-by-token streaming from RAG engine to WebSocket clients.
"""

import json
import traceback
from typing import Dict, Any, Iterator, Optional
import boto3
from logger import get_logger

logger = get_logger(__name__)


class StreamingHandler:
    """Manages streaming responses via WebSocket API Gateway."""

    def __init__(self, endpoint_url: str, region: str = "us-east-1"):
        """
        Initialize streaming handler.

        Args:
            endpoint_url: WebSocket API Gateway management URL
            region: AWS region
        """
        self.endpoint_url = endpoint_url
        self.region = region
        self.client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url,
            region_name=region
        )

    def stream_rag_response(
        self,
        connection_id: str,
        response_data: Dict[str, Any]
    ) -> bool:
        """
        Stream a RAG response to WebSocket client.

        Args:
            connection_id: WebSocket connection ID
            response_data: Response from RAG engine with 'stream' generator

        Returns:
            True if successful, False otherwise
        """
        try:
            # Send start event
            self._send_event(connection_id, {
                'type': 'chat.start',
                'metadata': response_data.get('metadata', {})
            })

            # Stream content chunks
            stream = response_data.get('stream')
            if stream:
                full_text = ""
                for chunk in stream:
                    full_text += chunk
                    self._send_event(connection_id, {
                        'type': 'chat.chunk',
                        'content': chunk
                    })

            # Send citations
            citations = response_data.get('citations', [])
            if citations:
                self._send_event(connection_id, {
                    'type': 'chat.citations',
                    'citations': citations
                })

            # Send complete event
            self._send_event(connection_id, {
                'type': 'chat.complete',
                'full_text': full_text if stream else ""
            })

            return True

        except Exception as e:
            logger.error("streaming_failed", error=str(e), connection_id=connection_id)
            self._send_error(connection_id, str(e))
            return False

    def stream_text(
        self,
        connection_id: str,
        text_iterator: Iterator[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Stream text chunks to WebSocket client.

        Args:
            connection_id: WebSocket connection ID
            text_iterator: Iterator yielding text chunks
            metadata: Optional metadata to send

        Returns:
            True if successful
        """
        try:
            # Send start
            if metadata:
                self._send_event(connection_id, {
                    'type': 'stream.start',
                    'metadata': metadata
                })

            # Stream chunks
            for chunk in text_iterator:
                self._send_event(connection_id, {
                    'type': 'stream.chunk',
                    'content': chunk
                })

            # Send complete
            self._send_event(connection_id, {
                'type': 'stream.complete'
            })

            return True

        except Exception as e:
            logger.error("text_streaming_failed", error=str(e))
            self._send_error(connection_id, str(e))
            return False

    def send_message(
        self,
        connection_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """
        Send a single message to WebSocket client.

        Args:
            connection_id: WebSocket connection ID
            message: Message data

        Returns:
            True if successful
        """
        try:
            self.client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(message).encode('utf-8')
            )
            return True

        except self.client.exceptions.GoneException:
            logger.warning("connection_gone", connection_id=connection_id)
            return False

        except Exception as e:
            logger.error("send_message_failed", error=str(e), connection_id=connection_id)
            return False

    def _send_event(
        self,
        connection_id: str,
        event: Dict[str, Any]
    ) -> bool:
        """
        Send an event to WebSocket client.

        Args:
            connection_id: WebSocket connection ID
            event: Event data

        Returns:
            True if successful
        """
        return self.send_message(connection_id, event)

    def _send_error(
        self,
        connection_id: str,
        error_message: str
    ) -> bool:
        """
        Send error message to WebSocket client.

        Args:
            connection_id: WebSocket connection ID
            error_message: Error description

        Returns:
            True if successful
        """
        return self._send_event(connection_id, {
            'type': 'error',
            'message': error_message
        })

    def broadcast(
        self,
        connection_ids: list[str],
        message: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Broadcast message to multiple connections.

        Args:
            connection_ids: List of connection IDs
            message: Message to broadcast

        Returns:
            Dict mapping connection_id to success status
        """
        results = {}

        for connection_id in connection_ids:
            results[connection_id] = self.send_message(connection_id, message)

        return results

    @staticmethod
    def create_from_request_context(
        request_context: Dict[str, Any]
    ) -> 'StreamingHandler':
        """
        Create StreamingHandler from WebSocket request context.

        Args:
            request_context: API Gateway WebSocket request context

        Returns:
            StreamingHandler instance
        """
        domain_name = request_context.get('domainName')
        stage = request_context.get('stage')

        endpoint_url = f"https://{domain_name}/{stage}"

        return StreamingHandler(endpoint_url=endpoint_url)


class StreamingResponseBuilder:
    """Helper to build streaming responses."""

    def __init__(self):
        """Initialize builder."""
        self.events = []

    def add_start(self, metadata: Optional[Dict[str, Any]] = None) -> 'StreamingResponseBuilder':
        """Add start event."""
        event = {'type': 'chat.start'}
        if metadata:
            event['metadata'] = metadata
        self.events.append(event)
        return self

    def add_chunk(self, content: str) -> 'StreamingResponseBuilder':
        """Add content chunk."""
        self.events.append({
            'type': 'chat.chunk',
            'content': content
        })
        return self

    def add_citations(self, citations: list[Dict[str, Any]]) -> 'StreamingResponseBuilder':
        """Add citations."""
        self.events.append({
            'type': 'chat.citations',
            'citations': citations
        })
        return self

    def add_complete(self, full_text: str = "") -> 'StreamingResponseBuilder':
        """Add complete event."""
        self.events.append({
            'type': 'chat.complete',
            'full_text': full_text
        })
        return self

    def add_error(self, error_message: str) -> 'StreamingResponseBuilder':
        """Add error event."""
        self.events.append({
            'type': 'error',
            'message': error_message
        })
        return self

    def build(self) -> list[Dict[str, Any]]:
        """Build list of events."""
        return self.events

    def send_all(self, handler: StreamingHandler, connection_id: str) -> bool:
        """Send all events via handler."""
        success = True
        for event in self.events:
            if not handler.send_message(connection_id, event):
                success = False
                break
        return success
