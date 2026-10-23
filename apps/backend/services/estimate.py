"""Движок расчёта сметы: геометрия помещения, расход, выбор товаров.

Модуль не обращается к БД: на вход — правила (NormativeRule) и товары
(Product) как объекты с атрибутами, на выход — строки сметы. Так логику
легко тестировать и переиспользовать в разных эндпоинтах.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Any, Iterable, Sequence

from database.classifier import WORK_TYPES

COSMETIC, CAPITAL, DESIGNER = "косметический", "капитальный", "дизайнерский"
LEVELS = (COSMETIC, CAPITAL, DESIGNER)
LABOR_K = {COSMETIC: Decimal("0.85"), CAPITAL: Decimal("1"), DESIGNER: Decimal("1.4")}
DEFAULT_TIER = {COSMETIC: "economy", CAPITAL: "balance", DESIGNER: "premium"}
TIERS = ("economy", "balance", "premium")
HUMIDITY = {"низкая": 0, "средняя": 1, "высокая": 2}
HUMIDITY_NAMES = ("низкая", "средняя", "высокая")

ROOM_ALIASES = {
    "санузел": "Санузел", "ванная": "Санузел", "ванна": "Санузел", "туалет": "Санузел", "с/у": "Санузел",
    "кухня": "Кухня", "кухня-гостиная": "Кухня",
    "детская": "Детская", "спальня": "Спальня", "гостиная": "Гостиная", "зал": "Гостиная",
    "комната": "Гостиная", "жилая": "Гостиная",
    "коридор": "Коридор", "прихожая": "Коридор", "холл": "Коридор",
    "балкон": "Балкон", "лоджия": "Балкон",
    "кладовая": "Кладовая", "гардеробная": "Кладовая",
}
ROOM_HUMIDITY = {"Санузел": 2, "Кухня": 1, "Балкон": 1}
ROOM_OPENINGS = {"Санузел": 1.6, "Кладовая": 1.6, "Коридор": 3.2}

# Раскладка общей площади по помещениям, если список комнат не задан
OBJECT_LAYOUTS: dict[str, list[tuple[str, float]]] = {
    "квартира": [("Санузел", .07), ("Кухня", .15), ("Коридор", .12), ("Гостиная", .30), ("Спальня", .36)],
    "дом": [("Санузел", .06), ("Кухня", .14), ("Коридор", .12), ("Гостиная", .30), ("Спальня", .20), ("Детская", .18)],
    "студия": [("Санузел", .12), ("Коридор", .10), ("Кухня", .20), ("Гостиная", .58)],
}

TWO = Decimal("0.01")


def money(x: Decimal | float | int) -> Decimal:
    return Decimal(str(x)).quantize(TWO, rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------ нормализация входа


def norm_room(value: str) -> str:
    v = (value or "").strip().lower()
    if v in ROOM_ALIASES:
        return ROOM_ALIASES[v]
    for k, room in ROOM_ALIASES.items():
        if v.startswith(k[:5]):
            return room
    return value.strip().capitalize() or "Гостиная"


def norm_level(value: str | None) -> str:
    v = (value or "").strip().lower()
    for lvl in LEVELS:
        if v.startswith(lvl[:5]):
            return lvl
    if v.startswith(("премиум", "элит")):
        return DESIGNER
    return CAPITAL


def norm_humidity(value: str | int | None, room: str) -> int:
    if isinstance(value, int):
        return max(0, min(2, value))
    v = (value or "").strip().lower()
    for name, h in HUMIDITY.items():
        if v.startswith(name[:4]):
            return h
    return ROOM_HUMIDITY.get(room, 0)


def norm_tier(value: str | None, level: str) -> str:
    v = (value or "").strip().lower()
    aliases = {"эконом": "economy", "дешевле": "economy", "баланс": "balance", "премиум": "premium"}
    v = aliases.get(v, v)
    return v if v in TIERS else DEFAULT_TIER[level]


# ------------------------------------------------------------------ геометрия


@dataclass
class Geometry:
    floor_area: float
    height: float
    openings: float
    perimeter: float
    wall_area: float
    ceiling_area: float
    wet_zone: float
    apron: float = 2.5

    def surface(self, name: str, tiled: float = 0.0) -> float:
        return {
            "floor": self.floor_area,
            "walls": self.wall_area,
            "ceiling": self.ceiling_area,
            "perimeter": self.perimeter,
            "wet_zone": self.wet_zone,
            "apron": self.apron,
            "tiled": tiled,
        }.get(name, 0.0)


def geometry(area: float, height: float = 2.7, openings: float | None = None,
             length: float | None = None, width: float | None = None, room: str = "") -> Geometry:
    """Если длина и ширина не заданы, периметр оценивается как у квадратной комнаты."""
    perimeter = 2 * (length + width) if length and width else 4 * math.sqrt(max(area, 0.5))
    op = ROOM_OPENINGS.get(room, 2.4) if openings is None else openings
    walls = max(0.0, perimeter * height - op)
    return Geometry(
        floor_area=round(area, 3), height=height, openings=op, perimeter=round(perimeter, 3),
        wall_area=round(walls, 3), ceiling_area=round(area, 3),
        wet_zone=round(area + perimeter * 0.3, 3),
    )


# ------------------------------------------------------------------ правила


def rule_applies(rule: Any, room: str, level: str, humidity: int) -> bool:
    return (
        level in (rule.repair_levels or [])
        and (not rule.room_types or room in rule.room_types)
        and humidity >= (rule.min_humidity or 0)
    )


# ------------------------------------------------------------------ расход и упаковки


@dataclass
class Coverage:
    per_package: float      # сколько единиц поверхности закрывает одна упаковка (с учётом слоёв)
    unit: str               # м² / п.м.
    pack_label: str         # что в упаковке: "1,44 м²", "25 кг", "9 л"
    rate: float | None      # применённая норма расхода
    rate_source: str | None  # карточка / норматив


def _fmt(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def coverage(product: Any, rule: Any) -> Coverage | None:
    """Покрытие одной упаковки для данного правила; None — если посчитать нельзя."""
    basis = rule.calc_basis
    layers = max(1, int(rule.layers or 1))
    if basis == "area":
        if product.package_area:
            return Coverage(float(product.package_area), "м²", f"{_fmt(product.package_area)} м²", None, None)
        return None
    if basis == "length":
        if product.package_length_m:
            return Coverage(float(product.package_length_m), "п.м.", f"{_fmt(product.package_length_m)} м", None, None)
        return None
    if basis in ("weight", "volume"):
        size = product.package_weight_kg if basis == "weight" else product.package_volume_l
        if not size or (basis == "volume" and size < 0.9):  # пробники и колеровочные баночки
            return None
        rate, src = (product.consumption_rate, "карточка товара") if product.consumption_rate else (rule.consumption_rate, "норматив")
        if not rate:
            return None
        unit = "кг" if basis == "weight" else "л"
        return Coverage(float(size) / (float(rate) * layers), "м²", f"{_fmt(size)} {unit}", float(rate), src)
    return None


@dataclass
class Line:
    product: Any
    cover: Coverage
    need: float           # объём работ с запасом, ед. поверхности
    packages: int
    cost: Decimal
    unit_price: Decimal   # цена за единицу поверхности


def make_line(product: Any, rule: Any, surface: float) -> Line | None:
    cov = coverage(product, rule)
    if cov is None or cov.per_package <= 0:
        return None
    need = surface * (1 + float(rule.waste_percent or 0) / 100)
    packages = max(1, math.ceil(need / cov.per_package - 1e-9))
    price = Decimal(product.result_price)
    return Line(product, cov, round(need, 3), packages, money(price * packages), money(price / Decimal(str(cov.per_package))))


def suitable(product: Any, rule: Any, humidity: int) -> bool:
    if product.work_type not in (rule.recommended_materials or []):
        return False
    if not product.result_price or Decimal(product.result_price) <= 0:
        return False
    need_mr = humidity >= 2 or bool(rule.requires_moisture_resistant)
    if need_mr and product.moisture_resistant is not True:
        return False
    if humidity == 1 and product.moisture_resistant is False:
        return False
    if rule.exclude_pattern and re.search(rule.exclude_pattern, product.name or "", re.I):
        return False
    return True


def pick(lines: Sequence[Line], tier: str) -> list[Line]:
    """Сортирует варианты под выбранный ценовой сегмент; первый — выбор сервиса.

    economy — минимальная стоимость на объём помещения;
    balance — ближе всего к медиане цены за единицу поверхности;
    premium — около 85-го перцентиля цены за единицу (не самый дорогой «выброс»).
    Варианты в слишком мелкой таре (в разы больше упаковок, чем у лучшего) не предлагаются.
    """
    if not lines:
        return []
    # отсекаем слишком мелкую фасовку: 59 банок по 0,5 кг вместо одного ведра никто не купит
    min_packs = min(x.packages for x in lines)
    limit = max(min_packs * 3, min_packs + 4)
    lines = [x for x in lines if x.packages <= limit]
    prices = sorted(float(x.unit_price) for x in lines)
    if tier == "economy":
        return sorted(lines, key=lambda x: (x.cost, x.unit_price))
    target = median(prices) if tier == "balance" else prices[min(len(prices) - 1, int(len(prices) * 0.85))]
    return sorted(lines, key=lambda x: (abs(float(x.unit_price) - target), x.cost))


@dataclass
class RoomItem:
    rule: Any
    surface: float
    surface_unit: str
    choice: Line | None
    alternatives: list[Line] = field(default_factory=list)
    labor_cost: Decimal = Decimal("0")
    candidates: int = 0


def estimate_room(rules: Iterable[Any], products_by_type: dict[str, list[Any]], *,
                  room: str, level: str, humidity: int, geom: Geometry, tier: str,
                  alternatives: int = 3) -> list[RoomItem]:
    """Смета одного помещения: подходящие правила → товары → упаковки и стоимость."""
    applicable = sorted((r for r in rules if rule_applies(r, room, level, humidity)), key=lambda r: r.priority or 0)
    items: list[RoomItem] = []
    tiled = 0.0
    for rule in applicable:
        surface = geom.surface(rule.surface, tiled)
        if surface <= 0:
            continue
        pool: list[Any] = []
        for wt in rule.recommended_materials or []:
            pool.extend(p for p in products_by_type.get(wt, []) if suitable(p, rule, humidity))
            if pool:   # берём первый тип материала, по которому есть подходящие товары
                break
        lines = [ln for ln in (make_line(p, rule, surface) for p in pool) if ln]
        ranked = pick(lines, tier)
        unit = "п.м." if rule.surface == "perimeter" else "м²"
        labor = money(Decimal(str(surface)) * Decimal(rule.labor_price or 0) * LABOR_K[level])
        item = RoomItem(rule, round(surface, 3), unit, ranked[0] if ranked else None,
                        ranked[1:1 + alternatives], labor, len(pool))
        items.append(item)
        if getattr(rule, "tiled", False) and item.choice:
            tiled += surface
    return items


def explain(item: RoomItem, room: str, humidity: int, tier: str) -> str:
    """Короткое пояснение выбора (до подключения RAG/LLM)."""
    if not item.choice:
        return "В каталоге нет подходящих товаров с известной фасовкой для этой работы."
    parts = []
    if humidity >= 2 or item.rule.requires_moisture_resistant:
        parts.append("только влагостойкие материалы")
    seg = {"economy": "минимальная стоимость", "balance": "средняя цена за м² среди подходящих",
           "premium": "верхний ценовой сегмент"}[tier]
    parts.append(seg)
    cov = item.choice.cover
    if cov.rate:
        parts.append(f"расход {_fmt(cov.rate)} {'кг' if item.rule.calc_basis == 'weight' else 'л'}/м² ({cov.rate_source})")
    parts.append(f"запас {_fmt(float(item.rule.waste_percent or 0))}%")
    return f"{room}, влажность {HUMIDITY_NAMES[humidity]}: " + ", ".join(parts) + f"; выбрано из {item.candidates} товаров."


def work_type_name(wt: str | None) -> str | None:
    return WORK_TYPES.get(wt or "")
