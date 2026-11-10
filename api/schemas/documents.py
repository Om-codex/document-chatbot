from pydantic import BaseModel, Field


# individual document schema

class DocumentResponse(BaseModel):
    doc_id: str = Field(
        description="Unique content-based document identifier."
    )

    filename: str = Field(
        description="Original document filename."
    )

    total_pages: int | None = Field(
        default=None,
        description="Total number of pages, if available."
    )

    total_chunks: int = Field(
        ge=0,
        description="Total number of chunks stored in ChromaDB."
    )


# Document listing Response schema

class DocumentListResponse(BaseModel):
    total_documents: int = Field(
        ge=0,
        description="Total number of indexed documents."
    )

    documents: list[DocumentResponse]


# Document upload Response schema

class DocumentUploadResponse(BaseModel):
    message: str
    filename: str
    doc_id: str
    total_chunks: int = Field(ge=0)
    file_size_bytes: int = Field(ge=0)


# Document deletion response schema

class DocumentDeleteResponse(BaseModel):
    message: str
    doc_id: str
    filename: str
    deleted_files: int = Field(ge=0)
    vectors_deleted: bool
    warnings: list[str] = Field(default_factory=list)
