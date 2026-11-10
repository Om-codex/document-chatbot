import logging

from config.settings import settings
from vectorstore.chroma_store import get_vector_store

logger = logging.getLogger(__name__)


def get_retriever(k: int = settings.default_top_k, doc_ids: list[str] | None = None):
    """Build a similarity retriever for all documents or a selected subset."""

    if k <= 0:
        raise ValueError("k must be greater than zero")

    vector_store = get_vector_store()

    search_kwargs: dict = {"k": k}

    if doc_ids:
        search_kwargs["filter"] = {"doc_id": {"$in": doc_ids}}

    logger.debug(
        "Creating retriever: k=%d selected_documents=%s",
        k,
        len(doc_ids) if doc_ids else "all",
    )

    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs=search_kwargs,
    )
