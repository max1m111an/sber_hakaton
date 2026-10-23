"""Каталожное API в формате раздела 1 ТЗ:

    GET /api/catalog/categories/tree
    GET /api/catalog/categories
    GET /api/catalog/products
    GET /api/catalog/products/{id}
    GET /api/regions

Данные — из выгрузки products_final.json (см. database/import_products.py).
"""
import math
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.schemas.catalog import (
    CategoryListResponse,
    CategoryTreeResponse,
    ProductCardResponse,
    ProductListResponse,
    RegionListResponse,
)
from apps.backend.services import catalog as svc
from database import get_db
from database.models import Category, Product, Region

router = APIRouter(prefix="/api", tags=["catalog"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]

PROPERTIES_LIMIT = 5000  # фильтры считаются, если в выборке не больше стольких товаров
SORTS = {
    "id": (Product.id,),
    "price_asc": (Product.result_price, Product.id),
    "price_desc": (Product.result_price.desc(), Product.id),
    "name": (Product.name, Product.id),
}


async def _all_categories(session: AsyncSession) -> list[Category]:
    return list((await session.execute(select(Category))).scalars().all())


@router.get("/catalog/categories/tree", response_model=CategoryTreeResponse, summary="Дерево категорий")
async def categories_tree(
    session: SessionDep,
    category_id: Annotated[int | None, Query(description="От какой категории строить дерево")] = None,
    depth_level: Annotated[int, Query(ge=1, le=50, description="Глубина дерева")] = 20,
    locale: str = "ru",
):
    categories = await _all_categories(session)
    if category_id is not None and not any(c.id == category_id for c in categories):
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return {"data": svc.build_tree(categories, category_id, depth_level)}


@router.get("/catalog/categories", response_model=CategoryListResponse, summary="Сведения о категориях")
async def categories_list(
    session: SessionDep,
    parent_id: Annotated[int | None, Query(description="Родительская категория; без параметра — корневые")] = None,
    depth_level: Annotated[int | None, Query(ge=1, le=50)] = None,
    q: Annotated[str | None, Query(description="Поиск по названию категории")] = None,
    work_type: Annotated[str | None, Query(description="Тип работ RepairCalc")] = None,
):
    categories = await _all_categories(session)
    by_id, children = svc.children_index(categories)
    totals = svc.totals_with_children(by_id, children)
    if parent_id is not None and parent_id not in by_id:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    if depth_level is not None and parent_id is None:
        selected = [c for c in categories if c.depth_level == depth_level]
    elif depth_level is not None and parent_id is not None:
        base = by_id[parent_id].depth_level
        selected = [by_id[i] for i in svc.descendants(parent_id, children)[1:]
                    if by_id[i].depth_level <= base + depth_level]
    else:
        selected = children.get(parent_id, [])
    if q:
        selected = [c for c in selected if q.lower() in c.name.lower()]
    if work_type:
        selected = [c for c in selected if c.work_type == work_type]
    selected = sorted(selected, key=lambda c: (c.depth_level, c.name))
    return {"data": [svc.category_info(c, totals) for c in selected]}


@router.get("/catalog/products", response_model=ProductListResponse, summary="Список товаров")
async def products_list(
    session: SessionDep,
    category_id: int | None = None,
    include_subsections: Annotated[int, Query(ge=0, le=1, description="1 — включая подкатегории")] = 0,
    include_categories_tree: Annotated[int, Query(ge=0, le=1)] = 0,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    page: Annotated[int, Query(ge=1)] = 1,
    locale: str = "ru",
    q: Annotated[str | None, Query(description="Поиск по названию")] = None,
    brand_id: int | None = None,
    price_min: Annotated[float | None, Query(ge=0)] = None,
    price_max: Annotated[float | None, Query(ge=0)] = None,
    work_type: Annotated[str | None, Query(description="Тип работ RepairCalc, напр. floor_tile")] = None,
    moisture_resistant: bool | None = None,
    sort: Literal["id", "price_asc", "price_desc", "name"] = "id",
):
    categories = await _all_categories(session)
    by_id, children = svc.children_index(categories)

    conditions = [Product.status.is_(True)]
    category = None
    if category_id is not None:
        category = by_id.get(category_id)
        if category is None:
            raise HTTPException(status_code=404, detail="Категория не найдена")
        ids = svc.descendants(category_id, children) if include_subsections else [category_id]
        conditions.append(Product.category_id.in_(ids))
    if q:
        for word in q.split()[:6]:
            conditions.append(Product.name.ilike(f"%{word}%"))
    if brand_id is not None:
        conditions.append(Product.brand["id"].as_integer() == brand_id)
    if price_min is not None:
        conditions.append(Product.result_price >= price_min)
    if price_max is not None:
        conditions.append(Product.result_price <= price_max)
    if work_type:
        conditions.append(Product.work_type == work_type)
    if moisture_resistant is not None:
        conditions.append(Product.moisture_resistant.is_(moisture_resistant))

    total = int((await session.execute(select(func.count()).select_from(Product).where(*conditions))).scalar_one())
    rows = (
        await session.execute(
            select(Product).where(*conditions).order_by(*SORTS[sort])
            .offset((page - 1) * per_page).limit(per_page)
        )
    ).scalars().all()

    properties = []
    if 0 < total <= PROPERTIES_LIMIT:
        chars = (await session.execute(select(Product.characteristics).where(*conditions))).scalars().all()
        properties = svc.filter_properties(chars)

    return {
        "items": [svc.product_item(p, by_id.get(p.category_id), bool(include_categories_tree)) for p in rows],
        "properties": properties,
        "generated_url": f"/catalog/{category.url_key}/" if category is not None else "/catalog/",
        "meta": {
            "total": total,
            "per_page": per_page,
            "current_page": page,
            "last_page": max(1, math.ceil(total / per_page)),
        },
    }


@router.get("/catalog/products/{product_id}", response_model=ProductCardResponse, summary="Полная карточка товара")
async def product_card(product_id: int, session: SessionDep, locale: str = "ru"):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    category = await session.get(Category, product.category_id) if product.category_id else None
    return {"data": svc.product_card(product, category)}


@router.get("/regions", response_model=RegionListResponse, summary="Регионы")
async def regions(session: SessionDep):
    rows = (await session.execute(select(Region).order_by(Region.priority, Region.id))).scalars().all()
    return {"data": [
        {"id": r.id, "code": r.code, "name": r.name, "oracle_cod_city": r.oracle_cod_city, "priority": r.priority,
         "status": r.status, "is_default": r.is_default, "warehouses_count": r.warehouses_count}
        for r in rows
    ]}
