from pathlib import Path 
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from ingestion.pipeline import ingest_document, generate_document_id
from vectorstore.chroma_store import add_documents, get_all_documents, delete_documents

router = APIRouter(
  prefix = "/api/documents",
  tags = ["Documents"]
)

# project root directory
BASE_DIR = Path(__file__).resolve().parents[2]

# upload directory
UPLOAD_DIR = BASE_DIR/"data"/"uploads"

# Supported file formats
ALLOWED_EXTENSIONS = {".pdf",".docx",".txt"}

# Maximum upload size : 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024


# document upload endpoint
@router.post("/upload")
def upload_document(file: UploadFile = File(...)):

  if not file.filename:
    raise HTTPException(
      status_code = 400,
      detail = "Filename is required."
    )

  # sanitize filename
  original_filename = file.filename.replace("\\","/").split("/")[-1]

  extension = Path(original_filename).suffix.lower()

  if extension not in ALLOWED_EXTENSIONS:
    raise HTTPException(
      status = 400,
      detail = "Unsupported file format. Upload PDF, DOCX, or TXT."
    )
  
  # creat a unique directory for this upload
  upload_id = str(uuid4())

  document_dir = UPLOAD_DIR / upload_id
  document_dir.mkdir(parents = True, exist_ok = True)

  file_path = document_dir / original_filename

  try:
    # save the file with upload size validation
    total_size = 0

    with open(file_path, "wb") as destination:
      while True:
        chunk = file.file.read(1024 * 1024)

        if not chunk:
          break
        
        total_size += len(chunk)

        if total_size > MAX_FILE_SIZE:
          raise HTTPException(
            status_code = 413,
            detatil = "File exceeds the 10 MB upload limit."
          )
        
        destination.write(chunk)
    
    # run existing ingestion pipeline
    chunks = ingest_document(str(file_path))

    if not chunks:
      raise ValueError("No text could be extracted from the document.")

    # store chunks in ChromaDB
    add_documents(chunks)

    doc_id = chunks[0].metadata["doc_id"]

    return {
      "message" : "Document uploaded and indexed successfully.",
      "filename" : original_filename,
      "doc_id" : doc_id,
      "total_chunks" : len(chunks),
      "file_size_bytes" : total_size
    }
  
  except HTTPException:
    # remove uploaded file if the request fails
    if document_dir.exists():
      import shutil
      shutil.rmtree(document_dir)

    raise
  
  except Exception as exc:
    # clean up the failed uploads
    if document_dir.exists():
      import shutil
      shutil.rmtree(document_dir)

    raise HTTPException(
      status_code = 500,
      detail = f"Document ingestion failed: {str(exc)}"
    )

# document listing endpoint
@router.get("/")
def list_documents():
  try:
    documents = get_all_documents()

    return {
      "total_documents" : len(documents),
      "documents" : documents
    }

  except Exception as exc:
    raise HTTPException(
      status_code = 500,
      detail = f"Failed to retrieve documents: {str(exc)}"
    )

# document deletion endpoint
@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    try:
        # 1. Check whether the document exists in ChromaDB
        documents = get_all_documents()

        document = next(
            (
                doc for doc in documents
                if doc["doc_id"] == doc_id
            ),
            None
        )

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found."
            )

        # 2. Find original uploaded files using their content hash
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

        # 3. Delete document chunks from ChromaDB
        delete_documents(doc_id)

        # 4. Delete corresponding physical files
        deleted_files = 0

        for file_path in matching_files:
            file_path.unlink()
            deleted_files += 1

            # Remove empty UUID upload directory
            try:
                file_path.parent.rmdir()
            except OSError:
                pass

        return {
            "message": "Document deleted successfully.",
            "doc_id": doc_id,
            "filename": document.get("filename"),
            "deleted_files": deleted_files,
            "vectors_deleted": True
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document deletion failed: {str(exc)}"
        )
