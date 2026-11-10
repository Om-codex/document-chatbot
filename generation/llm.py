import logging
from functools import lru_cache

from langchain_groq import ChatGroq

from config.settings import settings
from generation.exceptions import LLMNotConfiguredError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    """Create the Groq client once per process.

    ``max_retries`` is handled by the SDK.  We do not add a second retry loop in
    application code, which would multiply latency and cost on rate limits.
    """

    if settings.groq_api_key is None:
        raise LLMNotConfiguredError("GROQ_API_KEY is not configured.")

    logger.info(
        "Creating Groq client: model=%s temperature=%s max_retries=%d",
        settings.llm_model,
        settings.llm_temperature,
        settings.llm_max_retries,
    )

    return ChatGroq(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_retries=settings.llm_max_retries,
        timeout=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.groq_api_key.get_secret_value(),
    )
