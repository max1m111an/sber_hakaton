from os import getenv

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DB_HOST = getenv("DB_HOST", "localhost")
DB_PORT = getenv("DB_PORT", "5432")
DB_NAME = getenv("DB_NAME", "mydb")
DB_USER = getenv("DB_USER", "postgres")
DB_PASS = getenv("DB_PASS", "")
DB_SCHEME = getenv("DB_SCHEME", "postgresql+asyncpg")

DATABASE_URL = (
    f"{DB_SCHEME}://{DB_USER}:{DB_PASS}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
engine = create_async_engine(DATABASE_URL, echo=True)

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

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
