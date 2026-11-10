import logging
from operator import itemgetter

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough

from chains.prompt_template import get_rag_prompt
from generation.llm import get_llm
from retrieval.retriever import get_retriever

logger = logging.getLogger(__name__)


NO_CONTEXT_ANSWER = (
    "I could not find any relevant information in the selected documents. "
    "Try rephrasing the question or uploading a document that covers this topic."
)


def format_docs(documents) -> str:
    return "\n\n".join(document.page_content for document in documents)


def _answer_question(payload: dict, prompt, llm) -> dict:
    """Generate an answer, or return a deterministic message when retrieval is empty.

    Skipping the LLM when there is no context avoids paying for a call that can
    only hallucinate, and makes "no relevant context" distinguishable from an
    infrastructure failure.
    """

    documents = payload["documents"]

    if not documents:
        logger.info("No relevant chunks retrieved; returning the no-context answer.")
        return {"answer": NO_CONTEXT_ANSWER, "sources": []}

    answer = (prompt | llm | StrOutputParser()).invoke(
        {
            "context": payload["context"],
            "question": payload["question"],
        }
    )

    return {"answer": answer, "sources": documents}


def get_qa_chain(doc_ids: list[str] | None = None, k: int = 3):
    """Build the LCEL retrieval + answer chain."""

    if doc_ids is not None and not doc_ids:
        raise ValueError("doc_ids cannot be an empty list")

    retriever = get_retriever(k=k, doc_ids=doc_ids)
    prompt = get_rag_prompt()
    llm = get_llm()

    retrieval_chain = RunnableParallel(
        {
            "question": RunnablePassthrough(),
            "documents": retriever,
        }
    )

    context_chain = retrieval_chain | RunnablePassthrough.assign(
        context=lambda values: format_docs(values["documents"])
    )

    return context_chain | RunnableLambda(
        lambda payload: _answer_question(payload, prompt, llm)
    )
