from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_version: str
    llm_model: str
    embedding_model: str
    collection: str
    document_count: int | None = None
