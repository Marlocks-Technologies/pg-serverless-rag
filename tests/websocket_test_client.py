#!/usr/bin/env python3
"""
WebSocket Test Client for RAG Platform

Tests the WebSocket streaming chat functionality by connecting to the
WebSocket API Gateway endpoint and sending chat queries.

Usage:
    python websocket_test_client.py [--endpoint ENDPOINT]

Environment Variables:
    WS_ENDPOINT: WebSocket endpoint URL (overridden by --endpoint flag)
"""

import asyncio
import json
import sys
import argparse
from datetime import datetime
from typing import Optional

try:
    import websockets
except ImportError:
    print("Error: websockets library not installed")
    print("Install with: pip install websockets")
    sys.exit(1)


class WebSocketTestClient:
    """Test client for RAG platform WebSocket API."""

    def __init__(self, endpoint: str):
        """Initialize the test client.

        Args:
            endpoint: WebSocket endpoint URL (e.g., wss://example.execute-api.region.amazonaws.com/dev)
        """
        self.endpoint = endpoint
        self.connection_id: Optional[str] = None
        self.session_id: Optional[str] = None

    async def connect(self) -> websockets.WebSocketClientProtocol:
        """Establish WebSocket connection.

        Returns:
            WebSocket connection object
        """
        print(f"Connecting to {self.endpoint}...")
        ws = await websockets.connect(self.endpoint)
        print("✓ Connected successfully")
        return ws

    async def send_chat_message(self, ws: websockets.WebSocketClientProtocol,
                                 question: str, session_id: Optional[str] = None,
                                 top_k: int = 5) -> None:
        """Send a chat message and receive streaming response.

        Args:
            ws: WebSocket connection
            question: User question to ask
            session_id: Optional session ID for conversation continuity
            top_k: Number of top documents to retrieve
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = f"test-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        self.session_id = session_id

        # Prepare chat message
        message = {
            "action": "chat",
            "question": question,
            "sessionId": session_id,
            "topK": top_k
        }

        print(f"\n{'='*80}")
        print(f"Question: {question}")
        print(f"Session ID: {session_id}")
        print(f"{'='*80}\n")

        # Send message
        await ws.send(json.dumps(message))
        print("Message sent. Waiting for response...\n")

        # Receive streaming response
        response_text = ""
        citations = []
        start_time = datetime.now()
        chunk_count = 0

        try:
            async for raw_message in ws:
                chunk_count += 1
                msg = json.loads(raw_message)
                msg_type = msg.get('type')

                if msg_type == 'chat.start':
                    print("→ Chat started")
                    print(f"  Session: {msg.get('sessionId')}")
                    print(f"  Time: {msg.get('timestamp')}\n")

                elif msg_type == 'chat.chunk':
                    # Print chunk inline
                    content = msg.get('content', '')
                    response_text += content
                    print(content, end='', flush=True)

                elif msg_type == 'chat.citations':
                    citations = msg.get('citations', [])
                    print("\n\n→ Citations received:")
                    for i, citation in enumerate(citations, 1):
                        print(f"  [{i}] {citation.get('title', 'Unknown')} "
                              f"(Score: {citation.get('score', 0):.4f})")
                        if citation.get('text'):
                            preview = citation['text'][:100]
                            print(f"      {preview}...")

                elif msg_type == 'chat.complete':
                    elapsed = (datetime.now() - start_time).total_seconds()
                    print("\n\n→ Chat completed")
                    print(f"  Session: {msg.get('sessionId')}")
                    print(f"  Time: {msg.get('timestamp')}")
                    print(f"  Elapsed: {elapsed:.2f}s")
                    print(f"  Chunks: {chunk_count}")
                    print(f"  Response length: {len(response_text)} chars")
                    break

                elif msg_type == 'error':
                    print(f"\n✗ Error: {msg.get('message')}")
                    if msg.get('details'):
                        print(f"  Details: {msg.get('details')}")
                    break

                else:
                    print(f"\n→ Unknown message type: {msg_type}")
                    print(f"  Data: {json.dumps(msg, indent=2)}")

        except websockets.exceptions.ConnectionClosed:
            print("\n✗ Connection closed unexpectedly")
        except Exception as e:
            print(f"\n✗ Error receiving response: {e}")

    async def run_test_session(self):
        """Run a complete test session with multiple queries."""
        print("="*80)
        print("WebSocket Test Client - RAG Platform")
        print("="*80)

        try:
            async with await self.connect() as ws:
                # Test 1: Simple greeting
                await self.send_chat_message(
                    ws,
                    "Hello! Can you help me understand what documents are available?"
                )

                await asyncio.sleep(1)

                # Test 2: Document query (if Knowledge Base has documents)
                await self.send_chat_message(
                    ws,
                    "What information do you have about AWS services?",
                    session_id=self.session_id
                )

                await asyncio.sleep(1)

                # Test 3: Follow-up question
                await self.send_chat_message(
                    ws,
                    "Can you summarize the key points?",
                    session_id=self.session_id
                )

                print("\n" + "="*80)
                print("Test session completed successfully!")
                print("="*80)

        except Exception as e:
            print(f"\n✗ Test session failed: {e}")
            import traceback
            traceback.print_exc()


async def test_single_query(endpoint: str, question: str):
    """Test a single query without a full session.

    Args:
        endpoint: WebSocket endpoint URL
        question: Question to ask
    """
    client = WebSocketTestClient(endpoint)
    async with await client.connect() as ws:
        await client.send_chat_message(ws, question)


def main():
    """Main entry point for the test client."""
    parser = argparse.ArgumentParser(
        description="WebSocket Test Client for RAG Platform"
    )
    parser.add_argument(
        '--endpoint',
        help='WebSocket endpoint URL',
        default='wss://t4muis95q7.execute-api.eu-west-1.amazonaws.com/dev'
    )
    parser.add_argument(
        '--question',
        help='Single question to test (skips full test session)',
        default=None
    )

    args = parser.parse_args()

    if args.question:
        # Single query mode
        asyncio.run(test_single_query(args.endpoint, args.question))
    else:
        # Full test session
        client = WebSocketTestClient(args.endpoint)
        asyncio.run(client.run_test_session())


if __name__ == '__main__':
    main()
