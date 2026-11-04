from ingestion.loaders import load_document
from ingestion.text_splitter import split_documents

def ingest_document(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):
  # load documents
  documents = load_document(file_path)

  # split documents into chunks
  chunks = split_documents(documents,chunk_size,chunk_overlap)

  return chunks