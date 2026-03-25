# WebSocket Streaming API Documentation

Real-time streaming responses for the RAG Platform chat interface.

---

## Overview

The WebSocket API provides:
- ✅ **Real-time streaming** of AI responses token-by-token
- ✅ **Lower latency** - see responses as they're generated
- ✅ **Better UX** - users don't wait for complete response
- ✅ **Bi-directional** - send and receive messages over persistent connection
- ✅ **Session management** - maintain context across WebSocket connection

**WebSocket URL:** `wss://[websocket-api-id].execute-api.eu-west-1.amazonaws.com/dev`

---

## Table of Contents
- [Connection Flow](#connection-flow)
- [Message Types](#message-types)
- [Client Implementation](#client-implementation)
- [Error Handling](#error-handling)
- [Integration Examples](#integration-examples)

---

## Connection Flow

```
1. Client connects to WebSocket URL
   ↓
2. Server sends connection confirmation
   ↓
3. Client sends chat message
   ↓
4. Server streams response chunks
   ↓
5. Server sends completion message
   ↓
6. Connection remains open for next message
```

---

## WebSocket Events

### 1. Connection Events

#### $connect
Triggered when client connects to WebSocket.

**Client Action:**
```javascript
const ws = new WebSocket('wss://[api-id].execute-api.eu-west-1.amazonaws.com/dev');

ws.onopen = () => {
  console.log('Connected to WebSocket');
};
```

**Server Response:**
```json
{
  "type": "connection",
  "status": "connected",
  "connectionId": "abc123",
  "timestamp": "2026-03-25T12:00:00Z"
}
```

#### $disconnect
Triggered when client disconnects.

**Client Action:**
```javascript
ws.close();
```

---

### 2. Chat Message Event

Send a chat message to get streaming response.

**Route:** `chat`

**Client Message Format:**
```json
{
  "action": "chat",
  "message": "What is Amazon Bedrock?",
  "sessionId": "user-session-123",
  "topK": 5,
  "useHistory": true
}
```

**Server Response Sequence:**

#### 2.1 Chat Start
```json
{
  "type": "chat.start",
  "sessionId": "user-session-123",
  "timestamp": "2026-03-25T12:00:01Z"
}
```

#### 2.2 Content Chunks (Multiple)
```json
{
  "type": "chat.chunk",
  "content": "Amazon Bedrock is "
}
```
```json
{
  "type": "chat.chunk",
  "content": "a fully managed service "
}
```
```json
{
  "type": "chat.chunk",
  "content": "that provides access to foundation models..."
}
```

#### 2.3 Citations (Optional)
```json
{
  "type": "chat.citations",
  "citations": [
    {
      "source": "aws-bedrock-guide.pdf",
      "documentId": "abc123",
      "score": 0.87
    }
  ]
}
```

#### 2.4 Chat Complete
```json
{
  "type": "chat.complete",
  "sessionId": "user-session-123",
  "timestamp": "2026-03-25T12:00:05Z"
}
```

---

## Message Types

### Client to Server

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `chat` | Send chat message | `message`, `sessionId` |

### Server to Client

| Type | Description | When Sent |
|------|-------------|-----------|
| `connection` | Connection status | On connect |
| `chat.start` | Response starting | Before first chunk |
| `chat.chunk` | Response content | Multiple times during streaming |
| `chat.citations` | Source citations | After content, if available |
| `chat.complete` | Response finished | End of stream |
| `error` | Error occurred | On any error |

---

## Client Implementation

### JavaScript/Browser

```javascript
class RAGWebSocketClient {
  constructor(url, sessionId) {
    this.url = url;
    this.sessionId = sessionId;
    this.ws = null;
    this.messageHandlers = {
      'connection': [],
      'chat.start': [],
      'chat.chunk': [],
      'chat.citations': [],
      'chat.complete': [],
      'error': []
    };
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        resolve();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
      };
    });
  }

  handleMessage(data) {
    const handlers = this.messageHandlers[data.type] || [];
    handlers.forEach(handler => handler(data));
  }

  on(eventType, handler) {
    if (this.messageHandlers[eventType]) {
      this.messageHandlers[eventType].push(handler);
    }
  }

  sendMessage(message, options = {}) {
    const payload = {
      action: 'chat',
      message,
      sessionId: options.sessionId || this.sessionId,
      topK: options.topK || 5,
      useHistory: options.useHistory !== false
    };

    this.ws.send(JSON.stringify(payload));
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// Usage
const client = new RAGWebSocketClient(
  'wss://[api-id].execute-api.eu-west-1.amazonaws.com/dev',
  'user-session-123'
);

await client.connect();

// Handle streaming response
let fullResponse = '';

client.on('chat.start', (data) => {
  console.log('Response starting...');
  fullResponse = '';
});

client.on('chat.chunk', (data) => {
  fullResponse += data.content;
  console.log('Chunk received:', data.content);
  // Update UI with new content
});

client.on('chat.citations', (data) => {
  console.log('Citations:', data.citations);
  // Display citations in UI
});

client.on('chat.complete', (data) => {
  console.log('Response complete:', fullResponse);
  // Show completion indicator
});

client.on('error', (data) => {
  console.error('Error:', data.message);
  // Show error message
});

// Send a message
client.sendMessage('What is Amazon Bedrock?');
```

---

### React Integration

```tsx
import { useState, useEffect, useRef } from 'react';

function useRAGWebSocket(url, sessionId) {
  const [connected, setConnected] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [currentResponse, setCurrentResponse] = useState('');
  const [citations, setCitations] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, []);

  function connect() {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setConnected(true);
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'chat.start':
          setStreaming(true);
          setCurrentResponse('');
          setCitations([]);
          break;

        case 'chat.chunk':
          setCurrentResponse(prev => prev + data.content);
          break;

        case 'chat.citations':
          setCitations(data.citations);
          break;

        case 'chat.complete':
          setStreaming(false);
          break;

        case 'error':
          console.error('WebSocket error:', data.message);
          setStreaming(false);
          break;
      }
    };

    ws.onclose = () => {
      setConnected(false);
      console.log('WebSocket disconnected');
    };

    wsRef.current = ws;
  }

  function disconnect() {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }

  function sendMessage(message, options = {}) {
    if (!wsRef.current || !connected) {
      throw new Error('WebSocket not connected');
    }

    const payload = {
      action: 'chat',
      message,
      sessionId: options.sessionId || sessionId,
      topK: options.topK || 5,
      useHistory: options.useHistory !== false
    };

    wsRef.current.send(JSON.stringify(payload));
  }

  return {
    connected,
    streaming,
    currentResponse,
    citations,
    sendMessage,
    disconnect
  };
}

// Component using the hook
function StreamingChatInterface() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);

  const {
    connected,
    streaming,
    currentResponse,
    citations,
    sendMessage
  } = useRAGWebSocket(
    'wss://[api-id].execute-api.eu-west-1.amazonaws.com/dev',
    'user-session-123'
  );

  useEffect(() => {
    // When streaming starts, add placeholder message
    if (streaming && !messages.find(m => m.streaming)) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '',
        streaming: true
      }]);
    }

    // Update streaming message with current response
    if (streaming || currentResponse) {
      setMessages(prev => prev.map(msg =>
        msg.streaming ? { ...msg, content: currentResponse } : msg
      ));
    }

    // When complete, finalize message
    if (!streaming && currentResponse) {
      setMessages(prev => prev.map(msg =>
        msg.streaming
          ? { ...msg, streaming: false, citations }
          : msg
      ));
    }
  }, [streaming, currentResponse, citations]);

  function handleSend() {
    if (!input.trim() || streaming) return;

    // Add user message
    setMessages(prev => [...prev, {
      role: 'user',
      content: input
    }]);

    // Send to WebSocket
    sendMessage(input);
    setInput('');
  }

  return (
    <div className="chat-interface">
      <div className="status">
        {connected ? (
          <span className="connected">🟢 Connected</span>
        ) : (
          <span className="disconnected">🔴 Disconnected</span>
        )}
      </div>

      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <div className="content">{msg.content}</div>
            {msg.streaming && <span className="typing">▋</span>}
            {msg.citations && msg.citations.length > 0 && (
              <div className="citations">
                {msg.citations.map((c, i) => (
                  <div key={i}>{c.source}</div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type your message..."
          disabled={!connected || streaming}
        />
        <button
          onClick={handleSend}
          disabled={!connected || streaming || !input.trim()}
        >
          {streaming ? 'Streaming...' : 'Send'}
        </button>
      </div>
    </div>
  );
}
```

---

### Python Client

```python
import asyncio
import json
import websockets

class RAGWebSocketClient:
    def __init__(self, url, session_id):
        self.url = url
        self.session_id = session_id
        self.ws = None
        self.handlers = {}

    async def connect(self):
        """Connect to WebSocket server."""
        self.ws = await websockets.connect(self.url)
        print("Connected to WebSocket")

    async def listen(self):
        """Listen for messages from server."""
        async for message in self.ws:
            data = json.loads(message)
            await self.handle_message(data)

    async def handle_message(self, data):
        """Handle incoming message."""
        msg_type = data.get('type')
        handler = self.handlers.get(msg_type)

        if handler:
            await handler(data)
        else:
            print(f"Unhandled message type: {msg_type}")

    def on(self, event_type, handler):
        """Register event handler."""
        self.handlers[event_type] = handler

    async def send_message(self, message, **options):
        """Send chat message."""
        payload = {
            'action': 'chat',
            'message': message,
            'sessionId': options.get('sessionId', self.session_id),
            'topK': options.get('topK', 5),
            'useHistory': options.get('useHistory', True)
        }

        await self.ws.send(json.dumps(payload))

    async def disconnect(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()

# Usage
async def main():
    client = RAGWebSocketClient(
        'wss://[api-id].execute-api.eu-west-1.amazonaws.com/dev',
        'user-session-123'
    )

    full_response = []

    async def on_chunk(data):
        content = data.get('content', '')
        full_response.append(content)
        print(content, end='', flush=True)

    async def on_complete(data):
        print("\n\nResponse complete!")
        print("Full response:", ''.join(full_response))

    client.on('chat.chunk', on_chunk)
    client.on('chat.complete', on_complete)

    await client.connect()

    # Start listening in background
    listen_task = asyncio.create_task(client.listen())

    # Send message
    await client.send_message('What is Amazon Bedrock?')

    # Wait for response
    await asyncio.sleep(10)

    # Clean up
    await client.disconnect()
    listen_task.cancel()

# Run
asyncio.run(main())
```

---

## Error Handling

### Connection Errors

```javascript
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
  // Retry connection with exponential backoff
  setTimeout(() => connect(), 1000 * Math.pow(2, retryCount));
};

ws.onclose = (event) => {
  if (event.code !== 1000) {  // Not a normal closure
    console.error('Connection closed unexpectedly:', event.code);
    // Attempt reconnection
  }
};
```

### Message Errors

```json
{
  "type": "error",
  "message": "Failed to process message",
  "code": "PROCESSING_ERROR",
  "details": "..."
}
```

**Handle in client:**
```javascript
client.on('error', (data) => {
  switch (data.code) {
    case 'INVALID_MESSAGE':
      alert('Invalid message format');
      break;
    case 'PROCESSING_ERROR':
      alert('Failed to generate response. Please try again.');
      break;
    case 'RATE_LIMIT':
      alert('Too many requests. Please wait.');
      break;
    default:
      alert(`Error: ${data.message}`);
  }
});
```

---

## Best Practices

### 1. Connection Management

```javascript
class ConnectionManager {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onclose = () => {
        this.handleReconnect();
      };

      this.ws.onerror = (error) => {
        reject(error);
      };
    });
  }

  handleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      this.connect();
    }, delay);
  }
}
```

### 2. Message Queuing

Queue messages if connection is lost:

```javascript
class MessageQueue {
  constructor(ws) {
    this.ws = ws;
    this.queue = [];
  }

  send(message) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      this.queue.push(message);
    }
  }

  flush() {
    while (this.queue.length > 0 && this.ws.readyState === WebSocket.OPEN) {
      const message = this.queue.shift();
      this.ws.send(JSON.stringify(message));
    }
  }
}
```

### 3. Heartbeat/Keep-Alive

Implement ping/pong to keep connection alive:

```javascript
let heartbeatInterval;

function startHeartbeat(ws) {
  heartbeatInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: 'ping' }));
    }
  }, 30000);  // Every 30 seconds
}

function stopHeartbeat() {
  clearInterval(heartbeatInterval);
}
```

---

## Performance Optimization

### 1. Throttle UI Updates

When receiving many chunks quickly:

```javascript
let updateBuffer = '';
let updateTimeout;

client.on('chat.chunk', (data) => {
  updateBuffer += data.content;

  // Throttle updates to 60fps
  if (!updateTimeout) {
    updateTimeout = setTimeout(() => {
      setCurrentResponse(prev => prev + updateBuffer);
      updateBuffer = '';
      updateTimeout = null;
    }, 16);  // ~60fps
  }
});
```

### 2. Batch Message Processing

Process multiple messages in single render:

```javascript
const [messageQueue, setMessageQueue] = useState([]);

useEffect(() => {
  if (messageQueue.length > 0) {
    // Process all queued messages at once
    setMessages(prev => [...prev, ...messageQueue]);
    setMessageQueue([]);
  }
}, [messageQueue]);
```

---

## Comparison: REST vs WebSocket

| Feature | REST API | WebSocket API |
|---------|----------|---------------|
| **Response Type** | Complete response | Streaming chunks |
| **Latency** | Higher (wait for full response) | Lower (see tokens as generated) |
| **Connection** | Request/Response | Persistent connection |
| **Overhead** | HTTP headers each request | Initial handshake only |
| **User Experience** | Wait indicator | Real-time typing effect |
| **Complexity** | Simple | More complex |
| **Best For** | Simple queries, mobile | Interactive chat, desktop |

**Recommendation:** Use WebSocket for interactive chat interfaces, REST for mobile apps or simple integrations.

---

## Troubleshooting

### Connection Fails
- **Check URL:** Ensure using `wss://` not `https://`
- **CORS:** WebSocket doesn't use CORS, but check origin policies
- **Firewall:** Ensure port 443 is open

### No Messages Received
- **Check handlers:** Ensure `onmessage` handler is registered
- **JSON parsing:** Messages must be valid JSON
- **Message format:** Verify action field is correct

### Connection Drops
- **Idle timeout:** Implement heartbeat/ping
- **Network issues:** Implement reconnection logic
- **Lambda timeout:** Responses longer than 29 minutes will disconnect

---

## Security Considerations

### 1. Authentication (Future)

```javascript
const ws = new WebSocket(url, {
  headers: {
    'Authorization': 'Bearer ' + token
  }
});
```

### 2. Message Validation

Always validate received messages:

```javascript
function validateMessage(data) {
  if (!data.type) {
    console.warn('Invalid message: missing type');
    return false;
  }

  // Validate expected fields for each type
  return true;
}
```

### 3. Rate Limiting

Implement client-side rate limiting:

```javascript
class RateLimiter {
  constructor(maxMessages, windowMs) {
    this.maxMessages = maxMessages;
    this.windowMs = windowMs;
    this.messages = [];
  }

  canSend() {
    const now = Date.now();
    this.messages = this.messages.filter(t => now - t < this.windowMs);

    if (this.messages.length >= this.maxMessages) {
      return false;
    }

    this.messages.push(now);
    return true;
  }
}

const limiter = new RateLimiter(10, 60000);  // 10 messages per minute
```

---

## Next Steps

1. ✅ Understand message flow
2. ✅ Implement basic WebSocket client
3. ✅ Add error handling and reconnection
4. ✅ Build streaming UI component
5. ✅ Test with real queries
6. ✅ Deploy to production

---

## Support

- **REST API Docs:** `API_DOCUMENTATION.md`
- **GitHub:** https://github.com/Marlocks-Technologies/pg-serverless-rag
- **Issues:** GitHub Issues

Ready for real-time streaming! ⚡🚀
