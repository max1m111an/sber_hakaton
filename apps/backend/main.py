import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apps.backend.api.v1 import api_router
from database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception as exc:
        logger.warning("Database unavailable, starting without DB: %s", exc)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)


@app.get("/hello")
async def hello():
    return {
        "status": 200,
        "message": "Hello, World!",
    }
