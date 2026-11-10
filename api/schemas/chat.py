from pydantic import BaseModel, Field, ConfigDict, field_validator

# chat request schema

class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Question to ask about the uploaded documents."
    )

    doc_ids: list[str] | None = Field(
        default=None,
        max_length=50,
        description="Optional list of document IDs to search."
    )

    k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of document chunks to retrieve."
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

        cleaned_ids = []

        for doc_id in value:
            doc_id = doc_id.strip()

            if not doc_id:
                raise ValueError("Document IDs cannot contain empty values.")

            cleaned_ids.append(doc_id)

        if len(cleaned_ids) != len(set(cleaned_ids)):
            raise ValueError("Duplicate document IDs are not allowed.")

        return cleaned_ids

# retrieved chunk metadata schema
class ChunkMetadata(BaseModel):

  doc_id : str
  filename : str
  chunk_index : int
  
  page : int | None = None
  page_number : int | None = None
  page_label : str | None = None
  total_pages : int | None = None

# retrieved chunk schema
class RetrievedChunk(BaseModel):

  chunk_id : str
  content : str
  metadata : ChunkMetadata

# chat response schema
class ChatResponse(BaseModel):

  model_config = ConfigDict(
    json_schema_extra = {
      "example" : {
        "question" : "What is the main topic?",
      "answer" : "The document discusses...",
      "total_chunks_retrieved" : 3,
      "retrieved_chunks" : []
      }
    }
  )

  question : str
  answer : str
  total_chunks_retrieved : int
  retrieved_chunks : list[RetrievedChunk]