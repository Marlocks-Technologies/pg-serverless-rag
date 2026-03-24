"""
ChatHandlerLambda - Phase 4: Complete backend API with WebSocket streaming and conversation history.

Handles:
- REST API for chat queries
- WebSocket API for streaming responses
- Conversation history in DynamoDB
- Multi-turn context management
- Session state management
"""

import json
import os
import sys
from typing import Dict, Any, Optional

# Add Lambda layer path
sys.path.insert(0, '/opt/python')

import boto3
from rag_engine import RAGEngine
from conversation_history import ConversationHistory
from streaming_handler import StreamingHandler
from websocket_handler import (
    WebSocketRouter,
    WebSocketConnection,
    WebSocketMessage,
    create_response,
    create_error_response
)
from logger import get_logger

logger = get_logger(__name__)


class ChatHandler:
    """Main chat handler with RAG, history, and streaming capabilities."""

    def __init__(self):
        """Initialize chat handler with all Phase 4 components."""
        # Get configuration from environment
        self.vectors_bucket = os.environ['VECTORS_BUCKET']
        self.embedding_model_id = os.environ['EMBEDDING_MODEL_ID']
        self.generation_model_id = os.environ['GENERATION_MODEL_ID']
        self.region = os.environ.get('AWS_REGION', 'us-east-1')
        self.chat_history_table = os.environ.get('CHAT_HISTORY_TABLE')

        # Initialize RAG engine
        self.rag_engine = RAGEngine(
            vectors_bucket=self.vectors_bucket,
            embedding_model_id=self.embedding_model_id,
            generation_model_id=self.generation_model_id,
            region=self.region
        )

        # Initialize conversation history
        self.history = ConversationHistory(
            table_name=self.chat_history_table,
            region=self.region
        )

    def handle_query_with_history(
        self,
        question: str,
        session_id: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        use_history: bool = True
    ) -> Dict[str, Any]:
        """
        Handle a chat query with conversation history.

        Args:
            question: User's question
            session_id: Session identifier
            filters: Optional metadata filters
            top_k: Number of chunks to retrieve
            use_history: Whether to use conversation history

        Returns:
            Response dict with answer and citations
        """
        log = logger.bind(
            session_id=session_id,
            question_length=len(question)
        )

        log.info("processing_query_with_history")

        try:
            # Load conversation history
            conversation_context = []
            if use_history:
                conversation_context = self.history.get_recent_context(
                    session_id=session_id,
                    max_turns=5
                )
                log.info("loaded_history", turns=len(conversation_context) // 2)

            # Execute RAG query with conversation context
            result = self.rag_engine.conversational_query(
                question=question,
                conversation_history=conversation_context,
                filters=filters,
                top_k=top_k
            )

            # Save user message to history
            self.history.save_message(
                session_id=session_id,
                role='user',
                content=question
            )

            # Save assistant response to history
            self.history.save_message(
                session_id=session_id,
                role='assistant',
                content=result['answer'],
                metadata={
                    'citations': result.get('citations', []),
                    'chunks_retrieved': result['metadata']['chunks_retrieved']
                }
            )

            log.info(
                "query_completed",
                chunks_retrieved=result['metadata']['chunks_retrieved']
            )

            return {
                'success': True,
                'sessionId': session_id,
                'answer': result['answer'],
                'citations': result.get('citations', []),
                'metadata': result['metadata']
            }

        except Exception as e:
            log.error("query_failed", error=str(e))
            raise

    def handle_streaming_query(
        self,
        question: str,
        session_id: str,
        connection_id: str,
        streaming_handler: StreamingHandler,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> bool:
        """
        Handle a streaming query via WebSocket.

        Args:
            question: User's question
            session_id: Session identifier
            connection_id: WebSocket connection ID
            streaming_handler: Streaming handler instance
            filters: Optional metadata filters
            top_k: Number of chunks to retrieve

        Returns:
            True if successful
        """
        log = logger.bind(
            session_id=session_id,
            connection_id=connection_id
        )

        log.info("processing_streaming_query")

        try:
            # Load conversation history
            conversation_context = self.history.get_recent_context(
                session_id=session_id,
                max_turns=5
            )

            # Execute RAG query with streaming
            result = self.rag_engine.conversational_query(
                question=question,
                conversation_history=conversation_context,
                filters=filters,
                top_k=top_k
            )

            # For now, we'll send the complete answer
            # In future, we can integrate with invoke_model_streaming
            streaming_handler.send_message(connection_id, {
                'type': 'chat.start',
                'sessionId': session_id
            })

            # Simulate streaming by chunking the answer
            answer = result['answer']
            chunk_size = 50
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i + chunk_size]
                streaming_handler.send_message(connection_id, {
                    'type': 'chat.chunk',
                    'content': chunk
                })

            # Send citations
            if result.get('citations'):
                streaming_handler.send_message(connection_id, {
                    'type': 'chat.citations',
                    'citations': result['citations']
                })

            # Send complete
            streaming_handler.send_message(connection_id, {
                'type': 'chat.complete',
                'sessionId': session_id
            })

            # Save to history
            self.history.save_message(
                session_id=session_id,
                role='user',
                content=question
            )

            self.history.save_message(
                session_id=session_id,
                role='assistant',
                content=answer,
                metadata={
                    'citations': result.get('citations', []),
                    'chunks_retrieved': result['metadata']['chunks_retrieved']
                }
            )

            log.info("streaming_query_completed")
            return True

        except Exception as e:
            log.error("streaming_query_failed", error=str(e))
            streaming_handler.send_message(connection_id, {
                'type': 'error',
                'message': str(e)
            })
            return False

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum messages to retrieve

        Returns:
            History data
        """
        messages = self.history.get_conversation(session_id, limit)

        return {
            'success': True,
            'sessionId': session_id,
            'messages': messages,
            'count': len(messages)
        }

    def search_documents(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """Search documents without generating an answer."""
        log = logger.bind(query_length=len(query))
        log.info("searching_documents")

        try:
            results = self.rag_engine.search_documents(
                query=query,
                filters=filters,
                top_k=top_k
            )

            log.info("search_completed", results_count=len(results))

            return {
                'success': True,
                'results': results,
                'count': len(results)
            }

        except Exception as e:
            log.error("search_failed", error=str(e))
            raise


# Global handler instance
_handler_instance = None


def get_handler() -> ChatHandler:
    """Get or create handler instance (singleton)."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = ChatHandler()
    return _handler_instance


def handler(event, context):
    """
    Lambda entry point - routes to REST or WebSocket handler.

    Handles both REST API Gateway and WebSocket API Gateway events.
    """
    request_id = context.aws_request_id if context else "local"

    # Detect event type
    if "requestContext" in event and "connectionId" in event.get("requestContext", {}):
        return _handle_websocket_event(event, context, request_id)
    else:
        return _handle_rest_event(event, context, request_id)


def _handle_rest_event(event, context, request_id):
    """Handle REST API Gateway events."""
    # Get handler instance
    try:
        chat_handler = get_handler()
    except Exception as e:
        logger.error("handler_initialization_failed", error=str(e))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Service initialization failed"})
        }

    # Route request
    path = event.get("path", "")
    method = event.get("httpMethod", "")

    logger.info("rest_request", path=path, method=method, request_id=request_id)

    try:
        # Health check endpoint
        if path == "/health" and method == "GET":
            return _handle_health(request_id)

        # Chat query endpoint
        elif path == "/chat/query" and method == "POST":
            return _handle_chat_query(event, context, chat_handler, request_id)

        # Document search endpoint
        elif path == "/chat/search" and method == "POST":
            return _handle_search(event, context, chat_handler, request_id)

        # Get chat history
        elif path.startswith("/chat/history/") and method == "GET":
            return _handle_get_history(event, context, chat_handler, request_id)

        # Delete session
        elif path.startswith("/chat/session/") and method == "DELETE":
            return _handle_delete_session(event, context, chat_handler, request_id)

        # Not found
        else:
            logger.warning("endpoint_not_found", path=path, method=method)
            return {
                "statusCode": 404,
                "headers": _cors_headers(),
                "body": json.dumps({"error": "Endpoint not found"})
            }

    except Exception as e:
        logger.error("rest_request_failed", error=str(e), path=path, method=method)
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Internal server error"})
        }


def _handle_websocket_event(event, context, request_id):
    """Handle WebSocket API Gateway events."""
    request_context = event.get('requestContext', {})
    route_key = request_context.get('routeKey', '$default')
    connection_id = request_context.get('connectionId')

    logger.info(
        "websocket_event",
        route_key=route_key,
        connection_id=connection_id,
        request_id=request_id
    )

    try:
        chat_handler = get_handler()

        # $connect - client connects
        if route_key == '$connect':
            logger.info("websocket_connected", connection_id=connection_id)
            return create_response(200)

        # $disconnect - client disconnects
        elif route_key == '$disconnect':
            logger.info("websocket_disconnected", connection_id=connection_id)
            return create_response(200)

        # chat - chat message
        elif route_key == 'chat':
            return _handle_websocket_chat(event, context, chat_handler, connection_id, request_id)

        # Unknown route
        else:
            logger.warning("unknown_websocket_route", route_key=route_key)
            return create_error_response("Unknown route", 400)

    except Exception as e:
        logger.error("websocket_event_failed", error=str(e), route_key=route_key)
        return create_response(500)


def _handle_websocket_chat(event, context, chat_handler, connection_id, request_id):
    """Handle WebSocket chat message."""
    try:
        # Parse message
        message = WebSocketMessage(event.get('body', '{}'))

        question = message.get_message()
        session_id = message.get_session_id() or f"ws-{connection_id}"
        filters = message.get('filters')
        top_k = message.get('topK', 5)

        # Validate
        if not question:
            return create_error_response("Missing message", 400)

        # Create streaming handler
        streaming_handler = StreamingHandler.create_from_request_context(
            event['requestContext']
        )

        # Process streaming query
        success = chat_handler.handle_streaming_query(
            question=question,
            session_id=session_id,
            connection_id=connection_id,
            streaming_handler=streaming_handler,
            filters=filters,
            top_k=top_k
        )

        return create_response(200 if success else 500)

    except Exception as e:
        logger.error("websocket_chat_failed", error=str(e), connection_id=connection_id)
        return create_response(500)


def _handle_health(request_id: str) -> Dict[str, Any]:
    """Handle health check."""
    return {
        "statusCode": 200,
        "headers": _cors_headers(),
        "body": json.dumps({
            "status": "healthy",
            "service": "chat-handler",
            "version": "0.4.0",
            "phase": "4",
            "features": ["rag", "search", "citations", "websocket", "history", "streaming"],
            "requestId": request_id
        })
    }


def _handle_chat_query(
    event: Dict[str, Any],
    context: Any,
    chat_handler: ChatHandler,
    request_id: str
) -> Dict[str, Any]:
    """Handle REST chat query request."""
    try:
        body = json.loads(event.get("body", "{}"))

        # Extract parameters
        question = body.get("question", "").strip()
        session_id = body.get("sessionId", f"session-{request_id}")
        filters = body.get("filters")
        top_k = body.get("topK", 5)
        use_history = body.get("useHistory", True)

        # Validate input
        if not question:
            return {
                "statusCode": 400,
                "headers": _cors_headers(),
                "body": json.dumps({"error": "Missing required field: question"})
            }

        if len(question) > 1000:
            return {
                "statusCode": 400,
                "headers": _cors_headers(),
                "body": json.dumps({"error": "Question too long (max 1000 characters)"})
            }

        # Process query with history
        result = chat_handler.handle_query_with_history(
            question=question,
            session_id=session_id,
            filters=filters,
            top_k=top_k,
            use_history=use_history
        )

        return {
            "statusCode": 200,
            "headers": _cors_headers(),
            "body": json.dumps({
                **result,
                "requestId": request_id
            })
        }

    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Invalid JSON in request body"})
        }
    except Exception as e:
        logger.error("query_handling_failed", error=str(e))
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Query processing failed"})
        }


def _handle_search(
    event: Dict[str, Any],
    context: Any,
    chat_handler: ChatHandler,
    request_id: str
) -> Dict[str, Any]:
    """Handle document search request."""
    try:
        body = json.loads(event.get("body", "{}"))

        # Extract parameters
        query = body.get("query", "").strip()
        filters = body.get("filters")
        top_k = body.get("topK", 10)

        # Validate input
        if not query:
            return {
                "statusCode": 400,
                "headers": _cors_headers(),
                "body": json.dumps({"error": "Missing required field: query"})
            }

        # Execute search
        result = chat_handler.search_documents(
            query=query,
            filters=filters,
            top_k=top_k
        )

        return {
            "statusCode": 200,
            "headers": _cors_headers(),
            "body": json.dumps({
                **result,
                "requestId": request_id
            })
        }

    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Invalid JSON in request body"})
        }
    except Exception as e:
        logger.error("search_handling_failed", error=str(e))
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Search failed"})
        }


def _handle_get_history(
    event: Dict[str, Any],
    context: Any,
    chat_handler: ChatHandler,
    request_id: str
) -> Dict[str, Any]:
    """Handle get chat history request."""
    try:
        session_id = event.get("path", "").split("/")[-1]

        logger.info("history_request", session_id=session_id)

        result = chat_handler.get_conversation_history(session_id=session_id)

        return {
            "statusCode": 200,
            "headers": _cors_headers(),
            "body": json.dumps({
                **result,
                "requestId": request_id
            })
        }

    except Exception as e:
        logger.error("get_history_failed", error=str(e))
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Failed to retrieve history"})
        }


def _handle_delete_session(
    event: Dict[str, Any],
    context: Any,
    chat_handler: ChatHandler,
    request_id: str
) -> Dict[str, Any]:
    """Handle delete session request."""
    try:
        session_id = event.get("path", "").split("/")[-1]

        logger.info("delete_session_request", session_id=session_id)

        count = chat_handler.history.delete_session(session_id)

        return {
            "statusCode": 200,
            "headers": _cors_headers(),
            "body": json.dumps({
                "success": True,
                "sessionId": session_id,
                "messagesDeleted": count,
                "requestId": request_id
            })
        }

    except Exception as e:
        logger.error("delete_session_failed", error=str(e))
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Failed to delete session"})
        }


def _cors_headers() -> Dict[str, str]:
    """Get CORS headers for API responses."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
