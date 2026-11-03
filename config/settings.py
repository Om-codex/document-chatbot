
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# config/settings.py -> config -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application paths
    project_root: Path = PROJECT_ROOT

    upload_dir: Path = PROJECT_ROOT / "data" / "uploaded_docs"

    chroma_dir: Path = PROJECT_ROOT / "chroma_db"

    # Document ingestion
    chunk_size: int = Field(default=1000, gt=0)

    chunk_overlap: int = Field(default=200, ge=0)

    supported_extensions: tuple[str, ...] = (
        ".pdf",
        ".txt",
        ".docx",
    )

    # Upload limits
    max_file_size_mb: int = Field(default=20, gt=0)

    @model_validator(mode="after")
    def validate_chunk_configuration(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size"
            )

        return self

    @model_validator(mode="after")
    def resolve_paths(self):
        # Resolve relative paths against project root.
        root = self.project_root.expanduser().resolve()

        self.project_root = root

        for field_name in ("upload_dir", "chroma_dir"):
            path = getattr(self, field_name).expanduser()

            if not path.is_absolute():
                path = root / path

            setattr(self, field_name, path.resolve())

        return self

    def ensure_directories(self) -> None:
        """Create application storage directories when needed."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
