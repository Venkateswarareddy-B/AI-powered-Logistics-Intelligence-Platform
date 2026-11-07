"""Application configuration for YottaFlex.

Settings are loaded from environment variables and an optional local
``.env`` file via pydantic-settings. The module is designed so that the
backend can be imported and started in local/demo mode WITHOUT any external
credentials (no running database and no Groq API key required to import
this module or boot the app).

Provider abstraction note:
    GenAI access is routed through a single ``GROQ_*`` configuration group.
    The application intentionally never uses the OpenAI API. Swapping the
    LLM provider later only requires changing this group plus the provider
    implementation in ``genai/llm`` — business logic stays unchanged.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings sourced from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---------------- Branding ----------------
    APP_NAME: str = "YottaFlex"
    APP_TAGLINE: str = "AI-Powered Logistics Intelligence Platform"
    APP_VERSION: str = "0.1.0"

    # ---------------- Application ----------------
    ENV: Literal["local", "demo", "production"] = "local"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api"
    LOG_LEVEL: str = "INFO"

    # ---------------- CORS ----------------
    # Stored as a plain string in .env (comma-separated).
    # pydantic-settings v2 would attempt JSON-decoding a list[str] field before
    # any validator runs, which breaks comma-separated values in .env files.
    # We declare it as str here and expose a validated list via a property.
    CORS_ORIGINS_STR: str = (
        "http://localhost:5173,http://localhost:4173,http://localhost:3000"
    )

    @property
    def CORS_ORIGINS(self) -> list[str]:
        """Return the parsed CORS origins list."""
        return [o.strip() for o in self.CORS_ORIGINS_STR.split(",") if o.strip()]

    # ---------------- PostgreSQL ----------------
    POSTGRES_HOST: str = "localhost"
    # Platform Postgres runs on 5434 to avoid conflict with native PG installs.
    POSTGRES_PORT: int = 5434
    POSTGRES_USER: str = "logistics"
    POSTGRES_PASSWORD: str = "logistics"
    POSTGRES_DB: str = "logistics_ai"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE_SECONDS: int = 1800

    # ---------------- JWT / Auth ----------------
    JWT_SECRET: str = "change-me-this-is-not-a-real-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---------------- Demo login ----------------
    DEMO_USER_ENABLED: bool = True
    DEMO_USERNAME: str = "demo_admin"
    DEMO_PASSWORD: str = "Demo@YottaFlex2026"
    DEMO_USER_FULL_NAME: str = "Demo Administrator"
    DEMO_USER_ROLE: str = "ADMIN"

    # ---------------- Groq / GenAI (OpenAI is intentionally NOT used) -----
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_REQUEST_TIMEOUT_SECONDS: float = 60.0
    # Flipped on only after a valid GROQ_API_KEY is provided.
    GROQ_ENABLED: bool = False

    # ---------------- RAG ----------------
    RAG_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    RAG_CHUNK_SIZE: int = 800
    RAG_CHUNK_OVERLAP: int = 120
    RAG_TOP_K: int = 5
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    # Flipped on after ChromaDB + embeddings are initialized (Phase 17).
    RAG_ENABLED: bool = False

    # ---------------- Machine Learning ----------------
    ML_MODELS_DIR: str = "./ml/models"
    ML_ARTIFACTS_DIR: str = "./ml/artifacts"
    ML_DEFAULT_ETA_MODEL: str = "eta_gradient_boosting"
    ML_DEFAULT_DELAY_MODEL: str = "delay_gradient_boosting"
    RANDOM_SEED: int = 20261022

    # ---------------- Demo data ----------------
    DEMO_DATA_SEED: int = 20261022
    DEMO_DEFAULT_SHIPMENTS: int = 100
    DEMO_DATA_DIR: str = "./data/demo"

    # ---------------- Derived helpers ----------------
    @property
    def database_url(self) -> str:
        """Synchronous SQLAlchemy URL using the psycopg3 dialect."""
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def async_database_url(self) -> str:
        """Async-capable SQLAlchemy URL (psycopg3 supports async natively)."""
        return self.database_url

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.

    Using a factory (instead of a module-level singleton) keeps settings
    easy to override in tests via ``get_settings.cache_clear()``.
    """
    return Settings()
