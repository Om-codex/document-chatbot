import hashlib
import logging
from pathlib import Path

from ingestion.exceptions import EmptyDocumentError
from ingestion.loaders import load_document
from ingestion.text_splitter import split_documents

logger = logging.getLogger(__name__)


def generate_document_id(file_path: str) -> str:
    """Return the SHA-256 hex digest of the file contents."""

    file_hash = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            file_hash.update(chunk)

    return file_hash.hexdigest()


def ingest_document(
    file_path: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
):
    """Load, split and annotate a document for vector storage."""

    path = Path(file_path)

    if not path.is_file():

        raise FileNotFoundError(f"File not found: {file_path}")

    doc_id = generate_document_id(str(path))

    documents = load_document(str(path))
    chunks = split_documents(documents, chunk_size, chunk_overlap)

    if not chunks:
        raise EmptyDocumentError("No text could be extracted from the document.")

    for index, chunk in enumerate(chunks):
        chunk.metadata.update(
            {
                "doc_id": doc_id,
                "filename": path.name,
                "chunk_index": index,
            }
        )

    logger.info(
        "Ingestion completed: filename=%s doc_id=%s chunks=%d",
        path.name,
        doc_id[:12],
        len(chunks),
    )

    return chunks
