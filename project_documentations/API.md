# Enterprise Knowledge Assistant — API Reference

Base URL: `http://localhost:8000`  
Interactive docs (Swagger UI): `http://localhost:8000/docs`  
ReDoc: `http://localhost:8000/redoc`

---

## Authentication

All endpoints except `/auth/login`, `/health`, and `/ready` require a **Bearer token** in the `Authorization` header.

```
Authorization: Bearer <access_token>
```

Tokens are obtained via `POST /auth/login` and expire after 480 minutes (configurable via `JWT_EXPIRE_MINUTES`).

**Roles**

| Role | Permissions |
|---|---|
| `employee` | Ask questions, view sources, submit feedback |
| `admin` | All of the above + ingest documents, delete documents, access admin endpoints |

---

## Endpoint Index

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/login` | None | Obtain a JWT access token |
| GET | `/auth/me` | Bearer | Get current user info |
| POST | `/ask` | Bearer | Ask a question (batch response) |
| POST | `/ask/stream` | Bearer | Ask a question (streaming response) |
| POST | `/ingest` | Admin | Upload and ingest a single document |
| POST | `/ingest/directory` | Admin | Ingest all documents in a directory |
| DELETE | `/ingest/documents/{document_id}` | Admin | Remove a document from the index |
| GET | `/ingest/jobs/{job_id}` | Bearer | Get ingestion job status |
| GET | `/ingest/runs/{run_id}` | Bearer | Get ingestion run status with all jobs |
| GET | `/sources/{chunk_id}` | Bearer | Retrieve full text of a source chunk |
| POST | `/feedback` | Bearer | Submit a thumbs-up / thumbs-down rating |
| GET | `/admin/dashboard` | Admin | Aggregate system metrics |
| GET | `/admin/feedback` | Admin | List recent feedback entries |
| GET | `/admin/feedback/export` | Admin | Export all feedback as CSV |
| POST | `/admin/cache/clear` | Admin | Clear the in-memory response cache |
| GET | `/admin/retrieval-stats` | Admin | View per-request RAG trace logs |
| GET | `/health` | None | Liveness check |
| GET | `/ready` | None | Readiness check (component status) |

---

## Auth

### `POST /auth/login`

Exchange email and password for a JWT token.

**Request body**

```json
{
  "email": "admin@example.com",
  "password": "admin123"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `email` | string | ✅ | User email address |
| `password` | string | ✅ | Plain-text password |

**Response `200 OK`**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role": "admin",
  "department": "all",
  "email": "admin@example.com"
}
```

**Error responses**

| Code | Reason |
|---|---|
| `401` | Invalid email or password |

---

### `GET /auth/me`

Return the currently authenticated user's profile.

**Response `200 OK`**

```json
{
  "id": 1,
  "email": "admin@example.com",
  "role": "admin",
  "department": "all"
}
```

**Error responses**

| Code | Reason |
|---|---|
| `401` | Missing or invalid token |

---

## Ask

### `POST /ask`

Submit a question and receive a complete RAG-generated answer in a single response. Use this when you don't need streaming.

**Request body**

```json
{
  "question": "What is the employee leave policy?",
  "session_id": "abc-123",
  "top_k": 4,
  "filters": {
    "department": "hr",
    "document_type": "policy",
    "tags": ["leave", "annual"],
    "uploaded_after": "2024-01-01"
  },
  "include_debug": false
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `question` | string | ✅ | — | Natural-language question (1–2000 chars) |
| `session_id` | string | ❌ | auto-generated UUID | Conversation session ID for multi-turn memory |
| `top_k` | integer | ❌ | config value | Number of context chunks passed to the LLM (1–20) |
| `filters` | object | ❌ | `{}` | Metadata filters for targeted retrieval (see below) |
| `include_debug` | boolean | ❌ | `false` | Include `retrieval_trace` and `latencies` in response |

**`filters` fields**

| Field | Type | Description |
|---|---|---|
| `department` | string | Filter chunks by department (e.g. `"hr"`, `"engineering"`) |
| `document_type` | string | Filter by document type (e.g. `"policy"`, `"faq"`) |
| `author` | string | Filter by document author |
| `tags` | string[] | Filter chunks that carry any of the given tags |
| `policy_version` | string | Filter by policy version string |
| `uploaded_after` | string | ISO 8601 date — only chunks from documents uploaded after this date |
| `content_types` | string[] | Filter by content type: `"text"`, `"table"` |

**Response `200 OK`**

```json
{
  "answer": "Employees receive 18 of Earned Leave (EL) annually.",
  "sources": [
    {
      "citation_id": 1,
      "document": "HR_Policy.docx",
      "page": 12,
      "chunk_id": "chunk_a1b2c3",
      "snippet": "...employees accrue 2 days of paid leave per month...",
      "score": 0.91,
      "content_type": "text",
      "extraction_method": "pdfplumber",
      "section_title": "Leave Entitlements"
    }
  ],
  "confidence": 0.91,
  "session_id": "abc-123",
  "rewritten_query": "What is the annual paid leave entitlement for employees?",
  "answerability": "answered",
  "retrieval_trace": null,
  "latencies": null,
  "prompt_version": "v2"
}
```

**Response fields**

| Field | Type | Description |
|---|---|---|
| `answer` | string | Generated answer grounded in retrieved documents |
| `sources` | CitationResponse[] | Ranked list of source chunks supporting the answer |
| `confidence` | float | Top retrieval score (0.0–1.0) |
| `session_id` | string | Session ID for subsequent follow-up questions |
| `rewritten_query` | string | Query after LLM rewriting for clarity/context |
| `answerability` | string | `answered` · `partially_answered` · `not_found` |
| `retrieval_trace` | object\|null | Debug trace (only when `include_debug: true`) |
| `latencies` | object\|null | Per-stage latency in ms (only when `include_debug: true`) |
| `prompt_version` | string\|null | Version tag of the prompt template used |

**`answerability` values**

| Value | Meaning |
|---|---|
| `answered` | A confident answer was found in the knowledge base |
| `partially_answered` | Relevant chunks were found but answer may be incomplete |
| `not_found` | No sufficiently relevant chunks found; LLM was not called |

**Error responses**

| Code | Reason |
|---|---|
| `401` | Missing or invalid token |
| `422` | Validation error (e.g. question exceeds 2000 chars) |

---

### `POST /ask/stream`

Same as `POST /ask` but returns the answer as a **stream of newline-delimited JSON events** (`application/x-ndjson`). Tokens are emitted as they are generated, enabling real-time rendering.

**Request body** — identical to `POST /ask`.

**Response** — `200 OK` with `Content-Type: application/x-ndjson`

Events are emitted one per line. Each line is a JSON object with an `event` field.

**Event: `delta`** — a token chunk from the LLM

```json
{"event": "delta", "data": {"text": "Employees are "}}
```

**Event: `final_sources`** — emitted once, after generation completes

```json
{
  "event": "final_sources",
  "data": {
    "answer": "Employees receive 18 of Earned Leave (EL) annually.",
    "sources": [
      {
        "citation_id": 1,
        "document": "HR_Policy.docx",
        "page": 12,
        "chunk_id": "chunk_a1b2c3",
        "snippet": "...employees accrue 2 days of paid leave per month...",
        "score": 0.91,
        "content_type": "text",
        "extraction_method": "pdfplumber",
        "section_title": "Leave Entitlements"
      }
    ],
    "confidence": 0.91,
    "session_id": "abc-123",
    "rewritten_query": "What is the annual paid leave entitlement for employees?",
    "answerability": "answered"
  }
}
```

**Example — curl**

```bash
curl -N -X POST http://localhost:8000/ask/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the refund policy?"}'
```

**Error responses**

| Code | Reason |
|---|---|
| `401` | Missing or invalid token |
| `422` | Validation error |

---

## Ingest

### `POST /ingest`

Upload a single document file (PDF, DOCX, TXT) and queue it for ingestion. Processing runs asynchronously in the background. **Admin only.**

**Request** — `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `file` | binary | The document file to upload |

**Example — curl**

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@HR_Policy.pdf"
```

**Response `200 OK`**

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "filename": "HR_Policy.docx",
  "status": "queued"
}
```

Use the `job_id` with `GET /ingest/jobs/{job_id}` to poll for progress.

**Error responses**

| Code | Reason |
|---|---|
| `401` | Missing or invalid token |
| `403` | User is not an admin |

---

### `POST /ingest/directory`

Queue all supported documents in a server-side directory for ingestion. **Admin only.**

**Query parameters**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | string | ❌ | `DOCUMENTS_PATH` from config | Absolute path to directory on the server |

**Response `200 OK`**

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "queued",
  "directory": "/app/data/documents"
}
```

**Error responses**

| Code | Reason |
|---|---|
| `403` | Not admin |
| `404` | Directory not found on server |

---

### `DELETE /ingest/documents/{document_id}`

Remove a document and all of its indexed chunks from both ChromaDB and the BM25 index. **Admin only.**

**Path parameters**

| Parameter | Type | Description |
|---|---|---|
| `document_id` | string | The document ID assigned during ingestion |

**Response `200 OK`**

```json
{
  "document_id": "6ad50a0362b8b07cb2121e9742e7254e",
  "chroma_chunks_deleted": 14,
  "bm25_chunks_deleted": 14,
  "file_deleted": true,
  "status": "deleted"
}
```

**Error responses**

| Code | Reason |
|---|---|
| `403` | Not admin |
| `404` | Document not found in index |

---

### `GET /ingest/jobs/{job_id}`

Poll the status of a single ingestion job.

**Path parameters**

| Parameter | Type | Description |
|---|---|---|
| `job_id` | string | Job ID returned by `POST /ingest` |

**Response `200 OK`**

```json
{
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "HR_Policy.docx",
  "status": "done",
  "stage": "embedding",
  "progress": 1.0,
  "chunks_added": 28,
  "ocr_pages": 3,
  "tables_extracted": 2,
  "error": "",
  "started_at": "2025-06-10T09:00:00Z",
  "finished_at": "2025-06-10T09:00:45Z"
}
```

**`status` values:** `queued` · `processing` · `done` · `failed`

**Error responses**

| Code | Reason |
|---|---|
| `401` | Missing or invalid token |
| `404` | Job ID not found |

---

### `GET /ingest/runs/{run_id}`

Get the aggregate status of an ingestion run along with all individual job records within it.

**Path parameters**

| Parameter | Type | Description |
|---|---|---|
| `run_id` | string | Run ID returned by `POST /ingest` or `POST /ingest/directory` |

**Response `200 OK`**

```json
{
  "run": {
    "run_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "done",
    "files_seen": 5,
    "files_added": 4,
    "files_updated": 0,
    "files_skipped": 1,
    "files_failed": 0,
    "chunks_added": 112,
    "ocr_pages": 7,
    "tables_extracted": 6,
    "started_at": "2025-06-10T09:00:00Z",
    "finished_at": "2025-06-10T09:02:10Z"
  },
  "jobs": [ /* array of IngestJobResponse objects */ ]
}
```

---

## Sources

### `GET /sources/{chunk_id}`

Retrieve the full text and metadata of a specific source chunk. Access is denied if the chunk's `access_roles` metadata does not include the current user's role (admins bypass this check).

**Path parameters**

| Parameter | Type | Description |
|---|---|---|
| `chunk_id` | string | Chunk ID from a `CitationResponse.chunk_id` field |

**Response `200 OK`**

```json
{
  "chunk_id": "chunk_a1b2c3",
  "document": "HR_Policy.docx",
  "page": 12,
  "text": "Full text of the chunk as extracted from the source document...",
  "content_type": "text",
  "extraction_method": "pdfplumber",
  "section_title": "Leave Entitlements",
  "department": "hr",
  "document_id": "doc_hr_policy_v3",
  "tags": "leave,annual,policy",
  "policy_version": "3.1",
  "uploaded_at": "2025-05-01T10:30:00Z"
}
```

**Error responses**

| Code | Reason |
|---|---|
| `401` | Missing or invalid token |
| `403` | User's role does not have access to this chunk |
| `404` | Chunk ID not found |

---

## Feedback

### `POST /feedback`

Submit a thumbs-up or thumbs-down rating for an answer. Re-submitting feedback for the same `message_id` replaces the previous rating.

**Request body**

```json
{
  "message_id": "msg-uuid-001",
  "session_id": "abc-123",
  "question": "What is the employee leave policy?",
  "answer": "Employees receive 18 of Earned Leave (EL) annually.",
  "rating": 1,
  "category": "incorrect",
  "comment": "The policy was updated in 2024 to 28 days."
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `message_id` | string | ❌ | Unique identifier for the answer being rated |
| `session_id` | string | ❌ | Session the answer belongs to |
| `question` | string | ✅ | The original question |
| `answer` | string | ✅ | The answer being rated |
| `rating` | integer | ✅ | `1` = thumbs up · `0` = neutral · `-1` = thumbs down |
| `category` | string | ❌ | `incorrect` · `missing_source` · `incomplete` · `slow` · `other` |
| `comment` | string | ❌ | Optional free-text comment |

**Response `200 OK`**

```json
{
  "id": "feedback-uuid-001",
  "status": "recorded"
}
```

**Error responses**

| Code | Reason |
|---|---|
| `401` | Missing or invalid token |
| `422` | `rating` outside the range -1 to 1 |

---

## Admin

All admin endpoints require the `admin` role.

### `GET /admin/dashboard`

Return aggregate metrics for the admin dashboard.

**Response `200 OK`**

```json
{
  "index": {
    "chroma_collection": "eka_v1",
    "vector_chunks": 1450,
    "bm25_chunks": 1450,
    "embedding_model": "BAAI/bge-small-en-v1.5"
  },
  "feedback": {
    "total": 87,
    "positive": 72,
    "negative": 15
  },
  "ingestion": {
    "runs": 12,
    "total_chunks": 1450
  },
  "performance": {
    "total_requests": 340,
    "avg_latency_ms": 4200,
    "answerability_ratio": 0.88
  },
  "config": {
    "llm_model": "qwen3:4b",
    "reranker_model": "",
    "top_k_semantic": 8,
    "top_k_context": 4
  }
}
```

---

### `GET /admin/feedback`

List the most recent feedback entries.

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | `50` | Maximum number of entries to return |

**Response `200 OK`** — array of feedback records

```json
[
  {
    "id": "feedback-uuid-001",
    "user_id": 3,
    "session_id": "abc-123",
    "message_id": "msg-uuid-001",
    "question": "What is the leave policy?",
    "answer": "Employees get 24 days...",
    "rating": -1,
    "category": "incorrect",
    "comment": "Policy was updated in 2024.",
    "created_at": "2025-06-10T10:15:00Z"
  }
]
```

---

### `GET /admin/feedback/export`

Download all feedback as a CSV file.

**Response `200 OK`** — `Content-Type: text/csv`  
`Content-Disposition: attachment; filename=feedback_export.csv`

CSV columns: `created_at`, `user_email`, `question`, `answer`, `rating`, `category`, `comment`

---

### `POST /admin/cache/clear`

Clear the in-memory response cache. Returns the number of entries removed.

**Response `200 OK`**

```json
{
  "status": "ok",
  "entries_cleared": 42
}
```

If caching is disabled:

```json
{
  "status": "skipped",
  "message": "Cache is disabled or not initialised."
}
```

---

### `GET /admin/retrieval-stats`

Return detailed per-request RAG trace logs for debugging retrieval quality.

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | `50` | Maximum number of traces to return |

**Response `200 OK`** — array of trace objects (schema defined by `app/observability/trace.py`)

---

## Health

### `GET /health`

Liveness probe. Always returns `200` while the process is running.

**Response `200 OK`**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

### `GET /ready`

Readiness probe. Checks connectivity to ChromaDB and Ollama.

**Response `200 OK`**

```json
{
  "status": "ok",
  "components": {
    "chroma": "ok",
    "ollama": "ok",
    "ocr_tesseract": "available"
  }
}
```

`status` is `"degraded"` if any component reports an error. Individual component values: `ok` · `available` · `disabled` · `model_not_found` · `error: <message>`.

---

## Error Format

All API errors follow the standard FastAPI error envelope:

```json
{
  "detail": "Human-readable error message."
}
```

**Common HTTP status codes**

| Code | Meaning |
|---|---|
| `200` | Success |
| `401` | Unauthenticated — missing, expired, or invalid JWT |
| `403` | Forbidden — authenticated but insufficient role |
| `404` | Resource not found |
| `422` | Validation error — request body failed Pydantic validation |
| `500` | Internal server error |

---

## Complete Usage Example

```bash
# 1. Log in and capture the token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Upload a document
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@HR_Policy.pdf"

# 3. Ask a question
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the employee leave policy?",
    "filters": {"department": "hr"}
  }'

# 4. Stream the answer
curl -N -X POST http://localhost:8000/ask/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the refund policy?"}'

# 5. Submit feedback
curl -X POST http://localhost:8000/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the employee leave policy?",
    "answer": "24 days annually.",
    "rating": 1
  }'

# 6. View admin dashboard
curl http://localhost:8000/admin/dashboard \
  -H "Authorization: Bearer $TOKEN"
```
