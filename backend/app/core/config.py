"""
Application configuration using Pydantic Settings.

Environment variables can be set in .env file or system environment.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )

    # Application
    app_name: str = "Projektant Copilot"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = Field(default="development", env="ENVIRONMENT")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True

    # Database - Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", env="NEO4J_USER")
    neo4j_password: str = Field(default="password", env="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", env="NEO4J_DATABASE")

    # RAG Services - OpenAI
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        env="OPENAI_EMBEDDING_MODEL"
    )
    openai_chat_model: str = Field(default="gpt-4-turbo-preview", env="OPENAI_CHAT_MODEL")
    openai_max_tokens: int = Field(default=4096, env="OPENAI_MAX_TOKENS")

    # RAG Services - Pinecone
    pinecone_api_key: str = Field(default="", env="PINECONE_API_KEY")
    pinecone_environment: str = Field(default="us-east-1", env="PINECONE_ENVIRONMENT")
    pinecone_index_name: str = Field(default="csn-building-codes", env="PINECONE_INDEX_NAME")

    # RAG Configuration
    rag_chunk_size: int = Field(default=500, env="RAG_CHUNK_SIZE")
    rag_chunk_overlap: int = Field(default=50, env="RAG_CHUNK_OVERLAP")
    rag_top_k: int = Field(default=10, env="RAG_TOP_K")
    rag_dense_weight: float = Field(default=0.7, env="RAG_DENSE_WEIGHT")
    rag_sparse_weight: float = Field(default=0.3, env="RAG_SPARSE_WEIGHT")

    # Document Processing
    docs_data_dir: str = Field(default="data/building_codes", env="DOCS_DATA_DIR")
    docs_cache_dir: str = Field(default="data/cache", env="DOCS_CACHE_DIR")

    # Redis Cache
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    redis_cache_ttl: int = Field(default=3600, env="REDIS_CACHE_TTL")  # 1 hour

    # Monitoring
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )

    # Security
    secret_key: str = Field(default="change-me-in-production", env="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    @validator("openai_api_key", "pinecone_api_key")
    def validate_api_keys(cls, v: str, field) -> str:
        """Validate that API keys are set in production."""
        if not v and os.getenv("ENVIRONMENT") == "production":
            raise ValueError(f"{field.name} must be set in production environment")
        return v

    @validator("rag_dense_weight", "rag_sparse_weight")
    def validate_weights(cls, v: float) -> float:
        """Validate that weights are between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Weight must be between 0 and 1")
        return v

    class Config:
        """Pydantic config."""
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
