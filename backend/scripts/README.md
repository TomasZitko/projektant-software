# RAG Pipeline Scripts

This directory contains scripts for managing the RAG (Retrieval Augmented Generation) pipeline.

## Prerequisites

Before running these scripts, ensure:

1. **Environment variables are set** (`.env` file):
   ```bash
   OPENAI_API_KEY=your_openai_api_key
   PINECONE_API_KEY=your_pinecone_api_key
   PINECONE_ENVIRONMENT=your_pinecone_environment
   PINECONE_INDEX_NAME=csn-building-codes
   REDIS_URL=redis://localhost:6379/0
   ```

2. **Services are running**:
   - Redis: `redis-server` or `docker run -p 6379:6379 redis`
   - PostgreSQL (optional for this script)

3. **Pinecone index exists**:
   - The script will create the index if it doesn't exist
   - Index name: `csn-building-codes`
   - Dimension: 1536 (OpenAI ada-002)
   - Metric: cosine

## Scripts

### `ingest_sample_rules.py`

Ingests 20+ sample Czech building code rules into Pinecone for testing.

**Usage:**
```bash
cd backend
python scripts/ingest_sample_rules.py
```

**What it does:**
1. Loads 20+ sample ČSN (Czech building code) rules
2. Converts rules to chunks with metadata
3. Generates embeddings using OpenAI ada-002
4. Uploads vectors to Pinecone
5. Runs a test query to verify ingestion

**Sample rules include:**
- ČSN 73 0802 - Fire Protection (escape routes, corridors, doors)
- ČSN 73 4301 - Residential Buildings (room sizes, heights)
- ČSN 73 0580 - Daylight in Buildings
- ČSN 73 0532 - Acoustics
- ČSN 73 0540 - Thermal Protection
- ČSN 73 4130 - Stairs and Ramps
- ČSN 73 6058 - Individual Garages

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

============================================================
INGESTION COMPLETE
============================================================
Total vectors in index: 24
```

## Testing the Pipeline

After ingestion, test the API:

```bash
# Start the API server
cd backend
uvicorn app.main:app --reload

# Test compliance check
curl -X POST http://localhost:8000/api/v1/compliance/check \
  -H "Content-Type: application/json" \
  -d '{
    "element_type": "Wall",
    "properties": {
      "width_mm": 1100
    },
    "context": {
      "room_type": "Corridor",
      "building_type": "Residential"
    }
  }'
```

**Expected response:**
```json
{
  "compliant": false,
  "violations": [
    {
      "rule_id": "chunk_0_42",
      "severity": "critical",
      "message": "šířka (1100mm) je menší než požadovaných 1200mm",
      "confidence_score": 0.92,
      "required_value": 1200,
      "actual_value": 1100,
      "code_reference": "ČSN 73 0802"
    }
  ],
  "recommendations": [
    "⚠️ CRITICAL: 1 critical violations must be resolved immediately.",
    "Adjust dimension by 100mm to meet ČSN 73 0802 requirement",
    "Review complete ČSN documentation for detailed requirements."
  ]
}
```

## Performance Targets

- **Query latency**: <100ms p95
- **Cache hit rate**: >70%
- **Ingestion**: 100-page PDF in <2 min

## Troubleshooting

### "Pinecone connection failed"
- Check `PINECONE_API_KEY` in `.env`
- Verify Pinecone environment/region

### "OpenAI API error"
- Check `OPENAI_API_KEY` in `.env`
- Verify API quota/billing

### "Redis connection failed"
- Start Redis: `redis-server`
- Check `REDIS_URL` in `.env`

### "No results found"
- Verify ingestion completed successfully
- Check index stats: `GET /api/v1/compliance/rules`
- Increase `TOP_K_RESULTS` or lower `SIMILARITY_THRESHOLD` in config

## Next Steps

1. **Ingest real ČSN documents**: Replace sample rules with actual PDF documents
2. **Fine-tune chunking**: Adjust chunk size for optimal retrieval
3. **Add filters**: Filter by building type, rule type, etc.
4. **Monitor performance**: Track query latency, cache hit rate
5. **Scale**: Add more rules, optimize embeddings
