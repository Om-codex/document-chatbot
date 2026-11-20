import logging

from fastapi import APIRouter

from schemas.health import HealthResponse
from config.settings import settings
from vectorstore.qdrant_store import is_collection_available

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/health",
    tags=["Health"],
)


@router.get("", response_model=HealthResponse)
def health():
    """Cheap readiness check. Does not load the embedding model or call the LLM."""

    status = "ok"

    try:
        if not is_collection_available():
            status = "degraded"
    except Exception:
        logger.exception("Health check could not read the vector store.")
        status = "degraded"

    return {
        "status": status,
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "llm_model": settings.llm_model,
        "embedding_model": settings.gemini_embedding_model,
        "collection": settings.qdrant_collection_name,
    }
