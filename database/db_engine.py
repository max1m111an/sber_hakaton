import asyncio
import logging
from os import getenv

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

DB_HOST = getenv("DB_HOST", "localhost")
DB_PORT = getenv("DB_PORT", "5432")
DB_NAME = getenv("DB_NAME", "mydb")
DB_USER = getenv("DB_USER", "postgres")
DB_PASS = getenv("DB_PASS", "")
DB_SCHEME = getenv("DB_SCHEME", "postgresql+asyncpg")
DB_ECHO = getenv("DB_ECHO", "false").lower() in ("1", "true", "yes")

DATABASE_URL = (
    f"{DB_SCHEME}://{DB_USER}:{DB_PASS}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
engine = create_async_engine(DATABASE_URL, echo=DB_ECHO, pool_pre_ping=True)

class Base(DeclarativeBase):
    pass

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def _outdated_tables(sync_conn) -> list[str]:
    """Таблицы, чьи колонки в БД не совпадают с моделями (схема поменялась)."""
    insp = inspect(sync_conn)
    outdated = []
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        if existing != set(table.columns.keys()):
            outdated.append(table.name)
    return outdated


async def init_db(retries: int = 30, delay: float = 2.0) -> None:
    """Создаёт таблицы. Ждёт, пока Postgres поднимется (в docker он стартует дольше API).

    Миграций в проекте нет: если модели изменились, таблицы пересоздаются
    (данные каталога затем заново загружаются импортом).
    """
    from database import models  # noqa: F401  — регистрирует модели в Base.metadata

    for attempt in range(1, retries + 1):
        try:
            async with engine.begin() as conn:
                outdated = await conn.run_sync(_outdated_tables)
                if outdated:
                    logger.warning("Схема БД устарела (%s) — таблицы будут пересозданы", ", ".join(outdated))
                    await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            return
        except Exception as exc:  # noqa: BLE001 — ошибки подключения у драйверов разные
            if attempt == retries:
                raise
            logger.info("БД недоступна (%s), попытка %d/%d", exc.__class__.__name__, attempt, retries)
            await asyncio.sleep(delay)
