"""Response utility functions."""

from fastapi import status
from fastapi.responses import JSONResponse


def error_response(message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    """Create standardized error response."""
    return JSONResponse(
        content={"ok": False, "error": message},
        status_code=status_code
    )