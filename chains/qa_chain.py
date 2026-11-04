
from operator import itemgetter

from langchain_core.runnables import (
    RunnablePassthrough,
    RunnableParallel
)
from langchain_core.output_parsers import StrOutputParser

from retrieval.retriever import get_retriever
from chains.prompt_template import get_rag_prompt
from generation.llm import get_llm


def format_docs(documents):

    return "\n\n".join(
        document.page_content
        for document in documents
    )


def get_qa_chain():

    retriever = get_retriever(k=3)

    prompt = get_rag_prompt()

    llm = get_llm()

    # Step 1: Retrieve documents
    retrieval_chain = RunnableParallel({
        "question": RunnablePassthrough(),
        "documents": retriever
    })

    # Step 2: Format retrieved documents
    context_chain = retrieval_chain | RunnablePassthrough.assign(
        context=lambda x: format_docs(x["documents"])
    )

    # Step 3: Generate answer and return sources
    qa_chain = context_chain | RunnableParallel({

        "answer": (
            prompt
            | llm
            | StrOutputParser()
        ),

        "sources": itemgetter("documents")

    })

    return qa_chain
