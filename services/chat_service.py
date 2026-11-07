from chains.qa_chain import get_qa_chain

def chat_with_documents(question : str, doc_id : int, k : int) -> dict:
  question = question.strip()

  if not question:
    raise ValueError("Question cannot be empty.")

  # normalize document IDs
  doc_ids = [
    doc_id.strip()
    for doc_id in (doc_ids or [])
    if doc_id.strip()
  ]

  # empty IDs means searching across all documents
  if not doc_ids:
    doc_ids = None

  # 1. initialize QA chain with option document filtering
  qa_chain = get_qa_chain(
    doc_ids = doc_ids,
    k = k
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


