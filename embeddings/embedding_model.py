import logging
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from config.settings import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model() -> HuggingFaceEmbeddings:
    """Load the local sentence-transformers model once per process.

    The cache is process-local.  With multiple Uvicorn workers, each worker
    loads its own copy, so keep ``--workers 1`` for local development.
    """

    logger.info(
        "Loading embedding model %s on %s",
        settings.embedding_model_name,
        settings.embedding_device,
    )

    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model_name,
        model_kwargs={"device": settings.embedding_device},
        encode_kwargs={"normalize_embeddings": settings.normalize_embeddings},
    )
