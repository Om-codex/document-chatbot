from pathlib import Path
from langchain_chroma import Chroma
from embeddings.embedding_model import get_embedding_model
from config.settings import settings

BASE_DIR = Path(__file__).resolve().parent.parent

CHROMA_PATH = settings.chroma_persist_directory

COLLECTION_NAME = settings.chroma_collection_name

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

def get_all_documents():

  vector_store = get_vector_store()

  # get the metadata for each chunks "metadatas"
  result = vector_store.get(
    include = ["metadatas"]
  )

  # store chunks with same doc_id here
  documents = {}

  # iterate over each chunk metadata
  for metadata in result["metadatas"]:

    # get the doc_id of that chunk
    doc_id = metadata.get("doc_id")

    # if no doc_id then skip the iteration & move to next chunk iteration
    if not doc_id:
      continue

    # if a doc_id doesn't exists in documents{} then create a first time entry of that document
    if doc_id not in documents:

      documents[doc_id] = {
        "doc_id" : doc_id,
        "filename" : metadata.get("filename"),
        "total_pages" : metadata.get("total_pages"),
        "total_chunks" : 0
      }

    # increment the total_chunk count
    documents[doc_id]["total_chunks"] += 1
  
  return list(documents.values())
  

def delete_documents(doc_id : str):
  vector_store = get_vector_store()

  vector_store.delete(
    where = {"doc_id":doc_id}
  )