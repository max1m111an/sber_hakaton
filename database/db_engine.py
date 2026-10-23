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


def _sync_schema(sync_conn) -> list[str]:
    """Приводит существующие таблицы к моделям.

    Новые колонки добавляются через ALTER TABLE (данные сохраняются). Если колонки
    удалены или переименованы, возвращает такие таблицы — их придётся пересоздать.
    """
    insp = inspect(sync_conn)
    outdated = []
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        if existing - set(table.columns.keys()):
            outdated.append(table.name)
            continue
        for col in table.columns:
            if col.name in existing:
                continue
            if not col.nullable and col.default is None and col.server_default is None:
                outdated.append(table.name)
                break
            ddl_type = col.type.compile(dialect=sync_conn.dialect)
            default = ""
            if col.default is not None and getattr(col.default, "is_scalar", False):
                default = f" DEFAULT {col.default.arg!r}"
            sync_conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl_type}{default}')
            logger.info("Схема БД: добавлена колонка %s.%s", table.name, col.name)
    return outdated


async def init_db(retries: int = 30, delay: float = 2.0) -> None:
    """Создаёт таблицы. Ждёт, пока Postgres поднимется (в docker он стартует дольше API).

    Миграций в проекте нет: новые колонки добавляются автоматически, а если
    колонки удалены — таблицы пересоздаются (каталог затем загружается импортом).
    """
    from database import models  # noqa: F401  — регистрирует модели в Base.metadata

    for attempt in range(1, retries + 1):
        try:
            async with engine.begin() as conn:
                outdated = await conn.run_sync(_sync_schema)
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
