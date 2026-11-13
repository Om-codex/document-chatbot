"""Unit tests for the Gemini embedding module.

All tests mock the Google Gen AI client so no API quota is consumed.
"""

from unittest.mock import MagicMock, patch

import pytest

from embeddings.gemini_embedding import GeminiEmbedding
from langchain_core.embeddings import Embeddings


class _FakeEmbedding:
    """Fake Gemini embedding response object with a ``values`` attribute."""

    def __init__(self, values):
        self.values = values


class _FakeResponse:
    """Fake Gemini ``embed_content`` response."""

    def __init__(self, embeddings):
        self.embeddings = list(embeddings)


def _make_client(embeddings_per_call):
    """Return a fake genai.Client.

    ``embeddings_per_call`` is a list of per-call embedding lists.  Each
    call to ``embed_content`` returns the next entry.
    """

    client = MagicMock()
    client.models.embed_content.side_effect = [
        _FakeResponse(embs) for embs in embeddings_per_call
    ]
    return client


def _embedding_vector(values):
    return [_FakeEmbedding(list(values))]


def _fake_response_for_texts(texts, vector_template):
    """Return a single FakeResponse with one embedding per text."""

    return _FakeResponse([
        _FakeEmbedding(list(vector_template)) for _ in texts
    ])


# ------------------------------------------------------------------
# Interface checks
# ------------------------------------------------------------------

def test_gemini_embedding_is_langchain_embeddings_subclass():
    assert issubclass(GeminiEmbedding, Embeddings)


def test_gemini_embedding_has_required_methods():
    assert hasattr(GeminiEmbedding, "embed_documents")
    assert hasattr(GeminiEmbedding, "embed_query")


# ------------------------------------------------------------------
# Construction
# ------------------------------------------------------------------

def test_construction_with_plain_string_key():
    with patch("embeddings.gemini_embedding.genai.Client", return_value=MagicMock()):
        emb = GeminiEmbedding(api_key="test-key")
        assert emb.model == "gemini-embedding-2"
        assert emb.dimensions == 768
        assert emb.batch_size == 50
        assert emb.normalize is True
        assert emb.max_retries == 3


def test_construction_reads_settings(monkeypatch):
    from config import settings as settings_module

    monkeypatch.setattr(
        settings_module.settings,
        "gemini_embedding_model",
        "gemini-embedding-2",
    )
    monkeypatch.setattr(settings_module.settings, "embedding_dimensions", 768)
    monkeypatch.setattr(settings_module.settings, "embedding_batch_size", 25)
    monkeypatch.setattr(settings_module.settings, "normalize_embeddings", False)
    monkeypatch.setattr(settings_module.settings, "embedding_max_retries", 5)
    monkeypatch.setattr(
        settings_module.settings, "embedding_initial_backoff_seconds", 2.0
    )

    with patch("embeddings.gemini_embedding.genai.Client", return_value=MagicMock()):
        emb = GeminiEmbedding(api_key="test-key")
        assert emb.model == "gemini-embedding-2"
        assert emb.dimensions == 768
        assert emb.batch_size == 25
        assert emb.normalize is False
        assert emb.max_retries == 5
        assert emb.initial_backoff_seconds == 2.0


def test_construction_without_api_key_raises():
    with patch("embeddings.gemini_embedding.genai.Client", return_value=MagicMock()):
        with patch.object(
            GeminiEmbedding, "__init__", lambda self, api_key=None: None
        ):
            pass
        # Directly test the validation logic
        with patch(
            "embeddings.gemini_embedding.settings.gemini_api_key", None
        ):
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                GeminiEmbedding(api_key=None)


# ------------------------------------------------------------------
# embed_query
# ------------------------------------------------------------------

def test_embed_query_returns_768_dimensions():
    fake_client = _make_client([_embedding_vector([0.5] * 768)])
    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        emb = GeminiEmbedding(api_key="test-key", normalize=False)
        result = emb.embed_query("What is caching?")

    assert len(result) == 768
    assert all(v == 0.5 for v in result)

    # Verify task_type is RETRIEVAL_QUERY
    call_kwargs = fake_client.models.embed_content.call_args.kwargs
    assert call_kwargs["config"].task_type == "RETRIEVAL_QUERY"
    assert call_kwargs["config"].output_dimensionality == 768


def test_embed_query_uses_separate_content_object():
    fake_client = _make_client([_embedding_vector([0.1] * 768)])
    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        emb = GeminiEmbedding(api_key="test-key")
        emb.embed_query("hello world")

    call_kwargs = fake_client.models.embed_content.call_args.kwargs
    contents = call_kwargs["contents"]
    assert len(contents) == 1
    assert contents[0].parts[0].text == "hello world"


# ------------------------------------------------------------------
# embed_documents
# ------------------------------------------------------------------

def test_embed_documents_returns_n_vectors():
    fake_client = _make_client([
        [_FakeEmbedding([0.1] * 768), _FakeEmbedding([0.2] * 768)],
    ])
    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        emb = GeminiEmbedding(api_key="test-key", normalize=False)
        result = emb.embed_documents(["doc one", "doc two"])

    assert len(result) == 2
    assert result[0] == [0.1] * 768
    assert result[1] == [0.2] * 768

    call_kwargs = fake_client.models.embed_content.call_args.kwargs
    assert call_kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"


def test_embed_documents_empty_list_returns_empty():
    with patch("embeddings.gemini_embedding.genai.Client", return_value=MagicMock()):
        emb = GeminiEmbedding(api_key="test-key")
        result = emb.embed_documents([])
        assert result == []


def test_embed_documents_batching_preserves_order():
    """120 texts with batch_size=50 → 3 API calls, ordering preserved."""

    texts = [f"text {i}" for i in range(120)]
    expected = [[float(i % 7) / 7.0] * 768 for i in range(120)]

    fake_client = _make_client([
        [_FakeEmbedding(expected[i]) for i in range(50)],
        [_FakeEmbedding(expected[i]) for i in range(50, 100)],
        [_FakeEmbedding(expected[i]) for i in range(100, 120)],
    ])
    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        emb = GeminiEmbedding(api_key="test-key", batch_size=50, normalize=False)
        result = emb.embed_documents(texts)

    assert len(result) == 120
    for i, vec in enumerate(result):
        assert vec == expected[i], f"Mismatch at index {i}"
    assert fake_client.models.embed_content.call_count == 3

    # Verify each batch used RETRIEVAL_DOCUMENT
    for call in fake_client.models.embed_content.call_args_list:
        assert call.kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"


def test_embed_documents_each_input_gets_own_content_object():
    fake_client = _make_client([
        _embedding_vector([0.1] * 768),
        _embedding_vector([0.2] * 768),
    ])
    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        emb = GeminiEmbedding(api_key="test-key", batch_size=1)
        emb.embed_documents(["first", "second"])

    # Two calls, each with one Content object
    assert fake_client.models.embed_content.call_count == 2
    first_contents = fake_client.models.embed_content.call_args_list[0].kwargs[
        "contents"
    ]
    second_contents = fake_client.models.embed_content.call_args_list[1].kwargs[
        "contents"
    ]
    assert len(first_contents) == 1
    assert first_contents[0].parts[0].text == "first"
    assert len(second_contents) == 1
    assert second_contents[0].parts[0].text == "second"


# ------------------------------------------------------------------
# Dimension validation
# ------------------------------------------------------------------

def test_wrong_dimension_raises():
    fake_client = _make_client([_embedding_vector([0.1] * 512)])  # wrong dim
    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        emb = GeminiEmbedding(api_key="test-key", dimensions=768)
        with pytest.raises(ValueError, match="dimensions"):
            emb.embed_query("test")


def test_missing_values_field_raises():
    """A non-list 'embeddings' attribute should raise 'not a list'."""

    class FakeResponseNonList:
        embeddings = "not-a-list"

    fake_client = MagicMock()
    fake_client.models.embed_content.return_value = FakeResponseNonList()

    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        emb = GeminiEmbedding(api_key="test-key", dimensions=768)
        with pytest.raises(ValueError, match="not a list"):
            emb.embed_query("test")


def test_mismatched_count_raises():
    fake_client = _make_client([
        _embedding_vector([0.1] * 768),  # only 1 embedding for 2 inputs
    ])
    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        emb = GeminiEmbedding(api_key="test-key", dimensions=768)
        with pytest.raises(ValueError, match="Expected 2 embeddings, got 1"):
            emb.embed_documents(["a", "b"])


# ------------------------------------------------------------------
# Normalization
# ------------------------------------------------------------------

def test_normalization_applied():
    """[3, 4, 0, ...] → L2 norm = 1."""

    vector = [3.0, 4.0] + [0.0] * 766
    fake_client = _make_client([_embedding_vector(vector)])
    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        emb = GeminiEmbedding(api_key="test-key", dimensions=768, normalize=True)
        result = emb.embed_query("test")

    norm = sum(v * v for v in result) ** 0.5
    assert abs(norm - 1.0) < 1e-6
    assert abs(result[0] - 0.6) < 1e-6
    assert abs(result[1] - 0.8) < 1e-6


def test_normalization_can_be_disabled():
    vector = [3.0, 4.0] + [0.0] * 766
    fake_client = _make_client([_embedding_vector(vector)])
    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        emb = GeminiEmbedding(api_key="test-key", dimensions=768, normalize=False)
        result = emb.embed_query("test")

    assert result[0] == 3.0
    assert result[1] == 4.0


# ------------------------------------------------------------------
# Retry / backoff
# ------------------------------------------------------------------

def test_retry_on_429_then_success():
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            exc = Exception("rate limited")
            exc.status_code = 429
            raise exc
        return _FakeResponse([_FakeEmbedding([0.5] * 768)])

    fake_client = MagicMock()
    fake_client.models.embed_content.side_effect = side_effect

    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        with patch("embeddings.gemini_embedding.time.sleep") as mock_sleep:
            emb = GeminiEmbedding(
                api_key="test-key", max_retries=3, initial_backoff_seconds=0.01
            )
            result = emb.embed_query("test")

    assert len(result) == 768
    assert call_count == 2  # initial + 1 retry
    mock_sleep.assert_called_once()


def test_all_retries_exhausted_raises():
    def always_fail(*args, **kwargs):
        exc = Exception("rate limited")
        exc.status_code = 429
        raise exc

    fake_client = MagicMock()
    fake_client.models.embed_content.side_effect = always_fail

    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        with patch("embeddings.gemini_embedding.time.sleep"):
            emb = GeminiEmbedding(
                api_key="test-key", max_retries=2, initial_backoff_seconds=0.01
            )
            with pytest.raises(Exception, match="rate limited"):
                emb.embed_query("test")

    assert fake_client.models.embed_content.call_count == 3  # initial + 2 retries


def test_non_retryable_error_raises_immediately():
    def always_fail(*args, **kwargs):
        raise ValueError("bad request")

    fake_client = MagicMock()
    fake_client.models.embed_content.side_effect = always_fail

    with patch("embeddings.gemini_embedding.genai.Client", return_value=fake_client):
        with patch("embeddings.gemini_embedding.time.sleep") as mock_sleep:
            emb = GeminiEmbedding(api_key="test-key", max_retries=3)
            with pytest.raises(ValueError, match="bad request"):
                emb.embed_query("test")

    mock_sleep.assert_not_called()
    assert fake_client.models.embed_content.call_count == 1


# ------------------------------------------------------------------
# Error message safety (no keys or document text)
# ------------------------------------------------------------------

def test_safe_error_message_truncates():
    from embeddings.gemini_embedding import GeminiEmbedding as GE

    long_message = "x" * 500
    exc = RuntimeError(long_message)
    safe = GE._safe_error_message(exc)
    assert len(safe) <= len("RuntimeError: ") + 200
    assert "x" * 500 not in safe
