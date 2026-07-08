from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # Core
    APP_NAME: str = "GSM-OS"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    # API
    FASTAPI_HOST: str = "0.0.0.0"
    FASTAPI_PORT: int = 8000

    # LLM (Free Providers)
    GROQ_API_KEY: Optional[str] = None
    HUGGINGFACE_API_KEY: Optional[str] = None
    OLLAMA_ENDPOINT: str = "http://localhost:11434"
    DEFAULT_LLM_PROVIDER: str = "groq"
    DEFAULT_LLM_MODEL: str = "llama-3.3-70b-versatile"
    # OpenRouter: free frontier models — https://openrouter.ai
    OPENROUTER_API_KEY: Optional[str] = None

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_COLLECTION: str = "scientific_memory"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"  # Community Edition: use 'neo4j'; Enterprise: any name

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Research Sources (all free)
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = None
    CROSSREF_API_KEY: Optional[str] = None
    OPENALEX_API_KEY: Optional[str] = None
    # NCBI/PubMed: free key increases rate limit 3→10 req/sec — https://www.ncbi.nlm.nih.gov/account/
    NCBI_API_KEY: Optional[str] = None
    # CORE Open Access: free key required — https://core.ac.uk/api-documentation
    CORE_API_KEY: Optional[str] = None

    # Processing
    MAX_CONCURRENT_TASKS: int = 10
    BATCH_SIZE: int = 100
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Security
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3003"
    JWT_SECRET_KEY: str = "change-me-in-production-use-a-strong-random-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    RATE_LIMIT_DEFAULT_RATE: float = 10.0
    RATE_LIMIT_DEFAULT_BURST: int = 20
    RATE_LIMIT_AUTH_RATE: float = 5.0
    RATE_LIMIT_AUTH_BURST: int = 10

    # Audit
    AUDIT_LOG_DIR: str = "audit_logs"
    AUDIT_MAX_MEMORY_EVENTS: int = 10_000

    # Monitoring
    PROMETHEUS_PORT: int = 9090
    LOG_LEVEL: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
