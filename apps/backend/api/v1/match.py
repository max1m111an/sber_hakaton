"""Матчинг товаров к типам работ (п. 3.1 ТЗ) и справочники для админки.

    POST /api/v1/match            — классифицировать произвольный товар (новая позиция каталога)
    GET  /api/v1/match/products   — товары каталога с предложенным типом работ и уверенностью
    PATCH /api/v1/match/products/{id} — менеджер подтверждает или меняет тип работ
    POST /api/v1/match/confirm    — массовое подтверждение
    GET  /api/v1/stats            — сводка по каталогу и разметке
    GET  /api/v1/work-types       — типы работ и число товаров
    GET  /api/v1/rules            — нормативы расхода
    GET  /api/v1/health           — состояние сервиса, БД и импорта
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.schemas.calculator import (
    ConfirmRequest,
    ConfirmResponse,
    MatchedProduct,
    MatchedProductList,
    MatchUpdate,
    StatsResponse,
    MatchRequest,
    MatchResponse,
    RuleOut,
    WorkTypeOut,
)
from database import get_db
from database.catalog_parser import parse_pack
from database.classifier import WORK_TYPES, classify, detect_moisture, suitable_rooms
from database.import_products import IMPORT_STATUS
from database.models import Category, NormativeRule, Product

router = APIRouter(prefix="/api/v1", tags=["matching"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/match", response_model=MatchResponse, summary="Тип работ и помещения для товара")
async def match_product(payload: MatchRequest):
    chars = {str(c.get("name")): str(c.get("value")) for c in payload.characteristics if c.get("name")}
    cls = classify(payload.category_name, payload.name, chars)
    moisture = detect_moisture(payload.name, chars, cls.work_type)
    pack = parse_pack(payload.name, None, chars, cls.work_type)
    return {
        "work_type": cls.work_type,
        "work_type_name": WORK_TYPES.get(cls.work_type or ""),
        "confidence": cls.confidence,
        "source": cls.source,
        "moisture_resistant": moisture,
        "suitable_rooms": suitable_rooms(cls.work_type, moisture),
        "package_area": pack.area_m2,
        "package_weight_kg": pack.weight_kg,
        "package_volume_l": pack.volume_l,
        "package_length_m": pack.length_m,
    }


@router.get("/match/products", response_model=MatchedProductList, summary="Разметка товаров каталога")
async def matched_products(
    session: SessionDep,
    work_type: str | None = None,
    min_confidence: Annotated[float, Query(ge=0, le=1)] = 0.01,
    max_confidence: Annotated[float, Query(ge=0, le=1)] = 1,
    q: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
):
    conditions = [Product.match_confidence >= min_confidence, Product.match_confidence <= max_confidence]
    if work_type:
        conditions.append(Product.work_type == work_type)
    if q:
        conditions.append(Product.name.ilike(f"%{q}%"))
    total = int((await session.execute(select(func.count()).select_from(Product).where(*conditions))).scalar_one())
    rows = (
        await session.execute(
            select(Product).where(*conditions)
            .order_by(Product.match_confidence, Product.id)
            .offset((page - 1) * per_page).limit(per_page)
        )
    ).scalars().all()
    return {"items": [_matched(p) for p in rows], "total": total, "page": page, "per_page": per_page}


def _matched(p: Product) -> dict:
    return {"id": p.id, "name": p.name, "category_id": p.category_id, "work_type": p.work_type,
            "work_type_name": WORK_TYPES.get(p.work_type or ""), "confidence": p.match_confidence,
            "source": p.match_source, "moisture_resistant": p.moisture_resistant,
            "suitable_rooms": suitable_rooms(p.work_type, p.moisture_resistant), "price": p.result_price}


@router.patch("/match/products/{product_id}", response_model=MatchedProduct, summary="Подтвердить / изменить тип работ")
async def update_match(product_id: int, payload: MatchUpdate, session: SessionDep):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if payload.work_type is not None:
        if payload.work_type not in WORK_TYPES:
            raise HTTPException(status_code=422, detail="Неизвестный тип работ")
        product.work_type = payload.work_type
    product.match_confidence = 1.0
    product.match_source = "manager"   # подтверждения менеджера — разметка для обучения модели
    await session.commit()
    return _matched(product)


@router.post("/match/confirm", response_model=ConfirmResponse, summary="Массовое подтверждение разметки")
async def confirm_matches(payload: ConfirmRequest, session: SessionDep):
    conditions = [Product.work_type.is_not(None), Product.match_source.is_distinct_from("manager")]
    if payload.ids:
        conditions.append(Product.id.in_(payload.ids))
    if payload.min_confidence is not None:
        conditions.append(Product.match_confidence >= payload.min_confidence)
    if payload.work_type:
        conditions.append(Product.work_type == payload.work_type)
    if payload.q:
        conditions.append(Product.name.ilike(f"%{payload.q}%"))
    result = await session.execute(
        update(Product).where(*conditions).values(match_confidence=1.0, match_source="manager")
    )
    await session.commit()
    return {"confirmed": result.rowcount or 0}


@router.get("/stats", response_model=StatsResponse, summary="Сводка по каталогу и разметке")
async def stats(session: SessionDep):
    async def count(*where) -> int:
        stmt = select(func.count()).select_from(Product)
        if where:
            stmt = stmt.where(*where)
        return int((await session.execute(stmt)).scalar_one())

    by_source = dict((await session.execute(
        select(func.coalesce(Product.match_source, "none"), func.count()).group_by(Product.match_source)
    )).all())
    return {
        "products": await count(),
        "categories": int((await session.execute(select(func.count()).select_from(Category))).scalar_one()),
        "classified": await count(Product.work_type.is_not(None)),
        "with_package": await count(Product.work_type.is_not(None), or_(Product.package_area.is_not(None), Product.package_weight_kg.is_not(None),
                                        Product.package_volume_l.is_not(None), Product.package_length_m.is_not(None))),
        "by_source": {str(k): int(v) for k, v in by_source.items()},
        "rules": int((await session.execute(select(func.count()).select_from(NormativeRule))).scalar_one()),
        "import_state": IMPORT_STATUS.get("state"),
    }


@router.get("/work-types", response_model=list[WorkTypeOut], summary="Типы работ")
async def work_types(session: SessionDep):
    counts = dict(
        (await session.execute(
            select(Product.work_type, func.count()).where(Product.work_type.is_not(None)).group_by(Product.work_type)
        )).all()
    )
    return [{"code": code, "name": name, "products": int(counts.get(code, 0))} for code, name in WORK_TYPES.items()]


@router.get("/rules", response_model=list[RuleOut], summary="Нормативы расхода")
async def rules(session: SessionDep):
    return (await session.execute(select(NormativeRule).order_by(NormativeRule.priority))).scalars().all()


@router.get("/health", summary="Состояние сервиса")
async def health(session: SessionDep):
    try:
        products = int((await session.execute(select(func.count()).select_from(Product))).scalar_one())
        db = "ok"
    except Exception as exc:  # noqa: BLE001
        products, db = None, f"error: {exc.__class__.__name__}"
    return {"status": "ok", "db": db, "products": products, "import": IMPORT_STATUS}
