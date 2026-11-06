import shutil
from pathlib import Path 
from uuid import uuid4
from typing import BinaryIO

from ingestion.pipeline import (ingest_document, generate_document_id)
from vectorstore.chroma_store import (add_documents, get_all_documents, delete_documents)

# configuration

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_FILE = BASE_DIR / "data" / "uploads"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

MAX_FILE_SIZE = 10 * 1024 * 1024 # 10 MB

# Application-level exceptions

class UnsupportedDocumentError(Exception):
  pass

class DocumentTooLargeError(Exception):
  pass

class DocumentNotFoundError(Exception):
  pass

# -----------------------------------------
# Upload Document
# -----------------------------------------

def upload_document(
    filename: str,
    file_stream: BinaryIO
) -> dict:

    if not filename:
        raise ValueError("Filename is required.")

    # Sanitize filename
    original_filename = filename.replace("\\", "/").split("/")[-1]

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedDocumentError(
            "Unsupported file format. Upload PDF, DOCX, or TXT."
        )

    # Create a unique upload directory
    upload_id = str(uuid4())

    document_dir = UPLOAD_DIR / upload_id
    document_dir.mkdir(parents=True, exist_ok=True)

    file_path = document_dir / original_filename

    try:
        # Save uploaded file in chunks
        total_size = 0

        with open(file_path, "wb") as destination:

            while True:
                chunk = file_stream.read(1024 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise DocumentTooLargeError(
                        "File exceeds the 10 MB upload limit."
                    )

                destination.write(chunk)

        if total_size == 0:
            raise ValueError("Uploaded file is empty.")

        # Run the existing RAG ingestion pipeline
        chunks = ingest_document(str(file_path))

        if not chunks:
            raise ValueError(
                "No text could be extracted from the document."
            )

        # Store document chunks in ChromaDB
        add_documents(chunks)

        doc_id = chunks[0].metadata["doc_id"]

        return {
            "message": "Document uploaded and indexed successfully.",
            "filename": original_filename,
            "doc_id": doc_id,
            "total_chunks": len(chunks),
            "file_size_bytes": total_size
        }

    except Exception:
        # Clean up uploaded files if ingestion or storage fails
        if document_dir.exists():
            shutil.rmtree(document_dir)

        raise


# -----------------------------------------
# List Documents
# -----------------------------------------

def list_documents() -> dict:

    documents = get_all_documents()

    return {
        "total_documents": len(documents),
        "documents": documents
    }


# -----------------------------------------
# Delete Document
# -----------------------------------------

def delete_document(doc_id: str) -> dict:

    # Check whether document exists
    documents = get_all_documents()

    document = next(
        (
            doc for doc in documents
            if doc["doc_id"] == doc_id
        ),
        None
    )

    if document is None:
        raise DocumentNotFoundError(
            "Document not found."
        )

    # Find original files using their content hash
    matching_files = []

    if UPLOAD_DIR.exists():

        for file_path in UPLOAD_DIR.rglob("*"):

            if not file_path.is_file():
                continue

            try:
                file_hash = generate_document_id(str(file_path))

                if file_hash == doc_id:
                    matching_files.append(file_path)

            except OSError:
                continue

    # Delete vectors from ChromaDB
    delete_documents(doc_id)

    # Delete corresponding physical files
    deleted_files = 0

    for file_path in matching_files:

        file_path.unlink()
        deleted_files += 1

        # Remove empty upload directory
        try:
            file_path.parent.rmdir()
        except OSError:
            pass

    return {
        "message": "Document deleted successfully.",
        "doc_id": doc_id,
        "filename": document["filename"],
        "deleted_files": deleted_files,
        "vectors_deleted": True
    }
