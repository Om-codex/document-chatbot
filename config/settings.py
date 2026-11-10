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

    # Accept the older EMBEDDING_MODEL name as well as EMBEDDING_MODEL_NAME.
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        validation_alias=AliasChoices("embedding_model_name", "embedding_model"),
    )
    embedding_device: str = "cpu"
    normalize_embeddings: bool = True

    # -------------------------------------
    # ChromaDB Configuration
    # -------------------------------------

    chroma_collection_name: str = "document_collection_v2"
    chroma_persist_directory: Path = BASE_DIR / "data" / "chroma_db"

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
