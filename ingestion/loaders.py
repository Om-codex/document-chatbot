from pathlib import Path
from langchain_community.document_loaders import (PyPDFLoader, TextLoader, Docx2txtLoader)

def load_document(file_path:str):
  path = Path(file_path)

  # raise error if file not exists
  if not path.exists():
    raise FileNotFoundError(f"File not found: {file_path}")

  extension = path.suffix.lower()

  # load pdf file
  if extension == ".pdf":
    loader = PyPDFLoader(str(path))
  # load txt file
  elif extension == ".txt":
    loader = TextLoader(
      str(path),
      encoding ="utf-8"
    )
  # load docx file
  elif extension == ".docx":
    loader = Docx2txtLoader(str(path))
  else:
    raise ValueError(
      f"Unsupported file format: {extenstion}"
    )

  documents = loader.load()

  return documents