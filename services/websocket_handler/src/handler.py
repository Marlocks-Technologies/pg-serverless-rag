"""
WebSocket Handler Lambda - Real-time streaming chat with RAG.

Handles:
- WebSocket connections ($connect, $disconnect)
- Streaming chat messages with Bedrock
- Real-time token-by-token responses
"""

import json
import os
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

# Add Lambda layer path
sys.path.insert(0, '/opt/python')

import boto3
from botocore.exceptions import ClientError
from shared.logger import get_logger

logger = get_logger(__name__)


class WebSocketHandler:
    """Handles WebSocket connections and streaming chat."""

    def __init__(self):
        """Initialize AWS clients and configuration."""
        self.dynamodb = boto3.resource('dynamodb')
        self.bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name=os.environ.get('AWS_REGION', 'eu-west-1'))
        self.apigw_management = None  # Initialized per connection

        # Configuration from environment
        self.connections_table_name = os.environ.get('CONNECTIONS_TABLE', 'rag-mt-dev-ws-connections')
        self.chat_history_table_name = os.environ['CHAT_HISTORY_TABLE']
        self.knowledge_base_id = os.environ['KNOWLEDGE_BASE_ID']
        self.generation_model_id = os.environ['GENERATION_MODEL_ID']

        # DynamoDB tables
        try:
            self.connections_table = self.dynamodb.Table(self.connections_table_name)
        except Exception as e:
            logger.warning("connections_table_not_found", error=str(e))
            self.connections_table = None

        self.chat_history_table = self.dynamodb.Table(self.chat_history_table_name)

    def initialize_management_api(self, domain_name: str, stage: str):
        """Initialize API Gateway Management API client."""
        endpoint_url = f"https://{domain_name}/{stage}"
        self.apigw_management = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url
        )

    def handle_connect(self, connection_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WebSocket connection."""
        log = logger.bind(connection_id=connection_id)
        log.info("websocket_connect")

        if not self.connections_table:
            log.warning("connections_table_not_available")
            return {"statusCode": 200}

        try:
            # Store connection
            self.connections_table.put_item(
                Item={
                    'connectionId': connection_id,
                    'connectedAt': datetime.utcnow().isoformat() + 'Z',
                    'ttl': int(datetime.utcnow().timestamp()) + (2 * 60 * 60)  # 2 hours
                }
            )
            log.info("connection_stored")
            return {"statusCode": 200}

        except Exception as e:
            log.error("connection_store_failed", error=str(e))
            return {"statusCode": 500}

    def handle_disconnect(self, connection_id: str) -> Dict[str, Any]:
        """Handle WebSocket disconnection."""
        log = logger.bind(connection_id=connection_id)
        log.info("websocket_disconnect")

        if not self.connections_table:
            return {"statusCode": 200}

        try:
            # Remove connection
            self.connections_table.delete_item(
                Key={'connectionId': connection_id}
            )
            log.info("connection_removed")
            return {"statusCode": 200}

        except Exception as e:
            log.error("connection_remove_failed", error=str(e))
            return {"statusCode": 500}

    def handle_chat(self, connection_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat message with streaming response."""
        log = logger.bind(
            connection_id=connection_id,
            question=message.get('question', '')[:100]
        )
        log.info("chat_request_received")

        try:
            question = message.get('question')
            session_id = message.get('sessionId', f"ws-{connection_id}")
            top_k = message.get('topK', 5)

            if not question:
                self._send_error(connection_id, "Missing required field: question")
                return {"statusCode": 400}

            # Send start message
            self._send_message(connection_id, {
                'type': 'chat.start',
                'sessionId': session_id,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })

            # Query with streaming
            full_response = ""
            citations = []

            try:
                # Retrieve and generate with streaming
                response = self.bedrock_runtime.retrieve_and_generate(
                    input={'text': question},
                    retrieveAndGenerateConfiguration={
                        'type': 'KNOWLEDGE_BASE',
                        'knowledgeBaseConfiguration': {
                            'knowledgeBaseId': self.knowledge_base_id,
                            'modelArn': f"arn:aws:bedrock:eu-west-1::foundation-model/{self.generation_model_id}",
                            'retrievalConfiguration': {
                                'vectorSearchConfiguration': {
                                    'numberOfResults': top_k
                                }
                            }
                        }
                    }
                )

                # Get response text
                output = response.get('output', {})
                full_response = output.get('text', '')

                # Extract citations
                citations_data = response.get('citations', [])
                for citation in citations_data:
                    retrieved_refs = citation.get('retrievedReferences', [])
                    for ref in retrieved_refs:
                        location = ref.get('location', {})
                        s3_location = location.get('s3Location', {})
                        citations.append({
                            'text': ref.get('content', {}).get('text', ''),
                            'source': s3_location.get('uri', ''),
                            'score': ref.get('metadata', {}).get('score', 0)
                        })

                # Stream response in chunks (simulate streaming for now)
                chunk_size = 10  # words per chunk
                words = full_response.split()

                for i in range(0, len(words), chunk_size):
                    chunk = ' '.join(words[i:i + chunk_size])
                    if i + chunk_size < len(words):
                        chunk += ' '

                    self._send_message(connection_id, {
                        'type': 'chat.chunk',
                        'content': chunk,
                        'sessionId': session_id
                    })

                # Send citations
                if citations:
                    self._send_message(connection_id, {
                        'type': 'chat.citations',
                        'citations': citations,
                        'sessionId': session_id
                    })

                # Send completion
                self._send_message(connection_id, {
                    'type': 'chat.complete',
                    'sessionId': session_id,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'totalTokens': len(full_response.split())
                })

                # Store in chat history
                self._save_to_history(session_id, question, full_response, citations)

                log.info("chat_completed", response_length=len(full_response))
                return {"statusCode": 200}

            except Exception as e:
                log.error("bedrock_query_failed", error=str(e), error_type=type(e).__name__)
                self._send_error(connection_id, f"Query failed: {str(e)}")
                return {"statusCode": 500}

        except Exception as e:
            log.error("chat_handling_failed", error=str(e))
            self._send_error(connection_id, "Internal server error")
            return {"statusCode": 500}

    def _send_message(self, connection_id: str, data: Dict[str, Any]):
        """Send message to WebSocket connection."""
        if not self.apigw_management:
            logger.error("apigw_management_not_initialized")
            return

        try:
            self.apigw_management.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(data).encode('utf-8')
            )
        except self.apigw_management.exceptions.GoneException:
            logger.warning("connection_gone", connection_id=connection_id)
            # Connection is gone, clean up
            if self.connections_table:
                try:
                    self.connections_table.delete_item(Key={'connectionId': connection_id})
                except Exception:
                    pass
        except Exception as e:
            logger.error("send_message_failed", connection_id=connection_id, error=str(e))

    def _send_error(self, connection_id: str, error_message: str):
        """Send error message to WebSocket connection."""
        self._send_message(connection_id, {
            'type': 'error',
            'error': error_message,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    def _save_to_history(self, session_id: str, question: str, answer: str, citations: list):
        """Save chat exchange to DynamoDB."""
        try:
            timestamp = datetime.utcnow().isoformat() + 'Z'

            self.chat_history_table.put_item(
                Item={
                    'sessionId': session_id,
                    'timestamp': timestamp,
                    'question': question,
                    'answer': answer,
                    'citations': citations,
                    'messageType': 'chat',
                    'ttl': int(datetime.utcnow().timestamp()) + (7 * 24 * 60 * 60)  # 7 days
                }
            )
        except Exception as e:
            logger.error("history_save_failed", error=str(e))


# Global handler instance
_handler_instance = None


def get_handler() -> WebSocketHandler:
    """Get or create handler instance."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = WebSocketHandler()
    return _handler_instance


def handler(event, context):
    """
    Lambda entry point for WebSocket events.
    """
    request_id = context.aws_request_id if context else "local"
    connection_id = event.get('requestContext', {}).get('connectionId', 'unknown')
    route_key = event.get('requestContext', {}).get('routeKey', 'unknown')
    domain_name = event.get('requestContext', {}).get('domainName', '')
    stage = event.get('requestContext', {}).get('stage', 'dev')

    logger.info("websocket_request",
                connection_id=connection_id,
                route_key=route_key,
                request_id=request_id)

    try:
        ws_handler = get_handler()

        # Initialize management API
        if domain_name:
            ws_handler.initialize_management_api(domain_name, stage)

        # Route to appropriate handler
        if route_key == '$connect':
            return ws_handler.handle_connect(connection_id, event)

        elif route_key == '$disconnect':
            return ws_handler.handle_disconnect(connection_id)

        elif route_key == 'chat':
            # Parse message body
            body = event.get('body', '{}')
            try:
                message = json.loads(body) if isinstance(body, str) else body
            except json.JSONDecodeError:
                logger.error("invalid_json", body=body[:100])
                return {"statusCode": 400}

            return ws_handler.handle_chat(connection_id, message)

        else:
            logger.warning("unknown_route", route_key=route_key)
            return {"statusCode": 400}

    except Exception as e:
        logger.error("handler_failed",
                    error=str(e),
                    traceback=traceback.format_exc(),
                    connection_id=connection_id)
        return {"statusCode": 500}
