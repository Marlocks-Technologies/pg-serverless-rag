# RAG Platform API Documentation

**Version:** 1.0.0
**Base URL:** `https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev`
**Environment:** Development
**Region:** eu-west-1

---

## Table of Contents
- [Overview](#overview)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Health Check](#1-health-check)
  - [Chat Query](#2-chat-query)
  - [Document Search](#3-document-search)
  - [Get Chat History](#4-get-chat-history)
  - [Delete Session](#5-delete-session)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Testing Guide](#testing-guide)
- [Postman Collection](#postman-collection)

---

## Overview

The RAG (Retrieval Augmented Generation) Platform API provides endpoints for:
- Document-based question answering with AI
- Semantic search across uploaded documents
- Conversation history management
- Multi-turn contextual conversations

### Key Features
- **RAG-powered responses** - Answers grounded in your document corpus
- **Citations** - Source attribution for transparency
- **Session management** - Maintains conversation context
- **Semantic search** - Find relevant documents by meaning, not just keywords

### Technology Stack
- **Embeddings:** Amazon Titan Embeddings v2 (1024 dimensions)
- **LLM:** Claude Sonnet 4.6
- **Vector Storage:** Amazon S3 Vectors
- **Chat History:** DynamoDB

---

## Authentication

**Current Status:** No authentication required (development environment)

**Future Production:**
- API Keys via `x-api-key` header
- AWS IAM authentication
- Cognito JWT tokens

**Headers (Optional):**
```
Content-Type: application/json
```

---

## Endpoints

### 1. Health Check

Check if the API service is running and healthy.

**Endpoint:** `GET /health`

**Request:**
```bash
curl -X GET https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/health
```

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "service": "chat-handler",
  "version": "0.4.0",
  "phase": "4",
  "features": [
    "rag",
    "search",
    "citations",
    "websocket",
    "history",
    "streaming"
  ],
  "requestId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

### 2. Chat Query

Ask a question and get an AI-generated answer based on your documents.

**Endpoint:** `POST /chat/query`

**Request Body:**
```json
{
  "question": "What is Amazon Bedrock?",
  "sessionId": "user-session-123",
  "topK": 5,
  "useHistory": true,
  "filters": {
    "category": "documentation"
  }
}
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `question` | string | ✅ Yes | - | The user's question (max 1000 chars) |
| `sessionId` | string | ❌ No | Auto-generated | Session ID for conversation continuity |
| `topK` | number | ❌ No | 5 | Number of document chunks to retrieve |
| `useHistory` | boolean | ❌ No | true | Use conversation history for context |
| `filters` | object | ❌ No | null | Metadata filters (e.g., category, date) |

**Example Request:**
```bash
curl -X POST https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is Amazon Bedrock?",
    "sessionId": "demo-session-001"
  }'
```

**Response:** `200 OK`
```json
{
  "success": true,
  "sessionId": "demo-session-001",
  "answer": "Amazon Bedrock is a fully managed service that makes foundation models (FMs) from leading AI companies available through a unified API. It allows developers to build and scale generative AI applications without managing infrastructure.",
  "citations": [
    {
      "source": "aws-bedrock-guide.pdf",
      "documentId": "abc123-def456-ghi789",
      "category": "documentation",
      "chunkIndex": 0,
      "score": 0.87
    }
  ],
  "metadata": {
    "chunks_retrieved": 3,
    "query_intent": "factual",
    "filters_applied": null
  },
  "requestId": "xyz789-abc123-def456"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the query was successful |
| `sessionId` | string | Session ID for this conversation |
| `answer` | string | AI-generated answer in Markdown format |
| `citations` | array | Sources used to generate the answer |
| `citations[].source` | string | Original filename |
| `citations[].documentId` | string | Unique document identifier |
| `citations[].category` | string | Document category |
| `citations[].chunkIndex` | number | Chunk number within document |
| `citations[].score` | number | Relevance score (0.0 - 1.0) |
| `metadata` | object | Query processing metadata |
| `metadata.chunks_retrieved` | number | Number of chunks found |
| `metadata.query_intent` | string | Detected intent (factual, conversational, etc.) |
| `requestId` | string | Unique request identifier for tracking |

**Error Response:** `400 Bad Request`
```json
{
  "error": "Missing required field: question"
}
```

**Error Response:** `500 Internal Server Error`
```json
{
  "error": "Query processing failed"
}
```

---

### 3. Document Search

Search for relevant documents without generating an answer.

**Endpoint:** `POST /chat/search`

**Request Body:**
```json
{
  "query": "machine learning deployment",
  "topK": 10,
  "filters": {
    "category": "technical"
  }
}
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | ✅ Yes | - | Search query |
| `topK` | number | ❌ No | 10 | Number of results to return |
| `filters` | object | ❌ No | null | Metadata filters |

**Example Request:**
```bash
curl -X POST https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/chat/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "deployment best practices",
    "topK": 5
  }'
```

**Response:** `200 OK`
```json
{
  "success": true,
  "results": [
    {
      "id": "doc123-chunk-0",
      "text": "Deployment best practices include automated testing, gradual rollouts...",
      "metadata": {
        "documentId": "doc123",
        "filename": "deployment-guide.pdf",
        "category": "technical",
        "chunkIndex": 0
      },
      "score": 0.92
    }
  ],
  "count": 5,
  "requestId": "search-request-123"
}
```

---

### 4. Get Chat History

Retrieve conversation history for a specific session.

**Endpoint:** `GET /chat/history/{sessionId}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sessionId` | string | ✅ Yes | Session identifier |

**Example Request:**
```bash
curl -X GET https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/chat/history/demo-session-001
```

**Response:** `200 OK`
```json
{
  "success": true,
  "sessionId": "demo-session-001",
  "messages": [
    {
      "Role": "user",
      "Content": "What is Amazon Bedrock?",
      "Timestamp": "2026-03-25T11:43:41.222322+00:00",
      "SessionId": "demo-session-001",
      "TTL": 1782215021.0
    },
    {
      "Role": "assistant",
      "Content": "Amazon Bedrock is a fully managed service...",
      "Timestamp": "2026-03-25T11:43:41.265030+00:00",
      "SessionId": "demo-session-001",
      "TTL": 1782215021.0,
      "Metadata": {
        "chunks_retrieved": 3.0,
        "citations": [
          {
            "source": "aws-bedrock-guide.pdf",
            "documentId": "abc123",
            "score": 0.87
          }
        ]
      }
    }
  ],
  "count": 2,
  "requestId": "history-request-456"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `messages` | array | List of messages in chronological order |
| `messages[].Role` | string | "user" or "assistant" |
| `messages[].Content` | string | Message content |
| `messages[].Timestamp` | string | ISO 8601 timestamp |
| `messages[].TTL` | number | Unix timestamp for DynamoDB TTL (30 days) |
| `messages[].Metadata` | object | Additional data (assistant messages only) |
| `count` | number | Total number of messages |

---

### 5. Delete Session

Delete all conversation history for a session.

**Endpoint:** `DELETE /chat/session/{sessionId}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sessionId` | string | ✅ Yes | Session identifier to delete |

**Example Request:**
```bash
curl -X DELETE https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/chat/session/demo-session-001
```

**Response:** `200 OK`
```json
{
  "success": true,
  "sessionId": "demo-session-001",
  "messagesDeleted": 8,
  "requestId": "delete-request-789"
}
```

---

## Data Models

### Citation Object
```typescript
interface Citation {
  source: string;           // Original filename
  documentId: string;       // Unique document ID
  category: string;         // Document category
  chunkIndex: number;       // Chunk number (0-based)
  score: number;           // Relevance score (0.0 - 1.0)
}
```

### Message Object
```typescript
interface Message {
  Role: "user" | "assistant";
  Content: string;
  Timestamp: string;        // ISO 8601 format
  SessionId: string;
  TTL: number;             // Unix timestamp
  Metadata?: {
    chunks_retrieved: number;
    citations: Citation[];
  };
}
```

### Filter Object
```typescript
interface Filters {
  category?: string;        // Filter by document category
  documentId?: string;      // Filter by specific document
  // Extensible - add custom metadata filters
}
```

---

## Error Handling

### Error Response Format
```json
{
  "error": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid input (missing fields, malformed JSON) |
| 404 | Not Found | Endpoint or resource not found |
| 500 | Internal Server Error | Server-side error |

### Common Errors

**Missing Required Field:**
```json
{
  "error": "Missing required field: question"
}
```

**Question Too Long:**
```json
{
  "error": "Question too long (max 1000 characters)"
}
```

**Invalid JSON:**
```json
{
  "error": "Invalid JSON in request body"
}
```

**Query Processing Failed:**
```json
{
  "error": "Query processing failed"
}
```

---

## Testing Guide

### Prerequisites
1. **Postman** (recommended) or any HTTP client
2. **Base URL:** `https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev`

### Quick Start Test Flow

#### Step 1: Health Check
Verify the API is running:
```bash
GET /health
```
Expected: `200 OK` with service info

#### Step 2: Ask a Question
Send a query to the RAG system:
```bash
POST /chat/query
{
  "question": "What documents are in the knowledge base?",
  "sessionId": "test-session-001"
}
```
Expected: `200 OK` with answer and citations

#### Step 3: Check History
Retrieve the conversation:
```bash
GET /chat/history/test-session-001
```
Expected: `200 OK` with 2 messages (user + assistant)

#### Step 4: Continue Conversation
Ask a follow-up question:
```bash
POST /chat/query
{
  "question": "Can you tell me more about the first document?",
  "sessionId": "test-session-001"
}
```
Expected: Answer using previous context

#### Step 5: Search Documents
Search without generating an answer:
```bash
POST /chat/search
{
  "query": "deployment",
  "topK": 5
}
```
Expected: List of relevant document chunks

#### Step 6: Clean Up
Delete the test session:
```bash
DELETE /chat/session/test-session-001
```
Expected: Confirmation of deletion

---

## Testing Scenarios

### Scenario 1: Single Question (No Context)
**Goal:** Test basic RAG functionality

```bash
POST /chat/query
{
  "question": "What is machine learning?",
  "sessionId": "scenario-1-{{$timestamp}}"
}
```

**Expected Results:**
- ✅ Answer generated from documents
- ✅ Citations included if relevant docs found
- ✅ Session created with new ID

---

### Scenario 2: Multi-Turn Conversation
**Goal:** Test conversation context maintenance

**Turn 1:**
```bash
POST /chat/query
{
  "question": "What is Amazon Bedrock?",
  "sessionId": "scenario-2-multi-turn"
}
```

**Turn 2:**
```bash
POST /chat/query
{
  "question": "What are its main features?",
  "sessionId": "scenario-2-multi-turn"
}
```

**Turn 3:**
```bash
POST /chat/query
{
  "question": "How much does it cost?",
  "sessionId": "scenario-2-multi-turn"
}
```

**Expected Results:**
- ✅ Each answer builds on previous context
- ✅ Pronouns resolved correctly (e.g., "it" refers to Bedrock)
- ✅ History maintains all messages

---

### Scenario 3: No Relevant Documents
**Goal:** Test behavior when no matching documents exist

```bash
POST /chat/query
{
  "question": "What is the recipe for chocolate cake?",
  "sessionId": "scenario-3-no-docs"
}
```

**Expected Results:**
- ✅ Honest response about missing information
- ✅ `chunks_retrieved: 0`
- ✅ Empty citations array

---

### Scenario 4: Empty/Invalid Input
**Goal:** Test error handling

**Test 4a - Missing Question:**
```bash
POST /chat/query
{
  "sessionId": "scenario-4-error"
}
```
Expected: `400 Bad Request` - "Missing required field: question"

**Test 4b - Question Too Long:**
```bash
POST /chat/query
{
  "question": "{{ 1001 character string }}",
  "sessionId": "scenario-4-error"
}
```
Expected: `400 Bad Request` - "Question too long"

**Test 4c - Invalid JSON:**
```bash
POST /chat/query
{ invalid json }
```
Expected: `400 Bad Request` - "Invalid JSON"

---

### Scenario 5: Session Management
**Goal:** Test history persistence and retrieval

```bash
# Create conversation
POST /chat/query
{
  "question": "First question",
  "sessionId": "scenario-5-session"
}

POST /chat/query
{
  "question": "Second question",
  "sessionId": "scenario-5-session"
}

# Retrieve history
GET /chat/history/scenario-5-session

# Delete session
DELETE /chat/session/scenario-5-session

# Verify deletion
GET /chat/history/scenario-5-session
```

**Expected Results:**
- ✅ History contains all messages
- ✅ Deletion returns count of deleted items
- ✅ History is empty after deletion

---

### Scenario 6: Filtered Search
**Goal:** Test metadata filtering

```bash
POST /chat/search
{
  "query": "deployment",
  "topK": 10,
  "filters": {
    "category": "technical"
  }
}
```

**Expected Results:**
- ✅ Only documents matching category filter
- ✅ Sorted by relevance score
- ✅ Up to 10 results returned

---

## Performance Benchmarks

**Expected Response Times:**

| Endpoint | Cold Start | Warm | Notes |
|----------|-----------|------|-------|
| `/health` | < 500ms | < 100ms | Simple check |
| `/chat/query` | < 3s | < 2s | Includes embedding + LLM |
| `/chat/search` | < 2s | < 1s | No LLM generation |
| `/chat/history/{id}` | < 500ms | < 200ms | DynamoDB read |
| `/chat/session/{id}` (DELETE) | < 500ms | < 300ms | DynamoDB delete |

**Notes:**
- Cold start: First request after Lambda idle (>5 min)
- Warm: Subsequent requests with warm Lambda
- Actual times vary based on document corpus size

---

## Postman Collection

Import this JSON into Postman to get started quickly:

**Collection Name:** `RAG Platform API`
**File:** See `postman_collection.json` in this directory

### Environment Variables

Set these in Postman environment:

```json
{
  "base_url": "https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev",
  "session_id": "postman-test-{{$timestamp}}"
}
```

---

## WebSocket API (Future)

**Status:** Not yet implemented

**Planned Endpoint:** `wss://[websocket-api-id].execute-api.eu-west-1.amazonaws.com/dev`

**Use Case:** Streaming responses for real-time chat experience

---

## Rate Limits

**Current Status:** No rate limiting (development)

**Production Recommendations:**
- 100 requests per minute per IP
- 1000 requests per hour per API key
- Burst: 20 requests per second

---

## Support & Issues

**Documentation:** This file
**GitHub:** https://github.com/Marlocks-Technologies/pg-serverless-rag
**Issues:** Submit via GitHub Issues

---

## Changelog

### Version 1.0.0 (2026-03-25)
- ✅ Initial API release
- ✅ Chat query endpoint with RAG
- ✅ Document search
- ✅ Chat history management
- ✅ Multi-turn conversations
- ✅ Citation support

---

## License

MIT License - See LICENSE file for details
