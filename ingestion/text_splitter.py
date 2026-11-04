from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_documents( documents, chunk_size: int = 1000, chunk_overlap: int = 200):
  
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