import logging

from fastapi import APIRouter

from api.schemas.health import HealthResponse
from config.settings import settings
from vectorstore.chroma_store import get_document_count

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/health",
    tags=["Health"],
)


@router.get("", response_model=HealthResponse)
def health():
    """Cheap readiness check. Does not load the embedding model or call the LLM."""

    document_count: int | None = None
    status = "ok"

    try:
        document_count = get_document_count()
    except Exception:
        logger.exception("Health check could not read the vector store.")
        status = "degraded"

    return {
        "status": status,
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model_name,
        "collection": settings.chroma_collection_name,
        "document_count": document_count,
    }
