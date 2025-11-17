# 🚀 Projektant Copilot - 60-Second Quickstart

## What You Get

✅ **Production-ready FastAPI backend** with /health and /api/v1/compliance/check endpoints
✅ **Complete database models** (User, Project, ComplianceRule, CheckResult)
✅ **Docker Compose** setup with PostgreSQL 15, Neo4j 5.x, Redis 7.x
✅ **Service layer** (RAG, Vector, Compliance Engine)
✅ **Alembic migrations** ready to deploy
✅ **C# Revit plugin shell** structure

## ⚡ Quick Start (60 seconds)

### 1. Start Infrastructure (15 sec)

```bash
# Start all services
docker-compose up -d

# Verify all UP
docker-compose ps
```

### 2. Install Backend Dependencies (30 sec)

```bash
cd backend
pip install -r requirements.txt
```

**FAST INSTALL** (core only, ~10 sec):
```bash
pip install fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary asyncpg redis pydantic pydantic-settings loguru python-dotenv
```

### 3. Configure Environment (5 sec)

```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 4. Run Migrations (5 sec)

```bash
alembic upgrade head
```

### 5. Start Server (5 sec)

```bash
uvicorn app.main:app --reload
```

**Server running at:** http://localhost:8000

## ✅ Test Your Setup

### Health Check
```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "app_name": "Projektant Copilot API",
  "version": "0.1.0"
}
```

### Compliance Check
```bash
curl -X POST http://localhost:8000/api/v1/compliance/check \
  -H "Content-Type: application/json" \
  -d '{
    "element_type": "Corridor",
    "properties": {"width_mm": 1000},
    "context": {"room_type": "Corridor", "building_type": "residential"}
  }'
```

**Expected Response:**
```json
{
  "compliant": false,
  "violations": [{
    "rule_id": "ČSN_73_0802_Sec_5.2.a",
    "severity": "critical",
    "message": "Corridor width (1000.0mm) is less than minimum 1200mm required by ČSN 73 0802",
    "required_value": 1200.0,
    "actual_value": 1000.0,
    "code_reference": "Section 5.2(a) - Escape Routes",
    "confidence_score": 0.98
  }],
  "recommendations": ["Increase corridor spacing to meet minimum requirements"],
  "checked_at": "2025-11-17T21:04:28.879277Z"
}
```

## 📁 Project Structure

```
projektant-software/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app with /health & /api/v1/*
│   │   ├── config.py                  # Pydantic settings
│   │   ├── models/                    # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   └── compliance.py          # ComplianceRule, ComplianceCheck, CheckResult
│   │   ├── schemas/                   # Pydantic validation
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   └── compliance.py
│   │   ├── api/v1/endpoints/
│   │   │   ├── health.py
│   │   │   └── compliance.py          # POST /check endpoint
│   │   ├── services/
│   │   │   ├── rag_service.py         # RAG pipeline for building codes
│   │   │   ├── vector_service.py      # Pinecone vector operations
│   │   │   └── compliance_engine.py   # Core compliance checking logic
│   │   ├── db/
│   │   │   ├── session.py             # Async SQLAlchemy session
│   │   │   └── base.py                # Declarative base
│   │   └── core/
│   │       ├── logging.py             # Loguru configuration
│   │       └── security.py            # Auth utilities
│   ├── alembic/
│   │   ├── versions/
│   │   │   └── 001_initial_tables.py  # Initial migration
│   │   └── env.py                     # Alembic config
│   ├── requirements.txt               # All dependencies
│   ├── .env.example                   # Environment template
│   └── alembic.ini                    # Alembic configuration
├── plugin/
│   └── ProjektantCopilot/             # C# Revit plugin shell
├── docker-compose.yml                 # PostgreSQL, Neo4j, Redis
└── README.md
```

## 🗄️ Database Services

| Service | Port | Credentials | Purpose |
|---------|------|-------------|---------|
| PostgreSQL | 5432 | postgres/postgres | Main database |
| Neo4j | 7474/7687 | neo4j/password | Graph relationships |
| Redis | 6379 | - | Caching |
| Adminer | 8080 | - | DB management UI |

### Access Neo4j Browser
http://localhost:7474

### Access Adminer (DB UI)
http://localhost:8080

## 🔑 Required API Keys

Add these to your `.env` file:

```bash
# OpenAI (for embeddings & GPT-4)
OPENAI_API_KEY=sk-...

# Pinecone (vector database)
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=us-west1-gcp-free
```

## 📊 Database Models

### ComplianceRule
```python
rule_id: "ČSN_73_0802_Sec_5.2.a"
rule_type: "min_width"
geometry_type: "corridor"
value_mm: 1200
building_types: ["residential", "office"]
severity: "critical"
```

### ComplianceCheck
Tracks every compliance check performed from Revit plugin.

### CheckResult
Detailed violation records with confidence scores.

## 🎯 Next Steps

1. **Load Building Codes** - Ingest ČSN PDFs into vector database
2. **Configure RAG Pipeline** - Connect to Pinecone
3. **Build Revit Plugin** - C# integration with FastAPI backend
4. **Add Authentication** - JWT-based user auth
5. **Deploy to Production** - Docker + Kubernetes

## 🚨 Troubleshooting

### Port Already in Use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Database Connection Failed
```bash
# Check if PostgreSQL is running
docker-compose ps

# View logs
docker-compose logs postgres
```

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## 📖 API Documentation

Once server is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 🔥 Demo for Autodesk

```bash
# 1. Start everything
docker-compose up -d && cd backend && uvicorn app.main:app --reload

# 2. Show health check
curl http://localhost:8000/health

# 3. Demo compliance check with violation
curl -X POST http://localhost:8000/api/v1/compliance/check \
  -H "Content-Type: application/json" \
  -d '{"element_type":"Corridor","properties":{"width_mm":900},"context":{"room_type":"Corridor"}}'

# 4. Demo compliant check
curl -X POST http://localhost:8000/api/v1/compliance/check \
  -H "Content-Type: application/json" \
  -d '{"element_type":"Corridor","properties":{"width_mm":1500},"context":{"room_type":"Corridor"}}'
```

---

**Built for production. Ready for Autodesk demo. 🚀**

Need help? Check logs: `docker-compose logs -f` or FastAPI docs at `/docs`
