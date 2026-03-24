#!/usr/bin/env python3
"""
End-to-end WebSocket tests for Phase 4.

Tests WebSocket connections, streaming responses, and multi-turn conversations.
"""

import asyncio
import json
import os
import websockets
from typing import List, Dict, Any


# Configuration
API_ENDPOINT = os.getenv('WEBSOCKET_ENDPOINT', 'wss://example.execute-api.us-east-1.amazonaws.com/dev')


async def test_websocket_connection():
    """Test WebSocket connection establishment."""
    print("Testing WebSocket connection...")

    try:
        async with websockets.connect(API_ENDPOINT) as websocket:
            print("  ✓ Connected to WebSocket")

            # Wait a moment
            await asyncio.sleep(0.5)

            print("  ✓ Connection stable")
            return True

    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return False


async def test_websocket_chat():
    """Test WebSocket chat message."""
    print("\nTesting WebSocket chat...")

    try:
        async with websockets.connect(API_ENDPOINT) as websocket:
            # Send chat message
            message = {
                "action": "chat",
                "sessionId": "test-session-123",
                "message": "What is RAG architecture?",
                "topK": 5
            }

            await websocket.send(json.dumps(message))
            print(f"  → Sent: {message['message']}")

            # Collect response events
            events = []
            response_text = ""

            # Receive events (timeout after 10 seconds)
            try:
                async with asyncio.timeout(10):
                    while True:
                        response = await websocket.recv()
                        event = json.loads(response)
                        events.append(event)

                        print(f"  ← Event: {event['type']}")

                        # Collect text chunks
                        if event['type'] == 'chat.chunk':
                            response_text += event['content']

                        # Check for completion
                        if event['type'] == 'chat.complete':
                            break

            except asyncio.TimeoutError:
                print("  ⚠ Timeout waiting for completion")

            # Verify response
            assert len(events) > 0, "No events received"
            assert any(e['type'] == 'chat.start' for e in events), "No start event"
            assert any(e['type'] == 'chat.complete' for e in events), "No complete event"
            assert len(response_text) > 0, "No response text"

            print(f"  ✓ Received {len(events)} events")
            print(f"  ✓ Response length: {len(response_text)} chars")

            # Check for citations
            citation_events = [e for e in events if e['type'] == 'chat.citations']
            if citation_events:
                citations = citation_events[0]['citations']
                print(f"  ✓ Citations: {len(citations)}")

            return True

    except Exception as e:
        print(f"  ✗ Chat failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multi_turn_conversation():
    """Test multi-turn conversation via WebSocket."""
    print("\nTesting multi-turn conversation...")

    try:
        async with websockets.connect(API_ENDPOINT) as websocket:
            session_id = "multi-turn-test-456"

            # Turn 1
            message1 = {
                "action": "chat",
                "sessionId": session_id,
                "message": "What is RAG?",
                "topK": 3
            }

            await websocket.send(json.dumps(message1))
            print(f"  Turn 1 → {message1['message']}")

            # Collect turn 1 response
            response1 = await collect_response(websocket)
            print(f"  Turn 1 ← {len(response1)} chars")

            # Turn 2 (follow-up question)
            message2 = {
                "action": "chat",
                "sessionId": session_id,
                "message": "Can you explain more about the retrieval component?",
                "topK": 3
            }

            await websocket.send(json.dumps(message2))
            print(f"  Turn 2 → {message2['message']}")

            # Collect turn 2 response
            response2 = await collect_response(websocket)
            print(f"  Turn 2 ← {len(response2)} chars")

            # Turn 3 (contextual follow-up)
            message3 = {
                "action": "chat",
                "sessionId": session_id,
                "message": "What about the generation part?",
                "topK": 3
            }

            await websocket.send(json.dumps(message3))
            print(f"  Turn 3 → {message3['message']}")

            # Collect turn 3 response
            response3 = await collect_response(websocket)
            print(f"  Turn 3 ← {len(response3)} chars")

            # Verify all responses
            assert len(response1) > 0, "Turn 1 response empty"
            assert len(response2) > 0, "Turn 2 response empty"
            assert len(response3) > 0, "Turn 3 response empty"

            print("  ✓ Multi-turn conversation successful")
            return True

    except Exception as e:
        print(f"  ✗ Multi-turn conversation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def collect_response(websocket, timeout: int = 10) -> str:
    """Collect streaming response from WebSocket."""
    response_text = ""

    try:
        async with asyncio.timeout(timeout):
            while True:
                response = await websocket.recv()
                event = json.loads(response)

                if event['type'] == 'chat.chunk':
                    response_text += event['content']

                elif event['type'] == 'chat.complete':
                    break

    except asyncio.TimeoutError:
        pass

    return response_text


async def test_concurrent_connections():
    """Test multiple concurrent WebSocket connections."""
    print("\nTesting concurrent connections...")

    async def send_message(connection_id: int):
        """Send a message from a connection."""
        try:
            async with websockets.connect(API_ENDPOINT) as websocket:
                message = {
                    "action": "chat",
                    "sessionId": f"concurrent-{connection_id}",
                    "message": f"Test message {connection_id}",
                    "topK": 3
                }

                await websocket.send(json.dumps(message))

                # Wait for response
                response_text = await collect_response(websocket)

                print(f"  Connection {connection_id}: ✓ ({len(response_text)} chars)")
                return True

        except Exception as e:
            print(f"  Connection {connection_id}: ✗ {e}")
            return False

    # Create 5 concurrent connections
    tasks = [send_message(i) for i in range(5)]
    results = await asyncio.gather(*tasks)

    success_count = sum(results)
    print(f"  ✓ {success_count}/5 concurrent connections successful")

    return success_count >= 4  # Allow 1 failure


async def run_all_tests():
    """Run all WebSocket E2E tests."""
    print("=" * 80)
    print("Phase 4 WebSocket End-to-End Tests")
    print("=" * 80)
    print(f"\nWebSocket Endpoint: {API_ENDPOINT}")
    print()

    tests = [
        ("WebSocket Connection", test_websocket_connection),
        ("WebSocket Chat", test_websocket_chat),
        ("Multi-turn Conversation", test_multi_turn_conversation),
        ("Concurrent Connections", test_concurrent_connections),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            print("\n" + "-" * 80)
            result = await test_func()
            if result:
                passed += 1
                print(f"\n✓ {test_name} PASSED")
            else:
                failed += 1
                print(f"\n✗ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"\n✗ {test_name} ERROR: {e}")

    print("\n" + "=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == '__main__':
    if not API_ENDPOINT or API_ENDPOINT == 'wss://example.execute-api.us-east-1.amazonaws.com/dev':
        print("ERROR: WEBSOCKET_ENDPOINT environment variable not set")
        print("Usage: WEBSOCKET_ENDPOINT=wss://your-api.execute-api.region.amazonaws.com/dev ./test_websocket_e2e.py")
        exit(1)

    # Run tests
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
