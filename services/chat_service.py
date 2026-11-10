import logging

from chains.qa_chain import get_qa_chain
from config.settings import settings
from generation.exceptions import (
    LLMError,
    LLMProviderError,
    is_llm_exception,
    translate_llm_error,
)
from services.exceptions import (
    ChatValidationError,
    InvalidDocumentSelectionError,
    NoDocumentsError,
    RetrievalError,
)
from utils.validation import is_valid_doc_id
from vectorstore.chroma_store import get_all_documents

logger = logging.getLogger(__name__)


def _normalize_doc_ids(doc_ids: list[str] | None) -> list[str] | None:
    """Validate and normalize the optional document selection.

    ``None`` and ``[]`` both mean "search all documents" to preserve the
    existing API behaviour.  Individual IDs must be well-formed SHA-256 hashes.
    """

    if not doc_ids:
        return None

    cleaned: list[str] = []

    for doc_id in doc_ids:
        if not isinstance(doc_id, str):
            raise ChatValidationError("Document IDs must be strings.")

        doc_id = doc_id.strip()

        if not doc_id:
            raise ChatValidationError("Document IDs cannot contain empty values.")

        if not is_valid_doc_id(doc_id):
            raise ChatValidationError(
                "Document IDs must be 64-character lowercase SHA-256 hex strings."
            )

        cleaned.append(doc_id)

    if len(cleaned) != len(set(cleaned)):
        raise ChatValidationError("Duplicate document IDs are not allowed.")

    if len(cleaned) > settings.max_selected_documents:
        raise ChatValidationError(
            f"At most {settings.max_selected_documents} document IDs can be selected."
        )

    return cleaned


def _ensure_documents_available(doc_ids: list[str] | None) -> None:
    """Fail early with a clear error instead of asking the LLM about nothing."""

    try:
        documents = get_all_documents()
    except Exception as exc:
        raise RetrievalError("The document index could not be read.") from exc

    if not documents:
        raise NoDocumentsError("No documents are indexed yet. Upload a document first.")

    if doc_ids is None:
        return

    indexed_ids = {document["doc_id"] for document in documents}
    missing = [doc_id for doc_id in doc_ids if doc_id not in indexed_ids]

    if missing:
        raise InvalidDocumentSelectionError(
            "One or more selected documents no longer exist. Refresh the library."
        )


def chat_with_documents(
    question: str,
    doc_ids: list[str] | None,
    k: int,
) -> dict:
    """Run retrieval + generation and return the answer with source chunks."""

    question = question.strip()

    if not question:
        raise ChatValidationError("Question cannot be empty.")

    if len(question) > settings.max_question_length:
        raise ChatValidationError(
            f"Question must be at most {settings.max_question_length} characters."
        )

    if k < 1 or k > settings.max_top_k:
        raise ChatValidationError(f"k must be between 1 and {settings.max_top_k}.")

    normalized_doc_ids = _normalize_doc_ids(doc_ids)

    logger.info(
        "Chat request started: question_length=%d k=%d selected_documents=%s",
        len(question),
        k,
        len(normalized_doc_ids) if normalized_doc_ids else "all",
    )

    _ensure_documents_available(normalized_doc_ids)

    try:
        qa_chain = get_qa_chain(doc_ids=normalized_doc_ids, k=k)
    except LLMError:
        raise
    except Exception as exc:
        logger.exception("Failed to build the QA chain.")
        raise RetrievalError("The retrieval pipeline could not be initialized.") from exc

    try:
        result = qa_chain.invoke(question)
    except LLMError:
        raise
    except Exception as exc:
        if is_llm_exception(exc):
            raise translate_llm_error(exc) from exc

        logger.exception("Retrieval or generation failed.")
        raise RetrievalError("The documents could not be searched.") from exc

    answer = result.get("answer")

    if not isinstance(answer, str) or not answer.strip():
        raise LLMProviderError("The language model returned an empty answer.")

    retrieved_chunks: list[dict] = []

    for document in result.get("sources", []):
        metadata = document.metadata or {}
        doc_id = metadata.get("doc_id")
        chunk_index = metadata.get("chunk_index")

        # Metadata is written by the ingestion pipeline; skip anything that
        # cannot satisfy the response schema instead of failing the whole chat.
        if not doc_id or chunk_index is None:
            logger.warning("Skipping retrieved chunk with incomplete metadata.")
            continue

        page = metadata.get("page")

        retrieved_chunks.append(
            {
                "chunk_id": f"{doc_id}_{chunk_index}",
                "content": document.page_content,
                "metadata": {
                    "doc_id": doc_id,
                    "filename": metadata.get("filename") or "Unknown",
                    "chunk_index": int(chunk_index),
                    "page": page,
                    "page_number": page + 1 if isinstance(page, int) else None,
                    "page_label": metadata.get("page_label"),
                    "total_pages": metadata.get("total_pages"),
                },
            }
        )

    logger.info(
        "Chat request completed: retrieved_chunks=%d answer_length=%d",
        len(retrieved_chunks),
        len(answer),
    )

    return {
        "question": question,
        "answer": answer,
        "total_chunks_retrieved": len(retrieved_chunks),
        "retrieved_chunks": retrieved_chunks,
    }
