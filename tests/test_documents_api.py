"""Document upload, listing and deletion API tests."""

from pathlib import Path

from services import document_service
from vectorstore.chroma_store import get_all_documents


def test_list_documents_empty(client):
    response = client.get("/api/documents/")

    assert response.status_code == 200
    assert response.json() == {"total_documents": 0, "documents": []}


def test_upload_txt_document(client, upload_document):
    response = upload_document(
        "notes.txt",
        b"Caching stores frequently used data. A cache reduces latency.",
        "text/plain",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "notes.txt"
    assert len(payload["doc_id"]) == 64
    assert int(payload["doc_id"], 16) >= 0
    assert payload["total_chunks"] >= 1
    assert payload["file_size_bytes"] > 0

    listing = client.get("/api/documents/").json()
    assert listing["total_documents"] == 1
    assert listing["documents"][0]["doc_id"] == payload["doc_id"]
    assert listing["documents"][0]["filename"] == "notes.txt"
    assert listing["documents"][0]["total_chunks"] == payload["total_chunks"]


def test_upload_pdf_document(client, upload_document):
    from tests.conftest import make_pdf_bytes

    response = upload_document("paper.pdf", make_pdf_bytes(), "application/pdf")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"] == "paper.pdf"
    assert payload["total_chunks"] >= 1

    documents = get_all_documents()
    assert documents[0]["total_pages"] == 1


def test_upload_docx_document(client, upload_document):
    from tests.conftest import make_docx_bytes

    response = upload_document(
        "memo.docx",
        make_docx_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert response.status_code == 200, response.text
    assert response.json()["total_chunks"] >= 1


def test_upload_unsupported_extension(client, upload_document):
    response = upload_document("script.exe", b"MZ", "application/octet-stream")

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "INVALID_FILE_TYPE"


def test_upload_empty_file(client, upload_document):
    response = upload_document("empty.txt", b"", "text/plain")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "EMPTY_DOCUMENT"


def test_upload_too_large(client, upload_document, monkeypatch):
    monkeypatch.setattr(document_service, "MAX_FILE_SIZE", 16)

    response = upload_document("big.txt", b"x" * 32, "text/plain")

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "FILE_TOO_LARGE"


def test_upload_malformed_pdf(client, upload_document):
    response = upload_document("broken.pdf", b"not really a pdf", "application/pdf")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "MALFORMED_DOCUMENT"


def test_upload_missing_filename(client):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("", b"some text", "text/plain")},
    )

    # Starlette rejects an empty multipart filename before the service runs.
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_upload_path_traversal_is_sanitized(client, upload_document, isolated_storage):
    response = upload_document("../../evil.txt", b"safe text content", "text/plain")

    assert response.status_code == 200, response.text
    assert response.json()["filename"] == "evil.txt"

    uploads_dir = isolated_storage / "uploads"
    assert (uploads_dir / "evil.txt").exists() is False  # file lives in a UUID subdirectory
    assert list(uploads_dir.rglob("evil.txt"))
    assert not (isolated_storage / "evil.txt").exists()


def test_loader_failure_cleans_up(client, upload_document, isolated_storage, monkeypatch):
    def broken_ingest(_):
        raise RuntimeError("loader exploded")

    monkeypatch.setattr(document_service, "ingest_document", broken_ingest)

    response = upload_document("notes.txt", b"valid text", "text/plain")

    assert response.status_code == 500
    assert list((isolated_storage / "uploads").glob("*")) == []
    assert get_all_documents() == []


def test_vector_insert_failure_cleans_up(client, upload_document, isolated_storage, monkeypatch):
    def broken_add(_):
        raise RuntimeError("vector store unavailable")

    monkeypatch.setattr(document_service, "add_documents", broken_add)

    response = upload_document("notes.txt", b"valid text", "text/plain")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "STORAGE_ERROR"
    assert list((isolated_storage / "uploads").glob("*")) == []


def test_partial_vector_insert_failure_is_rolled_back(
    client, upload_document, isolated_storage, monkeypatch
):
    original_add = document_service.add_documents

    def add_then_fail(chunks):
        original_add(chunks)
        raise RuntimeError("failed after partial insert")

    monkeypatch.setattr(document_service, "add_documents", add_then_fail)

    response = upload_document("notes.txt", b"valid text", "text/plain")

    assert response.status_code == 503
    assert get_all_documents() == []
    assert list((isolated_storage / "uploads").glob("*")) == []


def test_delete_document(client, indexed_txt, isolated_storage):
    doc_id = indexed_txt["doc_id"]

    response = client.delete(f"/api/documents/{doc_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["doc_id"] == doc_id
    assert payload["vectors_deleted"] is True
    assert payload["deleted_files"] == 1
    assert payload["warnings"] == []

    assert client.get("/api/documents/").json()["total_documents"] == 0
    assert list((isolated_storage / "uploads").rglob("notes.txt")) == []


def test_delete_nonexistent_document(client):
    response = client.delete(f"/api/documents/{'a' * 64}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "DOCUMENT_NOT_FOUND"


def test_delete_malformed_document_id(client):
    response = client.delete("/api/documents/not-a-sha256")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_delete_vector_failure_keeps_document(
    client, indexed_txt, isolated_storage, monkeypatch
):
    def broken_delete(_):
        raise RuntimeError("chroma delete failed")

    monkeypatch.setattr(document_service, "delete_documents", broken_delete)

    response = client.delete(f"/api/documents/{indexed_txt['doc_id']}")

    assert response.status_code == 500
    assert client.get("/api/documents/").json()["total_documents"] == 1
    assert list((isolated_storage / "uploads").rglob("notes.txt"))


def test_delete_filesystem_failure_returns_warning(
    client, indexed_txt, isolated_storage, monkeypatch
):
    original_unlink = Path.unlink

    def failing_unlink(self, *args, **kwargs):
        if self.name == "notes.txt":
            raise OSError("file is locked")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", failing_unlink)

    response = client.delete(f"/api/documents/{indexed_txt['doc_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["vectors_deleted"] is True
    assert payload["deleted_files"] == 0
    assert payload["warnings"]
    assert client.get("/api/documents/").json()["total_documents"] == 0
    assert list((isolated_storage / "uploads").rglob("notes.txt"))


def test_delete_only_removes_the_selected_document(client, upload_document):
    first = upload_document("first.txt", b"first document content", "text/plain").json()
    second = upload_document("second.txt", b"second document content", "text/plain").json()

    response = client.delete(f"/api/documents/{first['doc_id']}")

    assert response.status_code == 200
    listing = client.get("/api/documents/").json()
    assert listing["total_documents"] == 1
    assert listing["documents"][0]["doc_id"] == second["doc_id"]
