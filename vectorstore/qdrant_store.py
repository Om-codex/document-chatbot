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
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PointStruct,
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


def _user_id_filter(user_id: int) -> Filter:
    """Match all documents belonging to a specific user."""

    return Filter(
        must = [
            FieldCondition(
                key="metadata.user_id",
                match = MatchAny(any=[user_id]),
            )
        ]
    )

def _user_doc_id_filter(user_id: int, doc_id: str) -> Filter:
    """Match a specific document belonging to a specific user."""

    return Filter(
        must=[
            FieldCondition(
                key="metadata.user_id",
                match=MatchAny(any=[user_id]),
            ),
            FieldCondition(
                key="metadata.doc_id",
                match=MatchAny(any=[doc_id]),
            )
            
        ]
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


def _ensure_payload_indexes(client: QdrantClient) -> None:
    """Ensure the payload indexes required by per-user metadata filters."""

    indexes = (
        ("metadata.user_id", "integer"),
        ("metadata.doc_id", "keyword"),
    )

    for field_name, field_schema in indexes:
        try:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field_name,
                field_schema=field_schema,
                wait=True,
            )
            logger.info(
                "Ensured payload index on %s for collection %s",
                field_name,
                COLLECTION_NAME,
            )
        except Exception as exc:
            if getattr(exc, "status_code", None) == 409:
                continue
            logger.warning(
                "Could not create payload index on %s: %s",
                field_name,
                exc,
            )


def _ensure_collection(client: QdrantClient) -> None:
    """Create the collection if needed and always ensure payload indexes.

    A collection lookup can transiently fail on Qdrant Cloud.  In that case we
    still attempt creation, but a ``409 Already exists`` response is treated as
    success instead of failing the upload.
    """

    try:
        if client.collection_exists(COLLECTION_NAME):
            _ensure_payload_indexes(client)
            return
    except Exception as exc:
        logger.warning(
            "Qdrant collection lookup failed; will retry via create: %s",
            exc,
        )

    distance = (
        Distance.COSINE
        if settings.qdrant_distance.lower() == "cosine"
        else Distance.DOT
    )

    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=distance),
        )
        logger.info(
            "Created Qdrant collection %s (%d-dim, %s)",
            COLLECTION_NAME,
            VECTOR_SIZE,
            settings.qdrant_distance,
        )
    except UnexpectedResponse as exc:
        if exc.status_code != 409:
            raise
        logger.info(
            "Qdrant collection %s already exists; continuing.",
            COLLECTION_NAME,
        )

    _ensure_payload_indexes(client)


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

    client = _get_qdrant_client()
    _ensure_collection(client)

    
    user_id = chunks[0].metadata.get("user_id")

    if user_id is None:
        raise ValueError("Every chunk must include a user_id.")

    if any(chunk.metadata.get("user_id") != user_id for chunk in chunks):
        raise ValueError("All chunks must belong to the same user.")

    # Deterministic UUID string IDs from chunk IDs.
    new_ids = [
        f"{user_id}_{doc_id}_{chunk.metadata['chunk_index']}"
        for chunk in chunks
    ]

    new_uuid_ids = [
        _chunk_id_to_uuid(cid)
        for cid in new_ids
    ]

    new_uuid_set = set(new_uuid_ids)

    # Find existing chunks for this document (scroll returns UUID point IDs).
    existing_points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=_user_doc_id_filter(user_id, doc_id),
        with_payload=False,
        with_vectors=False,
        limit=10000,
    )
    existing_uuid_ids = [str(point.id) for point in existing_points] if existing_points else []

    # Stale UUIDs are those that exist but are not in the new set.
    stale_uuid_ids = [uid for uid in existing_uuid_ids if uid not in new_uuid_set]

    logger.info(
        "Storing document chunks: doc_id=%s chunks=%d stale_chunks=%d",
        doc_id[:12],
        len(chunks),
        len(stale_uuid_ids),
    )

    # Generate embeddings for all chunks.
    embedding_model = get_embedding_model()
    texts = [chunk.page_content for chunk in chunks]
    vectors = embedding_model.embed_documents(texts)

    # Upsert points directly with deterministic UUIDs.  Using the raw client
    # ensures the exact IDs we computed are stored, which is required for
    # stale-chunk cleanup to work correctly.
    points = [
        PointStruct(
            id=uuid_id,
            vector=vector,
            payload={
                "page_content": chunk.page_content,
                "metadata": chunk.metadata,
            },
        )
        for uuid_id, vector, chunk in zip(new_uuid_ids, vectors, chunks)
    ]

    # Upsert in batches.
    for start in range(0, len(points), UPSERT_BATCH_SIZE):
        batch_points = points[start : start + UPSERT_BATCH_SIZE]
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=batch_points,
        )

    if stale_uuid_ids:
        try:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=stale_uuid_ids,
            )
        except Exception:
            logger.exception(
                "Failed to delete stale chunks: doc_id=%s stale_chunks=%d",
                doc_id[:12],
                len(stale_uuid_ids),
            )
            raise

    return new_ids


def get_all_documents(user_id: int) -> list[dict]:
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
        scroll_filter=_user_id_filter(user_id),
        with_payload=True,
        with_vectors=False,
        limit=10000,
    )

    documents: dict[str, dict] = {}

    for point in all_points or []:
        payload = point.payload or {}
        metadata = payload.get("metadata", {})
        doc_id = metadata.get("doc_id")

        if not doc_id:
            continue

        if doc_id not in documents:
            documents[doc_id] = {
                "doc_id": doc_id,
                "filename": metadata.get("filename"),
                "total_pages": metadata.get("total_pages"),
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


def document_exists(user_id: int, doc_id: str) -> bool:
    """Return True when at least one chunk is stored for ``doc_id``."""

    client = _get_qdrant_client()

    # If the collection doesn't exist yet, the document doesn't exist.
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        return False

    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=_user_doc_id_filter(user_id, doc_id),
        with_payload=False,
        with_vectors=False,
        limit=1,
    )
    return bool(points)


def count_document_chunks(user_id: int, doc_id: str) -> int:
    """Return the number of stored chunks for ``doc_id``."""

    client = _get_qdrant_client()

    # If the collection doesn't exist yet, there are no chunks.
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        return 0

    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=_user_doc_id_filter(user_id, doc_id),
        with_payload=False,
        with_vectors=False,
        limit=10000,
    )
    return len(points) if points else 0


def delete_documents(user_id: int, doc_id: str) -> int:
    """Delete every vector belonging to ``doc_id`` and return the count."""

    client = _get_qdrant_client()

    deleted_count = count_document_chunks(user_id, doc_id)

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=_user_doc_id_filter(user_id, doc_id),
    )

    logger.info(
        "Deleted document vectors: doc_id=%s chunks=%d",
        doc_id[:12],
        deleted_count,
    )

    return deleted_count


def is_collection_available() -> bool:
    """Cheap readiness check for the health endpoint.

    Only verifies that the Qdrant collection is reachable. It does not scroll
    payloads or expose document data: document counts are per-user and belong
    to the authenticated ``GET /api/documents/`` response.
    """

    try:
        _get_qdrant_client().get_collection(COLLECTION_NAME)
        return True
    except Exception:
        return False
