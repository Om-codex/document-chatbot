"""Small, reusable helpers with no application-specific side effects."""

from pathlib import Path

from config.settings import settings


# Characters Windows forbids in file names.  Replacing them keeps the upload
# portable even when the server runs on a different OS than the client.
_WINDOWS_INVALID_CHARS = '<>:"|?*'

# Device names Windows reserves regardless of extension (case-insensitive).
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def sanitize_filename(filename: str) -> str:
    """Return a safe basename for an uploaded file.

    Rules:
    - strip directory components (both ``/`` and ``\\`` separators);
    - remove control characters and NUL bytes;
    - replace characters Windows forbids in file names;
    - reject empty names, ``.`` and ``..``;
    - prefix Windows reserved device names (``CON``, ``NUL``, ...);
    - trim trailing dots/spaces (Windows rejects them);
    - cap the length while preserving the extension.
    """

    if not filename:
        raise ValueError("Filename is required.")

    # Treat both separators as path separators, regardless of host OS.
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()

    # Drop control characters (including NUL) that can confuse filesystems.
    name = "".join(character for character in name if character >= " " and character != "\x7f")

    # Replace characters that Windows cannot store.
    name = "".join(
        "_" if character in _WINDOWS_INVALID_CHARS else character for character in name
    )

    name = name.strip().strip(". ")

    if name in {"", ".", ".."}:
        raise ValueError("Filename is not valid.")

    if Path(name).stem.upper() in _WINDOWS_RESERVED_NAMES:
        name = f"_{name}"

    max_length = max(16, settings.max_filename_length)
    if len(name) > max_length:
        suffix = Path(name).suffix
        stem = Path(name).stem[: max_length - len(suffix)]
        name = f"{stem}{suffix}"

    return name


def extension_of(filename: str) -> str:
    """Return the lower-case extension including the dot (``".pdf"``)."""

    return Path(filename).suffix.lower()
