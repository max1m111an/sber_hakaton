import math
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.backend.schemas.calculator import (
    EstimateItem,
    GeneralCalcRequest,
    GeneralCalcResponse,
    ProductCalcRequest,
    ProductCalcResponse,
    RecommendedProduct,
    RoomCalcRequest,
    RoomCalcResponse,
    RuleMatch,
)
from database import get_db
from database.models import Category, NormativeRule, Product

router = APIRouter(tags=["calculator"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]

ML_NOTE = "Оценка приблизительная: расход по consumption_formula будет считать ML-модуль (заглушка)."
LIMIT_NOTE = "Показаны не все товары категории (лимит выдачи)."


def _packages_needed(area: float, package_area: float | None) -> int:
    if not package_area or package_area <= 0:
        return 1
    return max(1, math.ceil(area / package_area))


def _norm_tags(tags: list | None) -> set[str]:
    return {str(t).strip().lower() for t in (tags or [])}


def _tags_overlap(request_tags: set[str], rule_tags: list | None) -> list[str]:
    matched: list[str] = []
    for tag in _norm_tags(rule_tags):
        if tag in request_tags:
            matched.append(tag)
        elif any(
            len(tag) > 2 and len(req) > 2 and (tag in req or req in tag)
            for req in request_tags
        ):
            matched.append(tag)
    return sorted(matched)


async def _categories_by_materials(
    session: AsyncSession, materials: set[str]
) -> list[Category]:
    if not materials:
        return []
    result = await session.execute(
        select(Category).where(
            (Category.name.in_(materials)) | (Category.url_key.in_(materials))
        )
    )
    return list(result.scalars().all())


@router.post("/calc/general", response_model=GeneralCalcResponse)
async def general_calculator(
    payload: GeneralCalcRequest, session: SessionDep
) -> GeneralCalcResponse:
    notes = [ML_NOTE]
    tags = {
        payload.object_type.strip().lower(),
        payload.repair_variant.strip().lower(),
    }

    rules = list(
        (await session.execute(select(NormativeRule).limit(200))).scalars().all()
    )
    matched_rules = [r for r in rules if _tags_overlap(tags, r.context_tags)]
    if not matched_rules and rules:
        matched_rules = rules
        notes.append("Правила по тегам не найдены — взяты все материалы из каталога.")
    if not rules:
        notes.append("NormativeRule пуст — смета будет пустой.")

    materials: set[str] = set()
    for rule in matched_rules:
        materials.update(rule.recommended_materials or [])

    categories = await _categories_by_materials(session, materials)
    category_names = {c.id: c.name for c in categories}
    items: list[EstimateItem] = []
    currency = "RUB"

    if categories:
        products = list(
            (
                await session.execute(
                    select(Product)
                    .where(
                        Product.category_id.in_(set(category_names)),
                        Product.status.is_(True),
                    )
                    .order_by(Product.result_price)
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        if len(products) >= 50:
            notes.append(LIMIT_NOTE)
        for p in products:
            packages = _packages_needed(payload.area, p.package_area)
            units = packages * (p.quantity_in_package or 1)
            subtotal = Decimal(packages) * p.result_price
            items.append(
                EstimateItem(
                    product_id=p.id,
                    sku=p.sku,
                    name=p.name,
                    category_id=p.category_id,
                    category_name=category_names.get(p.category_id),
                    package_area=p.package_area,
                    packages_needed=packages,
                    units_needed=units,
                    price_per_package=p.result_price,
                    subtotal=subtotal,
                )
            )
        if not products:
            notes.append("В рекомендуемых категориях нет активных товаров.")
        else:
            currency = products[0].currency
    else:
        notes.append("Рекомендуемые материалы не сопоставились с категориями.")

    return GeneralCalcResponse(
        area=payload.area,
        object_type=payload.object_type,
        repair_variant=payload.repair_variant,
        items=items,
        total_cost=sum((i.subtotal for i in items), Decimal("0")),
        currency=currency,
        notes=notes,
    )


@router.post("/calc/room", response_model=RoomCalcResponse)
async def room_calculator(
    payload: RoomCalcRequest, session: SessionDep
) -> RoomCalcResponse:
    notes = [ML_NOTE]
    request_tags = {
        payload.room_type.strip().lower(),
        payload.repair_type.strip().lower(),
        payload.humidity_level.strip().lower(),
        payload.load_level.strip().lower(),
    }

    rules = list(
        (await session.execute(select(NormativeRule).limit(200))).scalars().all()
    )
    scored: list[tuple[NormativeRule, list[str]]] = []
    for rule in rules:
        overlap = _tags_overlap(request_tags, rule.context_tags)
        if overlap:
            scored.append((rule, overlap))
    scored.sort(key=lambda pair: -len(pair[1]))

    if not scored:
        notes.append("Подходящих NormativeRule не найдено — рекомендаций нет.")

    matched_rules = [
        RuleMatch(
            rule_id=rule.id,
            matched_tags=overlap,
            context_tags=list(rule.context_tags or []),
            recommended_materials=list(rule.recommended_materials or []),
            consumption_formula=rule.consumption_formula,
        )
        for rule, overlap in scored
    ]

    materials: set[str] = set()
    category_tags: dict[int, set[str]] = {}
    for rule, overlap in scored:
        materials.update(rule.recommended_materials or [])

    categories = await _categories_by_materials(session, materials)
    name_to_id = {}
    for c in categories:
        name_to_id[c.name.strip().lower()] = c.id
        name_to_id[c.url_key.strip().lower()] = c.id
    for rule, overlap in scored:
        for material in rule.recommended_materials or []:
            cid = name_to_id.get(material.strip().lower())
            if cid is not None:
                category_tags.setdefault(cid, set()).update(overlap)

    products: list[Product] = []
    if category_tags:
        result = await session.execute(
            select(Product)
            .options(selectinload(Product.category))
            .where(
                Product.category_id.in_(set(category_tags)),
                Product.status.is_(True),
            )
            .order_by(Product.result_price)
            .limit(20)
        )
        products = list(result.scalars().all())
        if len(products) >= 20:
            notes.append(LIMIT_NOTE)
    elif materials:
        notes.append("Рекомендуемые материалы не сопоставились с категориями.")
    if materials and not products and category_tags:
        notes.append("В рекомендуемых категориях нет активных товаров.")

    recommendations: list[RecommendedProduct] = []
    currency = "RUB"
    for p in products:
        packages = _packages_needed(payload.area, p.package_area)
        units = packages * (p.quantity_in_package or 1)
        subtotal = Decimal(packages) * p.result_price
        recommendations.append(
            RecommendedProduct(
                product_id=p.id,
                sku=p.sku,
                name=p.name,
                category_id=p.category_id,
                category_name=p.category.name if p.category else None,
                result_price=p.result_price,
                price_per_m2=p.price_per_m2,
                package_area=p.package_area,
                packages_needed=packages,
                units_needed=units,
                subtotal=subtotal,
                matched_tags=sorted(category_tags.get(p.category_id, set())),
            )
        )
        currency = p.currency

    return RoomCalcResponse(
        area=payload.area,
        room_type=payload.room_type,
        repair_type=payload.repair_type,
        matched_rules=matched_rules,
        products=recommendations,
        total_cost=sum((r.subtotal for r in recommendations), Decimal("0")),
        currency=currency,
        notes=notes,
    )


@router.post("/product/{product_id}/calc", response_model=ProductCalcResponse)
async def product_calculator(
    product_id: int, payload: ProductCalcRequest, session: SessionDep
) -> ProductCalcResponse:
    product = (
        (
            await session.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if not product.package_area or product.package_area <= 0:
        raise HTTPException(
            status_code=422,
            detail="У товара не задана площадь упаковки (package_area > 0)",
        )

    packages = _packages_needed(payload.area, product.package_area)
    units = packages * (product.quantity_in_package or 1)
    total = Decimal(packages) * product.result_price

    return ProductCalcResponse(
        product_id=product.id,
        sku=product.sku,
        area=payload.area,
        package_area=product.package_area,
        quantity_in_package=product.quantity_in_package,
        packages_needed=packages,
        units_needed=units,
        price_per_package=product.result_price,
        price_per_m2=product.price_per_m2,
        total_cost=total,
        currency=product.currency,
        detail={
            "unit": product.unit,
            "price": product.price,
            "name": product.name,
        },
    )
