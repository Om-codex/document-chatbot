from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# -----------------------------------------
# Project Configuration
# -----------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Central application configuration.

    Values come from environment variables or the project-root ``.env`` file.
    Field names are lower-case; pydantic-settings matches them case-insensitively
    (for example ``LOG_LEVEL`` -> ``log_level``).
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -------------------------------------
    # Application
    # -------------------------------------

    app_name: str = "Document Chatbot API"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    # JSON list in .env, e.g. CORS_ALLOW_ORIGINS=["http://127.0.0.1:5500"]
    cors_allow_origins: list[str] = ["*"]

    # -------------------------------------
    # LLM Configuration
    # -------------------------------------

    groq_api_key: SecretStr | None = None

    llm_model: str = "openai/gpt-oss-20b"
    llm_temperature: float = 0.0
    llm_max_retries: int = 2
    llm_timeout_seconds: float = 60.0
    llm_max_tokens: int = 1024

    # -------------------------------------
    # Embedding Configuration
    # -------------------------------------

    # Google Gemini Embedding API configuration.
    # Replaces local sentence-transformers inference for low-memory deployment.
    gemini_api_key: SecretStr | None = None
    gemini_embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 100
    embedding_max_retries: int = 6
    embedding_initial_backoff_seconds: float = 3.0
    embedding_rate_limit_delay_seconds: float = 60.0

    # Normalize embeddings (L2) after retrieval from the API.
    normalize_embeddings: bool = True

    # -------------------------------------
    # ChromaDB Configuration (kept for rollback)
    # -------------------------------------

    chroma_collection_name: str = "document_collection_v2"
    chroma_persist_directory: Path = BASE_DIR / "data" / "chroma_db"

    # -------------------------------------
    # Qdrant Cloud Configuration
    # -------------------------------------

    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_collection_name: str = "document_collection_v2_gemini"
    qdrant_distance: str = "Cosine"
    qdrant_upsert_batch_size: int = 100
    qdrant_timeout_seconds: float = 30.0

    # -------------------------------------
    # HTTP Client Timeouts
    # -------------------------------------

    # Timeout for outbound HTTP requests to Qdrant, Groq, and Gemini APIs.
    http_request_timeout_seconds: float = 120.0

    # -------------------------------------
    # Text Splitting Configuration
    # -------------------------------------

    chunk_size: int = 1000
    chunk_overlap: int = 200

    # -------------------------------------
    # Document Upload Configuration
    # -------------------------------------

    upload_directory: Path = BASE_DIR / "data" / "uploads"
    max_file_size_bytes: int = 10 * 1024 * 1024
    max_filename_length: int = 200
    upload_read_chunk_size: int = 1024 * 1024

    allowed_extensions: set[str] = {".pdf", ".docx", ".txt"}

    # -------------------------------------
    # Request Validation / Retrieval
    # -------------------------------------

    max_question_length: int = 4000
    max_selected_documents: int = 50
    default_top_k: int = 3
    max_top_k: int = 20

    # -------------------------------------
    # Frontend
    # -------------------------------------

    @property
    def frontend_directory(self) -> Path:
        return BASE_DIR / "frontend"


# -----------------------------------------
# Global Settings Instance
# -----------------------------------------

settings = Settings()
