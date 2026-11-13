"""Vector store and retrieval tests against a temporary Chroma collection."""

import pytest
from langchain_core.documents import Document

from retrieval.retriever import get_retriever
from vectorstore.qdrant_store import (
    add_documents,
    count_document_chunks,
    delete_documents,
    document_exists,
    get_all_documents,
    get_document_count,
)


def make_chunks(doc_id: str, filename: str, texts: list[str]) -> list[Document]:
    return [
        Document(
            page_content=text,
            metadata={
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": index,
            },
        )
        for index, text in enumerate(texts)
    ]


def test_add_and_list_documents(isolated_storage):
    chunks = make_chunks("a" * 64, "alpha.txt", ["alpha one", "alpha two", "alpha three"])

    ids = add_documents(chunks)

    assert ids == [f"{'a' * 64}_0", f"{'a' * 64}_1", f"{'a' * 64}_2"]
    documents = get_all_documents()
    assert len(documents) == 1
    assert documents[0]["doc_id"] == "a" * 64
    assert documents[0]["filename"] == "alpha.txt"
    assert documents[0]["total_chunks"] == 3
    assert document_exists("a" * 64)
    assert count_document_chunks("a" * 64) == 3
    assert get_document_count() == 1


def test_replacing_with_fewer_chunks_removes_stale_chunks(isolated_storage):
    doc_id = "b" * 64
    add_documents(make_chunks(doc_id, "beta.txt", ["one", "two", "three"]))

    add_documents(make_chunks(doc_id, "beta.txt", ["replacement"]))

    assert count_document_chunks(doc_id) == 1


def test_replacing_with_more_chunks_adds_new_chunks(isolated_storage):
    doc_id = "c" * 64
    add_documents(make_chunks(doc_id, "gamma.txt", ["one"]))

    add_documents(make_chunks(doc_id, "gamma.txt", ["one", "two", "three"]))

    assert count_document_chunks(doc_id) == 3


def test_delete_document_vectors_only_removes_selected_document(isolated_storage):
    first_id = "d" * 64
    second_id = "e" * 64
    add_documents(make_chunks(first_id, "first.txt", ["first content"]))
    add_documents(make_chunks(second_id, "second.txt", ["second content"]))

    deleted = delete_documents(first_id)

    assert deleted == 1
    assert not document_exists(first_id)
    assert document_exists(second_id)
    assert {document["doc_id"] for document in get_all_documents()} == {second_id}


def test_retriever_searches_all_documents(isolated_storage):
    add_documents(make_chunks("f" * 64, "alpha.txt", ["alpha caching content"]))
    add_documents(make_chunks("g" * 64, "beta.txt", ["beta database content"]))

    results = get_retriever(k=10).invoke("alpha caching")

    assert results
    assert {document.metadata["doc_id"] for document in results} <= {"f" * 64, "g" * 64}


def test_retriever_filters_selected_documents(isolated_storage):
    first_id = "h" * 64
    second_id = "i" * 64
    add_documents(make_chunks(first_id, "alpha.txt", ["alpha caching content"]))
    add_documents(make_chunks(second_id, "beta.txt", ["beta database content"]))

    results = get_retriever(k=10, doc_ids=[first_id]).invoke("caching database")

    assert results
    assert all(document.metadata["doc_id"] == first_id for document in results)


def test_add_documents_rejects_mixed_documents(isolated_storage):
    chunks = make_chunks("j" * 64, "alpha.txt", ["one"])
    chunks.append(
        Document(
            page_content="two",
            metadata={"doc_id": "k" * 64, "filename": "beta.txt", "chunk_index": 0},
        )
    )

    with pytest.raises(ValueError, match="same document"):
        add_documents(chunks)

    assert get_all_documents() == []


def test_add_documents_rejects_empty_list(isolated_storage):
    with pytest.raises(ValueError, match="No document chunks"):
        add_documents([])


def test_add_documents_requires_doc_id(isolated_storage):
    with pytest.raises(ValueError, match="doc_id"):
        add_documents([Document(page_content="text", metadata={"chunk_index": 0})])


def test_stale_chunk_deletion_failure_is_reported(isolated_storage, monkeypatch):
    doc_id = "l" * 64
    add_documents(make_chunks(doc_id, "alpha.txt", ["one", "two"]))

    from unittest.mock import MagicMock
    from vectorstore import qdrant_store

    mock_client = MagicMock()
    mock_client.get_collections.return_value.collections = []
    existing_point_0 = MagicMock()
    existing_point_0.id = qdrant_store._chunk_id_to_uuid(f"{doc_id}_0")
    existing_point_1 = MagicMock()
    existing_point_1.id = qdrant_store._chunk_id_to_uuid(f"{doc_id}_1")
    mock_client.scroll.return_value = ([existing_point_0, existing_point_1], None)
    mock_client.delete.side_effect = RuntimeError("delete failed")
    mock_client.upsert.return_value = None

    monkeypatch.setattr(qdrant_store, "_get_qdrant_client", lambda: mock_client)

    with pytest.raises(RuntimeError, match="delete failed"):
        add_documents(make_chunks(doc_id, "alpha.txt", ["replacement"]))
