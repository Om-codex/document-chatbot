import hashlib
from pathlib import Path

from ingestion.loaders import load_document
from ingestion.text_splitter import split_documents

def generate_document_id(file_path: str) -> str:
  
  file_hash = hashlib.sha256()
  with open(file_path, "rb") as file:

    for chunk in iter(lambda: file.read(8192), b""):
      file_hash.update(chunk)

  return file_hash.hexdigest()



def ingest_document(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):

  path = Path(file_path)
  
  if not path.is_file():
    raise FileNotFoundError(f"File not found: {file_path}")

  # generate the document id
  doc_id = generate_document_id(str(path))

  # load documents
  documents = load_document(str(path))

  # split documents into chunks
  chunks = split_documents(documents,chunk_size,chunk_overlap)

  # assign the metadata
  for index, chunk in enumerate(chunks):
    chunk.metadata.update({
      "doc_id" : doc_id,
      "filename" : path.name,
      "chunk_index" : index
    })

  return chunks