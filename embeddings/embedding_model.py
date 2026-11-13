import logging
from functools import lru_cache

from embeddings.gemini_embedding import GeminiEmbedding

from config.settings import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model() -> GeminiEmbedding:
    """Return the process-local Gemini embedding model.

    The cache is process-local: each Uvicorn worker gets its own client.
    No model is downloaded or loaded into memory -- only the API client is
    created -- which keeps the backend footprint small enough for free-tier
    hosts with 512 MB RAM.
    """

    logger.info(
        "Initializing Gemini embedding client: model=%s dimensions=%d batch_size=%d",
        settings.gemini_embedding_model,
        settings.embedding_dimensions,
        settings.embedding_batch_size,
    )

    return GeminiEmbedding()
