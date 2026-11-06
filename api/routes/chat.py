import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from api.schemas.chat import ChatRequest, ChatResponse

from chains.qa_chain import get_qa_chain

logger = logging.getLogger(__name__)

router = APIRouter(
  prefix = "/api/chat",
  tags = ["Chat"]
)


# Chat endpoint
@router.post("/", response_model = ChatResponse)
def chat(request: ChatRequest):

  question = request.question.strip()

  if not question:
    raise HTTPException(
      status_code = 422,
      detail = "Question cannot be empty!"
    )

  try:

    # normalize document IDs
    doc_ids = [
      doc_id.strip()
      for doc_id in (request.doc_ids or [])
      if doc_id.strip()
    ]

    # empty IDs means searching across all documents
    if not doc_ids:
      doc_ids = None

    # 1. initialize QA chain with option document filtering
    qa_chain = get_qa_chain(
      doc_ids = doc_ids,
      k = request.k
    )

    # 2. run retrieval and answer generation
    result = qa_chain.invoke(question)

    # 3. convert retrieved LangChain Documents into JSON
    retrieved_chunks = []

    for document in result["sources"]:
      metadata = document.metadata
      
      page = metadata.get("page")

      retrieved_chunks.append({
        "chunk_id" :(
          f"{metadata.get("doc_id")}_"
          f"{metadata.get("chunk_index")}"
        ),
        "content" : document.page_content,
        "metadata" : {
          "doc_id" : metadata.get("doc_id"),
          "filename" : metadata.get("filename"),
          "chunk_index" : metadata.get("chunk_index"),
          "page" : page,
          "page_number" : page + 1 if isinstance(page,int) else None,
          "page_label" : metadata.get("page_label"),
          "total_pages" : metadata.get("total_pages")
        }
      })

    return {
      "question" : question,
      "answer" : result["answer"],
      "total_chunks_retrieved" : len(retrieved_chunks),
      "retrieved_chunks" : retrieved_chunks
    }

  except HTTPException:
    raise
  
  except Exception:
    logger.exception("Chat request failed.")

    raise HTTPException(
      status_code = 500,
      detail = "Failed to generate an answer. Check backend logs."
    )