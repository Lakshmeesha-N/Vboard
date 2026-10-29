from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.v1.process import router as process_router
from app.services.llm_client import close_llm_client, init_llm_client
from app.services.meta_client import close_meta_client, init_meta_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_meta_client()
    await init_llm_client()
    yield
    await close_llm_client()
    await close_meta_client()


app = FastAPI(
    title="Vboard Backend",
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(process_router, prefix="/v1")
