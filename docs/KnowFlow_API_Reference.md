# KnowFlow HTTP API Reference

A complete reference for KnowFlow's RESTful API. This documentation is based on KnowFlow v2.1.5, which extends RAGFlow with enhanced features including MinerU layout parser and parent-child chunking strategies.

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

---

## Error Codes

| Code | Message               | Description                |
| ---- | --------------------- | -------------------------- |
| 0    | Success               | Request successful         |
| 102  | Invalid Parameter     | Required parameter missing or invalid |
| 400  | Bad Request           | Invalid request parameters |
| 401  | Unauthorized          | Unauthorized access        |
| 403  | Forbidden             | Access denied              |
| 404  | Not Found             | Resource not found         |
| 500  | Internal Server Error | Server internal error      |

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
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh' \
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

- `embedding_model` (*Body parameter*) `string`
  - The embedding model identifier
  - Format: `<model_name>@<provider>`
  - Example: `"BAAI/bge-m3@SILICONFLOW"`
  - Maximum 255 characters
  - **Important**: Must include both model name and provider separated by `@`

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
      - Default: 256
      - Range: 1-2048
    - `min_chunk_tokens` `integer`: Minimum tokens per chunk
      - Default: 10
      - Range: 1-100
    - `auto_keywords` `integer`: Number of keywords to auto-generate
      - Default: 0
      - Range: 0-32
    - `auto_questions` `integer`: Number of questions to auto-generate
      - Default: 0
      - Range: 0-10

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

Lists all datasets for the authenticated user.

#### Request

- Method: GET
- URL: `/api/v1/datasets?page=1&page_size=10`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/datasets?page=1&page_size=10' \
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh'
```

##### Query Parameters

- `page` (*Query parameter*) `integer`
  - Page number for pagination
  - Default: 1
  - Minimum: 1

- `page_size` (*Query parameter*) `integer`
  - Number of items per page
  - Default: 10
  - Range: 1-100

- `id` (*Query parameter*) `string`
  - Filter by specific dataset ID
  - When provided, returns only that dataset

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "success",
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

### Get Single Dataset

**GET** `/api/v1/datasets?id={dataset_id}`

Retrieves details of a specific dataset.

#### Request

- Method: GET
- URL: `/api/v1/datasets?id={dataset_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/datasets?id=4345aa0ea1a311f0b45566fc51ac58df' \
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh'
```

#### Response

Same format as List Datasets, but with a single dataset in the array.

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
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh' \
     --data '{
       "name": "Updated Knowledge Base",
       "description": "Updated description"
     }'
```

##### Request Parameters

- `name` (*Body parameter*) `string`
  - New name for the dataset
  - Maximum 128 characters

- `description` (*Body parameter*) `string`
  - New description for the dataset
  - Maximum 65535 characters

- `embedding_model` (*Body parameter*) `string`
  - New embedding model (format: `<model_name>@<provider>`)

- `chunk_method` (*Body parameter*) `enum<string>`
  - New chunking method (same options as Create Dataset)

- `parser_config` (*Body parameter*) `object`
  - New parser configuration

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "success",
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
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh' \
     --data '{
       "ids": ["4345aa0ea1a311f0b45566fc51ac58df"]
     }'
```

##### Request Parameters

- `ids` (*Body parameter*) `array<string>`, **Required**
  - List of dataset IDs to delete
  - Minimum: 1 ID

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "deleted_count": 1
  }
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
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh' \
     --form 'file=@/path/to/document.pdf' \
     --form 'parser_id=smart' \
     --form 'parser_config={"chunk_token_num":256,"layout_recognize":"mineru"}'
```

##### Request Parameters

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

Lists all documents in a dataset.

#### Request

- Method: GET
- URL: `/api/v1/datasets/{dataset_id}/documents?page=1&page_size=10`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents?page=1&page_size=10' \
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh'
```

##### Query Parameters

- `page` (*Query parameter*) `integer`
  - Page number
  - Default: 1

- `page_size` (*Query parameter*) `integer`
  - Items per page
  - Default: 10
  - Range: 1-100

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "success",
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
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "success",
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
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh' \
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
  "code": 0,
  "message": "success",
  "data": {
    "id": "c6db195ea4b811f097ee66fc51ac58df",
    "name": "updated_document.pdf",
    "updated_at": "2025-01-15T13:00:00Z"
  }
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
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh' \
     --data '{
       "ids": ["c6db195ea4b811f097ee66fc51ac58df"]
     }'
```

##### Request Parameters

- `ids` (*Body parameter*) `array<string>`, **Required**
  - List of document IDs to delete

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "deleted_count": 1
  }
}
```

---

## Chunk Management

### List Document Chunks

**GET** `/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks`

Lists all chunks of a document.

#### Request

- Method: GET
- URL: `/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks?page=1&page_size=10`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:9380/api/v1/datasets/4345aa0ea1a311f0b45566fc51ac58df/documents/c6db195ea4b811f097ee66fc51ac58df/chunks?page=1&page_size=10' \
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh'
```

##### Query Parameters

- `page` (*Query parameter*) `integer`
  - Page number
  - Default: 1

- `page_size` (*Query parameter*) `integer`
  - Items per page
  - Default: 10
  - Range: 1-100

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "chunks": [
      {
        "id": "8c204dcbb8955158",
        "content": "This is the chunk content extracted from the document...",
        "important_keywords": ["keyword1", "keyword2"],
        "positions": [[1, 100, 200, 300, 400]],
        "page_number": 1,
        "doc_id": "c6db195ea4b811f097ee66fc51ac58df",
        "kb_id": "4345aa0ea1a311f0b45566fc51ac58df",
        "created_at": "2025-01-15T12:05:00Z"
      }
    ],
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
     --header 'Authorization: Bearer ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh' \
     --data '{
       "question": "What is machine learning?",
       "dataset_ids": ["4345aa0ea1a311f0b45566fc51ac58df"],
       "page": 1,
       "page_size": 5,
       "similarity_threshold": 0.2,
       "vector_similarity_weight": 0.3
     }'
```

##### Request Parameters

- `question` (*Body parameter*) `string`, **Required**
  - The search query text
  - Minimum 1 character

- `dataset_ids` (*Body parameter*) `array<string>`, **Required**
  - List of dataset IDs to search in
  - Minimum: 1 dataset ID
  - **Note**: This is the SDK API parameter name (legacy API uses `kb_id`)

- `page` (*Body parameter*) `integer`
  - Page number for results
  - Default: 1

- `page_size` (*Body parameter*) `integer`
  - Number of chunks to return
  - Default: 5
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

- `top_k` (*Body parameter*) `integer`
  - Maximum number of chunks to retrieve before reranking
  - Default: 1024

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "success",
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
        "important_keywords": ["machine learning", "artificial intelligence"]
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
import time
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
   - Enhanced similarity scoring

### New Features

1. **MinerU Integration**: High-accuracy PDF parsing with structure preservation
2. **Parent-Child Chunking**: Two-tier chunking strategy for better context
3. **Coordinate Mapping**: Precise bounding boxes for chunk highlighting
4. **Dev Mode Logging**: Debug output for parent-child relationships (`dev_mode=true`)

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
