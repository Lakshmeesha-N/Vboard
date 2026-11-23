from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.exceptions import AppError, MetaApiError


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized application exception handlers on FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        # Exact failure reason for the server log. AppError messages are
        # fixed templates with numerics only (sizes, rates, durations) —
        # never audio, transcripts, or user text — so str(exc) is safe.
        logger.warning(
            "Request failed: path={} status={} error={}: {}",
            request.url.path,
            exc.status_code,
            type(exc).__name__,
            str(exc),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc)},
        )

    @app.exception_handler(MetaApiError)
    async def meta_api_error_handler(
        request: Request, exc: MetaApiError
    ) -> JSONResponse:
        # str(exc) holds the exact upstream/network reason (e.g. connect
        # error, timeout); the client still gets a generic message.
        logger.error(
            "Meta STT failed: path={} error={}: {}",
            request.url.path,
            type(exc).__name__,
            str(exc),
        )
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
        logger.error(
            "Unhandled error: {} path={}",
            type(exc).__name__,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
