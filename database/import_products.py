"""Импорт выгрузки каталога (products_final.json) в PostgreSQL.

Запуск:
    python -m database.import_products [путь к json] [--reset] [--reseed-rules]

    --reset         очистить товары и категории перед загрузкой
    --reseed-rules  перезаписать нормативы расхода значениями из seed_rules.py

Без --reset импорт идемпотентный: товары и категории обновляются по id.
Путь по умолчанию — переменная PRODUCTS_FILE или ./products_final.json.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.catalog_parser import CategoryAcc, category_rows, collect_category, iter_products, normalize_product
from database.db_engine import engine, init_db
from database.models import Category, NormativeRule, Product
from database.seed_rules import rule_rows

logger = logging.getLogger(__name__)

DEFAULT_FILE = os.getenv("PRODUCTS_FILE", "products_final.json")

# Состояние импорта — его отдаёт /api/v1/health
IMPORT_STATUS: dict[str, Any] = {"state": "idle"}


def _upsert(model, rows: list[dict], key: str = "id"):
    stmt = pg_insert(model)
    cols = {c: stmt.excluded[c] for c in rows[0] if c != key}
    return stmt.on_conflict_do_update(index_elements=[key], set_=cols)


async def seed_rules(overwrite: bool = False) -> int:
    """Записывает нормативы расхода. По умолчанию не трогает уже изменённые в БД правила."""
    rows = rule_rows()
    async with engine.begin() as conn:
        stmt = pg_insert(NormativeRule)
        if overwrite:
            stmt = stmt.on_conflict_do_update(
                index_elements=["code"], set_={c: stmt.excluded[c] for c in rows[0] if c != "code"}
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=["code"])
        await conn.execute(stmt, rows)
    return len(rows)


async def product_count() -> int:
    async with engine.connect() as conn:
        return int((await conn.execute(select(func.count()).select_from(Product))).scalar_one())


async def import_catalog(path: str | Path = DEFAULT_FILE, *, reset: bool = False, batch_size: int = 1000) -> dict:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Файл выгрузки не найден: {path}")

    started = time.monotonic()
    IMPORT_STATUS.clear()
    IMPORT_STATUS.update(state="running", file=str(path), processed=0, started_at=time.time())
    try:
        await init_db()
        if reset:
            async with engine.begin() as conn:
                await conn.execute(text("TRUNCATE TABLE product, category CASCADE"))

        acc: dict[int, CategoryAcc] = {}
        known_categories: set[int] = set()
        batch: list[dict] = []
        stats: dict[str, Any] = {"products": 0, "classified": 0, "with_pack": 0}

        async def flush() -> None:
            new_cats = [c for cid, c in acc.items() if cid not in known_categories]
            async with engine.begin() as conn:
                if new_cats:
                    cat_stmt = pg_insert(Category).on_conflict_do_nothing()
                    await conn.execute(cat_stmt, [
                        {"id": c.id, "parent_id": None, "name": c.name, "url_key": f"{c.url_key}",
                         "description": None, "status": True, "depth_level": 1, "product_count": 0,
                         "work_type": None}
                        for c in new_cats
                    ])
                    known_categories.update(c.id for c in new_cats)
                await conn.execute(_upsert(Product, batch), batch)
            batch.clear()

        for raw in iter_products(path):
            row = normalize_product(raw)
            collect_category(acc, raw, row)
            batch.append(row)
            stats["products"] += 1
            stats["classified"] += bool(row["work_type"])
            stats["with_pack"] += bool(row["package_area"] or row["package_weight_kg"]
                                       or row["package_volume_l"] or row["package_length_m"])
            if len(batch) >= batch_size:
                await flush()
                IMPORT_STATUS["processed"] = stats["products"]
                if stats["products"] % 10000 == 0:
                    logger.info("Импортировано товаров: %d", stats["products"])
        if batch:
            await flush()

        # итоговые счётчики и тип работ категорий
        cats = category_rows(acc)
        if cats:
            async with engine.begin() as conn:
                await conn.execute(_upsert(Category, cats), cats)
        stats["categories"] = len(cats)
        stats["rules"] = await seed_rules()
        stats["seconds"] = round(time.monotonic() - started, 1)
        IMPORT_STATUS.update(state="done", processed=stats["products"], result=stats)
        logger.info("Импорт завершён: %s", stats)
        return stats
    except Exception as exc:
        IMPORT_STATUS.update(state="error", error=f"{exc.__class__.__name__}: {exc}")
        raise


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Импорт products_final.json в PostgreSQL")
    parser.add_argument("path", nargs="?", default=DEFAULT_FILE)
    parser.add_argument("--reset", action="store_true", help="очистить товары и категории перед загрузкой")
    parser.add_argument("--reseed-rules", action="store_true", help="перезаписать нормативы из seed_rules.py")
    args = parser.parse_args()

    async def run() -> None:
        stats = await import_catalog(args.path, reset=args.reset)
        if args.reseed_rules:
            await seed_rules(overwrite=True)
        print(stats)
        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    main()
