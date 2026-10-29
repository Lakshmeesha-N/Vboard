from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.exceptions import AppError, MetaApiError


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized application exception handlers on FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc)},
        )

    @app.exception_handler(MetaApiError)
    async def meta_api_error_handler(
        request: Request, exc: MetaApiError
    ) -> JSONResponse:
        # Never leak Meta API internals or raw server traces
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Meta speech-to-text service error"},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Log ONLY the exception class name to prevent leakage of text or audio
        logger.error("Unhandled error: {}", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
