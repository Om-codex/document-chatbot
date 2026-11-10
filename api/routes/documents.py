import logging

from fastapi import APIRouter, File, Path, UploadFile

from api.errors import api_error
from api.schemas.documents import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentUploadResponse,
)
from services.document_service import (
    delete_document,
    list_documents,
    upload_document,
)
from services.exceptions import (
    DocumentDeletionError,
    DocumentNotFoundError,
    DocumentServiceError,
    DocumentStorageError,
    DocumentTooLargeError,
    EmptyDocumentError,
    InvalidDocumentIdError,
    MalformedDocumentError,
    UnsupportedDocumentError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)


# -----------------------------------------
# Upload Document
# -----------------------------------------

@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document_route(file: UploadFile = File(...)):
    try:
        return upload_document(
            filename=file.filename,
            file_stream=file.file,
        )

    except UnsupportedDocumentError as exc:
        raise api_error(415, "INVALID_FILE_TYPE", str(exc))

    except DocumentTooLargeError as exc:
        raise api_error(413, "FILE_TOO_LARGE", str(exc))

    except EmptyDocumentError as exc:
        raise api_error(422, "EMPTY_DOCUMENT", str(exc))

    except MalformedDocumentError as exc:
        raise api_error(422, "MALFORMED_DOCUMENT", str(exc))

    except DocumentStorageError as exc:
        logger.exception("Document storage failed.")
        raise api_error(503, "STORAGE_ERROR", str(exc))

    except ValueError as exc:
        raise api_error(400, "INVALID_REQUEST", str(exc))

    except Exception:
        logger.exception("Document upload failed.")
        raise api_error(500, "INTERNAL_ERROR", "Document upload failed.")

    finally:
        file.file.close()


# -----------------------------------------
# List Documents
# -----------------------------------------

@router.get("/", response_model=DocumentListResponse)
def list_documents_route():
    try:
        return list_documents()

    except DocumentStorageError as exc:
        logger.exception("Document listing failed.")
        raise api_error(503, "STORAGE_ERROR", str(exc))

    except Exception:
        logger.exception("Document listing failed.")
        raise api_error(500, "INTERNAL_ERROR", "Failed to retrieve documents.")


# -----------------------------------------
# Delete Document
# -----------------------------------------

@router.delete("/{doc_id}", response_model=DocumentDeleteResponse)
def delete_document_route(
    doc_id: str = Path(
        ...,
        pattern=r"^[a-f0-9]{64}$",
        description="64-character lowercase SHA-256 document ID.",
    ),
):
    try:
        return delete_document(doc_id)

    except DocumentNotFoundError as exc:
        raise api_error(404, "DOCUMENT_NOT_FOUND", str(exc))

    except InvalidDocumentIdError as exc:
        raise api_error(400, "INVALID_DOCUMENT_ID", str(exc))

    except DocumentDeletionError as exc:
        logger.exception("Document deletion failed.")
        raise api_error(500, "DELETION_ERROR", str(exc))

    except DocumentServiceError as exc:
        logger.exception("Document deletion failed.")
        raise api_error(500, "DELETION_ERROR", str(exc))

    except Exception:
        logger.exception("Document deletion failed.")
        raise api_error(500, "INTERNAL_ERROR", "Document deletion failed.")
