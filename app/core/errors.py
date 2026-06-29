"""
app/core/errors.py — Custom application exceptions and FastAPI error handlers.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

# ── Domain exceptions ─────────────────────────────────────────────────────────


class AppError(Exception):
    """Base class for all application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str = "An unexpected error occurred.") -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"

    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found.")


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"

    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(message)


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"

    def __init__(self, message: str = "Access denied.") -> None:
        super().__init__(message)


class IngestionError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "ingestion_error"


class RetrievalError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "retrieval_error"


class LLMUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "llm_unavailable"

    def __init__(self, model: str = "") -> None:
        msg = f"LLM model '{model}' is unavailable." if model else "LLM is unavailable."
        super().__init__(msg)


class ValidationError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "validation_error"


# ── FastAPI error handler registration ────────────────────────────────────────


def register_error_handlers(app: FastAPI) -> None:
    """Attach exception handlers to a FastAPI application."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred. Please check the server logs.",
            },
        )
