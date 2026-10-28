from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.services.meta_client import init_meta_client, close_meta_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_meta_client()
    yield
    await close_meta_client()


app = FastAPI(
    title="Vboard Backend",
    lifespan=lifespan,
)
