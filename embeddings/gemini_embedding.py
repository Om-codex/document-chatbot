"""Google Gemini embedding implementation for the Document Chatbot.

Replaces the local sentence-transformers model with the Gemini Embedding API.
Produces 768-dimensional vectors via ``gemini-embedding-2``.

Inputs are sent as separate ``types.Content`` objects (one per text) to
guarantee a one-to-one mapping between inputs and embeddings.  Large lists
are split into configurable batches and processed sequentially to avoid
unbounded concurrent API requests.
"""

import logging
import time
from functools import lru_cache

from google import genai
from google.genai import types
from langchain_core.embeddings import Embeddings
from pydantic import SecretStr

from config.settings import settings

logger = logging.getLogger(__name__)

DEFAULT_DIMENSIONS = 768
DEFAULT_BATCH_SIZE = 50
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF_SECONDS = 1.0


class GeminiEmbedding(Embeddings):
    """LangChain-compatible embeddings backed by Google Gemini Embedding API.

    Uses ``gemini-embedding-2`` with 768-dimensional output.  Document and
    query embeddings use distinct ``task_type`` values
    (``RETRIEVAL_DOCUMENT`` / ``RETRIEVAL_QUERY``) as recommended by the
    Gemini Embedding API for retrieval use cases.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        batch_size: int | None = None,
        normalize: bool | None = None,
        max_retries: int | None = None,
        initial_backoff_seconds: float | None = None,
        rate_limit_delay_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        # Accept both plain strings and pydantic SecretStr.
        api_key_value = (
            self.api_key.get_secret_value()
            if isinstance(self.api_key, SecretStr)
            else self.api_key
        )

        self.model = model or settings.gemini_embedding_model
        self.dimensions = dimensions or settings.embedding_dimensions
        self.batch_size = batch_size or settings.embedding_batch_size
        self.normalize = (
            settings.normalize_embeddings if normalize is None else normalize
        )
        self.max_retries = (
            max_retries if max_retries is not None else settings.embedding_max_retries
        )
        self.initial_backoff_seconds = (
            initial_backoff_seconds
            if initial_backoff_seconds is not None
            else settings.embedding_initial_backoff_seconds
        )
        self.embedding_rate_limit_delay_seconds = (
            rate_limit_delay_seconds
            if rate_limit_delay_seconds is not None
            else settings.embedding_rate_limit_delay_seconds
        )

        self._client = genai.Client(api_key=api_key_value)

        logger.info(
            "GeminiEmbedding initialized: model=%s dimensions=%d batch_size=%d "
            "normalize=%s max_retries=%d rate_limit_delay=%.1fs",
            self.model,
            self.dimensions,
            self.batch_size,
            self.normalize,
            self.max_retries,
            self.embedding_rate_limit_delay_seconds,
        )

    # ------------------------------------------------------------------
    # LangChain Embeddings interface
    # ------------------------------------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents, preserving order and batching sequentially.

        Splits the input into batches of ``batch_size`` and processes each
        batch sequentially.  Raises if any batch fails -- embeddings are never
        silently dropped or truncated.
        """

        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            batch_embeddings = self._embed_batch(batch, task_type="RETRIEVAL_DOCUMENT")
            all_embeddings.extend(batch_embeddings)

            # Rate-limit: wait between batches to avoid exceeding the
            # Gemini Embedding free tier limit (100 requests/minute).
            # Sleep only if there are more batches to process.
            if start + self.batch_size < len(texts):
                logger.debug(
                    "Rate limit: sleeping %ds before next embedding batch",
                    self.embedding_rate_limit_delay_seconds,
                )
                time.sleep(self.embedding_rate_limit_delay_seconds)

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text using the query task type."""

        embeddings = self._embed_batch([text], task_type="RETRIEVAL_QUERY")
        return embeddings[0]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed_batch(
        self,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        """Embed a single batch with retries and exponential backoff.

        Each text is wrapped in its own ``types.Content`` object so the API
        returns exactly one embedding per input.
        """

        contents = [
            types.Content(parts=[types.Part(text=text)]) for text in texts
        ]

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                result = self._client.models.embed_content(
                    model=self.model,
                    contents=contents,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self.dimensions,
                    ),
                )

                return self._parse_result(result, len(texts))

            except Exception as exc:
                last_exception = exc
                if attempt < self.max_retries and self._is_retryable(exc):
                    backoff = self.initial_backoff_seconds * (2**attempt)
                    logger.warning(
                        "Embedding attempt %d/%d failed, retrying in %.1fs: %s",
                        attempt + 1,
                        self.max_retries + 1,
                        backoff,
                        self._safe_error_message(exc),
                    )
                    time.sleep(backoff)
                    continue

                logger.error(
                    "Embedding failed after %d attempts: %s",
                    self.max_retries + 1,
                    self._safe_error_message(exc),
                )
                raise

        # Unreachable in practice, but satisfies type checkers.
        raise last_exception or RuntimeError("Embedding failed without an exception.")

    def _parse_result(
        self,
        result: types.EmbedContentResponse,
        expected_count: int,
    ) -> list[list[float]]:
        """Parse and validate the API response.

        Validates that every input text received exactly one embedding and
        that each embedding has the expected dimensionality.
        """

        embeddings = getattr(result, "embeddings", None)
        if embeddings is None:
            raise ValueError("Gemini embedding response contained no embeddings.")

        if not isinstance(embeddings, (list, tuple)):
            raise ValueError(
                "Gemini embedding response 'embeddings' is not a list."
            )

        if len(embeddings) != expected_count:
            raise ValueError(
                f"Expected {expected_count} embeddings, got {len(embeddings)}."
            )

        parsed: list[list[float]] = []
        for index, embedding in enumerate(embeddings):
            values = getattr(embedding, "values", None)
            if values is None:
                raise ValueError(f"Embedding {index} has no 'values' field.")

            if len(values) != self.dimensions:
                raise ValueError(
                    f"Embedding {index} has {len(values)} dimensions, "
                    f"expected {self.dimensions}."
                )

            vector = [float(v) for v in values]

            if self.normalize:
                vector = self._normalize(vector)

            parsed.append(vector)

        return parsed

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        """L2-normalize a vector, returning a new list."""

        norm = sum(v * v for v in vector) ** 0.5
        if norm == 0:
            return vector
        return [v / norm for v in vector]

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Return True if the exception warrants a retry.

        Handles HTTP status codes (429, 5xx) and common transient error
        messages without importing provider-specific exception classes.
        """

        status_code = getattr(exc, "code", None) or getattr(
            exc, "status_code", None
        )
        if status_code in (429, 500, 502, 503, 504):
            return True

        message = str(exc).lower()
        retryable_markers = (
            "rate limit",
            "quota",
            "unavailable",
            "timeout",
            "internal",
        )
        return any(marker in message for marker in retryable_markers)

    @staticmethod
    def _safe_error_message(exc: Exception) -> str:
        """Return an error message that never contains the API key or document text."""

        message = str(exc)
        return f"{type(exc).__name__}: {message[:200]}"


@lru_cache(maxsize=1)
def get_embedding_model() -> GeminiEmbedding:
    """Return the process-local Gemini embedding model.

    The cache is process-local: each Uvicorn worker gets its own client.
    """
    return GeminiEmbedding()
