"""
Integration tests for Phase 4: WebSocket, conversation history, and streaming.
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

# Add shared library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared/src'))

from conversation_history import ConversationHistory
from streaming_handler import StreamingHandler, StreamingResponseBuilder
from websocket_handler import (
    WebSocketConnection,
    WebSocketRouter,
    WebSocketMessage,
    create_response
)


# Conversation History Tests

@patch('conversation_history.boto3')
def test_conversation_history_save_message(mock_boto3):
    """Test saving a message to conversation history."""
    # Mock DynamoDB
    mock_table = Mock()
    mock_dynamodb = Mock()
    mock_dynamodb.Table.return_value = mock_table
    mock_boto3.resource.return_value = mock_dynamodb

    history = ConversationHistory(table_name='test-table')

    # Save message
    result = history.save_message(
        session_id='session-123',
        role='user',
        content='What is RAG?'
    )

    # Verify put_item was called
    mock_table.put_item.assert_called_once()

    # Verify item structure
    call_args = mock_table.put_item.call_args
    item = call_args[1]['Item']

    assert item['SessionId'] == 'session-123'
    assert item['Role'] == 'user'
    assert item['Content'] == 'What is RAG?'
    assert 'Timestamp' in item
    assert 'TTL' in item


@patch('conversation_history.boto3')
def test_conversation_history_get_conversation(mock_boto3):
    """Test retrieving conversation history."""
    # Mock DynamoDB response
    mock_table = Mock()
    mock_table.query.return_value = {
        'Items': [
            {
                'SessionId': 'session-123',
                'Timestamp': '2024-01-01T12:00:00Z',
                'Role': 'user',
                'Content': 'Hello'
            },
            {
                'SessionId': 'session-123',
                'Timestamp': '2024-01-01T12:00:01Z',
                'Role': 'assistant',
                'Content': 'Hi there!'
            }
        ]
    }

    mock_dynamodb = Mock()
    mock_dynamodb.Table.return_value = mock_table
    mock_boto3.resource.return_value = mock_dynamodb

    history = ConversationHistory(table_name='test-table')

    # Get conversation
    messages = history.get_conversation('session-123')

    # Verify query was called
    mock_table.query.assert_called_once()

    # Verify messages
    assert len(messages) == 2
    assert messages[0]['Role'] == 'user'
    assert messages[1]['Role'] == 'assistant'


@patch('conversation_history.boto3')
def test_conversation_history_recent_context(mock_boto3):
    """Test getting recent context for RAG."""
    # Mock DynamoDB response
    mock_table = Mock()
    mock_table.query.return_value = {
        'Items': [
            {
                'SessionId': 'session-123',
                'Timestamp': '2024-01-01T12:00:00Z',
                'Role': 'user',
                'Content': 'What is RAG?'
            },
            {
                'SessionId': 'session-123',
                'Timestamp': '2024-01-01T12:00:01Z',
                'Role': 'assistant',
                'Content': 'RAG stands for...'
            }
        ]
    }

    mock_dynamodb = Mock()
    mock_dynamodb.Table.return_value = mock_table
    mock_boto3.resource.return_value = mock_dynamodb

    history = ConversationHistory(table_name='test-table')

    # Get recent context
    context = history.get_recent_context('session-123', max_turns=5)

    # Verify format
    assert len(context) == 2
    assert context[0]['role'] == 'user'
    assert context[0]['content'] == 'What is RAG?'
    assert context[1]['role'] == 'assistant'


def test_conversation_history_decimal_conversion():
    """Test Decimal to float conversion."""
    history = ConversationHistory(table_name='test-table')

    # Test float to Decimal
    obj = {'score': 0.95, 'nested': {'value': 0.85}}
    converted = history._convert_floats_to_decimal(obj)

    assert isinstance(converted['score'], Decimal)
    assert isinstance(converted['nested']['value'], Decimal)

    # Test Decimal to float
    obj = {'score': Decimal('0.95')}
    converted = history._convert_decimal_to_float(obj)

    assert isinstance(converted['score'], float)
    assert converted['score'] == 0.95


# Streaming Handler Tests

@patch('streaming_handler.boto3')
def test_streaming_handler_send_message(mock_boto3):
    """Test sending a message via WebSocket."""
    # Mock API Gateway Management API
    mock_client = Mock()
    mock_boto3.client.return_value = mock_client

    handler = StreamingHandler(
        endpoint_url='https://test.execute-api.us-east-1.amazonaws.com/dev'
    )

    # Send message
    success = handler.send_message(
        connection_id='conn-123',
        message={'type': 'chat.start'}
    )

    # Verify post_to_connection was called
    mock_client.post_to_connection.assert_called_once()

    call_args = mock_client.post_to_connection.call_args
    assert call_args[1]['ConnectionId'] == 'conn-123'
    assert success is True


@patch('streaming_handler.boto3')
def test_streaming_handler_gone_connection(mock_boto3):
    """Test handling gone connection."""
    # Mock API Gateway Management API with GoneException
    mock_client = Mock()
    mock_client.post_to_connection.side_effect = \
        mock_client.exceptions.GoneException({}, 'Gone')
    mock_client.exceptions.GoneException = type('GoneException', (Exception,), {})
    mock_boto3.client.return_value = mock_client

    handler = StreamingHandler(
        endpoint_url='https://test.execute-api.us-east-1.amazonaws.com/dev'
    )

    # Send message to gone connection
    success = handler.send_message(
        connection_id='conn-gone',
        message={'type': 'test'}
    )

    # Should return False
    assert success is False


def test_streaming_response_builder():
    """Test streaming response builder."""
    builder = StreamingResponseBuilder()

    # Build response
    builder.add_start({'metadata': 'test'})
    builder.add_chunk('Hello ')
    builder.add_chunk('world!')
    builder.add_citations([{'source': 'doc1.pdf'}])
    builder.add_complete('Hello world!')

    events = builder.build()

    # Verify events
    assert len(events) == 5
    assert events[0]['type'] == 'chat.start'
    assert events[1]['type'] == 'chat.chunk'
    assert events[1]['content'] == 'Hello '
    assert events[2]['type'] == 'chat.chunk'
    assert events[3]['type'] == 'chat.citations'
    assert events[4]['type'] == 'chat.complete'


# WebSocket Handler Tests

def test_websocket_connection_from_context():
    """Test creating WebSocket connection from request context."""
    request_context = {
        'connectionId': 'conn-123',
        'domainName': 'test.execute-api.us-east-1.amazonaws.com',
        'stage': 'dev'
    }

    connection = WebSocketConnection.from_request_context(request_context)

    assert connection.connection_id == 'conn-123'
    assert connection.domain_name == 'test.execute-api.us-east-1.amazonaws.com'
    assert connection.stage == 'dev'
    assert connection.endpoint_url == 'https://test.execute-api.us-east-1.amazonaws.com/dev'


def test_websocket_message_parsing():
    """Test WebSocket message parsing."""
    # Valid JSON
    message = WebSocketMessage('{"action": "chat", "message": "Hello"}')

    assert message.get_action() == 'chat'
    assert message.get_message() == 'Hello'

    # Invalid JSON
    message = WebSocketMessage('invalid json')

    assert message.get_action() is None
    assert message.data == {}


def test_websocket_router():
    """Test WebSocket router."""
    router = WebSocketRouter()

    # Register handlers
    @router.on_connect()
    def handle_connect(event, context):
        return {'statusCode': 200, 'body': 'connected'}

    @router.route('chat')
    def handle_chat(event, context):
        return {'statusCode': 200, 'body': 'chat'}

    # Test connect route
    event = {
        'requestContext': {
            'routeKey': '$connect',
            'connectionId': 'conn-123'
        }
    }

    response = router.handle_event(event, None)
    assert response['statusCode'] == 200
    assert response['body'] == 'connected'

    # Test custom route
    event = {
        'requestContext': {
            'routeKey': 'chat',
            'connectionId': 'conn-123'
        }
    }

    response = router.handle_event(event, None)
    assert response['statusCode'] == 200
    assert response['body'] == 'chat'


def test_create_response():
    """Test response creation helpers."""
    # Success response
    response = create_response(200, {'message': 'success'})

    assert response['statusCode'] == 200
    assert 'body' in response
    body = json.loads(response['body'])
    assert body['message'] == 'success'

    # Response without body
    response = create_response(200)

    assert response['statusCode'] == 200
    assert 'body' not in response


# Multi-turn Conversation Tests

@patch('conversation_history.boto3')
def test_multi_turn_conversation(mock_boto3):
    """Test multi-turn conversation flow."""
    mock_table = Mock()

    # Simulate existing conversation
    mock_table.query.return_value = {
        'Items': [
            {
                'SessionId': 'session-123',
                'Timestamp': '2024-01-01T12:00:00Z',
                'Role': 'user',
                'Content': 'What is RAG?'
            },
            {
                'SessionId': 'session-123',
                'Timestamp': '2024-01-01T12:00:01Z',
                'Role': 'assistant',
                'Content': 'RAG is Retrieval Augmented Generation.'
            }
        ]
    }

    mock_dynamodb = Mock()
    mock_dynamodb.Table.return_value = mock_table
    mock_boto3.resource.return_value = mock_dynamodb

    history = ConversationHistory(table_name='test-table')

    # Get context
    context = history.get_recent_context('session-123')

    assert len(context) == 2
    assert context[0]['role'] == 'user'
    assert context[1]['role'] == 'assistant'

    # Add new turn
    history.save_message('session-123', 'user', 'Can you explain more?')
    history.save_message('session-123', 'assistant', 'Sure, RAG combines...')

    # Verify save was called
    assert mock_table.put_item.call_count == 2


@patch('conversation_history.boto3')
def test_conversation_with_metadata(mock_boto3):
    """Test saving message with metadata."""
    mock_table = Mock()
    mock_dynamodb = Mock()
    mock_dynamodb.Table.return_value = mock_table
    mock_boto3.resource.return_value = mock_dynamodb

    history = ConversationHistory(table_name='test-table')

    # Save with metadata
    history.save_message(
        session_id='session-123',
        role='assistant',
        content='Answer text',
        metadata={
            'citations': [{'source': 'doc1.pdf', 'score': 0.95}],
            'chunks_retrieved': 5
        }
    )

    # Verify metadata was saved
    call_args = mock_table.put_item.call_args
    item = call_args[1]['Item']

    assert 'Metadata' in item
    assert 'citations' in item['Metadata']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
