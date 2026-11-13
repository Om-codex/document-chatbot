import logging
import shutil
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from config.settings import settings
from ingestion.exceptions import (
    DocumentLoadingError,
    EmptyDocumentError as IngestionEmptyDocumentError,
    UnsupportedDocumentFormatError,
)
from ingestion.pipeline import generate_document_id, ingest_document
from services.exceptions import (
    DocumentDeletionError,
    DocumentNotFoundError,
    DocumentStorageError,
    DocumentTooLargeError,
    EmptyDocumentError,
    InvalidDocumentIdError,
    MalformedDocumentError,
    UnsupportedDocumentError,
)
from utils.file_validation import FileSignatureError, validate_file_signature
from utils.helpers import extension_of, sanitize_filename
from utils.validation import InvalidDocumentIdError as InvalidDocumentIdFormatError
from utils.validation import validate_doc_id
from vectorstore.qdrant_store import (
    add_documents,
    delete_documents,
    document_exists,
    get_all_documents,
)

logger = logging.getLogger(__name__)


# Configuration is read once at import time.  Tests override these module-level
# values with temporary paths and small limits.
UPLOAD_DIR = settings.upload_directory
ALLOWED_EXTENSIONS = settings.allowed_extensions
MAX_FILE_SIZE = settings.max_file_size_bytes
READ_CHUNK_SIZE = settings.upload_read_chunk_size


def _cleanup_upload(document_dir: Path, doc_id: str | None, existed_before: bool) -> None:
    """Best-effort cleanup after a failed upload.

    Vector cleanup is only attempted for a brand-new document.  When replacing
    an existing document, deleting all vectors here would destroy the previous
    working version.
    """

    if doc_id and not existed_before:
        try:
            delete_documents(doc_id)
            logger.info("Cleaned up partial vectors: doc_id=%s", doc_id[:12])
        except Exception:
            logger.exception("Failed to clean up partial vectors: doc_id=%s", doc_id[:12])

    if document_dir.exists():
        try:
            shutil.rmtree(document_dir)
            logger.info("Removed failed upload directory: %s", document_dir.name)
        except OSError:
            logger.exception("Failed to remove upload directory: %s", document_dir.name)


# -----------------------------------------
# Upload Document
# -----------------------------------------

def upload_document(filename: str, file_stream: BinaryIO) -> dict:
    """Stream, validate, ingest and index a single uploaded document."""

    try:
        original_filename = sanitize_filename(filename)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    extension = extension_of(original_filename)

    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedDocumentError(
            "Unsupported file format. Upload PDF, DOCX, or TXT."
        )

    upload_id = str(uuid4())
    document_dir = UPLOAD_DIR / upload_id
    document_dir.mkdir(parents=True, exist_ok=True)
    file_path = document_dir / original_filename

    logger.info(
        "Upload started: filename=%s extension=%s upload_id=%s",
        original_filename,
        extension,
        upload_id,
    )

    doc_id: str | None = None
    existed_before = False

    try:
        total_size = 0

        with open(file_path, "wb") as destination:
            while True:
                chunk = file_stream.read(READ_CHUNK_SIZE)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise DocumentTooLargeError(
                        f"File exceeds the {MAX_FILE_SIZE // (1024 * 1024)} MB upload limit."
                    )

                destination.write(chunk)

        if total_size == 0:
            raise EmptyDocumentError("Uploaded file is empty.")

        logger.info(
            "Upload received: filename=%s bytes=%d",
            original_filename,
            total_size,
        )

        try:
            validate_file_signature(file_path, extension)
        except FileSignatureError as exc:
            raise MalformedDocumentError(str(exc)) from exc

        logger.info(
            "File validation completed: filename=%s extension=%s",
            original_filename,
            extension,
        )

        try:
            chunks = ingest_document(str(file_path))
        except UnsupportedDocumentFormatError as exc:
            raise UnsupportedDocumentError(str(exc)) from exc
        except IngestionEmptyDocumentError as exc:
            raise EmptyDocumentError(str(exc)) from exc
        except DocumentLoadingError as exc:
            raise MalformedDocumentError(str(exc)) from exc

        if not chunks:
            raise EmptyDocumentError("No text could be extracted from the document.")

        doc_id = chunks[0].metadata["doc_id"]
        existed_before = document_exists(doc_id)

        logger.info(
            "Document loaded: filename=%s doc_id=%s chunks=%d replacement=%s",
            original_filename,
            doc_id[:12],
            len(chunks),
            existed_before,
        )

        try:
            add_documents(chunks)
        except Exception as exc:
            raise DocumentStorageError(
                "The document could not be stored in the vector database."
            ) from exc

        logger.info(
            "Vector insertion completed: filename=%s doc_id=%s chunks=%d",
            original_filename,
            doc_id[:12],
            len(chunks),
        )

        return {
            "message": "Document uploaded and indexed successfully.",
            "filename": original_filename,
            "doc_id": doc_id,
            "total_chunks": len(chunks),
            "file_size_bytes": total_size,
        }

    except Exception:
        logger.exception(
            "Upload failed: filename=%s doc_id=%s",
            original_filename,
            doc_id[:12] if doc_id else "n/a",
        )
        _cleanup_upload(document_dir, doc_id, existed_before)
        raise


# -----------------------------------------
# List Documents
# -----------------------------------------

def list_documents() -> dict:
    """Return summaries for every indexed document."""

    documents = get_all_documents()

    logger.debug("Document listing requested: count=%d", len(documents))

    return {
        "total_documents": len(documents),
        "documents": documents,
    }


# -----------------------------------------
# Delete Document
# -----------------------------------------

def _find_uploaded_files(doc_id: str) -> list[Path]:
    """Find original files whose content hash matches ``doc_id``.

    Only paths under ``UPLOAD_DIR`` are considered.  The scan is intentionally
    content-based so it works regardless of which UUID directory was used.
    """

    matching_files: list[Path] = []

    if not UPLOAD_DIR.exists():
        return matching_files

    for file_path in UPLOAD_DIR.rglob("*"):
        if not file_path.is_file():
            continue

        try:
            if generate_document_id(str(file_path)) == doc_id:
                matching_files.append(file_path)
        except OSError:
            logger.warning("Could not hash uploaded file during deletion: %s", file_path.name)

    return matching_files


def delete_document(doc_id: str) -> dict:
    """Delete vectors first, then the original upload files.

    Vectors are deleted first so a failure leaves the document fully intact.
    If a file cannot be removed after vectors are gone, the document is already
    logically deleted; the response includes a warning and the orphaned file is
    left for manual cleanup.
    """

    try:
        validate_doc_id(doc_id)
    except InvalidDocumentIdFormatError as exc:
        raise InvalidDocumentIdError(str(exc)) from exc

    documents = get_all_documents()
    document = next((item for item in documents if item["doc_id"] == doc_id), None)

    if document is None:
        raise DocumentNotFoundError("Document not found.")

    matching_files = _find_uploaded_files(doc_id)

    logger.info(
        "Document deletion started: doc_id=%s filename=%s files=%d",
        doc_id[:12],
        document.get("filename"),
        len(matching_files),
    )

    try:
        delete_documents(doc_id)
    except Exception as exc:
        logger.exception("Vector deletion failed: doc_id=%s", doc_id[:12])
        raise DocumentDeletionError("Failed to delete the document vectors.") from exc

    logger.info("Vector deletion completed: doc_id=%s", doc_id[:12])

    deleted_files = 0
    warnings: list[str] = []

    for file_path in matching_files:
        try:
            file_path.unlink()
            deleted_files += 1

            try:
                file_path.parent.rmdir()
            except OSError:
                # Directory is not empty (or already gone); nothing to do.
                pass

        except OSError:
            logger.exception("File deletion failed: %s", file_path.name)
            warnings.append(f"Could not delete the stored file: {file_path.name}")

    logger.info(
        "File deletion completed: doc_id=%s deleted_files=%d warnings=%d",
        doc_id[:12],
        deleted_files,
        len(warnings),
    )

    return {
        "message": "Document deleted successfully.",
        "doc_id": doc_id,
        "filename": document["filename"],
        "deleted_files": deleted_files,
        "vectors_deleted": True,
        "warnings": warnings,
    }
