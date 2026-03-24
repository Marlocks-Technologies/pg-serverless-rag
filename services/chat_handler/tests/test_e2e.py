#!/usr/bin/env python3
"""
End-to-end test for Phase 3 RAG chat API.

Tests the complete flow from API request to RAG answer with citations.
"""

import requests
import json
import time
import os

# Configuration
PROJECT_NAME = os.getenv('PROJECT_NAME', 'rag-platform')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Get API endpoint from environment or use placeholder
API_ENDPOINT = os.getenv('API_ENDPOINT', 'https://api.example.com')


def test_health_check():
    """Test health check endpoint."""
    print("Testing health check endpoint...")

    response = requests.get(f"{API_ENDPOINT}/health")

    assert response.status_code == 200, f"Health check failed: {response.status_code}"

    data = response.json()
    assert data['status'] == 'healthy'
    assert data['service'] == 'chat-handler'
    assert data['phase'] == '3'

    print("✓ Health check passed")
    return True


def test_chat_query():
    """Test chat query endpoint."""
    print("\nTesting chat query endpoint...")

    payload = {
        "question": "What is the architecture of the RAG platform?",
        "sessionId": f"test-session-{int(time.time())}",
        "topK": 5
    }

    print(f"  Query: {payload['question']}")

    response = requests.post(
        f"{API_ENDPOINT}/chat/query",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 200, f"Query failed: {response.status_code}"

    data = response.json()

    # Validate response structure
    assert 'answer' in data, "Response missing 'answer'"
    assert 'citations' in data, "Response missing 'citations'"
    assert 'metadata' in data, "Response missing 'metadata'"
    assert data['success'] is True, "Query not successful"

    print(f"  ✓ Answer length: {len(data['answer'])} chars")
    print(f"  ✓ Citations: {len(data['citations'])}")
    print(f"  ✓ Chunks retrieved: {data['metadata']['chunks_retrieved']}")
    print(f"  ✓ Query intent: {data['metadata']['query_intent']}")

    if data['citations']:
        print("\n  Top citation:")
        citation = data['citations'][0]
        print(f"    - Source: {citation['source']}")
        print(f"    - Category: {citation['category']}")
        print(f"    - Score: {citation['score']}")

    print(f"\n  Answer preview:\n    {data['answer'][:200]}...")

    return True


def test_chat_query_with_filters():
    """Test chat query with category filters."""
    print("\nTesting chat query with filters...")

    payload = {
        "question": "What technical specifications are available?",
        "sessionId": f"test-session-filtered-{int(time.time())}",
        "filters": {
            "category": "technical-spec"
        },
        "topK": 3
    }

    print(f"  Query: {payload['question']}")
    print(f"  Filter: category=technical-spec")

    response = requests.post(
        f"{API_ENDPOINT}/chat/query",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 200, f"Filtered query failed: {response.status_code}"

    data = response.json()
    assert data['success'] is True

    # Verify all citations match the filter
    if data['citations']:
        for citation in data['citations']:
            assert citation['category'] == 'technical-spec', \
                f"Citation category mismatch: {citation['category']}"

    print(f"  ✓ Retrieved {len(data['citations'])} technical-spec documents")

    return True


def test_document_search():
    """Test document search endpoint."""
    print("\nTesting document search endpoint...")

    payload = {
        "query": "RAG platform implementation",
        "topK": 10
    }

    print(f"  Search query: {payload['query']}")

    response = requests.post(
        f"{API_ENDPOINT}/chat/search",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 200, f"Search failed: {response.status_code}"

    data = response.json()
    assert 'results' in data, "Response missing 'results'"
    assert 'count' in data, "Response missing 'count'"
    assert data['success'] is True

    print(f"  ✓ Found {data['count']} results")

    if data['results']:
        print("\n  Top result:")
        result = data['results'][0]
        print(f"    - ID: {result['id']}")
        print(f"    - Score: {result['score']}")
        print(f"    - Text preview: {result['text'][:100]}...")

    return True


def test_invalid_requests():
    """Test error handling for invalid requests."""
    print("\nTesting error handling...")

    # Missing question
    response = requests.post(
        f"{API_ENDPOINT}/chat/query",
        json={"sessionId": "test"},
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400, "Should return 400 for missing question"
    print("  ✓ Handles missing question")

    # Invalid JSON
    response = requests.post(
        f"{API_ENDPOINT}/chat/query",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400, "Should return 400 for invalid JSON"
    print("  ✓ Handles invalid JSON")

    # Question too long
    response = requests.post(
        f"{API_ENDPOINT}/chat/query",
        json={"question": "x" * 1500, "sessionId": "test"},
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400, "Should return 400 for oversized question"
    print("  ✓ Handles oversized question")

    # Unknown endpoint
    response = requests.get(f"{API_ENDPOINT}/unknown")
    assert response.status_code == 404, "Should return 404 for unknown endpoint"
    print("  ✓ Handles unknown endpoint")

    return True


def test_cors_headers():
    """Test CORS headers are present."""
    print("\nTesting CORS headers...")

    response = requests.get(f"{API_ENDPOINT}/health")

    assert 'Access-Control-Allow-Origin' in response.headers, "Missing CORS header"
    assert response.headers['Access-Control-Allow-Origin'] == '*', "CORS not set to *"

    print("  ✓ CORS headers present")

    return True


def run_all_tests():
    """Run all end-to-end tests."""
    print("=" * 80)
    print("Phase 3 RAG Chat API - End-to-End Tests")
    print("=" * 80)
    print(f"\nAPI Endpoint: {API_ENDPOINT}")
    print(f"Region: {AWS_REGION}")
    print()

    tests = [
        ("Health Check", test_health_check),
        ("Chat Query", test_chat_query),
        ("Chat Query with Filters", test_chat_query_with_filters),
        ("Document Search", test_document_search),
        ("Error Handling", test_invalid_requests),
        ("CORS Headers", test_cors_headers),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            print("\n" + "-" * 80)
            result = test_func()
            if result:
                passed += 1
                print(f"\n✓ {test_name} PASSED")
        except AssertionError as e:
            failed += 1
            print(f"\n✗ {test_name} FAILED: {e}")
        except Exception as e:
            failed += 1
            print(f"\n✗ {test_name} ERROR: {e}")

    print("\n" + "=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == '__main__':
    if not API_ENDPOINT or API_ENDPOINT == 'https://api.example.com':
        print("ERROR: API_ENDPOINT environment variable not set")
        print("Usage: API_ENDPOINT=https://your-api.execute-api.region.amazonaws.com/dev ./test_e2e.py")
        exit(1)

    success = run_all_tests()
    exit(0 if success else 1)
