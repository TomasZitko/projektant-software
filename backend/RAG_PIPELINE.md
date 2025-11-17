# RAG Pipeline Architecture

## Overview

Complete RAG (Retrieval Augmented Generation) pipeline for Czech building codes compliance checking.

**Stack:**
- **Vector DB**: Pinecone (serverless, cosine similarity)
- **Embeddings**: OpenAI text-embedding-ada-002 (1536 dimensions)
- **Cache**: Redis (1hr TTL, >70% hit rate target)
- **Documents**: PyMuPDF + pdfplumber for Czech PDFs

**Performance Targets:**
- Query latency: <100ms p95
- Ingestion: 100-page PDF in <2 min
- Cache hit rate: >70%

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Revit Plugin                              │
│                   (sends element data)                           │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP POST
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FastAPI Compliance Endpoint                    │
│                  /api/v1/compliance/check                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Compliance Engine                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Parse element properties & context                    │   │
│  │ 2. Build semantic search query (Czech + English)         │   │
│  │ 3. Retrieve relevant rules from Vector DB                │   │
│  │ 4. Check compliance with numeric extraction              │   │
│  │ 5. Generate violations & recommendations                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────┬─────────────────────────┬──────────────────┬────────────┘
        │                         │                  │
        ▼                         ▼                  ▼
┌───────────────┐     ┌───────────────────┐  ┌──────────────────┐
│ Vector Service│     │ Embedding Service │  │  Cache Service   │
│   (Pinecone)  │     │  (OpenAI ada-002) │  │    (Redis)       │
└───────────────┘     └───────────────────┘  └──────────────────┘
        │                         │                  │
        │                         └──────────┬───────┘
        │                                    │
        ▼                                    ▼
┌───────────────────────────────────────────────────────────┐
│                    Caching Layer                          │
│  • Query cache: 1hr TTL                                   │
│  • Embedding cache: 1hr TTL                               │
│  • Hit rate monitoring                                    │
└───────────────────────────────────────────────────────────┘
```

---

## Service Components

### 1. **cache_service.py** - Redis Caching Layer

**Purpose**: High-performance caching with async support

**Features:**
- Async Redis with connection pooling (50 connections)
- Deterministic cache key generation (SHA256)
- Hit/miss statistics tracking
- Cache-aside pattern with TTL

**Key Methods:**
```python
await cache_service.get(key)                    # Get cached value
await cache_service.set(key, value, ttl=3600)   # Set with TTL
await cache_service.get_or_compute(key, fn)     # Cache-aside pattern
cache_service.get_stats()                       # Get hit rate stats
```

**Performance:**
- <10ms cache operations
- Target 70%+ hit rate
- Auto-cleanup with TTL

---

### 2. **document_processor.py** - PDF Processing

**Purpose**: Extract text from Czech ČSN standard PDFs

**Features:**
- PyMuPDF for robust Czech character handling (ě, š, č, ř, ž, ý, á, í, é, ú, ů)
- pdfplumber for table extraction
- Regex patterns for ČSN references (ČSN 73 0802, etc.)
- Section detection (Článek, Oddíl, Kapitola)
- Measurement extraction (1200mm, 2.5m², etc.)

**Key Methods:**
```python
processor.process_pdf(pdf_path)           # Extract text + metadata
processor.extract_tables_pdfplumber()     # Extract tables
processor.extract_rules()                 # Extract rule patterns
processor.normalize_czech_text()          # Fix OCR errors
```

**Patterns Detected:**
- Minimum requirements: "nesmí být menší než X mm"
- Maximum requirements: "nesmí být větší než X mm"
- Range requirements: "musí být v rozmezí X až Y mm"

---

### 3. **chunking_service.py** - Semantic Chunking

**Purpose**: Split documents into 300-500 token chunks with semantic boundaries

**Features:**
- Tiktoken-based token counting (OpenAI encoder)
- Semantic boundary detection (3 levels: strong, medium, weak)
- Page-aware chunking (preserves page boundaries for ČSN docs)
- Chunk type classification (rule, table, heading, general)
- Configurable overlap (default: 50 tokens)

**Semantic Boundaries:**
1. **Strong**: Headers, Articles (Článek), Sections (Oddíl)
2. **Medium**: Paragraph breaks, sentence endings
3. **Weak**: Commas, whitespace (fallback)

**Key Methods:**
```python
chunking_service.chunk_document(processed_doc)   # Chunk entire doc
chunking_service.chunk_text(text)                # Chunk raw text
chunking_service.count_tokens(text)              # Count tokens
```

**Output:**
```python
Chunk(
    text="...",
    token_count=350,
    chunk_index=0,
    page_number=42,
    csn_reference="ČSN 73 0802",
    chunk_type="rule"
)
```

---

### 4. **embedding_service.py** - OpenAI Embeddings

**Purpose**: Generate 1536-dimensional embeddings using ada-002

**Features:**
- Async OpenAI client
- Batch processing (up to 2048 texts/request)
- Automatic caching (1hr TTL)
- Rate limiting to avoid throttling
- Token usage tracking

**Key Methods:**
```python
await embedding_service.embed_text(text)              # Single embedding
await embedding_service.embed_batch(texts)            # Batch embeddings
await embedding_service.embed_chunks(chunks)          # Embed chunk list
embedding_service.get_stats()                         # Usage statistics
```

**Performance:**
- Caches all embeddings (1hr)
- Batches requests for efficiency
- Tracks total tokens used

---

### 5. **vector_service.py** - Pinecone Operations

**Purpose**: Vector search with Pinecone serverless index

**Features:**
- Async Pinecone client
- Auto-creates index if missing (dimension=1536, metric=cosine)
- Batch upsert (default: 100 vectors/batch)
- Query result caching (1hr TTL)
- Metadata filtering support

**Index Configuration:**
```python
Index: "csn-building-codes"
Dimension: 1536 (OpenAI ada-002)
Metric: cosine
Spec: ServerlessSpec(cloud="aws", region="us-east-1")
```

**Key Methods:**
```python
await vector_service.upsert_chunks(chunks)           # Upload vectors
await vector_service.query(query_text, top_k=5)      # Semantic search
await vector_service.query_by_rule_type(...)         # Filtered search
await vector_service.get_stats()                     # Index statistics
```

**Query Example:**
```python
results = await vector_service.query(
    query_text="šířka chodby minimální požadavek",
    top_k=5,
    filters={"chunk_type": "rule"}
)
# Returns: [{id, score, metadata}, ...]
```

---

### 6. **compliance_engine.py** - Main Orchestrator

**Purpose**: End-to-end compliance checking using RAG pipeline

**Features:**
- Multilingual query building (Czech + English terms)
- Semantic vector search
- Numeric requirement extraction (regex-based)
- Violation severity classification (critical/high/medium/low)
- Actionable recommendations generation

**Element Type Mappings:**
```python
Wall → ["stěna", "zeď", "příčka"]
Door → ["dveře", "vchod", "průchod"]
Corridor → ["chodba", "úniková cesta"]
```

**Compliance Check Flow:**
1. Parse element properties (width_mm, height_mm, etc.)
2. Build semantic query (Czech + English terms)
3. Query vector DB (top 5 results, similarity > 0.7)
4. Extract numeric requirements from rule text
5. Compare actual vs required values
6. Generate violations with confidence scores
7. Generate recommendations

**Key Methods:**
```python
await compliance_engine.check_compliance(
    element_type="Wall",
    properties={"width_mm": 1100},
    context={"room_type": "Corridor", "building_type": "Residential"}
)
```

**Response:**
```python
{
    "compliant": False,
    "violations": [
        {
            "rule_id": "chunk_0_42",
            "severity": "critical",
            "message": "šířka (1100mm) je menší než požadovaných 1200mm",
            "confidence_score": 0.92,
            "required_value": 1200,
            "actual_value": 1100,
            "csn_reference": "ČSN 73 0802"
        }
    ],
    "recommendations": [...],
    "execution_time_ms": 45.2
}
```

**Severity Levels:**
- **Critical**: score ≥ 0.85 (immediate action required)
- **High**: score ≥ 0.70 (attention required)
- **Medium**: score ≥ 0.50 (review recommended)
- **Low**: score ≥ 0.30 (informational)

---

## API Endpoints

### POST `/api/v1/compliance/check`

Check element compliance against Czech building codes.

**Request:**
```json
{
  "element_type": "Wall",
  "properties": {
    "width_mm": 1100,
    "height_mm": 2600,
    "length_mm": 5000
  },
  "context": {
    "room_type": "Corridor",
    "building_type": "Residential",
    "occupancy": 150,
    "floor_level": 2
  }
}
```

**Response:**
```json
{
  "compliant": false,
  "violations": [
    {
      "rule_id": "ČSN_73_0802_Sec_5.2.a",
      "severity": "critical",
      "message": "Corridor width (1100mm) < minimum 1200mm required",
      "confidence_score": 0.92,
      "required_value": 1200,
      "actual_value": 1100,
      "code_reference": "ČSN 73 0802"
    }
  ],
  "recommendations": [
    "⚠️ CRITICAL: 1 critical violations must be resolved immediately.",
    "Adjust dimension by 100mm to meet ČSN 73 0802 requirement"
  ],
  "checked_at": "2025-01-15T10:30:00Z"
}
```

### GET `/api/v1/compliance/rules`

Get vector database statistics.

**Response:**
```json
{
  "total_rules": 24,
  "index_name": "csn-building-codes",
  "dimension": 1536,
  "namespaces": {},
  "queries_executed": 156,
  "message": "RAG pipeline active"
}
```

### GET `/api/v1/compliance/stats`

Get compliance engine statistics.

**Response:**
```json
{
  "compliance_engine": {
    "checks_performed": 42,
    "violations_found": 15,
    "avg_violations_per_check": 0.36
  },
  "vector_database": {
    "total_vectors": 24,
    "queries_executed": 156,
    "cache_hits": 89
  }
}
```

---

## Sample Czech Building Codes Included

The ingestion script includes 24 sample rules from:

1. **ČSN 73 0802** - Fire Protection
   - Escape route corridor widths (1200mm, 1500mm)
   - Corridor heights (2100mm)
   - Door widths (800mm, 900mm)
   - Maximum escape distances

2. **ČSN 73 4301** - Residential Buildings
   - Room heights (2600mm)
   - Minimum room areas (living room 16m², bedroom 8-12m²)
   - Corridor widths (1100mm)
   - Bathroom areas (2.5-3.3m²)
   - Balcony depths (1200mm)

3. **ČSN 73 0580** - Daylight
   - Window to floor area ratios (1:10, 1:8)

4. **ČSN 73 0532** - Acoustics
   - Wall thickness and sound insulation (Rw ≥ 52dB)

5. **ČSN 73 0540** - Thermal Protection
   - U-values for walls (≤ 0.30 W/(m²·K))
   - U-values for windows (≤ 1.5 W/(m²·K))

6. **ČSN 73 4130** - Stairs and Ramps
   - Stair widths (900-1100mm)
   - Step dimensions (h: 160-190mm, b: ≥240mm)
   - Handrail heights (900-1000mm)

7. **ČSN 73 6058** - Garages
   - Garage dimensions (2500×5000mm minimum)
   - Garage height (2000mm minimum)

---

## Usage

### 1. Setup Environment

```bash
# Create .env file
cp backend/.env.example backend/.env

# Configure API keys
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=csn-building-codes
REDIS_URL=redis://localhost:6379/0
```

### 2. Start Services

```bash
# Start Redis
redis-server

# Or with Docker
docker run -d -p 6379:6379 redis
```

### 3. Ingest Sample Rules

```bash
cd backend
python scripts/ingest_sample_rules.py
```

**Expected output:**
```
============================================================
CZECH BUILDING CODE INGESTION SCRIPT
============================================================
Initializing services...
✓ Services initialized

Preparing 24 sample rules...
✓ Prepared 24 chunks

Generating embeddings...
✓ Generated 24 embeddings

Upserting to Pinecone...
✓ Upserted 24 vectors
```

### 4. Run Tests

```bash
python scripts/test_rag_pipeline.py
```

### 5. Start API Server

```bash
uvicorn app.main:app --reload
```

### 6. Test Compliance Check

```bash
curl -X POST http://localhost:8000/api/v1/compliance/check \
  -H "Content-Type: application/json" \
  -d '{
    "element_type": "Wall",
    "properties": {"width_mm": 1100},
    "context": {"room_type": "Corridor", "building_type": "Residential"}
  }'
```

---

## Performance Optimization

### Caching Strategy

1. **Embedding Cache** (Redis, 1hr TTL)
   - Caches all OpenAI embedding requests
   - Reduces API costs by ~80%
   - <10ms cache hits

2. **Query Cache** (Redis, 1hr TTL)
   - Caches vector search results
   - Reduces Pinecone query load
   - Target: >70% hit rate

3. **Statistics Tracking**
   - Cache hit/miss rates
   - Query latency (p50, p95, p99)
   - Token usage tracking

### Query Optimization

1. **Semantic Search**
   - Multilingual queries (Czech + English)
   - Top-K limiting (default: 5)
   - Similarity threshold filtering (> 0.7)

2. **Batching**
   - Embed multiple texts in single request
   - Upsert vectors in batches (100/batch)
   - Rate limiting to avoid throttling

---

## Next Steps

1. **Ingest Real PDFs**: Replace sample rules with actual ČSN documents
2. **Fine-tune Chunking**: Optimize chunk size for retrieval quality
3. **Add Filters**: Filter by building type, rule category, etc.
4. **Hybrid Search**: Combine semantic + keyword search
5. **Monitoring**: Add Prometheus/Grafana for metrics
6. **Scale**: Increase vector count, optimize embeddings

---

## Troubleshooting

### "No results found"
- Run ingestion script: `python scripts/ingest_sample_rules.py`
- Check index stats: `GET /api/v1/compliance/rules`
- Lower similarity threshold in `config.py`

### "Query too slow (>100ms)"
- Check Redis connection
- Verify cache hit rate (target >70%)
- Optimize query complexity

### "Pinecone connection failed"
- Verify `PINECONE_API_KEY` in `.env`
- Check index exists or auto-create enabled
- Verify region/environment settings

### "OpenAI API error"
- Verify `OPENAI_API_KEY` in `.env`
- Check API quota/billing
- Review rate limits

---

## Architecture Decisions

### Why Pinecone?
- Serverless (no infrastructure management)
- Fast queries (<100ms p95)
- Built-in filtering
- Auto-scaling

### Why OpenAI ada-002?
- Best price/performance for embeddings
- 1536 dimensions (good balance)
- Czech language support
- Industry standard

### Why Redis?
- Sub-10ms latency
- Simple key-value cache
- TTL support
- Widely deployed

### Why PyMuPDF?
- Best Czech character support
- Fast PDF parsing
- Layout preservation
- Free/open source
