
from pathlib import Path
from functools import cached_property

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# -----------------------------------------
# Project Configuration
# -----------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):

    # Load environment variables from project root
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # -------------------------------------
    # Application
    # -------------------------------------

    app_name: str = "Document Chatbot API"
    app_version: str = "1.0.0"

    # -------------------------------------
    # LLM Configuration
    # -------------------------------------

    groq_api_key: SecretStr | None = None

    llm_model: str = "openai/gpt-oss-20b"
    llm_temperature: float = 0.0
    llm_max_retries: int = 2

    # -------------------------------------
    # Embedding Configuration
    # -------------------------------------

    embedding_model_name: str = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    embedding_device: str = "cpu"
    normalize_embeddings: bool = True

    # -------------------------------------
    # ChromaDB Configuration
    # -------------------------------------

    chroma_collection_name: str = "document_collection_v2"

    @cached_property
    def chroma_persist_directory(self) -> Path:
        return BASE_DIR / "data" / "chroma_db"

    # -------------------------------------
    # Text Splitting Configuration
    # -------------------------------------

    chunk_size: int = 1000
    chunk_overlap: int = 200

    # -------------------------------------
    # Document Upload Configuration
    # -------------------------------------

    @cached_property
    def upload_directory(self) -> Path:
        return BASE_DIR / "data" / "uploads"

    max_file_size_bytes: int = 10 * 1024 * 1024

    allowed_extensions: set[str] = {
        ".pdf",
        ".docx",
        ".txt"
    }


# -----------------------------------------
# Global Settings Instance
# -----------------------------------------

settings = Settings()
