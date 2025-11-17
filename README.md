# Projektant Copilot - AI-Powered Building Code Compliance Engine

**Revolutionary real-time compliance checking for Autodesk Revit using RAG technology**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![.NET Framework 4.8](https://img.shields.io/badge/.NET-4.8-purple.svg)](https://dotnet.microsoft.com/)

## 🚀 60-Second Pitch

Projektant Copilot is an AI-powered Revit plugin that checks building code compliance **in real-time** as you design. No more manual code review. No more compliance violations discovered late in the project. Just instant, intelligent feedback powered by RAG (Retrieval Augmented Generation) and Czech building codes (ČSN standards).

> 🔥 **[→ 60-SECOND QUICKSTART GUIDE ←](QUICKSTART.md)** - Get running NOW!

**Key Features:**
- ⚡ **Real-time compliance checking** as you model in Revit
- 🧠 **RAG-powered** intelligent code interpretation
- 🇨🇿 **Czech ČSN standards** (ČSN 73 0802 Fire Safety and more)
- 📊 **Detailed violation reports** with code references
- 🔌 **Seamless Revit integration** via ribbon panel
- 🐳 **Easy deployment** with Docker Compose

## 📸 Screenshots

*Coming soon - Plugin in action*

## 🏗️ Architecture

```
┌─────────────────┐
│  Revit Plugin   │  ← C# .NET Framework 4.8
│  (User Interface)│
└────────┬────────┘
         │ REST API
         ▼
┌─────────────────┐
│  FastAPI Backend│  ← Python 3.11
│  (RAG Engine)   │
└────────┬────────┘
         │
    ┌────┴─────────────────┬──────────────┐
    ▼                      ▼              ▼
┌──────────┐         ┌──────────┐   ┌─────────┐
│PostgreSQL│         │ Pinecone │   │  Neo4j  │
│(Metadata)│         │ (Vectors)│   │ (Graph) │
└──────────┘         └──────────┘   └─────────┘
```

## 🛠️ Technology Stack

### Backend
- **FastAPI** - High-performance async web framework
- **LangChain** - RAG pipeline orchestration
- **Pinecone** - Vector database for embeddings
- **PostgreSQL** - Relational database for metadata
- **Neo4j** - Graph database for BIM relationships
- **Redis** - Caching layer
- **OpenAI** - Embeddings generation

### Revit Plugin
- **C# .NET Framework 4.8** - Revit API compatibility
- **Revit API 2024** - Building information modeling
- **RestSharp** - HTTP client
- **Serilog** - Structured logging

## ⚡ Quick Start (< 5 minutes)

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Visual Studio 2022 (for plugin development)
- Autodesk Revit 2024 (for testing plugin)
- Pinecone API key (free tier)
- OpenAI API key

### 1. Clone Repository

```bash
git clone https://github.com/yourorg/projektant-software.git
cd projektant-software
```

### 2. Start Backend Services

```bash
cd docker
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Neo4j (ports 7474, 7687)
- Redis (port 6379)
- Adminer database UI (port 8080)

### 3. Configure Backend

```bash
cd ../backend
cp .env.example .env
```

Edit `.env` and add your API keys:
```bash
PINECONE_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

### 4. Install Backend Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

### 6. Start Backend API

```bash
uvicorn app.main:app --reload
```

Visit http://localhost:8000/docs to see the API documentation.

### 7. Build Revit Plugin (Windows only)

Open `plugin/ProjektantCopilot/ProjektantCopilot.csproj` in Visual Studio 2022 and build.

### 8. Install Plugin in Revit

Copy files to Revit addins folder:
```powershell
# Windows
xcopy /Y plugin\ProjektantCopilot\bin\Debug\*.dll "%APPDATA%\Autodesk\Revit\Addins\2024\"
xcopy /Y plugin\ProjektantCopilot\bin\Debug\*.addin "%APPDATA%\Autodesk\Revit\Addins\2024\"
```

### 9. Test It!

1. Open Revit 2024
2. Look for "Projektant" tab in ribbon
3. Draw a corridor wall
4. Click "Check Compliance"
5. See instant feedback!

## 📚 Documentation

- [Architecture Guide](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Plugin Development](docs/PLUGIN.md)
- [Development Setup](docs/DEVELOPMENT.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v --cov=app
```

### Plugin Tests
Open `plugin/ProjektantCopilot.Tests/` in Visual Studio and run tests.

## 🐛 Troubleshooting

### Backend won't start
- Check Docker containers are running: `docker-compose ps`
- Verify database connection: `docker-compose logs postgres`

### Plugin won't load in Revit
- Check logs: `%APPDATA%\ProjektantCopilot\Logs\`
- Verify .NET Framework 4.8 is installed
- Check manifest.addin file is in correct location

### API connection fails
- Ensure backend is running on http://localhost:8000
- Check firewall settings
- Verify API key in plugin settings

## 🗺️ Roadmap

### Phase 1: MVP ✅ (Current)
- [x] FastAPI backend infrastructure
- [x] Basic RAG pipeline
- [x] Revit plugin foundation
- [x] PostgreSQL integration
- [x] Docker Compose setup

### Phase 2: RAG Enhancement (Next)
- [ ] Document ingestion pipeline for Czech codes
- [ ] Pinecone vector search optimization
- [ ] Multi-language support (Czech/English)
- [ ] Advanced reranking

### Phase 3: Advanced Features
- [ ] Neo4j graph queries for BIM relationships
- [ ] PDF report generation
- [ ] Historical compliance tracking
- [ ] Batch project analysis

### Phase 4: Production
- [ ] Authentication & authorization
- [ ] Multi-tenant support
- [ ] Cloud deployment (AWS/Azure)
- [ ] Performance optimization
- [ ] Monitoring & observability

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Czech Office for Standards, Metrology and Testing (ÚNMZ) for ČSN standards
- Autodesk for Revit API
- OpenAI for embeddings technology
- Pinecone for vector database

## 📞 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/yourorg/projektant-software/issues)
- **Email**: support@projektant.ai
- **Website**: https://projektant.ai

---

**Built with ❤️ for architects and engineers**

*Making building code compliance automatic, not an afterthought.*
