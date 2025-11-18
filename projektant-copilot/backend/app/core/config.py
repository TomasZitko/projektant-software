"""
Application Configuration

Centralized configuration using Pydantic Settings.
Reads from environment variables with validation.

Author: Projektant Copilot Team
License: Commercial
"""

from pydantic_settings import BaseSettings
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All sensitive data (API keys, passwords) MUST be in .env file,
    NEVER committed to git.
    """

    # Application
    APP_NAME: str = "Projektant Copilot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production

    # API
    API_V1_PREFIX: str = "/api/v1"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Security
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_TO_RANDOM_SECRET"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Database (PostgreSQL)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/projektant_copilot"
    DB_ECHO: bool = False  # SQL query logging
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Neo4j Graph Database
    NEO4J_URI: str = "neo4j://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Pinecone Vector Database
    PINECONE_API_KEY: str = "your-pinecone-api-key"
    PINECONE_ENVIRONMENT: str = "us-east-1"
    PINECONE_INDEX_NAME: str = "projektant-copilot"

    # OpenAI
    OPENAI_API_KEY: str = "your-openai-api-key"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    OPENAI_EMBEDDING_DIMENSION: int = 3072

    # Anthropic Claude
    ANTHROPIC_API_KEY: str = "your-anthropic-api-key"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250929"
    ANTHROPIC_MAX_TOKENS: int = 4000

    # Redis Cache (optional)
    REDIS_URL: Optional[str] = None
    CACHE_TTL_SECONDS: int = 3600

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 100

    # RAG Configuration
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 100
    RAG_TOP_K: int = 15
    RAG_SIMILARITY_THRESHOLD: float = 0.7

    # Compliance Checking
    COMPLIANCE_CONFIDENCE_THRESHOLD: float = 0.8
    COMPLIANCE_MAX_RETRIES: int = 3

    # Czech Language Support
    ENABLE_CZECH_LANGUAGE: bool = True
    DEFAULT_LANGUAGE: str = "cs"

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MAX_CONNECTIONS: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Convenience instance
settings = get_settings()
