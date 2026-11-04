from vectorstore.chroma_store import get_vector_store

def get_retriever(k: int = 3):

  if k <= 0:
    raise ValueError("k must be greater than zero")

  vector_store = get_vector_store()

  retriever = vector_store.as_retriever(
    search_type = "similarity",
    search_kwargs = {
      "k" : k
    }
  )

  return retriever