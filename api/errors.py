"""Helpers for consistent, non-leaky API error responses."""

from typing import Any

from fastapi import HTTPException


def api_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    """Return an ``HTTPException`` with a stable machine-readable detail object."""

    detail: dict[str, Any] = {
        "code": code,
        "message": message,
    }

    if details:
        detail["details"] = details

    return HTTPException(status_code=status_code, detail=detail, headers=headers)
