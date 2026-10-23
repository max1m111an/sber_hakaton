import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.backend.api.v1 import api_router
from database import init_db
from database.import_products import DEFAULT_FILE, import_catalog, product_count, seed_rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# При пустой БД каталог загружается из PRODUCTS_FILE в фоне при старте
AUTO_IMPORT = os.getenv("AUTO_IMPORT", "true").lower() in ("1", "true", "yes")


async def _background_import(path: str) -> None:
    try:
        await import_catalog(path)
    except Exception:  # noqa: BLE001
        logger.exception("Автоимпорт каталога не удался")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task: asyncio.Task | None = None
    try:
        await init_db()
        await seed_rules()
        if AUTO_IMPORT and await product_count() == 0:
            if Path(DEFAULT_FILE).is_file():
                logger.info("БД пуста — запускаю импорт каталога из %s", DEFAULT_FILE)
                task = asyncio.create_task(_background_import(DEFAULT_FILE))
            else:
                logger.warning("БД пуста, а файл выгрузки %s не найден — импорт пропущен", DEFAULT_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Database unavailable, starting without DB: %s", exc)
    yield
    if task and not task.done():
        task.cancel()


app = FastAPI(
    title="RepairCalc API",
    description="Микросервис умных калькуляторов ремонта на данных каталога maxidom.ru",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/hello")
async def hello():
    return {
        "status": 200,
        "message": "Hello, World!",
    }
