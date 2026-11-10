import logging

from fastapi import APIRouter

from api.errors import api_error
from api.schemas.chat import ChatRequest, ChatResponse
from generation.exceptions import (
    LLMNotConfiguredError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from services.chat_service import chat_with_documents
from services.exceptions import (
    ChatServiceError,
    ChatValidationError,
    InvalidDocumentSelectionError,
    NoDocumentsError,
    RetrievalError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"],
)


# Chat endpoint
@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        return chat_with_documents(request.question, request.doc_ids, request.k)

    except ChatValidationError as exc:
        raise api_error(400, "INVALID_REQUEST", str(exc))

    except NoDocumentsError as exc:
        raise api_error(400, "NO_DOCUMENTS", str(exc))

    except InvalidDocumentSelectionError as exc:
        raise api_error(400, "INVALID_DOCUMENT_SELECTION", str(exc))

    except RetrievalError as exc:
        logger.exception("Chat retrieval failed.")
        raise api_error(503, "RETRIEVAL_ERROR", str(exc))

    except LLMNotConfiguredError as exc:
        logger.exception("LLM is not configured.")
        raise api_error(503, "LLM_NOT_CONFIGURED", str(exc))

    except LLMRateLimitError as exc:
        headers = (
            {"Retry-After": str(exc.retry_after)}
            if exc.retry_after is not None
            else None
        )
        raise api_error(
            429,
            "LLM_RATE_LIMIT",
            str(exc),
            details={"retry_after": exc.retry_after} if exc.retry_after else None,
            headers=headers,
        )

    except LLMTimeoutError as exc:
        raise api_error(504, "LLM_TIMEOUT", str(exc))

    except LLMProviderError as exc:
        logger.exception("LLM provider failed.")
        raise api_error(502, "LLM_PROVIDER_ERROR", str(exc))

    except ChatServiceError as exc:
        logger.exception("Chat request failed.")
        raise api_error(500, "CHAT_ERROR", str(exc))

    except Exception:
        logger.exception("Chat request failed.")
        raise api_error(500, "INTERNAL_ERROR", "Failed to generate an answer.")
