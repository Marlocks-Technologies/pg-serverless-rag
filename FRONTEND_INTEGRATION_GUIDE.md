# Frontend Integration Guide

Quick start guide for integrating the RAG Platform API into your frontend application.

---

## Quick Start (5 Minutes)

### 1. Test the API

**Base URL:** `https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev`

```bash
# Health check
curl https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/health

# Ask a question
curl -X POST https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/chat/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What documents are available?", "sessionId": "test-123"}'
```

### 2. Import Postman Collection

1. Open Postman
2. Click **Import**
3. Upload `postman_collection.json` from this directory
4. Collection includes all endpoints with examples
5. Start testing immediately!

---

## JavaScript/TypeScript Integration

### Installation

```bash
# No special dependencies required - uses native fetch
# Or install axios for better support
npm install axios
```

### Basic Example

```typescript
// config.ts
export const API_CONFIG = {
  baseUrl: 'https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev',
  headers: {
    'Content-Type': 'application/json',
  },
};

// api.ts
import { API_CONFIG } from './config';

export interface ChatQueryRequest {
  question: string;
  sessionId: string;
  topK?: number;
  useHistory?: boolean;
  filters?: Record<string, any>;
}

export interface ChatQueryResponse {
  success: boolean;
  sessionId: string;
  answer: string;
  citations: Citation[];
  metadata: {
    chunks_retrieved: number;
    query_intent: string;
    filters_applied: any;
  };
  requestId: string;
}

export interface Citation {
  source: string;
  documentId: string;
  category: string;
  chunkIndex: number;
  score: number;
}

// Chat query function
export async function chatQuery(
  request: ChatQueryRequest
): Promise<ChatQueryResponse> {
  const response = await fetch(`${API_CONFIG.baseUrl}/chat/query`, {
    method: 'POST',
    headers: API_CONFIG.headers,
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Query failed');
  }

  return response.json();
}

// Usage in component
async function askQuestion() {
  try {
    const response = await chatQuery({
      question: 'What is Amazon Bedrock?',
      sessionId: 'user-session-123',
    });

    console.log('Answer:', response.answer);
    console.log('Citations:', response.citations);
  } catch (error) {
    console.error('Error:', error);
  }
}
```

---

## React Integration

### Complete Chat Component

```tsx
// ChatInterface.tsx
import { useState, useEffect } from 'react';
import { chatQuery, getChatHistory } from './api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: Citation[];
}

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `session-${Date.now()}`);

  // Load chat history on mount
  useEffect(() => {
    loadHistory();
  }, []);

  async function loadHistory() {
    try {
      const response = await fetch(
        `${API_CONFIG.baseUrl}/chat/history/${sessionId}`
      );
      const data = await response.json();

      if (data.success && data.messages.length > 0) {
        const formattedMessages = data.messages.map((msg: any) => ({
          role: msg.Role,
          content: msg.Content,
          timestamp: msg.Timestamp,
          citations: msg.Metadata?.citations,
        }));
        setMessages(formattedMessages);
      }
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  }

  async function sendMessage() {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await chatQuery({
        question: input,
        sessionId,
      });

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.answer,
        timestamp: new Date().toISOString(),
        citations: response.citations,
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error:', error);
      // Show error message to user
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-interface">
      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <div className="content">{msg.content}</div>
            {msg.citations && msg.citations.length > 0 && (
              <div className="citations">
                <strong>Sources:</strong>
                {msg.citations.map((citation, i) => (
                  <div key={i} className="citation">
                    📄 {citation.source} (score: {citation.score.toFixed(2)})
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && <div className="loading">AI is thinking...</div>}
      </div>

      <div className="input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Ask a question..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
```

---

## Vue.js Integration

### Composition API Example

```vue
<!-- ChatInterface.vue -->
<template>
  <div class="chat-interface">
    <div class="messages" ref="messagesContainer">
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        :class="['message', msg.role]"
      >
        <div class="content" v-html="renderMarkdown(msg.content)"></div>
        <div v-if="msg.citations?.length" class="citations">
          <strong>Sources:</strong>
          <div
            v-for="(citation, i) in msg.citations"
            :key="i"
            class="citation"
          >
            📄 {{ citation.source }} ({{ citation.score.toFixed(2) }})
          </div>
        </div>
      </div>
      <div v-if="loading" class="loading">AI is thinking...</div>
    </div>

    <div class="input-area">
      <input
        v-model="input"
        @keyup.enter="sendMessage"
        placeholder="Ask a question..."
        :disabled="loading"
      />
      <button @click="sendMessage" :disabled="loading || !input.trim()">
        Send
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue';
import { marked } from 'marked'; // For markdown rendering

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

const messages = ref<Message[]>([]);
const input = ref('');
const loading = ref(false);
const sessionId = ref(`session-${Date.now()}`);
const messagesContainer = ref<HTMLElement | null>(null);

const API_BASE = 'https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev';

onMounted(() => {
  loadHistory();
});

async function loadHistory() {
  try {
    const response = await fetch(`${API_BASE}/chat/history/${sessionId.value}`);
    const data = await response.json();

    if (data.success && data.messages.length > 0) {
      messages.value = data.messages.map((msg: any) => ({
        role: msg.Role,
        content: msg.Content,
        citations: msg.Metadata?.citations,
      }));
      scrollToBottom();
    }
  } catch (error) {
    console.error('Failed to load history:', error);
  }
}

async function sendMessage() {
  if (!input.value.trim() || loading.value) return;

  messages.value.push({
    role: 'user',
    content: input.value,
  });

  const question = input.value;
  input.value = '';
  loading.value = true;

  try {
    const response = await fetch(`${API_BASE}/chat/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        sessionId: sessionId.value,
      }),
    });

    const data = await response.json();

    messages.value.push({
      role: 'assistant',
      content: data.answer,
      citations: data.citations,
    });

    await nextTick();
    scrollToBottom();
  } catch (error) {
    console.error('Error:', error);
  } finally {
    loading.value = false;
  }
}

function renderMarkdown(text: string): string {
  return marked(text);
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
}
</script>

<style scoped>
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 800px;
  margin: 0 auto;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message {
  margin-bottom: 20px;
  padding: 12px;
  border-radius: 8px;
}

.message.user {
  background: #e3f2fd;
  margin-left: 20%;
}

.message.assistant {
  background: #f5f5f5;
  margin-right: 20%;
}

.citations {
  margin-top: 10px;
  font-size: 0.9em;
  color: #666;
}

.input-area {
  display: flex;
  gap: 10px;
  padding: 20px;
  border-top: 1px solid #ddd;
}

input {
  flex: 1;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

button {
  padding: 12px 24px;
  background: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

button:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>
```

---

## API Client Helper

### Reusable API Module

```typescript
// ragAPI.ts
const API_BASE = 'https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev';

class RAGApiClient {
  private baseUrl: string;
  private defaultHeaders: HeadersInit;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    };
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        ...this.defaultHeaders,
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(error.error || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Health check
  async health() {
    return this.request<HealthResponse>('/health');
  }

  // Chat query
  async chatQuery(request: ChatQueryRequest) {
    return this.request<ChatQueryResponse>('/chat/query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Document search
  async search(request: SearchRequest) {
    return this.request<SearchResponse>('/chat/search', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Get chat history
  async getChatHistory(sessionId: string) {
    return this.request<ChatHistoryResponse>(`/chat/history/${sessionId}`);
  }

  // Delete session
  async deleteSession(sessionId: string) {
    return this.request<DeleteSessionResponse>(`/chat/session/${sessionId}`, {
      method: 'DELETE',
    });
  }
}

// Export singleton instance
export const ragAPI = new RAGApiClient();

// Type definitions
export interface ChatQueryRequest {
  question: string;
  sessionId: string;
  topK?: number;
  useHistory?: boolean;
  filters?: Record<string, any>;
}

export interface ChatQueryResponse {
  success: boolean;
  sessionId: string;
  answer: string;
  citations: Citation[];
  metadata: {
    chunks_retrieved: number;
    query_intent: string;
    filters_applied: any;
  };
  requestId: string;
}

export interface Citation {
  source: string;
  documentId: string;
  category: string;
  chunkIndex: number;
  score: number;
}

export interface SearchRequest {
  query: string;
  topK?: number;
  filters?: Record<string, any>;
}

export interface SearchResponse {
  success: boolean;
  results: SearchResult[];
  count: number;
  requestId: string;
}

export interface SearchResult {
  id: string;
  text: string;
  metadata: {
    documentId: string;
    filename: string;
    category: string;
    chunkIndex: number;
  };
  score: number;
}

export interface ChatHistoryResponse {
  success: boolean;
  sessionId: string;
  messages: Message[];
  count: number;
  requestId: string;
}

export interface Message {
  Role: 'user' | 'assistant';
  Content: string;
  Timestamp: string;
  SessionId: string;
  TTL: number;
  Metadata?: {
    chunks_retrieved: number;
    citations: Citation[];
  };
}

export interface DeleteSessionResponse {
  success: boolean;
  sessionId: string;
  messagesDeleted: number;
  requestId: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  phase: string;
  features: string[];
  requestId: string;
}
```

---

## Error Handling

### Best Practices

```typescript
// errorHandler.ts
export class APIError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public details?: any
  ) {
    super(message);
    this.name = 'APIError';
  }
}

export async function safeAPICall<T>(
  apiFunction: () => Promise<T>
): Promise<{ data?: T; error?: string }> {
  try {
    const data = await apiFunction();
    return { data };
  } catch (error) {
    console.error('API Error:', error);

    if (error instanceof APIError) {
      return { error: error.message };
    }

    return { error: 'An unexpected error occurred' };
  }
}

// Usage
const { data, error } = await safeAPICall(() =>
  ragAPI.chatQuery({
    question: 'What is Amazon Bedrock?',
    sessionId: 'user-123',
  })
);

if (error) {
  // Show error to user
  console.error(error);
} else if (data) {
  // Use the data
  console.log(data.answer);
}
```

---

## Features to Implement

### 1. Session Management

```typescript
// sessionManager.ts
export class SessionManager {
  private sessionId: string;

  constructor() {
    // Try to restore session from localStorage
    const saved = localStorage.getItem('ragSessionId');
    this.sessionId = saved || this.generateSessionId();
    localStorage.setItem('ragSessionId', this.sessionId);
  }

  private generateSessionId(): string {
    return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  getSessionId(): string {
    return this.sessionId;
  }

  reset(): void {
    this.sessionId = this.generateSessionId();
    localStorage.setItem('ragSessionId', this.sessionId);
  }

  async clearHistory(): Promise<void> {
    await ragAPI.deleteSession(this.sessionId);
    this.reset();
  }
}
```

### 2. Markdown Rendering

```bash
npm install marked
```

```typescript
import { marked } from 'marked';

function renderAnswer(answer: string): string {
  return marked(answer);
}
```

### 3. Loading States

```typescript
export enum LoadingState {
  Idle = 'idle',
  Loading = 'loading',
  Success = 'success',
  Error = 'error',
}

const [loadingState, setLoadingState] = useState(LoadingState.Idle);
```

### 4. Citation Display

```tsx
function CitationList({ citations }: { citations: Citation[] }) {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="citations">
      <h4>📚 Sources</h4>
      {citations.map((citation, idx) => (
        <div key={idx} className="citation-item">
          <span className="source-icon">📄</span>
          <span className="source-name">{citation.source}</span>
          <span className="source-score">
            {(citation.score * 100).toFixed(0)}% relevant
          </span>
        </div>
      ))}
    </div>
  );
}
```

---

## Testing Checklist

- [ ] Health check works
- [ ] Can send a simple question
- [ ] Answer appears in UI
- [ ] Citations display correctly
- [ ] Can ask follow-up questions
- [ ] Chat history persists across page refresh
- [ ] Error messages display properly
- [ ] Loading states work
- [ ] Session management works
- [ ] Can clear chat history

---

## Common Issues

### CORS Errors
**Issue:** Browser blocks requests due to CORS
**Solution:** API already configured with CORS. If issues persist, check browser console.

### Session Not Persisting
**Issue:** New session every time
**Solution:** Store sessionId in localStorage (see SessionManager example)

### Markdown Not Rendering
**Issue:** Answer shows raw markdown
**Solution:** Use `marked` library to parse markdown

### Citations Not Showing
**Issue:** Citations array is empty
**Solution:** This is normal when no relevant documents are found. Display message: "No sources found"

---

## Next Steps

1. **Clone the examples** - Start with React or Vue example
2. **Test with Postman** - Verify API works before integration
3. **Add styling** - Make it look good!
4. **Add features** - Document upload, search, filters
5. **Deploy** - Host your frontend

---

## Support

- **API Docs:** See `API_DOCUMENTATION.md`
- **Postman Collection:** Import `postman_collection.json`
- **OpenAPI Spec:** Use `openapi.yaml` with Swagger UI
- **Issues:** GitHub repository

Happy coding! 🚀
