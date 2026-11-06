from pydantic import BaseModel, Field, ConfigDict

# chat request schema

class ChatRequest(BaseModel):

  question : str = Field(
    min_length = 1,
    description = "Question to ask about the uploaded documents."
  )

  doc_ids : list[str] | None = Field(
    default = None,
    description = "Optional document IDs to search."
  )

  k : int = Field(
    default = 3,
    ge = 1,
    le = 20,
    description = "Number of relevant chunks to retrieve."
  )

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