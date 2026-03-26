# WebSocket API Documentation

## Overview

The RAG platform WebSocket API provides real-time, streaming chat functionality powered by Amazon Bedrock Knowledge Base. Clients connect via WebSocket to receive token-by-token streaming responses for a more interactive user experience.

**WebSocket Endpoint:**
```
wss://<api-gateway-id>.execute-api.<region>.amazonaws.com/<stage>
```

**Example (Dev Environment):**
```
wss://9hc3a3ur4j.execute-api.eu-west-1.amazonaws.com/dev
```

## Connection Lifecycle

### 1. Connect
Establish WebSocket connection to the endpoint. The connection is stored in DynamoDB with an automatic TTL for cleanup.

```javascript
const ws = new WebSocket('wss://9hc3a3ur4j.execute-api.eu-west-1.amazonaws.com/dev');

ws.onopen = () => {
  console.log('WebSocket connected');
};
```

### 2. Send Chat Message
Send a JSON message with the `chat` action to ask questions.

**Message Format:**
```json
{
  "action": "chat",
  "question": "What is Amazon S3?",
  "sessionId": "optional-session-id",
  "topK": 5
}
```

**Parameters:**
- `action` (required): Must be `"chat"`
- `question` (required): The user's question
- `sessionId` (optional): Session ID for conversation continuity. If not provided, a new session is created.
- `topK` (optional): Number of top documents to retrieve from Knowledge Base (default: 5)

### 3. Receive Streaming Response
The server sends multiple messages as the response streams back.

#### Message Types

**a) Chat Start**
```json
{
  "type": "chat.start",
  "sessionId": "ws-connection-id-123",
  "timestamp": "2026-03-25T14:51:49.823Z"
}
```

**b) Chat Chunk**
Streaming content chunks sent as they're generated.

```json
{
  "type": "chat.chunk",
  "content": "Amazon S3 is ",
  "sessionId": "ws-connection-id-123"
}
```

Multiple chunks are sent sequentially to build the complete response.

**c) Chat Citations**
Source documents used to generate the response.

```json
{
  "type": "chat.citations",
  "citations": [
    {
      "title": "AWS Services Overview",
      "text": "S3 provides scalable object storage...",
      "score": 0.8542,
      "location": {
        "s3Location": {
          "uri": "s3://bucket/path/document.pdf"
        }
      }
    }
  ],
  "sessionId": "ws-connection-id-123"
}
```

**d) Chat Complete**
Final message indicating the response is complete.

```json
{
  "type": "chat.complete",
  "sessionId": "ws-connection-id-123",
  "timestamp": "2026-03-25T14:51:50.305Z"
}
```

**e) Error**
Sent if an error occurs during processing.

```json
{
  "type": "error",
  "message": "Failed to process request",
  "details": "Optional error details"
}
```

### 4. Disconnect
Close the connection when done. The server automatically removes the connection from DynamoDB.

```javascript
ws.close();
```

## Complete Example (JavaScript)

```javascript
class RAGWebSocketClient {
  constructor(endpoint) {
    this.endpoint = endpoint;
    this.ws = null;
    this.sessionId = null;
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.endpoint);

      this.ws.onopen = () => {
        console.log('Connected to RAG WebSocket');
        resolve();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(JSON.parse(event.data));
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
      };
    });
  }

  handleMessage(message) {
    switch (message.type) {
      case 'chat.start':
        console.log('Chat started:', message.sessionId);
        this.sessionId = message.sessionId;
        this.onChatStart && this.onChatStart(message);
        break;

      case 'chat.chunk':
        // Append chunk to UI
        this.onChunk && this.onChunk(message.content);
        break;

      case 'chat.citations':
        console.log('Citations received:', message.citations.length);
        this.onCitations && this.onCitations(message.citations);
        break;

      case 'chat.complete':
        console.log('Chat completed');
        this.onComplete && this.onComplete(message);
        break;

      case 'error':
        console.error('Error:', message.message);
        this.onError && this.onError(message);
        break;

      default:
        console.warn('Unknown message type:', message.type);
    }
  }

  sendQuestion(question, topK = 5) {
    const message = {
      action: 'chat',
      question: question,
      sessionId: this.sessionId,
      topK: topK
    };

    this.ws.send(JSON.stringify(message));
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Usage
const client = new RAGWebSocketClient(
  'wss://9hc3a3ur4j.execute-api.eu-west-1.amazonaws.com/dev'
);

client.onChunk = (content) => {
  // Append to chat UI
  document.getElementById('response').textContent += content;
};

client.onCitations = (citations) => {
  // Display sources
  const citationsDiv = document.getElementById('citations');
  citations.forEach(citation => {
    const item = document.createElement('div');
    item.textContent = `${citation.title} (Score: ${citation.score.toFixed(4)})`;
    citationsDiv.appendChild(item);
  });
};

client.onComplete = () => {
  console.log('Response complete');
};

// Connect and send question
await client.connect();
client.sendQuestion('What is Amazon S3?');
```

## Python Example

```python
import asyncio
import json
import websockets

async def chat_with_rag(question):
    uri = "wss://9hc3a3ur4j.execute-api.eu-west-1.amazonaws.com/dev"

    async with websockets.connect(uri) as ws:
        # Send question
        message = {
            "action": "chat",
            "question": question,
            "topK": 5
        }
        await ws.send(json.dumps(message))

        # Receive streaming response
        response_text = ""
        async for raw_message in ws:
            msg = json.loads(raw_message)

            if msg['type'] == 'chat.start':
                print(f"Session: {msg['sessionId']}")

            elif msg['type'] == 'chat.chunk':
                content = msg['content']
                response_text += content
                print(content, end='', flush=True)

            elif msg['type'] == 'chat.citations':
                print("\n\nSources:")
                for citation in msg['citations']:
                    print(f"  - {citation['title']} (Score: {citation['score']:.4f})")

            elif msg['type'] == 'chat.complete':
                print("\n\nComplete!")
                break

            elif msg['type'] == 'error':
                print(f"\nError: {msg['message']}")
                break

        return response_text

# Run
asyncio.run(chat_with_rag("What is Amazon S3?"))
```

## React Example

```typescript
import { useEffect, useState, useRef } from 'react';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

interface Citation {
  title: string;
  text: string;
  score: number;
  location: {
    s3Location: {
      uri: string;
    };
  };
}

export function useRAGWebSocket(endpoint: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const currentResponseRef = useRef<string>('');
  const currentCitationsRef = useRef<Citation[]>([]);

  useEffect(() => {
    const ws = new WebSocket(endpoint);

    ws.onopen = () => {
      setIsConnected(true);
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      switch (message.type) {
        case 'chat.start':
          setIsStreaming(true);
          currentResponseRef.current = '';
          currentCitationsRef.current = [];
          break;

        case 'chat.chunk':
          currentResponseRef.current += message.content;
          // Update UI with streaming content
          setMessages(prev => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage && lastMessage.role === 'assistant') {
              lastMessage.content = currentResponseRef.current;
            }
            return newMessages;
          });
          break;

        case 'chat.citations':
          currentCitationsRef.current = message.citations;
          break;

        case 'chat.complete':
          setIsStreaming(false);
          // Update final message with citations
          setMessages(prev => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage && lastMessage.role === 'assistant') {
              lastMessage.citations = currentCitationsRef.current;
            }
            return newMessages;
          });
          break;

        case 'error':
          setIsStreaming(false);
          console.error('Error:', message.message);
          break;
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket disconnected');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [endpoint]);

  const sendQuestion = (question: string, topK: number = 5) => {
    if (!wsRef.current || !isConnected) {
      console.error('WebSocket not connected');
      return;
    }

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: question }]);

    // Add empty assistant message that will be filled by streaming
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    // Send to server
    const message = {
      action: 'chat',
      question,
      topK
    };
    wsRef.current.send(JSON.stringify(message));
  };

  return {
    messages,
    isConnected,
    isStreaming,
    sendQuestion
  };
}
```

## Error Handling

Always implement error handling for:
- Connection failures
- Network interruptions
- Server errors
- Timeout scenarios

```javascript
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
  // Implement retry logic or user notification
};

ws.onclose = (event) => {
  if (!event.wasClean) {
    console.error('Connection closed unexpectedly');
    // Implement reconnection logic
  }
};
```

## Best Practices

1. **Session Management**: Reuse `sessionId` across multiple questions for conversation continuity
2. **Connection Pooling**: Reuse connections when sending multiple questions in quick succession
3. **Timeout Handling**: Implement client-side timeouts (recommended: 30-60 seconds)
4. **Retry Logic**: Implement exponential backoff for reconnection attempts
5. **Message Buffering**: Buffer chunks to reduce UI update frequency for better performance
6. **Error Recovery**: Gracefully handle and display errors to users
7. **Cleanup**: Always close connections when done to free server resources

## Performance Considerations

- **Latency**: First token typically arrives within 500-1000ms
- **Throughput**: Streaming improves perceived performance vs. waiting for complete response
- **Connection Limits**: API Gateway WebSocket has connection limits (10,000 concurrent by default)
- **Message Size**: Individual messages limited to 128KB
- **Connection Duration**: Idle timeout is 10 minutes by default

## Security

- Use WSS (WebSocket Secure) protocol for encrypted communication
- Implement authentication via:
  - AWS IAM Signature Version 4 signing
  - Custom authorizers (Lambda)
  - API keys (if enabled)
- Validate all user input before sending
- Sanitize response content before rendering in UI to prevent XSS

## Troubleshooting

### Connection Fails
- Verify WebSocket endpoint URL
- Check network connectivity and firewalls
- Ensure API Gateway WebSocket is deployed

### No Response
- Check Lambda function logs in CloudWatch
- Verify Knowledge Base is provisioned and has indexed documents
- Ensure IAM permissions are correct

### Slow Response
- Check Lambda memory/timeout configuration
- Verify Knowledge Base is in same region
- Monitor CloudWatch metrics for throttling

## Monitoring

Monitor these CloudWatch metrics:
- `ExecutionError` - Lambda execution failures
- `IntegrationLatency` - Response time
- `MessageCount` - Number of messages sent/received
- Lambda `Duration` and `ConcurrentExecutions`

## Further Resources

- [API Gateway WebSocket Documentation](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api.html)
- [Amazon Bedrock Knowledge Base](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [WebSocket API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
