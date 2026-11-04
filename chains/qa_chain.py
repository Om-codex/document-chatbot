from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from retrieval.retriever import get_retriever
from chains.prompt_template import get_rag_prompt
from generation.llm import get_llm

def format_docs(documents):
  return "\n\n".join(
    document.page_content for document in documents
  )

def get_qa_chain():
  retriever = get_retriever(k = 3)
  prompt = get_rag_prompt()
  llm = get_llm()
  parser = StrOutputParser()

  qa_chain = (
    {
      "context" : retriever | format_docs,
      "question" : RunnablePassthrough()
    } | prompt | llm | parser
  )

  return qa_chain