"""Ingestion pipeline, loader and splitter tests (no embeddings/LLM)."""

import pytest

from ingestion.exceptions import EmptyDocumentError, UnsupportedDocumentFormatError
from ingestion.loaders import load_document
from ingestion.pipeline import generate_document_id, ingest_document
from ingestion.text_splitter import split_documents
from tests.conftest import make_docx_bytes, make_pdf_bytes
from utils.helpers import sanitize_filename


def test_generate_document_id_is_stable_sha256(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("stable content", encoding="utf-8")

    first = generate_document_id(str(file_path))
    second = generate_document_id(str(file_path))

    assert first == second
    assert len(first) == 64
    assert int(first, 16) >= 0

    file_path.write_text("different content", encoding="utf-8")
    assert generate_document_id(str(file_path)) != first


def test_ingest_txt_assigns_metadata(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text(
        "Caching stores frequently used data close to the application.",
        encoding="utf-8",
    )

    chunks = ingest_document(str(file_path))

    assert len(chunks) == 1
    metadata = chunks[0].metadata
    assert metadata["doc_id"] == generate_document_id(str(file_path))
    assert metadata["filename"] == "notes.txt"
    assert metadata["chunk_index"] == 0


def test_ingest_pdf_preserves_page_metadata(tmp_path):
    file_path = tmp_path / "paper.pdf"
    file_path.write_bytes(make_pdf_bytes("Caching improves latency."))

    chunks = ingest_document(str(file_path))

    assert chunks
    metadata = chunks[0].metadata
    assert metadata["page"] == 0
    assert metadata["page_label"] == "1"
    assert metadata["total_pages"] == 1
    assert metadata["filename"] == "paper.pdf"


def test_ingest_docx(tmp_path):
    file_path = tmp_path / "memo.docx"
    file_path.write_bytes(make_docx_bytes("A short memo about caching."))

    chunks = ingest_document(str(file_path))

    assert chunks
    assert chunks[0].metadata["filename"] == "memo.docx"
    assert chunks[0].metadata["chunk_index"] == 0


def test_ingest_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ingest_document(str(tmp_path / "missing.txt"))


def test_ingest_empty_document_raises(tmp_path):
    file_path = tmp_path / "empty.txt"
    file_path.write_text("", encoding="utf-8")

    with pytest.raises(EmptyDocumentError):
        ingest_document(str(file_path))


def test_loader_rejects_unsupported_extension(tmp_path):
    file_path = tmp_path / "notes.md"
    file_path.write_text("# heading", encoding="utf-8")

    with pytest.raises(UnsupportedDocumentFormatError):
        load_document(str(file_path))


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(0, 0), (100, -1), (100, 100), (100, 200)],
)
def test_splitter_rejects_invalid_configuration(chunk_size, chunk_overlap):
    with pytest.raises(ValueError):
        split_documents([], chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def test_splitter_respects_size_and_overlap(tmp_path):
    file_path = tmp_path / "long.txt"
    file_path.write_text("word " * 500, encoding="utf-8")

    documents = load_document(str(file_path))
    chunks = split_documents(documents, chunk_size=100, chunk_overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk.page_content) <= 100 for chunk in chunks)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("..\\..\\windows\\notes.txt", "notes.txt"),
        ("Meeting: notes?.txt", "Meeting_ notes_.txt"),
        ("CON", "_CON"),
        ("nul.txt", "_nul.txt"),
        ("  spaced  .txt  ", "spaced  .txt"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_caps_length_and_keeps_extension():
    name = sanitize_filename(f"{'a' * 500}.pdf")

    assert len(name) <= 200
    assert name.endswith(".pdf")


def test_sanitize_filename_rejects_empty_and_dot_names():
    for raw in ["", "   ", ".", "..", "../"]:
        with pytest.raises(ValueError):
            sanitize_filename(raw)
