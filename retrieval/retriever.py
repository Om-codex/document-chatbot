import logging

from qdrant_client.http.models import FieldCondition, Filter, MatchAny

from config.settings import settings
from vectorstore.qdrant_store import get_vector_store

logger = logging.getLogger(__name__)


def get_retriever(
    k: int = settings.default_top_k,
    doc_ids: list[str] | None = None,
    user_id: int | None = None,
):
    """Build a similarity retriever scoped to one user.

    ``user_id`` is always applied when supplied so one authenticated user can
    never retrieve another user's chunks, even when the same doc_id exists.
    """

    if k <= 0:
        raise ValueError("k must be greater than zero")

    vector_store = get_vector_store()

    search_kwargs: dict = {"k": k}

    conditions: list[FieldCondition] = []

    if user_id is not None:
        conditions.append(
            FieldCondition(
                key="metadata.user_id",
                match=MatchAny(any=[user_id]),
            )
        )

    if doc_ids:
        # QdrantVectorStore nests metadata under the "metadata" key.
        conditions.append(
            FieldCondition(
                key="metadata.doc_id",
                match=MatchAny(any=doc_ids),
            )
        )

    if conditions:
        search_kwargs["filter"] = Filter(must=conditions)

    logger.debug(
        "Creating retriever: k=%d user_id=%s selected_documents=%s",
        k,
        user_id,
        len(doc_ids) if doc_ids else "all",
    )

    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs=search_kwargs,
    )
