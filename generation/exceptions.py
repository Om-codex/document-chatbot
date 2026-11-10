"""LLM-facing exceptions and translation helpers.

The Groq SDK is an OpenAI-compatible client.  Its exception class names and
``status_code`` attributes are stable enough to translate without leaking the
provider's response body to API clients.
"""

from __future__ import annotations


class LLMError(Exception):
    """Base class for LLM configuration/provider failures."""


class LLMNotConfiguredError(LLMError):
    """The Groq API key is missing or rejected."""


class LLMRateLimitError(LLMError):
    """The provider asked us to slow down."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMTimeoutError(LLMError):
    """The model call exceeded the configured timeout."""


class LLMProviderError(LLMError):
    """The provider returned an error or could not be reached."""


def _retry_after_from_exception(exc: Exception) -> int | None:
    value = getattr(exc, "retry_after", None)

    if value is None:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if headers is not None:
            value = headers.get("retry-after") or headers.get("Retry-After")

    try:
        return int(float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def is_llm_exception(exc: Exception) -> bool:
    """Return True when an exception came from the Groq/OpenAI client layer."""

    module = type(exc).__module__.lower()
    name = type(exc).__name__.lower()

    if module.startswith(("groq", "openai")):
        return True

    return any(
        marker in name
        for marker in (
            "ratelimit",
            "authentication",
            "permissiondenied",
            "apitimeout",
            "apiconnection",
            "apistatus",
            "internalservererror",
        )
    )


def translate_llm_error(exc: Exception) -> LLMError:
    """Convert a provider exception into a stable application exception."""

    if isinstance(exc, LLMError):
        return exc

    name = type(exc).__name__.lower()
    status_code = getattr(exc, "status_code", None)

    if status_code == 429 or "ratelimit" in name:
        return LLMRateLimitError(
            "The language model is rate limited. Please retry shortly.",
            retry_after=_retry_after_from_exception(exc),
        )

    if status_code in (401, 403) or "authentication" in name or "permission" in name:
        return LLMNotConfiguredError(
            "The language model is not configured correctly on the server."
        )

    if "timeout" in name or isinstance(exc, TimeoutError):
        return LLMTimeoutError("The language model request timed out.")

    if status_code is not None or "connection" in name or "api" in name:
        return LLMProviderError("The language model provider returned an error.")

    return LLMProviderError("The language model request failed.")
