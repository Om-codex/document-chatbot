"""Qdrant Cloud vector store implementation.

Replaces ChromaDB for the Document Chatbot. Preserves the same public
interface as ``vectorstore.chroma_store`` so services and retrievers can
switch with minimal changes.

Uses ``gemini-embedding-2`` (768-dim, L2-normalized) with Cosine distance.
Point IDs are deterministic UUIDs derived from chunk IDs
(``{doc_id}_{chunk_index}``) via ``uuid.uuid5``.
"""

import logging
import uuid
from functools import lru_cache

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    VectorParams,
)

from config.settings import settings
from embeddings.embedding_model import get_embedding_model

logger = logging.getLogger(__name__)

COLLECTION_NAME = settings.qdrant_collection_name
VECTOR_SIZE = settings.embedding_dimensions
UPSERT_BATCH_SIZE = settings.qdrant_upsert_batch_size

# Fixed UUID namespace for deterministic point IDs from chunk IDs
_QDRANT_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _chunk_id_to_uuid(chunk_id: str) -> str:
    """Convert a deterministic chunk ID to a Qdrant-compatible UUID string.

    Uses ``uuid.uuid5`` so the same chunk ID always maps to the same UUID,
    preserving the deterministic ID behaviour required for document
    replacement and deletion.
    """

    return str(uuid.uuid5(_QDRANT_NAMESPACE, chunk_id))


def _doc_id_filter(doc_id: str) -> Filter:
    """Build a Qdrant filter matching a single ``doc_id`` in point payload."""

    return Filter(
        must=[FieldCondition(key="doc_id", match=MatchAny(any=[doc_id]))]
    )


def _doc_ids_filter(doc_ids: list[str]) -> Filter:
    """Build a Qdrant filter matching any of the given ``doc_ids`` in payload."""

    return Filter(
        must=[FieldCondition(key="doc_id", match=MatchAny(any=doc_ids))]
    )


def _get_qdrant_client() -> QdrantClient:
    """Create a Qdrant Cloud client from environment credentials."""

    if settings.qdrant_api_key is None:
        raise ValueError("QDRANT_API_KEY is not configured.")
    if settings.qdrant_url is None:
        raise ValueError("QDRANT_URL is not configured.")

    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )


def _ensure_collection(client: QdrantClient) -> None:
    """Create the Qdrant collection if it does not exist yet.

    The collection is created with ``VECTOR_SIZE`` dimensions and the
    configured distance metric (Cosine for normalized embeddings).
    """

    try:
        collections = client.get_collections().collections
        if any(c.name == COLLECTION_NAME for c in collections):
            return
    except Exception:
        logger.debug("Could not list collections; will attempt creation.")

    distance = (
        Distance.COSINE
        if settings.qdrant_distance.lower() == "cosine"
        else Distance.DOT
    )

    logger.info(
        "Creating Qdrant collection %s (%d-dim, %s)",
        COLLECTION_NAME,
        VECTOR_SIZE,
        settings.qdrant_distance,
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=distance),
    )

    # Create a payload index on doc_id so metadata filtering works.
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="doc_id",
        field_schema="keyword",
    )


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    """Return the process-local Qdrant vector store wrapper.

    The cache is process-local: each Uvicorn worker gets its own client
    and embedding model.  The collection is created on first access.
    """

    embedding_model = get_embedding_model()
    client = _get_qdrant_client()
    _ensure_collection(client)

    logger.info("Opening Qdrant collection %s", COLLECTION_NAME)

    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embedding_model,
    )


def add_documents(chunks) -> list[str]:
    """Insert or replace all chunks for one document.

    Replacement is deliberately *not* "delete everything, then insert".
    New chunks are upserted first (overwriting matching old IDs) and only
    then are IDs that no longer exist removed.  If the upsert fails, the
    previous version of the document is still present.

    Returns the original deterministic chunk ID strings
    (``{doc_id}_{chunk_index}``).
    """

    if not chunks:
        raise ValueError("No document chunks provided!")

    doc_id = chunks[0].metadata.get("doc_id")
    if not doc_id:
        raise ValueError("Every chunk must include a doc_id.")

    if any(chunk.metadata.get("doc_id") != doc_id for chunk in chunks):
        raise ValueError("All chunks must belong to the same document!")

    vector_store = get_vector_store()
    client = _get_qdrant_client()

    # Deterministic UUID string IDs from chunk IDs.
    new_ids = [f"{doc_id}_{chunk.metadata['chunk_index']}" for chunk in chunks]
    new_id_set = set(new_ids)
    new_uuid_ids = [_chunk_id_to_uuid(cid) for cid in new_ids]

    # Find existing chunks for this document.
    existing_points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=_doc_id_filter(doc_id),
        with_payload=False,
        with_vectors=False,
        limit=10000,
    )
    existing_ids = [str(point.id) for point in existing_points] if existing_points else []
    stale_ids = [cid for cid in existing_ids if cid not in new_id_set]

    logger.info(
        "Storing document chunks: doc_id=%s chunks=%d stale_chunks=%d",
        doc_id[:12],
        len(chunks),
        len(stale_ids),
    )

    # Upsert new chunks in batches.  QdrantVectorStore handles embedding
    # via the configured GeminiEmbedding function.
    for start in range(0, len(chunks), UPSERT_BATCH_SIZE):
        batch_chunks = chunks[start : start + UPSERT_BATCH_SIZE]
        batch_uuid_ids = new_uuid_ids[start : start + UPSERT_BATCH_SIZE]

        vector_store.add_documents(
            documents=batch_chunks,
            ids=batch_uuid_ids,
        )

    if stale_ids:
        stale_uuids = [_chunk_id_to_uuid(cid) for cid in stale_ids]
        try:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=stale_uuids,
            )
        except Exception:
            logger.exception(
                "Failed to delete stale chunks: doc_id=%s stale_chunks=%d",
                doc_id[:12],
                len(stale_ids),
            )
            raise

    return new_ids


def get_all_documents() -> list[dict]:
    """Return one summary row per indexed document."""

    client = _get_qdrant_client()

    # If the collection doesn't exist yet, there are no documents.
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        return []

    # Scroll all points with payload (no vectors needed).
    all_points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        with_payload=True,
        with_vectors=False,
        limit=10000,
    )

    documents: dict[str, dict] = {}

    for point in all_points or []:
        payload = point.payload or {}
        doc_id = payload.get("doc_id")

        if not doc_id:
            continue

        if doc_id not in documents:
            documents[doc_id] = {
                "doc_id": doc_id,
                "filename": payload.get("filename"),
                "total_pages": payload.get("total_pages"),
                "total_chunks": 0,
            }

        documents[doc_id]["total_chunks"] += 1

    return sorted(
        documents.values(),
        key=lambda document: (
            (document["filename"] or "").lower(),
            document["doc_id"],
        ),
    )


def document_exists(doc_id: str) -> bool:
    """Return True when at least one chunk is stored for ``doc_id``."""

    client = _get_qdrant_client()

    # If the collection doesn't exist yet, the document doesn't exist.
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        return False

    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=_doc_id_filter(doc_id),
        with_payload=False,
        with_vectors=False,
        limit=1,
    )
    return bool(points)


def count_document_chunks(doc_id: str) -> int:
    """Return the number of stored chunks for ``doc_id``."""

    client = _get_qdrant_client()

    # If the collection doesn't exist yet, there are no chunks.
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        return 0

    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=_doc_id_filter(doc_id),
        with_payload=False,
        with_vectors=False,
        limit=10000,
    )
    return len(points) if points else 0


def delete_documents(doc_id: str) -> int:
    """Delete every vector belonging to ``doc_id`` and return the count."""

    client = _get_qdrant_client()

    deleted_count = count_document_chunks(doc_id)

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=_doc_id_filter(doc_id),
    )

    logger.info(
        "Deleted document vectors: doc_id=%s chunks=%d",
        doc_id[:12],
        deleted_count,
    )

    return deleted_count


def get_document_count() -> int:
    """Cheap document count for health checks.

    Uses Qdrant collection info plus a payload scroll to count unique
    ``doc_id`` values without loading the embedding model.
    """

    client = _get_qdrant_client()

    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        return 0

    try:
        points, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            with_payload=True,
            with_vectors=False,
            limit=10000,
        )
    except Exception:
        return 0

    doc_ids = {
        (point.payload or {}).get("doc_id")
        for point in (points or [])
        if (point.payload or {}).get("doc_id")
    }

    return len(doc_ids)
