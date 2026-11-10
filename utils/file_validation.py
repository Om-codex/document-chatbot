"""Practical file-signature validation.

We do not trust the browser's ``Content-Type`` header.  These checks catch the
most common mismatches cheaply and let the real parser reject the rest.
"""

import zipfile
from pathlib import Path


class FileSignatureError(ValueError):
    """Raised when a file does not look like the extension it claims to be."""


def _read_head(path: Path, size: int = 4096) -> bytes:
    with open(path, "rb") as file:
        return file.read(size)


def validate_file_signature(path: Path, extension: str) -> None:
    """Validate that ``path`` is plausibly the format given by ``extension``."""

    if extension == ".pdf":
        # PDF readers tolerate leading whitespace/BOM, so check the first KB.
        if b"%PDF-" not in _read_head(path, 1024):
            raise FileSignatureError("The uploaded file is not a valid PDF.")

    elif extension == ".docx":
        if not zipfile.is_zipfile(path):
            raise FileSignatureError("The uploaded file is not a valid DOCX file.")

        try:
            with zipfile.ZipFile(path) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise FileSignatureError(
                        "The uploaded DOCX file does not contain a Word document."
                    )
        except zipfile.BadZipFile as exc:
            raise FileSignatureError("The uploaded file is not a valid DOCX file.") from exc

    elif extension == ".txt":
        head = _read_head(path, 64 * 1024)

        if b"\x00" in head:
            raise FileSignatureError("The uploaded TXT file contains binary data.")

        try:
            head.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileSignatureError("The uploaded TXT file is not valid UTF-8 text.") from exc

    else:
        raise FileSignatureError("Unsupported file format.")
