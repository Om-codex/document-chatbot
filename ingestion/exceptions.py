"""Exceptions raised by the ingestion layer.

Keeping these separate from the HTTP layer means loaders and the pipeline can
stay framework-agnostic.  ``services.document_service`` translates them into
API-facing exceptions.
"""


class IngestionError(Exception):
    """Base class for document ingestion failures."""


class UnsupportedDocumentFormatError(IngestionError):
    """The file extension is not supported."""


class DocumentLoadingError(IngestionError):
    """The chosen parser could not read the file."""


class EmptyDocumentError(IngestionError):
    """The file contained no extractable text."""
