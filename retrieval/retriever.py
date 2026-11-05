from vectorstore.chroma_store import get_vector_store

def get_retriever(k: int = 3, doc_ids: list[str] | None = None):

  if k <= 0:
    raise ValueError("k must be greater than zero")

  vector_store = get_vector_store()

  search_kwargs = {
    "k":k
  }

  # apply document-specific filtering
  if doc_ids:

    search_kwargs["filter"] = {
      "doc_id" : {
        "$in" : doc_ids
      }
    }

  retriever = vector_store.as_retriever(
    search_type = "similarity",
    search_kwargs = search_kwargs
  )

  return retriever