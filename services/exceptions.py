"""Application-level exceptions used by the service layer and API routes."""


class DocumentServiceError(Exception):
    """Base class for document-related failures."""


class UnsupportedDocumentError(DocumentServiceError):
    """The upload extension is not supported."""


class DocumentTooLargeError(DocumentServiceError):
    """The upload exceeds the configured size limit."""


class EmptyDocumentError(DocumentServiceError):
    """The upload or extracted text is empty."""


class MalformedDocumentError(DocumentServiceError):
    """The file cannot be parsed as the claimed format."""


class DocumentNotFoundError(DocumentServiceError):
    """No indexed document matches the requested ID."""


class InvalidDocumentIdError(DocumentServiceError):
    """The supplied document ID is not a SHA-256 hex digest."""


class DocumentStorageError(DocumentServiceError):
    """Embedding or vector storage failed."""


class DocumentDeletionError(DocumentServiceError):
    """Vector deletion failed."""


class ChatServiceError(Exception):
    """Base class for chat failures."""


class ChatValidationError(ChatServiceError):
    """The chat request is invalid before retrieval starts."""


class NoDocumentsError(ChatServiceError):
    """No documents are indexed yet."""


class InvalidDocumentSelectionError(ChatServiceError):
    """One or more selected document IDs do not exist."""


class RetrievalError(ChatServiceError):
    """Embedding, Chroma retrieval, or context assembly failed."""
