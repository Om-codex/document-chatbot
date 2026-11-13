"""Shared pytest fixtures.

Every test runs against a temporary Chroma directory and a temporary upload
directory.  The real Hugging Face embedding model and the real Groq API are
never used by the normal suite.
"""

import hashlib
import os
import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import FakeListChatModel

# Keep the normal suite away from real credentials even if .env exists.  The
# opt-in real-provider test must be able to use the developer's real key.
if os.getenv("RUN_REAL_LLM_TESTS") != "1":
    os.environ["GROQ_API_KEY"] = "test-key"
os.environ.setdefault("LOG_LEVEL", "WARNING")

from embeddings.embedding_model import get_embedding_model  # noqa: E402
from generation.llm import get_llm  # noqa: E402
from services import document_service  # noqa: E402
from vectorstore import chroma_store  # noqa: E402
from vectorstore import qdrant_store  # noqa: E402


class DeterministicFakeEmbeddings(Embeddings):
    """Small, stable embeddings for retrieval tests (no model download)."""

    def __init__(self, size: int = 64) -> None:
        self.size = size

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.size

        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "big") % self.size] += 1.0

        norm = sum(value * value for value in vector) ** 0.5
        if norm:
            vector = [value / norm for value in vector]

        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def make_pdf_bytes(text: str = "Hello PDF document about caching.") -> bytes:
    """Create a valid one-page PDF with extractable text (no extra dependency)."""

    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )

    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_docx_bytes(text: str = "Hello DOCX document about caching.") -> bytes:
    """Create a minimal valid DOCX archive."""

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>"
        f"{text}"
        "</w:t></w:r></w:p></w:body></w:document>"
    )

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>',
        )
        archive.writestr("word/document.xml", document_xml)

    return buffer.getvalue()


@pytest.fixture(autouse=True)
def reset_process_caches():
    """Caches are process-local; clear them so tests cannot leak state."""

    get_embedding_model.cache_clear()
    get_llm.cache_clear()
    chroma_store.get_vector_store.cache_clear()
    qdrant_store.get_vector_store.cache_clear()

    yield

    get_embedding_model.cache_clear()
    get_llm.cache_clear()
    chroma_store.get_vector_store.cache_clear()
    qdrant_store.get_vector_store.cache_clear()


@pytest.fixture
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the vector store and upload directory at temporary paths."""

    fake_embeddings = DeterministicFakeEmbeddings()
    collection_name = f"test_collection_{uuid4().hex}"

    monkeypatch.setattr(chroma_store, "get_embedding_model", lambda: fake_embeddings)
    monkeypatch.setattr(chroma_store, "CHROMA_PATH", tmp_path / "chroma")
    monkeypatch.setattr(chroma_store, "COLLECTION_NAME", collection_name)

    monkeypatch.setattr(qdrant_store, "get_embedding_model", lambda: fake_embeddings)
    monkeypatch.setattr(qdrant_store, "COLLECTION_NAME", collection_name)
    monkeypatch.setattr(qdrant_store, "VECTOR_SIZE", fake_embeddings.size)

    monkeypatch.setattr(document_service, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(document_service, "ALLOWED_EXTENSIONS", {".pdf", ".docx", ".txt"})
    monkeypatch.setattr(document_service, "MAX_FILE_SIZE", 10 * 1024 * 1024)
    monkeypatch.setattr(document_service, "READ_CHUNK_SIZE", 1024 * 1024)

    chroma_store.get_vector_store.cache_clear()
    qdrant_store.get_vector_store.cache_clear()

    yield tmp_path

    chroma_store.get_vector_store.cache_clear()
    qdrant_store.get_vector_store.cache_clear()


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch):
    """Patch the QA chain's LLM with a deterministic fake chat model."""

    model = FakeListChatModel(responses=["Test answer grounded in the context."])
    monkeypatch.setattr("chains.qa_chain.get_llm", lambda: model)
    return model


@pytest.fixture
def client(isolated_storage, fake_llm):
    """FastAPI TestClient wired to the isolated storage and fake LLM."""

    from app import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def upload_document(client):
    """Helper that uploads bytes through the real API route."""

    def _upload(filename: str, content: bytes, content_type: str = "application/octet-stream"):
        return client.post(
            "/api/documents/upload",
            files={"file": (filename, content, content_type)},
        )

    return _upload


@pytest.fixture
def indexed_txt(client, upload_document):
    """Upload a TXT document and return its upload response payload."""

    response = upload_document(
        "notes.txt",
        b"Caching stores frequently used data close to the application. "
        b"A write-through cache writes to the cache and the backing store.",
        "text/plain",
    )
    assert response.status_code == 200, response.text
    return response.json()
