# KnowFlow HTTP API Reference (Complete)

A complete reference for KnowFlow's RESTful API. This documentation is based on KnowFlow v2.1.5, which extends RAGFlow with enhanced features including MinerU layout parser and parent-child chunking strategies.

**Version**: KnowFlow v2.1.5
**Last Updated**: January 2025
**Based on**: RAGFlow v0.20.1

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Error Codes](#error-codes)
3. [OpenAI-Compatible API](#openai-compatible-api)
4. [Dataset Management](#dataset-management)
5. [Document Management](#document-management)
6. [Chunk Management](#chunk-management)
7. [Chat Assistant Management](#chat-assistant-management)
8. [Session Management](#session-management)
9. [Agent Management](#agent-management)
10. [System APIs](#system-apis)

---

## Getting Started

### Authentication

All API requests require authentication using an API key in the Authorization header:

```bash
Authorization: Bearer <YOUR_API_KEY>
```

To obtain your API key:
1. Log in to KnowFlow web interface
2. Navigate to Settings > API Key
3. Copy your API key

### Base URL

```
http://<your-server>:9380
```

Default development URL: `http://localhost:9380`

### Common Request Headers

```bash
Content-Type: application/json
Authorization: Bearer <YOUR_API_KEY>
```

---

## Error Codes

| Code | Message               | Description                |
| ---- | --------------------- | -------------------------- |
| 0    | Success               | Request successful         |
| 102  | Invalid Parameter     | Required parameter missing or invalid |
| 103  | Authorization Failed  | Permission denied          |
| 400  | Bad Request           | Invalid request parameters |
| 401  | Unauthorized          | Unauthorized access        |
| 403  | Forbidden             | Access denied              |
| 404  | Not Found             | Resource not found         |
| 500  | Internal Server Error | Server internal error      |
| 1001 | Invalid Chunk ID      | Invalid Chunk ID           |
| 1002 | Chunk Update Failed   | Chunk update failed        |

---

## OpenAI-Compatible API

### Create Chat Completion

**POST** `/api/v1/chats_openai/{chat_id}/chat/completions`

Creates a model response for a given chat conversation using OpenAI-compatible format.

#### Request

- Method: POST
- URL: `/api/v1/chats_openai/{chat_id}/chat/completions`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/chats_openai/{chat_id}/chat/completions \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
        "model": "model",
        "messages": [{"role": "user", "content": "What is machine learning?"}],
        "stream": true
      }'
```

##### Request Parameters

- `chat_id` (*Path parameter*) `string`, **Required**
  - The chat assistant ID

- `model` (*Body parameter*) `string`, **Required**
  - The model to use (server will parse automatically)

- `messages` (*Body parameter*) `array<object>`, **Required**
  - Chat message history
  - Must contain at least one message with `user` role
  - Format: `[{"role": "user", "content": "text"}]`

- `stream` (*Body parameter*) `boolean`
  - Whether to stream the response
  - Default: `false`

#### Response

Stream Response:

```json
data:{"id": "chatcmpl-xxx", "choices": [{"delta": {"content": "Machine learning is...", "role": "assistant"}, "finish_reason": null, "index": 0}], "created": 1755084508, "model": "model", "object": "chat.completion.chunk"}

data:[DONE]
```

Non-stream Response:

```json
{
  "choices": [{
    "finish_reason": "stop",
    "index": 0,
    "message": {
      "content": "Machine learning is a subset of artificial intelligence...",
      "role": "assistant"
    }
  }],
  "created": 1755084403,
  "id": "chatcmpl-xxx",
  "model": "model",
  "object": "chat.completion",
  "usage": {
    "completion_tokens": 55,
    "prompt_tokens": 5,
    "total_tokens": 60
  }
}
```

---

### Create Agent Completion

**POST** `/api/v1/agents_openai/{agent_id}/chat/completions`

Creates a model response for a given agent conversation using OpenAI-compatible format.

#### Request

- Method: POST
- URL: `/api/v1/agents_openai/{agent_id}/chat/completions`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/agents_openai/{agent_id}/chat/completions \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
        "model": "model",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": true,
        "session_id": "optional_session_id"
      }'
```

##### Request Parameters

- `agent_id` (*Path parameter*) `string`, **Required**
  - The agent ID

- `model` (*Body parameter*) `string`, **Required**
  - The model to use

- `messages` (*Body parameter*) `array<object>`, **Required**
  - Chat message history

- `stream` (*Body parameter*) `boolean`
  - Whether to stream the response

- `session_id` (*Body parameter*) `string`
  - Agent session ID (optional)

#### Response

Similar to Chat Completion API, with additional `reference` field containing retrieved chunks.

---

## Dataset Management

### Create Dataset

**POST** `/api/v1/datasets`

Creates a new dataset (knowledge base) with specified configuration.

#### Request

- Method: POST
- URL: `/api/v1/datasets`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/datasets \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "name": "My Knowledge Base",
       "description": "A test knowledge base",
       "embedding_model": "BAAI/bge-m3@SILICONFLOW",
       "chunk_method": "smart",
       "parser_config": {
         "layout_recognize": "mineru",
         "chunk_token_num": 256
       }
     }'
```

##### Request Parameters

- `name` (*Body parameter*) `string`, **Required**
  - The unique name of the dataset to create
  - Maximum 128 characters
  - Case-insensitive

- `description` (*Body parameter*) `string`
  - A brief description of the dataset
  - Maximum 65535 characters

- `avatar` (*Body parameter*) `string`
  - Base64 encoding of the avatar
  - Maximum 65535 characters

- `embedding_model` (*Body parameter*) `string`
  - The embedding model identifier
  - Format: `<model_name>@<provider>`
  - Example: `"BAAI/bge-m3@SILICONFLOW"`
  - Maximum 255 characters
  - **Important**: Must include both model name and provider separated by `@`

- `permission` (*Body parameter*) `enum<string>`
  - Access control for the dataset
  - Options:
    - `"me"`: (Default) Only you can manage
    - `"team"`: All team members can manage

- `chunk_method` (*Body parameter*) `enum<string>`
  - The chunking method for document parsing
  - Available options:
    - `"naive"`: General chunking (default)
    - `"smart"`: Smart chunking with structure awareness
    - `"book"`: Optimized for books
    - `"paper"`: Optimized for academic papers
    - `"presentation"`: Optimized for slides
    - `"qa"`: Question & Answer format
    - `"table"`: Table extraction
    - `"manual"`: Manual chunking
    - `"one"`: Single chunk per document
    - `"email"`: Email format
    - `"laws"`: Legal documents
    - `"picture"`: Image-focused
    - `"tag"`: Tag-based chunking

- `parser_config` (*Body parameter*) `object`
  - Configuration for the document parser
  - Attributes:
    - `layout_recognize` `string`: Layout parser to use
      - `"deepdoc"`: DeepDOC parser (default)
      - `"mineru"`: MinerU parser (recommended for complex layouts)
      - `"dots"`: DOTS parser
      - **Important**: Must be a string, not boolean
    - `chunk_token_num` `integer`: Target token count per chunk
      - Default: 512
      - Range: 1-2048
    - `delimiter` `string`: Delimiter for chunking
      - Default: `"\n"`
    - `html4excel` `boolean`: Convert Excel to HTML
      - Default: `false`
    - `auto_keywords` `integer`: Number of keywords to auto-generate
      - Default: 0
      - Range: 0-32
    - `auto_questions` `integer`: Number of questions to auto-generate
      - Default: 0
      - Range: 0-10
    - `task_page_size` `integer`: Pages per processing task (PDF only)
      - Default: 12

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "4345aa0ea1a311f0b45566fc51ac58df",
    "name": "My Knowledge Base",
    "description": "A test knowledge base",
    "embedding_model": "BAAI/bge-m3@SILICONFLOW",
    "chunk_method": "smart",
    "parser_config": {
      "layout_recognize": "mineru",
      "chunk_token_num": 256
    },
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:30:00Z",
    "tenant_id": "user123",
    "status": "1",
    "document_count": 0,
    "chunk_count": 0
  }
}
```

Failure (HTTP 400):

```json
{
  "code": 102,
  "message": "Embedding model identifier must follow <model_name>@<provider> format"
}
```

---

### List Datasets

**GET** `/api/v1/datasets`

Lists all datasets for the authenticated user with optional filtering and pagination.

#### Request

- Method: GET
- URL: `/api/v1/datasets?page={page}&page_size={page_size}&orderby={orderby}&desc={desc}&name={dataset_name}&id={dataset_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/datasets?page=1&page_size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `page` (*Query parameter*) `integer`
  - Page number for pagination
  - Default: 1
  - Minimum: 1

- `page_size` (*Query parameter*) `integer`
  - Number of items per page
  - Default: 30
  - Range: 1-100

- `orderby` (*Query parameter*) `string`
  - Sort by attribute
  - Options: `create_time` (default), `update_time`

- `desc` (*Query parameter*) `boolean`
  - Sort in descending order
  - Default: `true`

- `id` (*Query parameter*) `string`
  - Filter by specific dataset ID
  - When provided, returns only that dataset

- `name` (*Query parameter*) `string`
  - Filter by dataset name (partial match)

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "datasets": [
      {
        "id": "4345aa0ea1a311f0b45566fc51ac58df",
        "name": "My Knowledge Base",
        "description": "A test knowledge base",
        "embedding_model": "BAAI/bge-m3@SILICONFLOW",
        "chunk_method": "smart",
        "parser_config": {
          "layout_recognize": "mineru",
          "chunk_token_num": 256
        },
        "created_at": "2025-01-15T10:30:00Z",
        "document_count": 5,
        "chunk_count": 245
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```

---

### Update Dataset

**PUT** `/api/v1/datasets/{dataset_id}`

Updates an existing dataset's properties.

#### Request

- Method: PUT
- URL: `/api/v1/datasets/{dataset_id}`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request PUT \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "name": "Updated Knowledge Base",
       "description": "Updated description"
     }'
```

##### Request Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID to update

- `name` (*Body parameter*) `string`
  - New name for the dataset
  - Maximum 128 characters

- `description` (*Body parameter*) `string`
  - New description for the dataset

- `embedding_model` (*Body parameter*) `string`
  - New embedding model

- `chunk_method` (*Body parameter*) `enum<string>`
  - New chunking method

- `parser_config` (*Body parameter*) `object`
  - New parser configuration

- `permission` (*Body parameter*) `enum<string>`
  - New permission setting

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "4345aa0ea1a311f0b45566fc51ac58df",
    "name": "Updated Knowledge Base",
    "description": "Updated description",
    "updated_at": "2025-01-15T11:00:00Z"
  }
}
```

---

### Delete Datasets

**DELETE** `/api/v1/datasets`

Deletes one or more datasets.

#### Request

- Method: DELETE
- URL: `/api/v1/datasets`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:9380/api/v1/datasets \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "ids": ["4345aa0ea1a311f0b45566fc51ac58df"]
     }'
```

##### Request Parameters

- `ids` (*Body parameter*) `array<string>`, **Required**
  - List of dataset IDs to delete
  - Minimum: 1 ID
  - If empty, all datasets will be deleted (use with caution!)

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

### Get Knowledge Graph

**GET** `/api/v1/datasets/{dataset_id}/knowledge_graph`

Retrieves the knowledge graph for a specified dataset.

#### Request

- Method: GET
- URL: `/api/v1/datasets/{dataset_id}/knowledge_graph`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/knowledge_graph \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "nodes": [
      {"id": "entity1", "label": "Entity 1", "type": "concept"},
      {"id": "entity2", "label": "Entity 2", "type": "concept"}
    ],
    "edges": [
      {"source": "entity1", "target": "entity2", "relation": "related_to"}
    ]
  }
}
```

---

### Delete Knowledge Graph

**DELETE** `/api/v1/datasets/{dataset_id}/knowledge_graph`

Deletes the knowledge graph for a specified dataset.

#### Request

- Method: DELETE
- URL: `/api/v1/datasets/{dataset_id}/knowledge_graph`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/knowledge_graph \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

## Document Management

### Upload Document

**POST** `/api/v1/datasets/{dataset_id}/documents`

Uploads a document to a dataset for parsing and chunking.

#### Request

- Method: POST
- URL: `/api/v1/datasets/{dataset_id}/documents`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`
  - **Note**: Do NOT set `Content-Type` for file uploads (multipart/form-data is set automatically)

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --form 'file=@/path/to/document.pdf' \
     --form 'parser_id=smart' \
     --form 'parser_config={"chunk_token_num":256,"layout_recognize":"mineru"}'
```

##### Request Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID to upload to

- `file` (*Form parameter*) `file`, **Required**
  - The document file to upload
  - Supported formats: PDF, DOCX, TXT, MD, HTML, XLSX, PPTX, PNG, JPG, etc.
  - Maximum size: 1GB (configurable via MAX_CONTENT_LENGTH)

- `parser_id` (*Form parameter*) `string`
  - Override the dataset's default chunk method for this document
  - Same options as `chunk_method` in Create Dataset
  - Defaults to dataset's chunk_method

- `parser_config` (*Form parameter*) `string` (JSON)
  - Override the dataset's parser config for this document
  - Must be a JSON string
  - Example: `'{"chunk_token_num":256,"layout_recognize":"mineru"}'`

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": "c6db195ea4b811f097ee66fc51ac58df",
      "name": "document.pdf",
      "size": 1024567,
      "type": "application/pdf",
      "parser_id": "smart",
      "parser_config": {
        "chunk_token_num": 256,
        "layout_recognize": "mineru"
      },
      "status": "0",
      "progress": 0,
      "created_at": "2025-01-15T12:00:00Z",
      "updated_at": "2025-01-15T12:00:00Z"
    }
  ]
}
```

**Status Codes**:
- `"0"`: Parsing (in progress)
- `"1"`: Completed (parsing successful)
- `"2"`: Failed (parsing error)

---

### List Documents

**GET** `/api/v1/datasets/{dataset_id}/documents`

Lists all documents in a dataset with optional filtering and pagination.

#### Request

- Method: GET
- URL: `/api/v1/datasets/{dataset_id}/documents?page={page}&page_size={page_size}&orderby={orderby}&desc={desc}&keywords={keywords}&id={document_id}&name={document_name}&create_time_from={timestamp}&create_time_to={timestamp}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents?page=1&page_size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID

- `page` (*Query parameter*) `integer`
  - Page number
  - Default: 1

- `page_size` (*Query parameter*) `integer`
  - Items per page
  - Default: 30
  - Range: 1-100

- `orderby` (*Query parameter*) `string`
  - Sort by attribute
  - Options: `create_time` (default), `update_time`

- `desc` (*Query parameter*) `boolean`
  - Sort in descending order
  - Default: `true`

- `keywords` (*Query parameter*) `string`
  - Search keywords in document name

- `id` (*Query parameter*) `string`
  - Filter by document ID

- `name` (*Query parameter*) `string`
  - Filter by document name

- `create_time_from` (*Query parameter*) `integer`
  - Filter by creation time (Unix timestamp)

- `create_time_to` (*Query parameter*) `integer`
  - Filter by creation time (Unix timestamp)

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "documents": [
      {
        "id": "c6db195ea4b811f097ee66fc51ac58df",
        "name": "document.pdf",
        "size": 1024567,
        "type": "application/pdf",
        "parser_id": "smart",
        "status": "1",
        "progress": 100,
        "chunk_count": 45,
        "created_at": "2025-01-15T12:00:00Z",
        "updated_at": "2025-01-15T12:05:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```

---

### Get Document Details

**GET** `/api/v1/datasets/{dataset_id}/documents/{document_id}`

Retrieves detailed information about a specific document.

#### Request

- Method: GET
- URL: `/api/v1/datasets/{dataset_id}/documents/{document_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents/c6db195ea4b811f097ee66fc51ac58df \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "c6db195ea4b811f097ee66fc51ac58df",
    "name": "document.pdf",
    "size": 1024567,
    "type": "application/pdf",
    "parser_id": "smart",
    "parser_config": {
      "chunk_token_num": 256,
      "layout_recognize": "mineru"
    },
    "status": "1",
    "progress": 100,
    "chunk_count": 45,
    "page_count": 10,
    "created_at": "2025-01-15T12:00:00Z",
    "updated_at": "2025-01-15T12:05:00Z"
  }
}
```

---

### Update Document

**PUT** `/api/v1/datasets/{dataset_id}/documents/{document_id}`

Updates document properties (name, parser settings).

#### Request

- Method: PUT
- URL: `/api/v1/datasets/{dataset_id}/documents/{document_id}`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request PUT \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents/c6db195ea4b811f097ee66fc51ac58df \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "name": "updated_document.pdf",
       "parser_id": "smart",
       "parser_config": {
         "chunk_token_num": 512,
         "layout_recognize": "mineru"
       }
     }'
```

##### Request Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID

- `document_id` (*Path parameter*) `string`, **Required**
  - The document ID

- `name` (*Body parameter*) `string`
  - New document name

- `parser_id` (*Body parameter*) `string`
  - New chunking method

- `parser_config` (*Body parameter*) `object`
  - New parser configuration

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

### Delete Documents

**DELETE** `/api/v1/datasets/{dataset_id}/documents`

Deletes one or more documents from a dataset.

#### Request

- Method: DELETE
- URL: `/api/v1/datasets/{dataset_id}/documents`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "ids": ["c6db195ea4b811f097ee66fc51ac58df"]
     }'
```

##### Request Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID

- `ids` (*Body parameter*) `array<string>`, **Required**
  - List of document IDs to delete
  - If empty, all documents in the dataset will be deleted

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

## Chunk Management

### Create Chunk (Dataset Level)

**POST** `/api/v1/datasets/{dataset_id}/chunks`

Creates chunks at the dataset level (not tied to a specific document).

#### Request

- Method: POST
- URL: `/api/v1/datasets/{dataset_id}/chunks`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/chunks \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "document_id": "c6db195ea4b811f097ee66fc51ac58df",
       "content": "This is a chunk content",
       "important_keywords": ["keyword1", "keyword2"]
     }'
```

##### Request Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID

- `document_id` (*Body parameter*) `string`, **Required**
  - The document ID this chunk belongs to

- `content` (*Body parameter*) `string`, **Required**
  - The text content of the chunk

- `important_keywords` (*Body parameter*) `array<string>`
  - Key terms or phrases to tag with the chunk

- `questions` (*Body parameter*) `array<string>`
  - Questions that this chunk can answer

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "chunk_id": "8c204dcbb8955158"
  }
}
```

---

### Create Chunk (Document Level)

**POST** `/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks`

Adds a chunk to a specified document.

#### Request

- Method: POST
- URL: `/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents/c6db195ea4b811f097ee66fc51ac58df/chunks \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "content": "This is a chunk content",
       "important_keywords": ["keyword1", "keyword2"],
       "questions": ["What is this about?"]
     }'
```

##### Request Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID

- `document_id` (*Path parameter*) `string`, **Required**
  - The document ID

- `content` (*Body parameter*) `string`, **Required**
  - The text content of the chunk

- `important_keywords` (*Body parameter*) `array<string>`
  - Key terms or phrases to tag with the chunk

- `questions` (*Body parameter*) `array<string>`
  - Questions that this chunk can answer

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "chunk": {
      "id": "8c204dcbb8955158",
      "content": "This is a chunk content",
      "important_keywords": ["keyword1", "keyword2"],
      "questions": ["What is this about?"],
      "create_time": "2025-01-15T12:10:00Z",
      "dataset_id": "4345aa0ea1a311f0b45566fc51ac58df",
      "document_id": "c6db195ea4b811f097ee66fc51ac58df"
    }
  }
}
```

---

### List Document Chunks

**GET** `/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks`

Lists all chunks of a document with optional filtering.

#### Request

- Method: GET
- URL: `/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks?keywords={keywords}&page={page}&page_size={page_size}&id={id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents/c6db195ea4b811f097ee66fc51ac58df/chunks?page=1&page_size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID

- `document_id` (*Path parameter*) `string`, **Required**
  - The document ID

- `keywords` (*Query parameter*) `string`
  - Filter chunks by keywords in content

- `page` (*Query parameter*) `integer`
  - Page number
  - Default: 1

- `page_size` (*Query parameter*) `integer`
  - Items per page
  - Default: 1024
  - Range: 1-1024

- `id` (*Query parameter*) `string`
  - Filter by specific chunk ID

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "chunks": [
      {
        "id": "8c204dcbb8955158",
        "content": "This is the chunk content extracted from the document...",
        "important_keywords": ["keyword1", "keyword2"],
        "positions": [[1, 100, 200, 300, 400]],
        "page_number": 1,
        "available": true,
        "doc_id": "c6db195ea4b811f097ee66fc51ac58df",
        "dataset_id": "4345aa0ea1a311f0b45566fc51ac58df",
        "created_at": "2025-01-15T12:05:00Z"
      }
    ],
    "doc": {
      "id": "c6db195ea4b811f097ee66fc51ac58df",
      "name": "document.pdf",
      "chunk_count": 45,
      "chunk_method": "smart",
      "parser_config": {
        "chunk_token_num": 256,
        "layout_recognize": "mineru"
      }
    },
    "total": 45,
    "page": 1,
    "page_size": 10
  }
}
```

**Chunk Position Format**:
- For MinerU parser: `[page_idx, x1, x2, y1, y2]` (72 DPI PDF coordinates)
- For DOTS parser: `[x1, y1, x2, y2]` (200 DPI image coordinates)

---

### Update Chunk

**PUT** `/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks/{chunk_id}`

Updates content or configurations for a specified chunk.

#### Request

- Method: PUT
- URL: `/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks/{chunk_id}`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request PUT \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents/c6db195ea4b811f097ee66fc51ac58df/chunks/8c204dcbb8955158 \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "content": "Updated chunk content",
       "important_keywords": ["new_keyword"],
       "available": true
     }'
```

##### Request Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID

- `document_id` (*Path parameter*) `string`, **Required**
  - The document ID

- `chunk_id` (*Path parameter*) `string`, **Required**
  - The chunk ID to update

- `content` (*Body parameter*) `string`
  - New text content of the chunk

- `important_keywords` (*Body parameter*) `array<string>`
  - New list of key terms or phrases

- `available` (*Body parameter*) `boolean`
  - The chunk's availability status in the dataset
  - `true`: Available (default)
  - `false`: Unavailable (excluded from retrieval)

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

### Delete Chunks (Dataset Level)

**DELETE** `/api/v1/datasets/{dataset_id}/chunks`

Deletes chunks at the dataset level.

#### Request

- Method: DELETE
- URL: `/api/v1/datasets/{dataset_id}/chunks`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/chunks \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "chunk_ids": ["8c204dcbb8955158", "9d305eccc9066269"]
     }'
```

##### Request Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID

- `chunk_ids` (*Body parameter*) `array<string>`
  - List of chunk IDs to delete
  - If empty, all chunks in the dataset will be deleted

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

### Delete Chunks (Document Level)

**DELETE** `/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks`

Deletes chunks from a specified document.

#### Request

- Method: DELETE
- URL: `/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents/c6db195ea4b811f097ee66fc51ac58df/chunks \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "chunk_ids": ["8c204dcbb8955158"]
     }'
```

##### Request Parameters

- `dataset_id` (*Path parameter*) `string`, **Required**
  - The dataset ID

- `document_id` (*Path parameter*) `string`, **Required**
  - The document ID

- `chunk_ids` (*Body parameter*) `array<string>`
  - List of chunk IDs to delete
  - If empty, all chunks of the specified document will be deleted

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

### Retrieve Chunks (Semantic Search)

**POST** `/api/v1/retrieval`

Performs semantic search across one or more datasets to retrieve relevant chunks.

#### Request

- Method: POST
- URL: `/api/v1/retrieval`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/retrieval \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "question": "What is machine learning?",
       "dataset_ids": ["4345aa0ea1a311f0b45566fc51ac58df"],
       "page": 1,
       "page_size": 5,
       "similarity_threshold": 0.2,
       "vector_similarity_weight": 0.3,
       "keyword": true,
       "highlight": true
     }'
```

##### Request Parameters

- `question` (*Body parameter*) `string`, **Required**
  - The search query text
  - Minimum 1 character

- `dataset_ids` (*Body parameter*) `array<string>`
  - List of dataset IDs to search in
  - Either `dataset_ids` or `document_ids` must be provided

- `document_ids` (*Body parameter*) `array<string>`
  - List of document IDs to search in
  - Either `dataset_ids` or `document_ids` must be provided
  - All documents must use the same embedding model

- `page` (*Body parameter*) `integer`
  - Page number for results
  - Default: 1

- `page_size` (*Body parameter*) `integer`
  - Number of chunks to return per page
  - Default: 30
  - Range: 1-100

- `similarity_threshold` (*Body parameter*) `float`
  - Minimum similarity score (0.0-1.0)
  - Default: 0.2
  - Chunks below this threshold are filtered out

- `vector_similarity_weight` (*Body parameter*) `float`
  - Weight for vector similarity vs. keyword matching
  - Default: 0.3
  - Range: 0.0-1.0
  - Higher value = more weight on semantic similarity
  - If x is vector weight, then (1-x) is keyword weight

- `top_k` (*Body parameter*) `integer`
  - Maximum number of chunks to retrieve before reranking
  - Default: 1024

- `rerank_id` (*Body parameter*) `string`
  - ID of the rerank model to use
  - If not specified, vector cosine similarity will be used

- `keyword` (*Body parameter*) `boolean`
  - Enable keyword-based matching
  - Default: `false`

- `highlight` (*Body parameter*) `boolean`
  - Enable highlighting of matched terms in results
  - Default: `false`

- `cross_languages` (*Body parameter*) `array<string>`
  - Languages to translate query into for cross-language retrieval
  - Example: `["en", "zh", "ja"]`

- `metadata_condition` (*Body parameter*) `object`
  - Metadata filtering conditions
  - Example: `{"author": "John", "year": 2024}`

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "chunks": [
      {
        "id": "8c204dcbb8955158",
        "content": "Machine learning is a subset of artificial intelligence...",
        "document_id": "c6db195ea4b811f097ee66fc51ac58df",
        "document_name": "document.pdf",
        "dataset_id": "4345aa0ea1a311f0b45566fc51ac58df",
        "positions": [[1, 100, 200, 300, 400]],
        "page_number": 1,
        "similarity": 0.856,
        "vector_similarity": 0.892,
        "term_similarity": 0.745,
        "important_keywords": ["machine learning", "artificial intelligence"],
        "image_id": ""
      }
    ],
    "total": 45,
    "page": 1,
    "page_size": 5
  }
}
```

**Similarity Scores**:
- `similarity`: Overall combined score
- `vector_similarity`: Semantic embedding similarity (0.0-1.0)
- `term_similarity`: Keyword/BM25 similarity (0.0-1.0)

---

## Chat Assistant Management

### Create Chat Assistant

**POST** `/api/v1/chats`

Creates a chat assistant with specified configuration.

#### Request

- Method: POST
- URL: `/api/v1/chats`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/chats \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "name": "My Assistant",
       "dataset_ids": ["4345aa0ea1a311f0b45566fc51ac58df"],
       "llm": {
         "model_name": "qwen-plus@Tongyi-Qianwen",
         "temperature": 0.1,
         "top_p": 0.3
       },
       "prompt": {
         "similarity_threshold": 0.2,
         "top_n": 6,
         "opener": "Hi! I am your assistant. How can I help you?"
       }
     }'
```

##### Request Parameters

- `name` (*Body parameter*) `string`, **Required**
  - The name of the chat assistant
  - Must be unique

- `avatar` (*Body parameter*) `string`
  - Base64 encoding of the avatar

- `dataset_ids` (*Body parameter*) `array<string>`
  - The IDs of the associated datasets (knowledge bases)

- `llm` (*Body parameter*) `object`
  - LLM settings for the chat assistant
  - Attributes:
    - `model_name` `string`: The chat model name
      - If not set, user's default chat model will be used
    - `temperature` `float`: Randomness of predictions
      - Default: 0.1
      - Range: 0.0-1.0
    - `top_p` `float`: Nucleus sampling threshold
      - Default: 0.3
      - Range: 0.0-1.0
    - `presence_penalty` `float`: Penalty for repeating information
      - Default: 0.4
      - Range: 0.0-2.0
    - `frequency_penalty` `float`: Penalty for repeating words
      - Default: 0.7
      - Range: 0.0-2.0

- `prompt` (*Body parameter*) `object`
  - Instructions for the LLM
  - Attributes:
    - `similarity_threshold` `float`: Minimum similarity score
      - Default: 0.2
      - Range: 0.0-1.0
    - `keywords_similarity_weight` `float`: Weight of keyword similarity
      - Default: 0.7
      - Range: 0.0-1.0
    - `top_n` `integer`: Number of top chunks to feed to LLM
      - Default: 6
    - `variables` `array<object>`: Variables for system prompt
      - Default: `[{"key": "knowledge", "optional": true}]`
      - `knowledge` is reserved for retrieved chunks
    - `rerank_model` `string`: ID of rerank model to use
    - `top_k` `integer`: Top-k for reranking
      - Default: 1024
    - `empty_response` `string`: Response when nothing is retrieved
    - `opener` `string`: Opening greeting
      - Default: `"Hi! I am your assistant, can I help you?"`
    - `show_quote` `boolean`: Show source of text
      - Default: `true`
    - `prompt` `string`: The actual prompt content

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "b1f2f15691f911ef81180242ac120003",
    "name": "My Assistant",
    "avatar": "",
    "dataset_ids": ["4345aa0ea1a311f0b45566fc51ac58df"],
    "description": "A helpful Assistant",
    "language": "English",
    "llm": {
      "model_name": "qwen-plus@Tongyi-Qianwen",
      "temperature": 0.1,
      "top_p": 0.3,
      "presence_penalty": 0.4,
      "frequency_penalty": 0.7
    },
    "prompt": {
      "similarity_threshold": 0.2,
      "keywords_similarity_weight": 0.3,
      "top_n": 6,
      "opener": "Hi! I am your assistant. How can I help you?",
      "show_quote": true,
      "empty_response": "Sorry! No relevant content was found in the knowledge base!",
      "variables": [
        {"key": "knowledge", "optional": false}
      ]
    },
    "status": "1",
    "create_time": "2025-01-15T14:00:00Z",
    "update_time": "2025-01-15T14:00:00Z"
  }
}
```

Failure (HTTP 400):

```json
{
  "code": 102,
  "message": "Duplicated chat name in creating dataset."
}
```

---

### Update Chat Assistant

**PUT** `/api/v1/chats/{chat_id}`

Updates configurations for a specified chat assistant.

#### Request

- Method: PUT
- URL: `/api/v1/chats/{chat_id}`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request PUT \
     --url http://localhost:9380/api/v1/chats/b1f2f15691f911ef81180242ac120003 \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "name": "Updated Assistant",
       "llm": {
         "temperature": 0.5
       }
     }'
```

##### Request Parameters

- `chat_id` (*Path parameter*) `string`, **Required**
  - The ID of the chat assistant to update

- All other parameters are the same as Create Chat Assistant
- Only specified parameters will be updated

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

### Delete Chat Assistants

**DELETE** `/api/v1/chats`

Deletes chat assistants by ID.

#### Request

- Method: DELETE
- URL: `/api/v1/chats`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:9380/api/v1/chats \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "ids": ["b1f2f15691f911ef81180242ac120003"]
     }'
```

##### Request Parameters

- `ids` (*Body parameter*) `array<string>`, **Required**
  - List of chat assistant IDs to delete
  - If empty, all chat assistants will be deleted

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

### List Chat Assistants

**GET** `/api/v1/chats`

Lists chat assistants with optional filtering and pagination.

#### Request

- Method: GET
- URL: `/api/v1/chats?page={page}&page_size={page_size}&orderby={orderby}&desc={desc}&name={chat_name}&id={chat_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/chats?page=1&page_size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `page` (*Query parameter*) `integer`
  - Page number
  - Default: 1

- `page_size` (*Query parameter*) `integer`
  - Items per page
  - Default: 30

- `orderby` (*Query parameter*) `string`
  - Sort by attribute
  - Options: `create_time` (default), `update_time`

- `desc` (*Query parameter*) `boolean`
  - Sort in descending order
  - Default: `true`

- `id` (*Query parameter*) `string`
  - Filter by chat assistant ID

- `name` (*Query parameter*) `string`
  - Filter by chat assistant name

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": [
    {
      "id": "b1f2f15691f911ef81180242ac120003",
      "name": "My Assistant",
      "avatar": "",
      "dataset_ids": ["4345aa0ea1a311f0b45566fc51ac58df"],
      "description": "A helpful Assistant",
      "language": "English",
      "llm": {
        "model_name": "qwen-plus@Tongyi-Qianwen",
        "temperature": 0.1,
        "top_p": 0.3,
        "presence_penalty": 0.4,
        "frequency_penalty": 0.7
      },
      "status": "1",
      "create_time": "2025-01-15T14:00:00Z",
      "update_time": "2025-01-15T14:00:00Z"
    }
  ]
}
```

---

### Chat with Assistant (Native API)

**POST** `/api/v1/chats/{chat_id}/completions`

Sends a message to a chat assistant and receives a response.

#### Request

- Method: POST
- URL: `/api/v1/chats/{chat_id}/completions`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/chats/b1f2f15691f911ef81180242ac120003/completions \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "question": "What is machine learning?",
       "session_id": "optional_session_id",
       "stream": true
     }'
```

##### Request Parameters

- `chat_id` (*Path parameter*) `string`, **Required**
  - The chat assistant ID

- `question` (*Body parameter*) `string`, **Required**
  - The user's question

- `session_id` (*Body parameter*) `string`
  - Session ID to maintain conversation context
  - If not provided, a new session will be created

- `stream` (*Body parameter*) `boolean`
  - Whether to stream the response
  - Default: `false`

#### Response

Stream Response:

```
data:{"answer": "Machine learning is...", "reference": {...}}

data:{"answer": "a subset of artificial intelligence...", "reference": null}

data:[DONE]
```

Non-stream Response:

```json
{
  "code": 0,
  "data": {
    "answer": "Machine learning is a subset of artificial intelligence...",
    "reference": {
      "chunks": [...],
      "doc_aggs": {...}
    }
  }
}
```

---

## Session Management

### Create Session

**POST** `/api/v1/chats/{chat_id}/sessions`

Creates a new session for a chat assistant.

#### Request

- Method: POST
- URL: `/api/v1/chats/{chat_id}/sessions`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/chats/b1f2f15691f911ef81180242ac120003/sessions \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "name": "My Chat Session"
     }'
```

##### Request Parameters

- `chat_id` (*Path parameter*) `string`, **Required**
  - The chat assistant ID

- `name` (*Body parameter*) `string`
  - Session name
  - If not provided, a default name will be generated

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "session123",
    "name": "My Chat Session",
    "chat_id": "b1f2f15691f911ef81180242ac120003",
    "create_time": "2025-01-15T15:00:00Z",
    "update_time": "2025-01-15T15:00:00Z"
  }
}
```

---

### Update Session

**PUT** `/api/v1/chats/{chat_id}/sessions/{session_id}`

Updates a session's properties.

#### Request

- Method: PUT
- URL: `/api/v1/chats/{chat_id}/sessions/{session_id}`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request PUT \
     --url http://localhost:9380/api/v1/chats/b1f2f15691f911ef81180242ac120003/sessions/session123 \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "name": "Updated Session Name"
     }'
```

##### Request Parameters

- `chat_id` (*Path parameter*) `string`, **Required**
  - The chat assistant ID

- `session_id` (*Path parameter*) `string`, **Required**
  - The session ID to update

- `name` (*Body parameter*) `string`
  - New session name

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

### List Sessions

**GET** `/api/v1/chats/{chat_id}/sessions`

Lists sessions for a chat assistant.

#### Request

- Method: GET
- URL: `/api/v1/chats/{chat_id}/sessions?page={page}&page_size={page_size}&orderby={orderby}&desc={desc}&name={session_name}&id={session_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/chats/b1f2f15691f911ef81180242ac120003/sessions?page=1&page_size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `chat_id` (*Path parameter*) `string`, **Required**
  - The chat assistant ID

- `page` (*Query parameter*) `integer`
  - Page number
  - Default: 1

- `page_size` (*Query parameter*) `integer`
  - Items per page
  - Default: 30

- `orderby` (*Query parameter*) `string`
  - Sort by attribute
  - Options: `create_time` (default), `update_time`

- `desc` (*Query parameter*) `boolean`
  - Sort in descending order
  - Default: `true`

- `id` (*Query parameter*) `string`
  - Filter by session ID

- `name` (*Query parameter*) `string`
  - Filter by session name

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": [
    {
      "id": "session123",
      "name": "My Chat Session",
      "chat_id": "b1f2f15691f911ef81180242ac120003",
      "message_count": 15,
      "create_time": "2025-01-15T15:00:00Z",
      "update_time": "2025-01-15T16:30:00Z"
    }
  ]
}
```

---

### Delete Sessions

**DELETE** `/api/v1/chats/{chat_id}/sessions`

Deletes one or more sessions.

#### Request

- Method: DELETE
- URL: `/api/v1/chats/{chat_id}/sessions`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:9380/api/v1/chats/b1f2f15691f911ef81180242ac120003/sessions \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "ids": ["session123"]
     }'
```

##### Request Parameters

- `chat_id` (*Path parameter*) `string`, **Required**
  - The chat assistant ID

- `ids` (*Body parameter*) `array<string>`, **Required**
  - List of session IDs to delete
  - If empty, all sessions for the chat assistant will be deleted

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

### Get Related Questions

**POST** `/api/v1/sessions/related_questions`

Retrieves related questions based on the current conversation context.

#### Request

- Method: POST
- URL: `/api/v1/sessions/related_questions`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/sessions/related_questions \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "session_id": "session123",
       "question": "What is machine learning?"
     }'
```

##### Request Parameters

- `session_id` (*Body parameter*) `string`, **Required**
  - The session ID

- `question` (*Body parameter*) `string`, **Required**
  - The current question

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "related_questions": [
      "What are the types of machine learning?",
      "How does machine learning differ from deep learning?",
      "What are common machine learning algorithms?"
    ]
  }
}
```

---

## Agent Management

### List Agents

**GET** `/api/v1/agents`

Lists agents with optional filtering and pagination.

#### Request

- Method: GET
- URL: `/api/v1/agents?page={page}&page_size={page_size}&orderby={orderby}&desc={desc}&name={agent_name}&id={agent_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/agents?page=1&page_size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `page` (*Query parameter*) `integer`
  - Page number
  - Default: 1

- `page_size` (*Query parameter*) `integer`
  - Items per page
  - Default: 30

- `orderby` (*Query parameter*) `string`
  - Sort by attribute
  - Options: `create_time` (default), `update_time`

- `desc` (*Query parameter*) `boolean`
  - Sort in descending order
  - Default: `true`

- `id` (*Query parameter*) `string`
  - Filter by agent ID

- `title` (*Query parameter*) `string`
  - Filter by agent title/name

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": [
    {
      "id": "8d9ca0e2b2f911ef9ca20242ac120006",
      "title": "My Agent",
      "description": "A helpful agent",
      "avatar": null,
      "canvas_type": null,
      "dsl": {
        "components": {...},
        "graph": {...}
      },
      "create_time": "2025-01-15T16:00:00Z",
      "update_time": "2025-01-15T16:00:00Z",
      "user_id": "user123"
    }
  ]
}
```

---

### Create Agent

**POST** `/api/v1/agents`

Creates a new agent with specified Canvas DSL configuration.

#### Request

- Method: POST
- URL: `/api/v1/agents`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/agents \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "title": "My Agent",
       "description": "A helpful agent",
       "dsl": {
         "components": {
           "begin": {
             "obj": {
               "component_name": "Begin",
               "params": {}
             },
             "downstream": [],
             "upstream": []
           }
         },
         "graph": {
           "nodes": [...],
           "edges": []
         }
       }
     }'
```

##### Request Parameters

- `title` (*Body parameter*) `string`, **Required**
  - The title of the agent
  - Must be unique

- `description` (*Body parameter*) `string`
  - Description of the agent

- `dsl` (*Body parameter*) `object`, **Required**
  - The Canvas DSL object defining the agent's workflow
  - Contains components, graph, and configuration

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": true,
  "message": "success"
}
```

Failure (HTTP 400):

```json
{
  "code": 102,
  "message": "Agent with title 'My Agent' already exists."
}
```

---

### Update Agent

**PUT** `/api/v1/agents/{agent_id}`

Updates an existing agent by ID.

#### Request

- Method: PUT
- URL: `/api/v1/agents/{agent_id}`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request PUT \
     --url http://localhost:9380/api/v1/agents/8d9ca0e2b2f911ef9ca20242ac120006 \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "title": "Updated Agent",
       "description": "Updated description"
     }'
```

##### Request Parameters

- `agent_id` (*Path parameter*) `string`, **Required**
  - The agent ID to update

- `title` (*Body parameter*) `string`
  - New title for the agent

- `description` (*Body parameter*) `string`
  - New description

- `dsl` (*Body parameter*) `object`
  - New Canvas DSL configuration

**Note**: Only specify parameters you want to update. Unspecified parameters won't be changed.

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": true,
  "message": "success"
}
```

Failure (HTTP 403):

```json
{
  "code": 103,
  "message": "Only owner of canvas authorized for this operation."
}
```

---

### Delete Agent

**DELETE** `/api/v1/agents/{agent_id}`

Deletes an agent by ID.

#### Request

- Method: DELETE
- URL: `/api/v1/agents/{agent_id}`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:9380/api/v1/agents/8d9ca0e2b2f911ef9ca20242ac120006 \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Request Parameters

- `agent_id` (*Path parameter*) `string`, **Required**
  - The agent ID to delete

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": true,
  "message": "success"
}
```

---

### Create Agent Session

**POST** `/api/v1/agents/{agent_id}/sessions`

Creates a new session for an agent.

#### Request

- Method: POST
- URL: `/api/v1/agents/{agent_id}/sessions`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/agents/8d9ca0e2b2f911ef9ca20242ac120006/sessions \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{}'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "agent_session123",
    "agent_id": "8d9ca0e2b2f911ef9ca20242ac120006",
    "create_time": "2025-01-15T17:00:00Z"
  }
}
```

---

### Chat with Agent

**POST** `/api/v1/agents/{agent_id}/completions`

Sends a message to an agent and receives a response.

#### Request

- Method: POST
- URL: `/api/v1/agents/{agent_id}/completions`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:9380/api/v1/agents/8d9ca0e2b2f911ef9ca20242ac120006/completions \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "question": "Hello, agent!",
       "session_id": "agent_session123",
       "stream": false
     }'
```

##### Request Parameters

- `agent_id` (*Path parameter*) `string`, **Required**
  - The agent ID

- `question` (*Body parameter*) `string`, **Required**
  - The user's question

- `session_id` (*Body parameter*) `string`, **Required**
  - The agent session ID

- `stream` (*Body parameter*) `boolean`
  - Whether to stream the response
  - Default: `false`

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "answer": "Hello! How can I assist you today?",
    "reference": {...}
  }
}
```

---

### List Agent Sessions

**GET** `/api/v1/agents/{agent_id}/sessions`

Lists sessions for an agent.

#### Request

- Method: GET
- URL: `/api/v1/agents/{agent_id}/sessions?page={page}&page_size={page_size}&orderby={orderby}&desc={desc}&id={session_id}&user_id={user_id}&dsl={dsl}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/agents/8d9ca0e2b2f911ef9ca20242ac120006/sessions?page=1&page_size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `agent_id` (*Path parameter*) `string`, **Required**
  - The agent ID

- `page` (*Query parameter*) `integer`
  - Page number
  - Default: 1

- `page_size` (*Query parameter*) `integer`
  - Items per page
  - Default: 30

- `orderby` (*Query parameter*) `string`
  - Sort by attribute
  - Options: `create_time` (default), `update_time`

- `desc` (*Query parameter*) `boolean`
  - Sort in descending order
  - Default: `true`

- `id` (*Query parameter*) `string`
  - Filter by session ID

- `user_id` (*Query parameter*) `string`
  - Filter by user ID

- `dsl` (*Query parameter*) `string`
  - Filter by DSL configuration

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": [
    {
      "id": "agent_session123",
      "agent_id": "8d9ca0e2b2f911ef9ca20242ac120006",
      "user_id": "user123",
      "message_count": 10,
      "create_time": "2025-01-15T17:00:00Z",
      "update_time": "2025-01-15T17:30:00Z"
    }
  ]
}
```

---

### Delete Agent Sessions

**DELETE** `/api/v1/agents/{agent_id}/sessions`

Deletes one or more agent sessions.

#### Request

- Method: DELETE
- URL: `/api/v1/agents/{agent_id}/sessions`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:9380/api/v1/agents/8d9ca0e2b2f911ef9ca20242ac120006/sessions \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "ids": ["agent_session123"]
     }'
```

##### Request Parameters

- `agent_id` (*Path parameter*) `string`, **Required**
  - The agent ID

- `ids` (*Body parameter*) `array<string>`, **Required**
  - List of session IDs to delete
  - If empty, all sessions for the agent will be deleted

#### Response

Success (HTTP 200):

```json
{
  "code": 0
}
```

---

## System APIs

### Health Check

**GET** `/v1/system/healthz`

Checks the health status of the KnowFlow system.

#### Request

- Method: GET
- URL: `/v1/system/healthz`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:9380/v1/system/healthz
```

**Note**: This endpoint does not require authentication.

#### Response

Success (HTTP 200):

```json
{
  "status": "healthy",
  "version": "v2.1.5",
  "timestamp": "2025-01-15T18:00:00Z"
}
```

Failure (HTTP 503):

```json
{
  "status": "unhealthy",
  "error": "Database connection failed"
}
```

---

## KnowFlow-Specific Features

### MinerU Layout Parser

KnowFlow integrates [MinerU](https://github.com/opendatalab/MinerU), a powerful PDF parsing engine optimized for complex layouts, tables, and multi-column documents.

**Benefits**:
- High-accuracy OCR and layout recognition
- Preserves document structure (headings, paragraphs, tables)
- Extracts precise bounding box coordinates for each chunk
- Supports parent-child chunking for better context preservation

**Usage**:
```json
{
  "parser_config": {
    "layout_recognize": "mineru",
    "chunk_token_num": 256
  }
}
```

### Parent-Child Chunking

For documents parsed with MinerU or DOTS, KnowFlow supports a two-tier chunking strategy:

- **Child Chunks**: Small, granular chunks (256 tokens) used for semantic search
- **Parent Chunks**: Larger contextual chunks that contain multiple child chunks

**How it works**:
1. Documents are parsed and chunked into small child chunks
2. Child chunks are grouped into parent chunks based on document structure
3. During retrieval, child chunks are searched first
4. Parent chunks are returned to provide broader context

**Benefits**:
- More precise semantic matching (via small child chunks)
- Richer context for LLM generation (via parent chunks)
- Better handling of cross-chunk references

**Configuration**:
Parent-child chunking is automatically enabled when using MinerU or DOTS parsers with smart chunking method.

---

## Best Practices

### 1. Choosing the Right Parser

- **MinerU** (`"mineru"`): Best for complex PDFs with tables, multi-column layouts, academic papers
- **DOTS** (`"dots"`): Fast parser with good accuracy
- **DeepDOC** (`"deepdoc"`): Default parser, good for general documents

### 2. Choosing the Right Chunk Method

- **Smart** (`"smart"`): Recommended for most use cases, structure-aware chunking
- **Paper** (`"paper"`): For academic papers with abstract, sections, references
- **Book** (`"book"`): For books with chapters and sections
- **General** (`"naive"`): Simple token-based chunking

### 3. Chunk Size Tuning

- **Small chunks (128-256 tokens)**: Better for precise retrieval, more chunks to search
- **Medium chunks (256-512 tokens)**: Balanced approach (recommended)
- **Large chunks (512-1024 tokens)**: More context per chunk, fewer total chunks

### 4. Embedding Model Selection

Choose an embedding model based on your language and use case:

- **Chinese + English**: `BAAI/bge-m3@SILICONFLOW`
- **English only**: `BAAI/bge-large-en-v1.5@BAAI`
- **Multilingual**: `BAAI/bge-m3@SILICONFLOW`

### 5. Retrieval Tuning

- Start with default similarity threshold (0.2) and adjust based on results
- Increase `vector_similarity_weight` (0.5-0.7) for more semantic matching
- Decrease it (0.1-0.3) for more keyword-based matching
- Use `top_k` to control the search space (higher = more comprehensive but slower)

---

## Code Examples

### Python Example: Complete Workflow

```python
import requests
import json
import time

BASE_URL = "http://localhost:9380"
API_KEY = "ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 1. Create a dataset
dataset_data = {
    "name": "My Knowledge Base",
    "description": "Technical documentation",
    "embedding_model": "BAAI/bge-m3@SILICONFLOW",
    "chunk_method": "smart",
    "parser_config": {
        "layout_recognize": "mineru",
        "chunk_token_num": 256
    }
}

response = requests.post(
    f"{BASE_URL}/api/v1/datasets",
    headers=headers,
    json=dataset_data
)
dataset_id = response.json()["data"]["id"]
print(f"Created dataset: {dataset_id}")

# 2. Upload a document
with open("document.pdf", "rb") as f:
    files = {"file": ("document.pdf", f, "application/pdf")}
    form_data = {
        "parser_id": "smart",
        "parser_config": json.dumps({
            "chunk_token_num": 256,
            "layout_recognize": "mineru"
        })
    }
    headers_upload = {"Authorization": f"Bearer {API_KEY}"}

    response = requests.post(
        f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents",
        headers=headers_upload,
        data=form_data,
        files=files
    )
    document_id = response.json()["data"][0]["id"]
    print(f"Uploaded document: {document_id}")

# 3. Wait for parsing to complete
while True:
    response = requests.get(
        f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents/{document_id}",
        headers=headers
    )
    status = response.json()["data"]["status"]
    if status == "1":
        print("Document parsing completed")
        break
    elif status == "2":
        print("Document parsing failed")
        break
    time.sleep(5)

# 4. Retrieve relevant chunks
retrieval_data = {
    "question": "What is the main topic of this document?",
    "dataset_ids": [dataset_id],
    "page": 1,
    "page_size": 5
}

response = requests.post(
    f"{BASE_URL}/api/v1/retrieval",
    headers=headers,
    json=retrieval_data
)

chunks = response.json()["data"]["chunks"]
for chunk in chunks:
    print(f"Chunk: {chunk['content'][:100]}...")
    print(f"Similarity: {chunk['similarity']}")

# 5. Create a chat assistant
chat_data = {
    "name": "My Assistant",
    "dataset_ids": [dataset_id],
    "llm": {
        "model_name": "qwen-plus@Tongyi-Qianwen",
        "temperature": 0.1
    },
    "prompt": {
        "similarity_threshold": 0.2,
        "top_n": 6
    }
}

response = requests.post(
    f"{BASE_URL}/api/v1/chats",
    headers=headers,
    json=chat_data
)
chat_id = response.json()["data"]["id"]
print(f"Created chat assistant: {chat_id}")

# 6. Chat with the assistant
chat_request = {
    "question": "Summarize the document for me",
    "stream": False
}

response = requests.post(
    f"{BASE_URL}/api/v1/chats/{chat_id}/completions",
    headers=headers,
    json=chat_request
)

answer = response.json()["data"]["answer"]
print(f"Assistant response: {answer}")
```

---

## Troubleshooting

### Common Issues

#### 1. "Embedding model identifier must follow <model_name>@<provider> format"

**Solution**: Ensure embedding_model includes both model name and provider:
```json
{
  "embedding_model": "BAAI/bge-m3@SILICONFLOW"  // Correct
  // NOT: "BAAI/bge-m3"  // Wrong
}
```

#### 2. "Input should be a valid string" for layout_recognize

**Solution**: Use string value, not boolean:
```json
{
  "parser_config": {
    "layout_recognize": "mineru"  // Correct
    // NOT: "layout_recognize": true  // Wrong
  }
}
```

#### 3. "`dataset_ids` is required" in retrieval

**Solution**: Use `dataset_ids` (not `kb_id`) for SDK API:
```json
{
  "dataset_ids": ["4345aa0ea1a311f0b45566fc51ac58df"]  // Correct
  // NOT: "kb_id": ["..."]  // Wrong for SDK API
}
```

#### 4. Document parsing stuck at status "0"

**Causes**:
- MinerU service not running
- Document format not supported
- File corrupted

**Solution**:
- Check MinerU service status: `docker ps | grep mineru`
- Verify document format is supported
- Try with a different document

#### 5. "Unauthorized" error (401)

**Causes**:
- Invalid API key
- API key expired
- Missing Authorization header

**Solution**:
- Verify API key is correct
- Check Authorization header format: `Bearer <API_KEY>`
- Regenerate API key if needed

---

## Changelog from RAGFlow 0.20.1

### API Changes

1. **Dataset Creation**:
   - Added support for `"mineru"` and `"dots"` layout parsers
   - `embedding_model` validation now enforces `@provider` suffix
   - New `"smart"` chunk method available

2. **Document Upload**:
   - `parser_config` must be JSON string in form data (not object)
   - Enhanced status codes for parsing progress

3. **Retrieval API**:
   - SDK version uses `dataset_ids` parameter (legacy uses `kb_id`)
   - Added parent-child chunk support (automatic for MinerU/DOTS)
   - Enhanced similarity scoring with `vector_similarity` and `term_similarity`

### New Features

1. **MinerU Integration**: High-accuracy PDF parsing with structure preservation
2. **Parent-Child Chunking**: Two-tier chunking strategy for better context
3. **Coordinate Mapping**: Precise bounding boxes for chunk highlighting
4. **Dev Mode Logging**: Debug output for parent-child relationships (`dev_mode=true`)

### API Coverage

This documentation covers **36 API endpoints** across all major categories:
- OpenAI-Compatible API: 2 endpoints
- Dataset Management: 6 endpoints
- Document Management: 5 endpoints
- Chunk Management: 6 endpoints
- Chat Assistant Management: 5 endpoints
- Session Management: 5 endpoints
- Agent Management: 6 endpoints
- System APIs: 1 endpoint

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/your-repo/knowflow/issues
- Documentation: https://docs.knowflow.ai
- Email: support@knowflow.ai

---

**Version**: KnowFlow v2.1.5
**Last Updated**: January 2025
**Based on**: RAGFlow v0.20.1
**Total APIs Documented**: 36
