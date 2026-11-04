from pathlib import Path
from langchain_chroma import Chroma
from embeddings.embedding_model import get_embedding_model

BASE_DIR = Path(__file__).resolve().parent.parent

CHROMA_PATH = BASE_DIR / "data" / "chroma_db"

COLLECTION_NAME = "document_collection_v2"

def get_vector_store():
  embedding_model = get_embedding_model()

  vector_store = Chroma(
    collection_name = COLLECTION_NAME,
    embedding_function = embedding_model,
    persist_directory = str(CHROMA_PATH)
  )

  return vector_store

def add_documents(chunks):

  if not chunks:
    raise ValueError("No document chunks provided!")

  vector_store = get_vector_store()

  doc_id = chunks[0].metadata["doc_id"]

  # ensure that all chunks belongs to the same document
  if any(chunk.metadata.get("doc_id") != doc_id for chunk in chunks):
    raise ValueError("All chunks must belong to the same document!")

  # remove previously stored chunks of this doc
  delete_documents(doc_id)

  #  generate deterministic chunk IDs
  ids = [
    f"{doc_id}_{chunk.metadata['chunk_index']}" for chunk in chunks
  ]

  # store chunks and embeddings
  vector_store.add_documents(
    documents = chunks,
    ids = ids
  )

  return ids

def delete_documents(doc_id : str):
  vector_store = get_vector_store()

  vector_store.delete(
    where = {"doc_id":doc_id}
  )