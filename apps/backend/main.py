import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
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


@app.get("/hello")
async def hello():
    return {
        "status": 200,
        "message": "Hello, World!",
    }
