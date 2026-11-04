from pathlib import Path
from langchain_community.document_loaders import (PyPDFLoader, TextLoader, Docx2txtLoader)

def load_document(file_path:str):
  path = Path(file_path)

  # raise error if file not exists
  if not path.exists():
    raise FileNotFoundError(f"File not found: {file_path}")

  extenstion = path.suffix.lower()

  # load pdf file
  if extension == ".pdf":
    loader = PyPDFLoader(str(path))