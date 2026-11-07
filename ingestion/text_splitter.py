from langchain_text_splitters import RecursiveCharacterTextSplitter
from config.settings import settings

def split_documents( documents, chunk_size: int | None = None, chunk_overlap: int | None = None):
  
  if chunk_size is None:
    chunk_size = settings.chunk_size

  if chunk_overlap is None:
    chunk_overlap = settings.chunk_overlap

  if chunk_size <= 0:
    raise ValueError("chunk_size must be positive")

  if chunk_overlap < 0:
    raise ValueError("chunk_overlap cannot be negative")

  if chunk_overlap >= chunk_size:
    raise ValueError("chunk_overlap must be smaller than chunk_size")

  text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = chunk_size,
    chunk_overlap = chunk_overlap,
    separators = ["\n\n", "\n", " ", ""],
    length_function = len
  )

  chunks = text_splitter.split_documents(documents)

  return chunks