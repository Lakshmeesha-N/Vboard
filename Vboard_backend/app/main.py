from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.process import router as process_router
from app.core.exceptions import (
    InvalidAudioError,
    InvalidRequestError,
    MetaApiError,
    RateLimitedError,
)
from app.services.meta_client import close_meta_client, init_meta_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_meta_client()
    yield
    await close_meta_client()


app = FastAPI(
    title="Vboard Backend",
    lifespan=lifespan,
)


@app.exception_handler(InvalidRequestError)
async def invalid_request_handler(request: Request, exc: InvalidRequestError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc)},
    )


@app.exception_handler(InvalidAudioError)
async def invalid_audio_handler(request: Request, exc: InvalidAudioError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc)},
    )


@app.exception_handler(RateLimitedError)
async def rate_limited_handler(request: Request, exc: RateLimitedError):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": str(exc)},
    )


@app.exception_handler(MetaApiError)
async def meta_api_error_handler(request: Request, exc: MetaApiError):
    # Never leak internal Meta API errors or raw server traces
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": "Meta speech-to-text service error"},
    )


app.include_router(process_router, prefix="/v1")
