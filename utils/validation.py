"""Shared validation helpers.

Document IDs are SHA-256 hex digests (64 characters).  Validating the shape
before using an ID in a Chroma filter or filesystem scan prevents malformed
input from reaching storage code and makes error messages predictable.
"""

import re


DOC_ID_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class InvalidDocumentIdError(ValueError):
    """Raised when a document ID is not a 64-character SHA-256 hex digest."""


def is_valid_doc_id(doc_id: str) -> bool:
    return isinstance(doc_id, str) and bool(DOC_ID_PATTERN.fullmatch(doc_id))


def validate_doc_id(doc_id: str) -> str:
    """Return ``doc_id`` unchanged or raise :class:`InvalidDocumentIdError`."""

    if not is_valid_doc_id(doc_id):
        raise InvalidDocumentIdError(
            "Document ID must be a 64-character lowercase SHA-256 hex string."
        )

    return doc_id
