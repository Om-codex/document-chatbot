"""Chat API validation, retrieval and error-mapping tests."""

import pytest

from generation.exceptions import (
    LLMNotConfiguredError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from services import chat_service


def _chat(client, **body):
    return client.post("/api/chat/", json=body)


def test_chat_returns_answer_and_chunks(client, indexed_txt):
    response = _chat(client, question="What does the document say about caching?", k=2)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["question"] == "What does the document say about caching?"
    assert payload["answer"] == "Test answer grounded in the context."
    assert payload["total_chunks_retrieved"] == len(payload["retrieved_chunks"])
    assert payload["total_chunks_retrieved"] >= 1

    chunk = payload["retrieved_chunks"][0]
    assert len(chunk["chunk_id"]) > 0
    assert chunk["content"]
    assert chunk["metadata"]["doc_id"] == indexed_txt["doc_id"]
    assert chunk["metadata"]["filename"] == "notes.txt"
    assert chunk["metadata"]["chunk_index"] == 0
    assert chunk["metadata"]["page"] is None
    assert chunk["metadata"]["page_number"] is None


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_chat_rejects_empty_question(client, indexed_txt, question):
    response = _chat(client, question=question)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_chat_rejects_too_long_question(client, indexed_txt):
    response = _chat(client, question="x" * 4001)

    assert response.status_code == 422


@pytest.mark.parametrize("k", [1, 20])
def test_chat_accepts_valid_k(client, indexed_txt, k):
    response = _chat(client, question="What is caching?", k=k)

    assert response.status_code == 200


@pytest.mark.parametrize("k", [0, 21, -1])
def test_chat_rejects_invalid_k(client, indexed_txt, k):
    response = _chat(client, question="What is caching?", k=k)

    assert response.status_code == 422


@pytest.mark.parametrize("body", [
    {"question": "What is caching?"},
    {"question": "What is caching?", "doc_ids": None},
    {"question": "What is caching?", "doc_ids": []},
])
def test_chat_all_documents_variants(client, indexed_txt, body):
    response = _chat(client, **body)

    assert response.status_code == 200
    assert response.json()["total_chunks_retrieved"] >= 1


def test_chat_selected_document_filtering(client, upload_document):
    first = upload_document("first.txt", b"alpha caching content", "text/plain").json()
    upload_document("second.txt", b"beta database content", "text/plain")

    response = _chat(client, question="What is caching?", doc_ids=[first["doc_id"]], k=10)

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieved_chunks"]
    assert all(
        chunk["metadata"]["doc_id"] == first["doc_id"]
        for chunk in payload["retrieved_chunks"]
    )


def test_chat_rejects_duplicate_doc_ids(client, indexed_txt):
    response = _chat(
        client,
        question="What is caching?",
        doc_ids=[indexed_txt["doc_id"], indexed_txt["doc_id"]],
    )

    assert response.status_code == 422


def test_chat_rejects_empty_doc_id(client, indexed_txt):
    response = _chat(client, question="What is caching?", doc_ids=[""])

    assert response.status_code == 422


def test_chat_rejects_too_many_doc_ids(client, indexed_txt):
    response = _chat(
        client,
        question="What is caching?",
        doc_ids=[f"{index:064x}" for index in range(51)],
    )

    assert response.status_code == 422


def test_chat_rejects_malformed_doc_id(client, indexed_txt):
    response = _chat(client, question="What is caching?", doc_ids=["not-a-hash"])

    assert response.status_code == 422


def test_chat_rejects_unknown_selected_document(client, indexed_txt):
    response = _chat(client, question="What is caching?", doc_ids=["a" * 64])

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_DOCUMENT_SELECTION"


def test_chat_with_no_documents(client):
    response = _chat(client, question="What is caching?")

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "NO_DOCUMENTS"


def test_chat_no_chunks_retrieved_is_not_an_infrastructure_error(
    client, indexed_txt, monkeypatch
):
    class EmptyChain:
        def invoke(self, _question):
            return {
                "answer": "No relevant information found.",
                "sources": [],
            }

    monkeypatch.setattr(chat_service, "get_qa_chain", lambda **_: EmptyChain())

    response = _chat(client, question="What is caching?")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_chunks_retrieved"] == 0
    assert payload["retrieved_chunks"] == []
    assert "No relevant information" in payload["answer"]


def test_chat_retriever_failure_maps_to_503(client, indexed_txt, monkeypatch):
    def broken_chain(**_):
        raise RuntimeError("retrieval exploded")

    monkeypatch.setattr(chat_service, "get_qa_chain", broken_chain)

    response = _chat(client, question="What is caching?")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "RETRIEVAL_ERROR"


def test_chat_llm_provider_failure_maps_to_502(client, indexed_txt, monkeypatch):
    def broken_llm():
        raise LLMProviderError("provider down")

    monkeypatch.setattr("chains.qa_chain.get_llm", broken_llm)

    response = _chat(client, question="What is caching?")

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "LLM_PROVIDER_ERROR"


def test_chat_llm_rate_limit_maps_to_429_with_retry_after(
    client, indexed_txt, monkeypatch
):
    def rate_limited():
        raise LLMRateLimitError("slow down", retry_after=7)

    monkeypatch.setattr("chains.qa_chain.get_llm", rate_limited)

    response = _chat(client, question="What is caching?")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    assert response.json()["detail"]["code"] == "LLM_RATE_LIMIT"
    assert response.json()["detail"]["details"]["retry_after"] == 7


def test_chat_llm_timeout_maps_to_504(client, indexed_txt, monkeypatch):
    def timed_out():
        raise LLMTimeoutError("timeout")

    monkeypatch.setattr("chains.qa_chain.get_llm", timed_out)

    response = _chat(client, question="What is caching?")

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "LLM_TIMEOUT"


def test_chat_missing_llm_key_maps_to_503(client, indexed_txt, monkeypatch):
    def not_configured():
        raise LLMNotConfiguredError("missing key")

    monkeypatch.setattr("chains.qa_chain.get_llm", not_configured)

    response = _chat(client, question="What is caching?")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "LLM_NOT_CONFIGURED"


def test_chat_does_not_call_llm_when_no_documents(client, monkeypatch):
    def unexpected_llm():
        raise AssertionError("LLM must not be called when there are no documents")

    monkeypatch.setattr("chains.qa_chain.get_llm", unexpected_llm)

    response = _chat(client, question="What is caching?")

    assert response.status_code == 400
