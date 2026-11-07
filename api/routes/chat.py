import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from api.schemas.chat import ChatRequest, ChatResponse
from services.chat_service import chat_with_documents

logger = logging.getLogger(__name__)

router = APIRouter(
  prefix = "/api/chat",
  tags = ["Chat"]
)


# Chat endpoint
@router.post("/", response_model = ChatResponse)
def chat(request: ChatRequest):

  try:
    result = chat_with_documents(request.question, request.doc_ids, request.k)

    return result

  except HTTPException:
    raise
  
  except Exception:
    logger.exception("Chat request failed.")

    raise HTTPException(
      status_code = 500,
      detail = "Failed to generate an answer. Check backend logs."
    )