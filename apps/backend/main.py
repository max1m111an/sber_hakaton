import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.backend.api.v1 import api_router
from database import init_db
from database.import_products import DEFAULT_FILE, import_catalog, product_count, seed_rules, seed_work_types
from ml.matching import get_matcher
from ml.pipeline import needs_training, start_training

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# При пустой БД каталог загружается из PRODUCTS_FILE в фоне при старте
AUTO_IMPORT = os.getenv("AUTO_IMPORT", "true").lower() in ("1", "true", "yes")
# Обучать ML-матчинг при старте, если модели нет или у товаров нет предсказаний
ML_AUTO_TRAIN = os.getenv("ML_AUTO_TRAIN", "true").lower() in ("1", "true", "yes")


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
        await seed_work_types()
        if AUTO_IMPORT and await product_count() == 0:
            if Path(DEFAULT_FILE).is_file():
                logger.info("БД пуста — запускаю импорт каталога из %s", DEFAULT_FILE)
                task = asyncio.create_task(_background_import(DEFAULT_FILE))
            else:
                logger.warning("БД пуста, а файл выгрузки %s не найден — импорт пропущен", DEFAULT_FILE)
        if ML_AUTO_TRAIN:
            if task is not None:
                start_training(after=task)          # каталог только загружается — обучаемся после импорта
            else:
                await asyncio.to_thread(get_matcher)  # подгружаем обученный классификатор с диска
                reason = await needs_training()
                if reason:
                    logger.info("ML-матчинг: %s — запускаю обучение в фоне", reason)
                    start_training()
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
