import logging
from functools import lru_cache

from langchain_chroma import Chroma

from config.settings import settings
from embeddings.embedding_model import get_embedding_model

logger = logging.getLogger(__name__)


# These module-level values are read once at import time.  Tests override them
# with a temporary directory/collection and call ``get_vector_store.cache_clear()``.
CHROMA_PATH = settings.chroma_persist_directory
COLLECTION_NAME = settings.chroma_collection_name


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    """Return the process-local Chroma wrapper.

    The cache is process-local: each Uvicorn worker gets its own embedding model
    and Chroma client.  Run a single worker in local development because Chroma's
    persistent mode is SQLite-backed (see docs/DECISIONS.md, ADR-6).
    """

    embedding_model = get_embedding_model()

    logger.info("Opening Chroma collection %s", COLLECTION_NAME)

    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedding_model,
        persist_directory=str(CHROMA_PATH),
    )


def add_documents(chunks) -> list[str]:
    """Insert or replace all chunks for one document.

    Replacement is deliberately *not* "delete everything, then insert".  Chroma
    upserts by ID, so we first upsert the new deterministic IDs (overwriting
    matching old chunks) and only then remove IDs that no longer exist.  If the
    upsert fails, the previous version of the document is still present (apart
    from any trailing chunks removed in an earlier failed attempt, which is a
    documented limitation).
    """

    if not chunks:
        raise ValueError("No document chunks provided!")

    doc_id = chunks[0].metadata.get("doc_id")

    if not doc_id:
        raise ValueError("Every chunk must include a doc_id.")

    if any(chunk.metadata.get("doc_id") != doc_id for chunk in chunks):
        raise ValueError("All chunks must belong to the same document!")

    vector_store = get_vector_store()

    # Deterministic IDs make replacement idempotent.
    new_ids = [f"{doc_id}_{chunk.metadata['chunk_index']}" for chunk in chunks]
    new_id_set = set(new_ids)

    existing = vector_store.get(where={"doc_id": doc_id}, include=[])
    stale_ids = [chunk_id for chunk_id in existing["ids"] if chunk_id not in new_id_set]

    logger.info(
        "Storing document chunks: doc_id=%s chunks=%d stale_chunks=%d",
        doc_id[:12],
        len(chunks),
        len(stale_ids),
    )

    # LangChain Chroma uses ``collection.upsert`` internally, so this is safe
    # to call when the document already exists.
    vector_store.add_documents(documents=chunks, ids=new_ids)

    if stale_ids:
        try:
            vector_store.delete(ids=stale_ids)
        except Exception:
            # The new chunks are already stored.  Log loudly; the caller will
            # report the failure and the stale chunks can be cleaned by
            # re-uploading the document.
            logger.exception(
                "Failed to delete stale chunks: doc_id=%s stale_chunks=%d",
                doc_id[:12],
                len(stale_ids),
            )
            raise

    return new_ids


def get_all_documents() -> list[dict]:
    """Return one summary row per indexed document."""

    vector_store = get_vector_store()
    result = vector_store.get(include=["metadatas"])

    documents: dict[str, dict] = {}

    for metadata in result["metadatas"]:
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


def document_exists(doc_id: str) -> bool:
    """Return True when at least one chunk is stored for ``doc_id``."""

    vector_store = get_vector_store()
    result = vector_store.get(where={"doc_id": doc_id}, limit=1, include=[])
    return bool(result["ids"])


def count_document_chunks(doc_id: str) -> int:
    """Return the number of stored chunks for ``doc_id``."""

    vector_store = get_vector_store()
    result = vector_store.get(where={"doc_id": doc_id}, include=[])
    return len(result["ids"])


def delete_documents(doc_id: str) -> int:
    """Delete every vector belonging to ``doc_id`` and return the count."""

    vector_store = get_vector_store()
    deleted_count = count_document_chunks(doc_id)

    vector_store.delete(where={"doc_id": doc_id})

    logger.info(
        "Deleted document vectors: doc_id=%s chunks=%d",
        doc_id[:12],
        deleted_count,
    )

    return deleted_count


def get_document_count() -> int:
    """Cheap document count for health checks.

    Uses a plain Chroma client so the embedding model is not loaded just to
    answer a health request.
    """

    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    try:
        collection = client.get_collection(COLLECTION_NAME)
        result = collection.get(include=["metadatas"])
    except Exception:
        return 0

    doc_ids = {
        metadata.get("doc_id")
        for metadata in result.get("metadatas", [])
        if metadata.get("doc_id")
    }

    return len(doc_ids)
