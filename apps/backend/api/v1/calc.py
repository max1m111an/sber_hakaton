"""Калькуляторы RepairCalc (п. 2 ТЗ):

    POST /api/v1/calc/general          — общий калькулятор: объект + вариант ремонта → смета
    POST /api/v1/calc/room             — калькулятор специфики комнаты (влажность, назначение)
    POST /api/v1/product/{id}/calc     — сколько купить товара под заданные размеры
"""
import math
from collections import defaultdict
from decimal import Decimal
from types import SimpleNamespace
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from apps.backend.schemas.calculator import (
    GeneralCalcRequest,
    GeneralCalcResponse,
    ProductCalcRequest,
    ProductCalcResponse,
    RoomCalcRequest,
    RoomCalcResponse,
    RoomInput,
)
from apps.backend.services import estimate as est
from database import get_db
from database.models import NormativeRule, Product

router = APIRouter(prefix="/api/v1", tags=["calculator"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]

LABOR_NOTE = "Стоимость работ ориентировочная: расценки задаются в таблице normative_rule."
DATA_NOTE = ("Цены — result_price из выгрузки каталога; остатков и региональных цен в выгрузке нет, "
             "наличие не проверяется.")
ELECTRIC_NOTE = "Электромонтажные материалы (кабель, механизмы розеток) в выгрузке отсутствуют и в смету не входят."

_CALC_COLUMNS = (
    Product.id, Product.sku, Product.name, Product.url_key, Product.result_price, Product.currency,
    Product.unit, Product.package_area, Product.quantity_in_package, Product.package_weight_kg,
    Product.package_volume_l, Product.package_length_m, Product.consumption_rate,
    Product.moisture_resistant, Product.work_type, Product.price_per_m2,
)


async def _rules(session: AsyncSession) -> list[NormativeRule]:
    rules = list((await session.execute(select(NormativeRule).order_by(NormativeRule.priority))).scalars().all())
    if not rules:
        raise HTTPException(status_code=503, detail="Нормативы расхода не загружены: выполните импорт каталога")
    return rules


async def _products_for(session: AsyncSession, rules: list[NormativeRule]) -> dict[str, list[Product]]:
    work_types = sorted({wt for r in rules for wt in (r.recommended_materials or [])})
    rows = (
        await session.execute(
            select(Product).options(load_only(*_CALC_COLUMNS))
            .where(Product.work_type.in_(work_types), Product.status.is_(True), Product.result_price > 0)
        )
    ).scalars().all()
    by_type: dict[str, list[Product]] = defaultdict(list)
    for p in rows:
        by_type[p.work_type].append(p)  # type: ignore[index]
    return by_type


def _brief(line: est.Line) -> dict[str, Any]:
    p = line.product
    return {
        "product_id": p.id, "sku": p.sku, "name": p.name, "url_key": p.url_key, "price": p.result_price,
        "currency": p.currency, "unit": p.unit, "pack": line.cover.pack_label,
        "coverage_per_package": round(line.cover.per_package, 3), "coverage_unit": line.cover.unit,
        "moisture_resistant": p.moisture_resistant,
    }


def _room_result(room_in: RoomInput, level: str, tier_in: str | None, rules: list[NormativeRule],
                 products: dict[str, list[Product]], default_height: float = 2.7) -> dict[str, Any]:
    room = est.norm_room(room_in.room_type)
    humidity = est.norm_humidity(room_in.humidity_level, room)
    tier = est.norm_tier(tier_in, level)
    height = room_in.ceiling_height or default_height
    geom = est.geometry(room_in.area, height, room_in.openings_area, room_in.length, room_in.width, room)
    items = est.estimate_room(rules, products, room=room, level=level, humidity=humidity, geom=geom, tier=tier,
                              picks=room_in.picks, disabled=room_in.disabled)

    lines = []
    for it in items:
        c = it.choice
        lines.append({
            "rule_code": it.rule.code,
            "title": it.rule.title,
            "work_type": it.rule.work_type,
            "work_type_name": est.work_type_name(it.rule.work_type),
            "recommended_materials": list(it.rule.recommended_materials or []),
            "enabled": it.enabled,
            "manual": it.manual,
            "pick_rejected": it.pick_rejected,
            "surface": it.surface,
            "surface_unit": it.surface_unit,
            "quantity_with_waste": c.need if c else None,
            "waste_percent": it.rule.waste_percent,
            "consumption_rate": c.cover.rate if c else it.rule.consumption_rate,
            "consumption_source": c.cover.rate_source if c else None,
            "product": _brief(c) if c else None,
            "packages_needed": c.packages if c else 0,
            "material_cost": c.cost if c else Decimal("0"),
            "labor_cost": it.labor_cost,
            "formula": it.rule.consumption_formula,
            "explanation": est.explain(it, room, humidity, tier),
            "alternatives": [{**_brief(a), "packages_needed": a.packages, "material_cost": a.cost}
                             for a in it.alternatives],
        })
    active = [ln for ln in lines if ln["enabled"]]
    materials = sum((ln["material_cost"] for ln in active), Decimal("0"))
    labor = sum((ln["labor_cost"] for ln in active), Decimal("0"))
    notes = [LABOR_NOTE, DATA_NOTE]
    notes += [f"{it.rule.title}: {it.pick_rejected}." for it in items if it.pick_rejected]
    if not items:
        notes.append("Для этого сочетания помещения и уровня ремонта нет нормативов.")
    missing = [ln["title"] for ln in lines if ln["product"] is None]
    if missing:
        notes.append("Нет подходящих товаров для: " + "; ".join(missing) + ".")
    if (room_in.load_level or "").lower().startswith("высок"):
        notes.append("Высокая нагрузка: для пола рекомендуем керамогранит или SPC 43 класса.")

    return {
        "room_type": room,
        "repair_type": level,
        "area": room_in.area,
        "humidity_level": est.HUMIDITY_NAMES[humidity],
        "load_level": room_in.load_level,
        "tier": tier,
        "geometry": {
            "floor_area": geom.floor_area, "ceiling_height": geom.height, "perimeter": geom.perimeter,
            "wall_area": geom.wall_area, "openings_area": geom.openings, "ceiling_area": geom.ceiling_area,
        },
        "items": lines,
        "matched_rules": [
            {"rule_id": it.rule.id, "code": it.rule.code, "title": it.rule.title,
             "matched_tags": [t for t in (room, level) if t in (it.rule.context_tags or [])],
             "recommended_materials": list(it.rule.recommended_materials or []),
             "consumption_formula": it.rule.consumption_formula}
            for it in items
        ],
        "materials_cost": est.money(materials),
        "labor_cost": est.money(labor),
        "total_cost": est.money(materials + labor),
        "currency": "RUB",
        "notes": notes,
        "_lines": items,  # для сводного списка покупок (из ответа удаляется)
    }


@router.post("/calc/room", response_model=RoomCalcResponse, summary="Калькулятор специфики комнаты")
async def room_calculator(payload: RoomCalcRequest, session: SessionDep):
    rules = await _rules(session)
    products = await _products_for(session, rules)
    result = _room_result(payload, est.norm_level(payload.repair_type), payload.tier, rules, products)
    result.pop("_lines")
    return result


@router.post("/calc/general", response_model=GeneralCalcResponse, summary="Общий калькулятор")
async def general_calculator(payload: GeneralCalcRequest, session: SessionDep):
    level = est.norm_level(payload.repair_variant)
    object_type = payload.object_type.strip().lower()
    notes = [LABOR_NOTE, DATA_NOTE, ELECTRIC_NOTE]

    rooms_in = payload.rooms
    if not rooms_in:
        layout = est.OBJECT_LAYOUTS.get(object_type)
        if layout is None:
            layout = est.OBJECT_LAYOUTS["квартира"]
            notes.append(f"Тип объекта «{payload.object_type}» не распознан — использована раскладка квартиры.")
        rooms_in = [RoomInput(room_type=name, area=round(max(2.0, payload.area * share), 1))
                    for name, share in layout]
        notes.append("Помещения не заданы — площадь разложена по типовым долям: "
                     + ", ".join(f"{r.room_type} {r.area} м²" for r in rooms_in) + ".")

    rules = await _rules(session)
    products = await _products_for(session, rules)
    rooms = [_room_result(r, level, payload.tier, rules, products, payload.ceiling_height) for r in rooms_in]

    # сводный список покупок: суммируем объём по товару и округляем упаковки один раз
    need: dict[int, float] = defaultdict(float)
    info: dict[int, est.Line] = {}
    where: dict[int, list[str]] = defaultdict(list)
    for room in rooms:
        for it in room.pop("_lines"):
            if it.choice and it.enabled:
                pid = it.choice.product.id
                need[pid] += it.choice.need / it.choice.cover.per_package
                info[pid] = it.choice
                if room["room_type"] not in where[pid]:
                    where[pid].append(room["room_type"])
    items = []
    for pid, packs in need.items():
        line = info[pid]
        n = max(1, math.ceil(packs - 1e-9))
        items.append({
            "product_id": pid, "sku": line.product.sku, "name": line.product.name, "pack": line.cover.pack_label,
            "packages_needed": n, "price_per_package": line.product.result_price,
            "subtotal": est.money(Decimal(line.product.result_price) * n), "rooms": where[pid],
        })
    items.sort(key=lambda x: -x["subtotal"])

    materials = sum((i["subtotal"] for i in items), Decimal("0"))
    labor = sum((r["labor_cost"] for r in rooms), Decimal("0"))
    return {
        "object_type": payload.object_type,
        "repair_variant": level,
        "area": payload.area,
        "tier": est.norm_tier(payload.tier, level),
        "rooms": rooms,
        "items": items,
        "materials_cost": est.money(materials),
        "labor_cost": est.money(labor),
        "total_cost": est.money(materials + labor),
        "currency": "RUB",
        "notes": notes,
    }


@router.post("/product/{product_id}/calc", response_model=ProductCalcResponse, summary="Расчёт на карточке товара")
async def product_calculator(product_id: int, payload: ProductCalcRequest, session: SessionDep):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")

    rules = list((await session.execute(select(NormativeRule).order_by(NormativeRule.priority))).scalars().all())
    rule = next((r for r in rules if product.work_type and product.work_type in (r.recommended_materials or [])), None)

    if rule is not None:
        basis, rate, layers, waste = rule.calc_basis, rule.consumption_rate, rule.layers, rule.waste_percent
    elif product.package_area:
        basis, rate, layers, waste = "area", None, 1, 10.0
    elif product.package_length_m:
        basis, rate, layers, waste = "length", None, 1, 10.0
    else:
        raise HTTPException(status_code=422, detail="Для товара неизвестна фасовка — расчёт количества невозможен")

    if basis == "length":
        if payload.length and payload.width:
            surface = 2 * (payload.length + payload.width)    # периметр комнаты
        else:
            surface = payload.length or payload.area or 0.0
    elif payload.area:
        surface = payload.area
    elif payload.width and payload.height:
        surface = payload.width * payload.height
    else:
        surface = (payload.length or 0) * (payload.width or 0)
    if basis != "length":
        surface = max(0.0, surface - payload.openings_area)
    if surface <= 0:
        raise HTTPException(status_code=422, detail="Площадь поверхности получилась нулевой")

    calc_rule = SimpleNamespace(
        calc_basis=basis, consumption_rate=rate,
        layers=payload.layers or layers or 1,
        waste_percent=(payload.waste_percent if payload.waste_percent is not None else waste)
        + payload.extra_waste_percent,
    )
    line = est.make_line(product, calc_rule, surface)
    if line is None:
        raise HTTPException(status_code=422, detail="Для товара неизвестна фасовка — расчёт количества невозможен")

    unit = "п.м." if basis == "length" else "м²"
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "area": round(surface, 3),
        "calc_basis": basis,
        "rule_code": rule.code if rule else None,
        "waste_percent": calc_rule.waste_percent,
        "need_with_waste": line.need,
        "package_area": product.package_area,
        "coverage_per_package": round(line.cover.per_package, 3),
        "coverage_unit": line.cover.unit,
        "pack": line.cover.pack_label,
        "quantity_in_package": product.quantity_in_package,
        "packages_needed": line.packages,
        "units_needed": line.packages * product.quantity_in_package if product.quantity_in_package else None,
        "consumption_rate": line.cover.rate,
        "consumption_source": line.cover.rate_source,
        "price_per_package": product.result_price,
        "price_per_m2": product.price_per_m2,
        "total_cost": line.cost,
        "currency": product.currency,
        "formula_hint": (f"упаковок = ceil({unit} × (1 + запас) / покрытие_упаковки); "
                         f"итого = упаковок × result_price"),
        "detail": {"unit": product.unit, "work_type": product.work_type,
                   "work_type_name": est.work_type_name(product.work_type), "pack_source": product.pack_source,
                   "layers": calc_rule.layers},
    }
