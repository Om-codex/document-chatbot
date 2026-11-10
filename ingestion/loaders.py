import logging
from pathlib import Path

from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
)

from ingestion.exceptions import DocumentLoadingError, UnsupportedDocumentFormatError

logger = logging.getLogger(__name__)


def load_document(file_path: str):
    """Load a supported document and return LangChain ``Document`` objects."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    extension = path.suffix.lower()

    if extension == ".pdf":
        loader = PyPDFLoader(str(path))
    elif extension == ".txt":
        loader = TextLoader(str(path), encoding="utf-8")
    elif extension == ".docx":
        loader = Docx2txtLoader(str(path))
    else:
        raise UnsupportedDocumentFormatError(f"Unsupported file format: {extension}")

    try:
        documents = loader.load()
    except Exception as exc:
        logger.exception("Document loader failed for extension %s", extension)
        raise DocumentLoadingError(
            "The document could not be read. It may be malformed or unsupported."
        ) from exc

    logger.debug(
        "Loaded document: extension=%s pages=%d characters=%d",
        extension,
        len(documents),
        sum(len(document.page_content or "") for document in documents),
    )

    return documents
