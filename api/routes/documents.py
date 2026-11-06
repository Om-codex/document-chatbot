
from fastapi import APIRouter, File, HTTPException, UploadFile

from api.schemas.documents import (
    DocumentListResponse,
    DocumentUploadResponse,
    DocumentDeleteResponse
)

from services.document_service import (
    upload_document,
    list_documents,
    delete_document,
    UnsupportedDocumentError,
    DocumentTooLargeError,
    DocumentNotFoundError
)


router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"]
)


# -----------------------------------------
# Upload Document
# -----------------------------------------

@router.post("/upload",response_model=DocumentUploadResponse)
def upload_document_route(file: UploadFile = File(...)):

    try:
        result = upload_document(
            filename=file.filename,
            file_stream=file.file
        )

        return result

    except UnsupportedDocumentError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except DocumentTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc)
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Document upload failed. Check backend logs."
        )

    finally:
        file.file.close()


# -----------------------------------------
# List Documents
# -----------------------------------------

@router.get("/",response_model=DocumentListResponse)
def list_documents_route():

    try:
        return list_documents()

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve documents."
        )


# -----------------------------------------
# Delete Document
# -----------------------------------------

@router.delete("/{doc_id}",response_model=DocumentDeleteResponse)
def delete_document_route(doc_id: str):

    try:
        return delete_document(doc_id)

    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Document deletion failed. Check backend logs."
        )
