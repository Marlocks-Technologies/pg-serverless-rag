# Document Management API Documentation

Complete guide for uploading, managing, and deleting documents in the RAG Platform.

---

## Overview

The Document Management API allows you to:
- ✅ Upload documents in multiple formats (PDF, DOCX, TXT, MD)
- ✅ List all documents with filtering and pagination
- ✅ Get detailed document information and processing status
- ✅ Delete documents and their associated vectors
- ✅ Track processing status in real-time

**Base URL:** `https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev`

---

## Table of Contents
- [Endpoints](#endpoints)
- [Upload Document](#1-upload-document)
- [List Documents](#2-list-documents)
- [Get Document Details](#3-get-document-details)
- [Delete Document](#4-delete-document)
- [Status Codes](#status-codes)
- [Integration Examples](#integration-examples)

---

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/documents` | POST | Upload a new document |
| `/documents` | GET | List all documents |
| `/documents/{id}` | GET | Get document details |
| `/documents/{id}` | DELETE | Delete a document |

---

## 1. Upload Document

Upload a document to be processed and added to the knowledge base.

### Endpoint
```
POST /documents
```

### Request Format

**Option A: JSON with Base64 (Recommended for Testing)**

```json
{
  "filename": "my-document.pdf",
  "content": "base64-encoded-content-here",
  "contentType": "application/pdf",
  "metadata": {
    "author": "John Doe",
    "department": "Engineering",
    "tags": ["technical", "deployment"]
  }
}
```

**Option B: Multipart Form Data (Browser Upload)**

```http
POST /documents HTTP/1.1
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="document.pdf"
Content-Type: application/pdf

[binary file content]
------WebKitFormBoundary--
```

### Request Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filename` | string | ✅ Yes | Original filename with extension |
| `content` | string | ✅ Yes | Base64-encoded file content |
| `contentType` | string | ❌ No | MIME type (auto-detected if not provided) |
| `metadata` | object | ❌ No | Additional metadata (author, tags, etc.) |

### Supported File Formats

| Format | Extension | MIME Type | Max Size |
|--------|-----------|-----------|----------|
| PDF | .pdf | application/pdf | 10 MB |
| Word | .docx | application/vnd.openxmlformats-officedocument.wordprocessingml.document | 10 MB |
| Text | .txt | text/plain | 10 MB |
| Markdown | .md | text/markdown | 10 MB |

### Response

**Success (202 Accepted):**
```json
{
  "success": true,
  "documentId": "abc123-def456-ghi789",
  "filename": "my-document.pdf",
  "s3Key": "uploads/my-document.pdf",
  "status": "processing",
  "message": "Document uploaded successfully and is being processed",
  "requestId": "xyz-789"
}
```

**Error (400 Bad Request):**
```json
{
  "error": "File too large (max 10MB)"
}
```

**Error (415 Unsupported Media Type):**
```json
{
  "error": "Unsupported file type. Supported: PDF, DOCX, TXT, MD"
}
```

### Example Request (cURL)

```bash
# Prepare file
FILE_PATH="document.pdf"
FILE_BASE64=$(base64 -i "$FILE_PATH")

# Upload
curl -X POST https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents \
  -H "Content-Type: application/json" \
  -d "{
    \"filename\": \"document.pdf\",
    \"content\": \"$FILE_BASE64\",
    \"contentType\": \"application/pdf\",
    \"metadata\": {
      \"author\": \"John Doe\",
      \"department\": \"Engineering\"
    }
  }"
```

### Example Request (JavaScript)

```javascript
async function uploadDocument(file) {
  // Read file as base64
  const reader = new FileReader();

  reader.onload = async () => {
    const base64 = reader.result.split(',')[1];  // Remove data URL prefix

    const response = await fetch('https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        filename: file.name,
        content: base64,
        contentType: file.type,
        metadata: {
          uploadedBy: 'user@example.com',
          timestamp: new Date().toISOString()
        }
      })
    });

    const result = await response.json();
    console.log('Upload result:', result);

    return result;
  };

  reader.readAsDataURL(file);
}

// Usage with file input
document.getElementById('fileInput').addEventListener('change', (e) => {
  const file = e.target.files[0];
  uploadDocument(file);
});
```

---

## 2. List Documents

Retrieve a list of all documents with optional filtering.

### Endpoint
```
GET /documents?limit=50&status=completed&category=technical
```

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | number | ❌ No | 50 | Maximum number of documents to return |
| `status` | string | ❌ No | all | Filter by status: `processing`, `completed`, `failed` |
| `category` | string | ❌ No | all | Filter by category: `technical`, `contracts`, `financial`, etc. |
| `nextToken` | string | ❌ No | - | Pagination token for next page |

### Response

```json
{
  "success": true,
  "documents": [
    {
      "documentId": "abc123-def456-ghi789",
      "filename": "deployment-guide.pdf",
      "category": "technical",
      "status": "completed",
      "uploadedAt": "2026-03-25T10:30:00Z",
      "processedAt": "2026-03-25T10:30:15Z",
      "sizeBytes": 245678,
      "s3Uri": "s3://rag-dev-doc-staging/grouped/technical/abc123.pdf"
    },
    {
      "documentId": "xyz789-abc123-def456",
      "filename": "contract-template.docx",
      "category": "contracts",
      "status": "completed",
      "uploadedAt": "2026-03-25T09:15:00Z",
      "processedAt": "2026-03-25T09:15:20Z",
      "sizeBytes": 156234,
      "s3Uri": "s3://rag-dev-doc-staging/grouped/contracts/xyz789.pdf"
    }
  ],
  "count": 2,
  "nextToken": null,
  "requestId": "req-123"
}
```

### Example Request (cURL)

```bash
# List all documents
curl https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents

# Filter by category
curl "https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents?category=technical"

# Filter by status
curl "https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents?status=completed&limit=10"
```

### Example Request (JavaScript)

```javascript
async function listDocuments(filters = {}) {
  const params = new URLSearchParams(filters);

  const response = await fetch(
    `https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents?${params}`
  );

  const data = await response.json();
  return data.documents;
}

// Usage
const techDocs = await listDocuments({ category: 'technical', limit: 20 });
console.log('Technical documents:', techDocs);
```

---

## 3. Get Document Details

Get detailed information about a specific document.

### Endpoint
```
GET /documents/{documentId}
```

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `documentId` | string | ✅ Yes | Document identifier |

### Response

```json
{
  "success": true,
  "document": {
    "documentId": "abc123-def456-ghi789",
    "filename": "deployment-guide.pdf",
    "category": "technical",
    "secondaryTags": ["devops", "aws", "infrastructure"],
    "confidence": 0.89,
    "status": "completed",
    "uploadedAt": "2026-03-25T10:30:00Z",
    "processedAt": "2026-03-25T10:30:15Z",
    "sizeBytes": 245678,
    "contentType": "application/pdf",
    "checksum": "sha256:abc123...",
    "processing": {
      "parser": "pypdf",
      "ocrUsed": false,
      "textLengthChars": 15234,
      "pageCount": 12
    },
    "vectors": {
      "count": 8,
      "bucket": "rag-dev-kb-vectors"
    },
    "s3Uri": "s3://rag-dev-doc-staging/grouped/technical/abc123.pdf"
  },
  "requestId": "req-456"
}
```

### Error Response (404 Not Found)

```json
{
  "success": false,
  "error": "Document not found"
}
```

### Example Request (cURL)

```bash
curl https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents/abc123-def456-ghi789
```

### Example Request (JavaScript)

```javascript
async function getDocumentDetails(documentId) {
  const response = await fetch(
    `https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents/${documentId}`
  );

  if (!response.ok) {
    throw new Error('Document not found');
  }

  const data = await response.json();
  return data.document;
}

// Usage
const doc = await getDocumentDetails('abc123-def456-ghi789');
console.log(`Document has ${doc.vectors.count} vector chunks`);
```

---

## 4. Delete Document

Delete a document and all associated data (PDF, metadata, vectors).

### Endpoint
```
DELETE /documents/{documentId}
```

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `documentId` | string | ✅ Yes | Document identifier |

### Response

```json
{
  "success": true,
  "documentId": "abc123-def456-ghi789",
  "deletedFiles": 2,
  "vectorsDeleted": 8,
  "message": "Document deleted successfully",
  "requestId": "req-789"
}
```

### What Gets Deleted

1. **PDF file** in staging bucket
2. **Metadata JSON** in staging bucket
3. **All vector chunks** in vectors bucket
4. **Document entry** in DynamoDB (if tracking enabled)

**⚠️ Warning:** This operation is permanent and cannot be undone!

### Example Request (cURL)

```bash
curl -X DELETE https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents/abc123-def456-ghi789
```

### Example Request (JavaScript)

```javascript
async function deleteDocument(documentId) {
  const confirmed = confirm('Are you sure you want to delete this document? This cannot be undone.');

  if (!confirmed) return;

  const response = await fetch(
    `https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents/${documentId}`,
    { method: 'DELETE' }
  );

  const result = await response.json();
  console.log(`Deleted ${result.vectorsDeleted} vectors`);

  return result;
}
```

---

## Status Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 202 | Accepted | Document uploaded, processing started |
| 400 | Bad Request | Invalid request (missing fields, file too large) |
| 404 | Not Found | Document not found |
| 415 | Unsupported Media Type | File type not supported |
| 500 | Internal Server Error | Server-side error |

---

## Integration Examples

### React Component - File Upload

```tsx
import { useState } from 'react';

function DocumentUploader() {
  const [uploading, setUploading] = useState(false);
  const [uploadedDoc, setUploadedDoc] = useState(null);

  async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);

    try {
      // Read file as base64
      const base64 = await fileToBase64(file);

      // Upload to API
      const response = await fetch(
        'https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename: file.name,
            content: base64,
            contentType: file.type,
            metadata: {
              uploadedBy: 'user@example.com'
            }
          })
        }
      );

      const result = await response.json();
      setUploadedDoc(result);
      alert('Document uploaded successfully!');
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed');
    } finally {
      setUploading(false);
    }
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  return (
    <div>
      <input
        type="file"
        accept=".pdf,.docx,.txt,.md"
        onChange={handleFileUpload}
        disabled={uploading}
      />
      {uploading && <p>Uploading...</p>}
      {uploadedDoc && (
        <div>
          <h3>Upload Complete!</h3>
          <p>Document ID: {uploadedDoc.documentId}</p>
          <p>Status: {uploadedDoc.status}</p>
        </div>
      )}
    </div>
  );
}
```

### React Component - Document List

```tsx
import { useState, useEffect } from 'react';

function DocumentList() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    loadDocuments();
  }, [filter]);

  async function loadDocuments() {
    setLoading(true);
    try {
      const params = filter !== 'all' ? `?category=${filter}` : '';
      const response = await fetch(
        `https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents${params}`
      );
      const data = await response.json();
      setDocuments(data.documents);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(documentId) {
    if (!confirm('Delete this document?')) return;

    try {
      await fetch(
        `https://yvf4p3dpp7.execute-api.eu-west-1.amazonaws.com/dev/documents/${documentId}`,
        { method: 'DELETE' }
      );
      await loadDocuments();  // Reload list
    } catch (error) {
      console.error('Delete failed:', error);
    }
  }

  return (
    <div>
      <h2>Documents</h2>

      <select value={filter} onChange={(e) => setFilter(e.target.value)}>
        <option value="all">All Categories</option>
        <option value="technical">Technical</option>
        <option value="contracts">Contracts</option>
        <option value="financial">Financial</option>
      </select>

      {loading ? (
        <p>Loading...</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Filename</th>
              <th>Category</th>
              <th>Status</th>
              <th>Uploaded</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.documentId}>
                <td>{doc.filename}</td>
                <td>{doc.category}</td>
                <td>{doc.status}</td>
                <td>{new Date(doc.uploadedAt).toLocaleDateString()}</td>
                <td>
                  <button onClick={() => handleDelete(doc.documentId)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

---

## Processing Pipeline

When you upload a document, here's what happens:

```
1. Upload to S3 Ingestion Bucket
   ↓
2. Lambda Triggered Automatically
   ↓
3. Text Extraction (PDF/DOCX parser or OCR)
   ↓
4. Text Normalization
   ↓
5. Document Classification (AI-powered)
   ↓
6. PDF Generation (normalized version)
   ↓
7. Text Chunking (800 tokens per chunk)
   ↓
8. Embedding Generation (Titan Embeddings v2)
   ↓
9. Vector Storage (S3 Vectors)
   ↓
10. Status: completed ✅
```

**Average Processing Time:**
- Small document (< 5 pages): 5-10 seconds
- Medium document (5-20 pages): 10-30 seconds
- Large document (> 20 pages): 30-60 seconds

---

## Best Practices

### 1. Check Processing Status
After upload, poll the document details endpoint to check status:

```javascript
async function waitForProcessing(documentId, maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    const doc = await getDocumentDetails(documentId);

    if (doc.status === 'completed') {
      return doc;
    } else if (doc.status === 'failed') {
      throw new Error('Processing failed');
    }

    // Wait 2 seconds before next check
    await new Promise(resolve => setTimeout(resolve, 2000));
  }

  throw new Error('Processing timeout');
}
```

### 2. Validate File Size
Check file size before upload to avoid errors:

```javascript
const MAX_SIZE = 10 * 1024 * 1024;  // 10 MB

if (file.size > MAX_SIZE) {
  alert('File too large. Maximum size is 10MB.');
  return;
}
```

### 3. Handle Upload Progress
Show progress to users during large uploads:

```javascript
async function uploadWithProgress(file, onProgress) {
  // Implementation depends on your upload method
  // For base64: show percentage as file is read
  // For multipart: use XMLHttpRequest with progress events
}
```

### 4. Batch Uploads
For multiple files, upload sequentially or with limited concurrency:

```javascript
async function uploadMultiple(files, concurrency = 3) {
  const results = [];

  for (let i = 0; i < files.length; i += concurrency) {
    const batch = files.slice(i, i + concurrency);
    const batchResults = await Promise.all(
      batch.map(file => uploadDocument(file))
    );
    results.push(...batchResults);
  }

  return results;
}
```

---

## Troubleshooting

### Upload Fails with 413 Payload Too Large
- **Cause:** File exceeds 10MB limit
- **Solution:** Compress file or split into multiple documents

### Document Stuck in "processing" Status
- **Cause:** Processing Lambda error
- **Solution:** Check CloudWatch logs for document processor Lambda

### Upload Succeeds But Document Not Found
- **Cause:** Processing failed, document moved to failed/ prefix
- **Solution:** Check S3 bucket's `failed/` prefix for error manifest

### Unsupported File Type Error
- **Cause:** File extension not recognized
- **Solution:** Use supported formats: PDF, DOCX, TXT, MD

---

## Rate Limits (Future)

**Current:** No rate limits (development)

**Production Recommendations:**
- 10 uploads per minute per user
- 100 API calls per minute per user
- Maximum 50 concurrent uploads

---

## Next Steps

1. ✅ Import Postman collection with document endpoints
2. ✅ Test upload with a sample PDF
3. ✅ Build file upload UI component
4. ✅ Integrate with your frontend
5. ✅ Add document management dashboard

---

## Support

- **Full API Docs:** `API_DOCUMENTATION.md`
- **GitHub:** https://github.com/Marlocks-Technologies/pg-serverless-rag
- **Issues:** GitHub Issues

Ready to start uploading documents! 📄🚀
