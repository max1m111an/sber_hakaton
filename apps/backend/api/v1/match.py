"""ML-матчинг товаров к типам работ (п. 3.1 ТЗ) и справочники для админки.

    POST  /api/v1/match                 — предсказание модели для произвольного товара
    GET   /api/v1/match/products        — товары с предсказанным типом работ и уверенностью модели
    PATCH /api/v1/match/products/{id}   — менеджер подтверждает / исправляет тип (метка для дообучения)
    POST  /api/v1/match/confirm         — массовое подтверждение
    POST  /api/v1/ml/train              — переобучить модель (в фоне)
    GET   /api/v1/ml/status             — состояние модели и обучения
    GET   /api/v1/stats                 — сводка по каталогу и метрики модели
    GET   /api/v1/work-types            — типы работ и число товаров
    GET   /api/v1/rules                 — нормативы расхода
    GET   /api/v1/health                — состояние сервиса, БД, импорта и ML
"""
import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.schemas.calculator import (
    ConfirmRequest,
    ConfirmResponse,
    MatchedProduct,
    MatchedProductList,
    MatchRequest,
    MatchResponse,
    MatchUpdate,
    RuleOut,
    StatsResponse,
    WorkTypeOut,
)
from database import get_db
from database.catalog_parser import parse_pack
from database.import_products import IMPORT_STATUS
from database.models import Category, MLModel, NormativeRule, Product
from database.work_types import ID_BY_CODE, OTHER_ID, WORK_TYPES, detect_moisture, suitable_rooms
from ml.matching import CONFIDENCE_THRESHOLD, OTHER, get_matcher, product_text
from ml.pipeline import ML_STATUS, start_training

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["matching"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]

# товар попадает в подбор калькулятора, если модель уверена или тип подтвердил менеджер
ACCEPTED = or_(Product.match_confidence >= CONFIDENCE_THRESHOLD, Product.match_source == "manager")

# ------------------------------------------------------------------ предсказание


@router.post("/match", response_model=MatchResponse, summary="Тип работ для товара (ML-модель)")
async def match_product(payload: MatchRequest):
    matcher = get_matcher()
    if not matcher.ready:
        raise HTTPException(status_code=503, detail="ML-модель ещё обучается — повторите через пару минут")
    chars_list = [{"name": str(c.get("name")), "value": c.get("value")} for c in payload.characteristics if c.get("name")]
    text = product_text(payload.name, payload.description, chars_list)
    top = (await asyncio.to_thread(matcher.predict_topk, [text], 3))[0]
    code, conf = top[0]
    chars = {c["name"]: str(c["value"]) for c in chars_list if c["value"] is not None}
    moisture = detect_moisture(payload.name, chars, code)
    pack = parse_pack(payload.name, None, chars, code)
    return {
        "work_type_id": ID_BY_CODE.get(code or "", OTHER_ID),
        "work_type": code,
        "work_type_name": WORK_TYPES.get(code or ""),
        "confidence": round(conf, 4),
        "accepted": bool(code) and conf >= CONFIDENCE_THRESHOLD,
        "threshold": CONFIDENCE_THRESHOLD,
        "source": "ml",
        "alternatives": [{"work_type": c, "work_type_name": WORK_TYPES.get(c or "", "Не относится к работам"),
                          "confidence": round(p, 4)} for c, p in top],
        "moisture_resistant": moisture,
        "suitable_rooms": suitable_rooms(code, moisture),
        "package_area": pack.area_m2,
        "package_weight_kg": pack.weight_kg,
        "package_volume_l": pack.volume_l,
        "package_length_m": pack.length_m,
    }


def _matched(p: Product) -> dict:
    accepted = bool(p.work_type) and (p.match_source == "manager" or (p.match_confidence or 0) >= CONFIDENCE_THRESHOLD)
    label = p.label_work_type
    return {
        "id": p.id, "name": p.name, "category_id": p.category_id,
        "work_type": p.work_type, "work_type_name": WORK_TYPES.get(p.work_type or ""),
        "confidence": p.match_confidence or 0, "source": p.match_source, "accepted": accepted,
        "label_work_type": label, "label_source": p.label_source,
        "agrees_with_label": None if not label else (label == (p.work_type or OTHER)),
        "moisture_resistant": p.moisture_resistant,
        "suitable_rooms": suitable_rooms(p.work_type, p.moisture_resistant), "price": p.result_price,
    }


@router.get("/match/products", response_model=MatchedProductList, summary="Предсказания модели по каталогу")
async def matched_products(
    session: SessionDep,
    work_type: str | None = None,
    min_confidence: Annotated[float, Query(ge=0, le=1)] = 0,
    max_confidence: Annotated[float, Query(ge=0, le=1)] = 1,
    q: str | None = None,
    disagree: Annotated[bool, Query(description="Только расхождения модели и метки обучения")] = False,
    include_other: Annotated[bool, Query(description="Включать товары, которые модель не отнесла к работам")] = False,
    sort: Annotated[str, Query(pattern="^(confidence_asc|confidence_desc)$")] = "confidence_asc",
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
):
    conditions = [Product.match_confidence >= min_confidence, Product.match_confidence <= max_confidence,
                  Product.match_source.is_not(None)]
    if not include_other:
        conditions.append(Product.work_type.is_not(None))
    if work_type:
        conditions.append(Product.work_type == work_type)
    if q:
        conditions.append(Product.name.ilike(f"%{q}%"))
    if disagree:
        conditions += [Product.label_work_type.is_not(None),
                       Product.label_work_type != func.coalesce(Product.work_type, OTHER)]
    total = int((await session.execute(select(func.count()).select_from(Product).where(*conditions))).scalar_one())
    order = Product.match_confidence if sort == "confidence_asc" else Product.match_confidence.desc()
    rows = (
        await session.execute(
            select(Product).where(*conditions).order_by(order, Product.id)
            .offset((page - 1) * per_page).limit(per_page)
        )
    ).scalars().all()
    return {"items": [_matched(p) for p in rows], "total": total, "page": page, "per_page": per_page,
            "threshold": CONFIDENCE_THRESHOLD}


@router.patch("/match/products/{product_id}", response_model=MatchedProduct, summary="Подтвердить / исправить тип работ")
async def update_match(product_id: int, payload: MatchUpdate, session: SessionDep):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    label = payload.work_type if payload.work_type is not None else (product.work_type or OTHER)
    if label != OTHER and label not in WORK_TYPES:
        raise HTTPException(status_code=422, detail="Неизвестный тип работ")
    # решение менеджера: сразу действует в подборе и попадает в обучающую выборку
    product.work_type = None if label == OTHER else label
    product.match_confidence = 1.0
    product.match_source = "manager"
    product.label_work_type = label
    product.label_source = "manager"
    await session.commit()
    return _matched(product)


@router.post("/match/confirm", response_model=ConfirmResponse, summary="Массовое подтверждение предсказаний")
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
        update(Product).where(*conditions).values(
            match_confidence=1.0, match_source="manager",
            label_work_type=Product.work_type, label_source="manager",
        )
    )
    await session.commit()
    return {"confirmed": result.rowcount or 0}


# ------------------------------------------------------------------ обучение и метрики


@router.post("/ml/train", summary="Переобучить ML-матчинг (в фоне)")
async def train(session: SessionDep):
    if not (await session.execute(select(Product.id).limit(1))).first():
        raise HTTPException(status_code=409, detail="Каталог не загружен")
    if not start_training():
        raise HTTPException(status_code=409, detail="Обучение уже идёт")
    return {"state": "started"}


async def _active_model(session: AsyncSession) -> MLModel | None:
    return (await session.execute(
        select(MLModel).where(MLModel.is_active.is_(True)).order_by(MLModel.id.desc()).limit(1)
    )).scalars().first()


def _model_info(model: MLModel | None) -> dict[str, Any]:
    matcher = get_matcher()
    info: dict[str, Any] = {"ready": matcher.ready, "encoder": matcher.encoder.name, "threshold": CONFIDENCE_THRESHOLD,
                            "status": dict(ML_STATUS)}
    if model is not None:
        m = model.metrics or {}
        info.update(
            trained_at=model.trained_at,
            train_size=model.train_size,
            label_sources=(matcher.meta or {}).get("label_sources"),
            holdout={k: m.get(k) for k in ("holdout_size", "accuracy", "macro_f1", "weighted_f1",
                                           "precision_at_threshold", "recall_at_threshold")},
            per_class=m.get("per_class", {}),
            predictions=model.prediction_stats or {},
        )
    return info


@router.get("/ml/status", summary="Состояние ML-модели")
async def ml_status(session: SessionDep):
    return _model_info(await _active_model(session))


@router.get("/stats", response_model=StatsResponse, summary="Сводка по каталогу и метрики модели")
async def stats(session: SessionDep):
    async def count(*where) -> int:
        stmt = select(func.count()).select_from(Product)
        if where:
            stmt = stmt.where(*where)
        return int((await session.execute(stmt)).scalar_one())

    by_source = dict((await session.execute(
        select(func.coalesce(Product.match_source, "none"), func.count()).group_by(Product.match_source)
    )).all())
    accepted = (Product.work_type.is_not(None), ACCEPTED)
    has_pack = or_(Product.package_area.is_not(None), Product.package_weight_kg.is_not(None),
                   Product.package_volume_l.is_not(None), Product.package_length_m.is_not(None))
    # распределение уверенности модели по предсказанным типам работ — живое, из БД
    bucket = case(
        (Product.match_confidence >= 0.95, "0.95–1"), (Product.match_confidence >= 0.9, "0.9–0.95"),
        (Product.match_confidence >= 0.8, "0.8–0.9"), (Product.match_confidence >= 0.6, "0.6–0.8"),
        else_="<0.6",
    )
    hist = dict((await session.execute(
        select(bucket, func.count()).where(Product.work_type.is_not(None), Product.match_source == "ml").group_by(bucket)
    )).all())
    mean_conf = (await session.execute(
        select(func.avg(Product.match_confidence)).where(Product.work_type.is_not(None), Product.match_source == "ml")
    )).scalar()
    ml = _model_info(await _active_model(session))
    ml["live"] = {
        "mean_confidence": round(float(mean_conf), 4) if mean_conf is not None else None,
        "confidence_buckets": [{"bucket": b, "count": int(hist.get(b, 0))}
                               for b in ("<0.6", "0.6–0.8", "0.8–0.9", "0.9–0.95", "0.95–1")],
    }
    return {
        "products": await count(),
        "categories": int((await session.execute(select(func.count()).select_from(Category))).scalar_one()),
        "classified": await count(*accepted),
        "predicted": await count(Product.work_type.is_not(None)),
        "with_package": await count(*accepted, has_pack),
        "by_source": {str(k): int(v) for k, v in by_source.items()},
        "rules": int((await session.execute(select(func.count()).select_from(NormativeRule))).scalar_one()),
        "import_state": IMPORT_STATUS.get("state"),
        "ml": ml,
    }


@router.get("/work-types", response_model=list[WorkTypeOut], summary="Типы работ")
async def work_types(session: SessionDep):
    rows = (await session.execute(
        select(Product.work_type, func.count(), func.count().filter(ACCEPTED))
        .where(Product.work_type.is_not(None)).group_by(Product.work_type)
    )).all()
    counts = {wt: (int(total), int(acc)) for wt, total, acc in rows}
    return [{"id": ID_BY_CODE[code], "code": code, "name": name, "products": counts.get(code, (0, 0))[1],
             "predicted": counts.get(code, (0, 0))[0]} for code, name in WORK_TYPES.items()]


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
    return {"status": "ok", "db": db, "products": products, "import": IMPORT_STATUS,
            "ml": {"ready": get_matcher().ready, **ML_STATUS}}
