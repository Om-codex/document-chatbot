from pydantic import BaseModel, Field, field_validator

from config.settings import settings
from utils.validation import is_valid_doc_id


# chat request schema

class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_question_length,
        description="Question to ask about the uploaded documents.",
    )

    doc_ids: list[str] | None = Field(
        default=None,
        max_length=settings.max_selected_documents,
        description="Optional list of document IDs to search. Omit or null for all documents.",
    )

    k: int = Field(
        default=settings.default_top_k,
        ge=1,
        le=settings.max_top_k,
        description="Number of document chunks to retrieve.",
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Question cannot be empty.")

        return value

    @field_validator("doc_ids")
    @classmethod
    def validate_doc_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None

        cleaned_ids: list[str] = []

        for doc_id in value:
            doc_id = doc_id.strip()

            if not doc_id:
                raise ValueError("Document IDs cannot contain empty values.")

            if not is_valid_doc_id(doc_id):
                raise ValueError(
                    "Document IDs must be 64-character lowercase SHA-256 hex strings."
                )

            cleaned_ids.append(doc_id)

        if len(cleaned_ids) != len(set(cleaned_ids)):
            raise ValueError("Duplicate document IDs are not allowed.")

        return cleaned_ids


# retrieved chunk metadata schema
class ChunkMetadata(BaseModel):
    doc_id: str
    filename: str
    chunk_index: int

    page: int | None = None
    page_number: int | None = None
    page_label: str | None = None
    total_pages: int | None = None


# retrieved chunk schema
class RetrievedChunk(BaseModel):
    chunk_id: str
    content: str
    metadata: ChunkMetadata


# chat response schema
class ChatResponse(BaseModel):
    question: str
    answer: str
    total_chunks_retrieved: int
    retrieved_chunks: list[RetrievedChunk]
