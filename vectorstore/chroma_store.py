from pathlib import Path
from langchain_chroma import langchain_chroma
from embeddings.embedding_model import get_embedding_model

BASE_DIR = Path(__file__).resolve().parent.parent

CHROMA_PATH = BASE_DIR / "data" / "chroma_db"

COLLECTION_NAME = "document_collection"

def get_vector_store():
  embedding_model = get_embedding_model()

  vector_store = Chroma(
    collection_name = COLLECTION_NAME,
    embedding_function = embedding_model,
    persist_directory = str(CHROMA_PATH)
  )

  return vector_store

def add_documents(chunks):
  vector_store = get_vector_store()

  ids = vector_store.add_documents(chunks)

  return ids

def delete_documents(doc_id : str):
  vector_store = get_vector_store()

  vector_store.delete(
    where = {"doc_id":doc_id}
  )