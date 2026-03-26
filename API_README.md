# RAG Platform API - Testing & Integration

Complete documentation for testing and integrating with the RAG Platform API.

---

## 📚 Documentation Files

This directory contains everything you need to test and integrate with the RAG Platform API:

| File | Purpose | Use Case |
|------|---------|----------|
| **API_DOCUMENTATION.md** | Complete API reference | Understand all endpoints, parameters, and responses |
| **postman_collection.json** | Postman collection | Quick testing in Postman - import and start testing |
| **openapi.yaml** | OpenAPI 3.0 specification | Generate clients, use with Swagger UI |
| **FRONTEND_INTEGRATION_GUIDE.md** | Frontend integration examples | React, Vue, TypeScript examples |

---

## 🚀 Quick Start (2 Minutes)

### 1. Test with cURL

```bash
# Health check
curl https://lh8dbbvwbb.execute-api.eu-west-1.amazonaws.com/dev/health

# Ask a question
curl -X POST https://lh8dbbvwbb.execute-api.eu-west-1.amazonaws.com/dev/chat/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What documents are available?","sessionId":"test-123"}'
```

### 2. Import to Postman

1. Open Postman
2. Click **Import** → **Upload Files**
3. Select `postman_collection.json`
4. Click **Import**
5. Start testing! ✅

### 3. View in Swagger

1. Go to https://editor.swagger.io/
2. Click **File** → **Import file**
3. Select `openapi.yaml`
4. Browse interactive API docs

---

## 🎯 API Endpoints

**Base URL:** `https://lh8dbbvwbb.execute-api.eu-west-1.amazonaws.com/dev`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Check service health |
| `/chat/query` | POST | Ask questions with RAG |
| `/chat/search` | POST | Search documents |
| `/chat/history/{sessionId}` | GET | Get conversation history |
| `/chat/session/{sessionId}` | DELETE | Delete session |

---

## 💡 Example Requests

### Simple Chat Query

```bash
POST /chat/query
{
  "question": "What is Amazon Bedrock?",
  "sessionId": "user-123"
}
```

**Response:**
```json
{
  "success": true,
  "answer": "Amazon Bedrock is a fully managed service...",
  "citations": [
    {
      "source": "aws-guide.pdf",
      "score": 0.87
    }
  ]
}
```

### Multi-Turn Conversation

```bash
# First question
POST /chat/query
{
  "question": "What is Amazon Bedrock?",
  "sessionId": "conversation-1"
}

# Follow-up (uses context)
POST /chat/query
{
  "question": "What are its main features?",
  "sessionId": "conversation-1"
}
```

### Document Search

```bash
POST /chat/search
{
  "query": "deployment",
  "topK": 5
}
```

---

## 🔧 Integration Examples

### JavaScript/Fetch

```javascript
async function askQuestion(question, sessionId) {
  const response = await fetch(
    'https://lh8dbbvwbb.execute-api.eu-west-1.amazonaws.com/dev/chat/query',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, sessionId })
    }
  );

  return response.json();
}

// Usage
const result = await askQuestion('What is Amazon Bedrock?', 'user-123');
console.log(result.answer);
```

### Python

```python
import requests

def ask_question(question: str, session_id: str):
    response = requests.post(
        'https://lh8dbbvwbb.execute-api.eu-west-1.amazonaws.com/dev/chat/query',
        json={
            'question': question,
            'sessionId': session_id
        }
    )
    return response.json()

# Usage
result = ask_question('What is Amazon Bedrock?', 'user-123')
print(result['answer'])
```

### React Component

```tsx
import { useState } from 'react';

function ChatInterface() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);

  async function sendMessage() {
    const response = await fetch('https://lh8dbbvwbb.execute-api.eu-west-1.amazonaws.com/dev/chat/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: input,
        sessionId: 'user-session-123'
      })
    });

    const data = await response.json();
    setMessages([...messages, { role: 'assistant', content: data.answer }]);
  }

  return (
    <div>
      <input value={input} onChange={e => setInput(e.target.value)} />
      <button onClick={sendMessage}>Send</button>
    </div>
  );
}
```

---

## 📊 Response Format

All successful responses follow this structure:

```typescript
{
  success: boolean;           // true if request succeeded
  sessionId: string;          // Session identifier
  answer: string;             // AI-generated answer (markdown)
  citations: Citation[];      // Source documents
  metadata: {
    chunks_retrieved: number; // Number of relevant chunks found
    query_intent: string;     // Detected intent (factual, conversational)
    filters_applied: object;  // Applied filters (if any)
  };
  requestId: string;          // Unique request ID for tracking
}
```

---

## ⚠️ Error Handling

### Error Response Format

```json
{
  "error": "Error message here"
}
```

### HTTP Status Codes

- `200` - Success
- `400` - Bad Request (invalid input)
- `404` - Not Found
- `500` - Internal Server Error

### Common Errors

```json
// Missing required field
{
  "error": "Missing required field: question"
}

// Question too long
{
  "error": "Question too long (max 1000 characters)"
}

// Invalid JSON
{
  "error": "Invalid JSON in request body"
}
```

---

## 🧪 Testing Scenarios

### Basic Test Flow

1. **Health Check** → Verify API is running
2. **Ask Question** → Get AI response
3. **Check History** → Verify persistence
4. **Follow-up** → Test context maintenance
5. **Search** → Test document retrieval
6. **Clean Up** → Delete session

### Postman Test Suite

The included Postman collection has 10 pre-configured requests:

1. ✅ Health Check
2. ✅ Simple Chat Query
3. ✅ Chat with Options
4. ✅ Follow-up Question
5. ✅ Document Search
6. ✅ Get Chat History
7. ✅ Delete Session
8. ✅ No Relevant Docs Test
9. ✅ Error: Missing Question
10. ✅ Error: Question Too Long

---

## 🎨 Frontend Features to Implement

### Must Have
- [ ] Chat interface with message history
- [ ] Loading state while waiting for response
- [ ] Error message display
- [ ] Session persistence (localStorage)
- [ ] Markdown rendering for answers

### Nice to Have
- [ ] Citation display with source links
- [ ] Auto-scroll to latest message
- [ ] Typing indicator
- [ ] Copy answer to clipboard
- [ ] Search functionality
- [ ] Filter by category
- [ ] Export conversation

### Advanced
- [ ] Streaming responses (WebSocket - future)
- [ ] Voice input
- [ ] Multi-language support
- [ ] Theme customization
- [ ] Analytics dashboard

---

## 📈 Performance Expectations

| Operation | Cold Start | Warm | Notes |
|-----------|-----------|------|-------|
| Health Check | <500ms | <100ms | Simple status |
| Chat Query | <3s | <2s | Includes AI generation |
| Search | <2s | <1s | No AI generation |
| History | <500ms | <200ms | DynamoDB read |

**Note:** Cold start occurs after 5+ minutes of inactivity

---

## 🔐 Authentication

**Current Status:** No authentication required (development environment)

**Production (Future):**
- API Keys via `x-api-key` header
- AWS IAM authentication
- Cognito JWT tokens

When authentication is added, include the API key in requests:

```javascript
headers: {
  'Content-Type': 'application/json',
  'x-api-key': 'your-api-key-here'
}
```

---

## 🌐 CORS Configuration

The API is configured with CORS enabled:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

**Note:** In production, `*` should be replaced with specific domains.

---

## 📱 Mobile Integration

The API works seamlessly with mobile frameworks:

### React Native

```javascript
import axios from 'axios';

async function askQuestion(question, sessionId) {
  const response = await axios.post(
    'https://lh8dbbvwbb.execute-api.eu-west-1.amazonaws.com/dev/chat/query',
    { question, sessionId }
  );
  return response.data;
}
```

### Flutter

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

Future<Map<String, dynamic>> askQuestion(String question, String sessionId) async {
  final response = await http.post(
    Uri.parse('https://lh8dbbvwbb.execute-api.eu-west-1.amazonaws.com/dev/chat/query'),
    headers: {'Content-Type': 'application/json'},
    body: json.encode({
      'question': question,
      'sessionId': sessionId,
    }),
  );

  return json.decode(response.body);
}
```

---

## 🐛 Troubleshooting

### API not responding
- Check health endpoint: `curl https://lh8dbbvwbb.execute-api.eu-west-1.amazonaws.com/dev/health`
- Verify you're using the correct base URL
- Check internet connection

### CORS errors in browser
- API is configured for CORS
- Try request in Postman first
- Check browser console for details

### Empty answers
- System returns "Insufficient Context" when no relevant documents found
- This is expected behavior
- Upload documents to improve responses

### Session not persisting
- Store sessionId in localStorage
- Use same sessionId for follow-up questions
- See SessionManager example in FRONTEND_INTEGRATION_GUIDE.md

---

## 📞 Support

- **Full API Documentation:** `API_DOCUMENTATION.md`
- **Frontend Guide:** `FRONTEND_INTEGRATION_GUIDE.md`
- **GitHub Repository:** https://github.com/Marlocks-Technologies/pg-serverless-rag
- **Report Issues:** GitHub Issues

---

## 📝 License

MIT License - See LICENSE file for details

---

## ✅ Ready to Start?

1. **Test in Postman** - Import `postman_collection.json`
2. **Read Frontend Guide** - See `FRONTEND_INTEGRATION_GUIDE.md`
3. **Build your UI** - Use provided examples
4. **Deploy** - Share with users!

**Questions?** Check the detailed documentation or reach out via GitHub Issues.

Happy building! 🚀
