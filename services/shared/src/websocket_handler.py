"""
WebSocket Handler - Manages WebSocket connections and routing.

Handles $connect, $disconnect, and custom routes for WebSocket API.
"""

import json
from typing import Dict, Any, Optional, Callable
from shared.logger import get_logger

logger = get_logger(__name__)


class WebSocketConnection:
    """Represents a WebSocket connection."""

    def __init__(self, connection_id: str, domain_name: str, stage: str):
        """
        Initialize connection.

        Args:
            connection_id: WebSocket connection ID
            domain_name: API Gateway domain
            stage: API stage name
        """
        self.connection_id = connection_id
        self.domain_name = domain_name
        self.stage = stage
        self.endpoint_url = f"https://{domain_name}/{stage}"

    @classmethod
    def from_request_context(cls, request_context: Dict[str, Any]) -> 'WebSocketConnection':
        """
        Create connection from request context.

        Args:
            request_context: API Gateway request context

        Returns:
            WebSocketConnection instance
        """
        return cls(
            connection_id=request_context['connectionId'],
            domain_name=request_context['domainName'],
            stage=request_context['stage']
        )


class WebSocketRouter:
    """Routes WebSocket events to handlers."""

    def __init__(self):
        """Initialize router."""
        self.routes = {}
        self.connect_handler = None
        self.disconnect_handler = None
        self.default_handler = None

    def route(self, route_key: str) -> Callable:
        """
        Decorator to register route handler.

        Args:
            route_key: Route key to handle

        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            self.routes[route_key] = func
            return func
        return decorator

    def on_connect(self) -> Callable:
        """Decorator to register connect handler."""
        def decorator(func: Callable) -> Callable:
            self.connect_handler = func
            return func
        return decorator

    def on_disconnect(self) -> Callable:
        """Decorator to register disconnect handler."""
        def decorator(func: Callable) -> Callable:
            self.disconnect_handler = func
            return func
        return decorator

    def on_default(self) -> Callable:
        """Decorator to register default handler."""
        def decorator(func: Callable) -> Callable:
            self.default_handler = func
            return func
        return decorator

    def handle_event(
        self,
        event: Dict[str, Any],
        context: Any
    ) -> Dict[str, Any]:
        """
        Route event to appropriate handler.

        Args:
            event: WebSocket event
            context: Lambda context

        Returns:
            Response dictionary
        """
        request_context = event.get('requestContext', {})
        route_key = request_context.get('routeKey', '$default')
        connection_id = request_context.get('connectionId')

        logger.info(
            "websocket_event",
            route_key=route_key,
            connection_id=connection_id
        )

        try:
            # Handle special routes
            if route_key == '$connect':
                if self.connect_handler:
                    return self.connect_handler(event, context)
                return {'statusCode': 200}

            elif route_key == '$disconnect':
                if self.disconnect_handler:
                    return self.disconnect_handler(event, context)
                return {'statusCode': 200}

            # Handle custom routes
            elif route_key in self.routes:
                return self.routes[route_key](event, context)

            # Handle default
            elif self.default_handler:
                return self.default_handler(event, context)

            else:
                logger.warning("no_handler_for_route", route_key=route_key)
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': f'No handler for route: {route_key}'})
                }

        except Exception as e:
            logger.error(
                "websocket_handler_error",
                error=str(e),
                route_key=route_key,
                connection_id=connection_id
            )
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Internal server error'})
            }


class WebSocketMessage:
    """Represents a WebSocket message."""

    def __init__(self, raw_body: str):
        """
        Initialize message.

        Args:
            raw_body: Raw message body (JSON string)
        """
        self.raw_body = raw_body
        self.data = self._parse_body(raw_body)

    def _parse_body(self, body: str) -> Dict[str, Any]:
        """Parse JSON body."""
        try:
            return json.loads(body) if body else {}
        except json.JSONDecodeError:
            logger.warning("invalid_json_body", body=body)
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from message data."""
        return self.data.get(key, default)

    def get_action(self) -> Optional[str]:
        """Get action from message."""
        return self.data.get('action')

    def get_session_id(self) -> Optional[str]:
        """Get session ID from message."""
        return self.data.get('sessionId')

    def get_message(self) -> Optional[str]:
        """Get message content."""
        return self.data.get('message')

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.data


def create_response(
    status_code: int = 200,
    body: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create WebSocket response.

    Args:
        status_code: HTTP status code
        body: Optional response body

    Returns:
        Response dictionary
    """
    response = {'statusCode': status_code}

    if body:
        response['body'] = json.dumps(body)

    return response


def create_error_response(
    error_message: str,
    status_code: int = 400
) -> Dict[str, Any]:
    """
    Create error response.

    Args:
        error_message: Error message
        status_code: HTTP status code

    Returns:
        Error response dictionary
    """
    return create_response(
        status_code=status_code,
        body={'error': error_message}
    )


class ConnectionManager:
    """Manages WebSocket connection state."""

    def __init__(self):
        """Initialize connection manager."""
        self.connections = {}

    def add_connection(
        self,
        connection: WebSocketConnection,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add a connection.

        Args:
            connection: WebSocket connection
            metadata: Optional connection metadata
        """
        self.connections[connection.connection_id] = {
            'connection': connection,
            'metadata': metadata or {}
        }

    def remove_connection(self, connection_id: str):
        """Remove a connection."""
        self.connections.pop(connection_id, None)

    def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """Get connection by ID."""
        conn_data = self.connections.get(connection_id)
        if conn_data:
            return conn_data['connection']
        return None

    def get_metadata(self, connection_id: str) -> Dict[str, Any]:
        """Get connection metadata."""
        conn_data = self.connections.get(connection_id)
        if conn_data:
            return conn_data['metadata']
        return {}

    def update_metadata(
        self,
        connection_id: str,
        metadata: Dict[str, Any]
    ):
        """Update connection metadata."""
        if connection_id in self.connections:
            self.connections[connection_id]['metadata'].update(metadata)

    def list_connections(self) -> list[str]:
        """List all connection IDs."""
        return list(self.connections.keys())

    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.connections)


# Global connection manager instance
_connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get global connection manager instance."""
    return _connection_manager
