"""Разбор выгрузки каталога maxidom.ru (products_final.json) в строки для БД.

Модуль не зависит от SQLAlchemy: его можно запускать и тестировать отдельно.

Формат файла: {"products": [ {...}, ... ]}. Файл большой (~270 МБ), поэтому
читается потоково — в памяти держится только текущий фрагмент.

Что извлекается из товара, помимо исходных полей:
  * фасовка: площадь упаковки (м²), вес (кг), объём (л), длина (м), штук в упаковке;
  * размеры рулона (обои) и листа (панели) → площадь одной единицы продажи;
  * норма расхода из характеристик, если она указана и выглядит правдоподобно;
  * влагостойкость (True / False / None — неизвестно);
  * тип работ (см. classifier.py).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

from database.classifier import classify, detect_moisture

MARKETING_KEY = "Маркетинговое описание товара"

# ---------------------------------------------------------------- потоковое чтение


def iter_products(path: str | Path, chunk_size: int = 1 << 20) -> Iterator[dict[str, Any]]:
    """Отдаёт товары по одному, не загружая весь файл в память.

    Поддерживает {"products": [...]} и просто [...] на верхнем уровне.
    """
    decoder = json.JSONDecoder()
    with open(path, "r", encoding="utf-8") as fh:
        buf = fh.read(chunk_size)
        eof = False

        def more() -> bool:
            nonlocal buf, eof, pos
            if eof:
                return False
            chunk = fh.read(chunk_size)
            if not chunk:
                eof = True
                return False
            buf = buf[pos:] + chunk
            pos = 0
            return True

        pos = 0
        # ищем начало массива товаров
        while True:
            m = re.search(r'"products"\s*:\s*\[', buf)
            if m:
                pos = m.end()
                break
            stripped = buf.lstrip()
            if stripped.startswith("["):
                pos = len(buf) - len(stripped) + 1
                break
            if not more():
                raise ValueError("В файле не найден массив products")

        while True:
            # пропускаем пробелы и запятые между объектами
            while True:
                while pos < len(buf) and buf[pos] in " \t\r\n,":
                    pos += 1
                if pos < len(buf) or not more():
                    break
            if pos >= len(buf) or buf[pos] == "]":
                return
            try:
                obj, end = decoder.raw_decode(buf, pos)
            except json.JSONDecodeError:
                if not more():
                    raise
                continue
            pos = end
            yield obj
            if pos > chunk_size:  # периодически сжимаем буфер
                buf = buf[pos:]
                pos = 0


# ---------------------------------------------------------------- разбор чисел

_NUM = r"(\d+(?:[.,]\d+)?)"


def to_float(value: Any) -> float | None:
    """'1,44' → 1.44; '0,2-0,04' → 0.2 (первое число); мусор → None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(_NUM, str(value))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _in_range(v: float | None, lo: float, hi: float) -> float | None:
    return v if v is not None and lo <= v <= hi else None


# ---------------------------------------------------------------- фасовка из названия

_RE_AREA = re.compile(_NUM + r"\s*(?:м2|м²|кв\.?\s*м)", re.I)
_RE_KG = re.compile(_NUM + r"\s*кг", re.I)
_RE_G = re.compile(_NUM + r"\s*г(?:р)?\b(?!/)", re.I)
_RE_L = re.compile(_NUM + r"\s*л\b", re.I)
_RE_ML = re.compile(_NUM + r"\s*мл\b", re.I)
_RE_PCS = re.compile(r"(\d+)\s*шт", re.I)
_RE_ROLL = re.compile(_NUM + r"\s*[xх×]\s*" + _NUM + r"\s*м\b", re.I)
_RE_LEN_M = re.compile(_NUM + r"\s*(?:м|п\.?\s*м)\b", re.I)
_RE_ART = re.compile(r"арт\.?\s*([\w\-./]+)", re.I)


def _num(m: re.Match[str] | None, group: int = 1) -> float | None:
    return float(m.group(group).replace(",", ".")) if m else None


@dataclass
class Pack:
    """Фасовка единицы продажи."""

    area_m2: float | None = None       # покрытие одной упаковки, м²
    weight_kg: float | None = None
    volume_l: float | None = None
    length_m: float | None = None      # погонные метры (ленты, плинтус)
    quantity: int | None = None        # штук в упаковке
    sources: list[str] = field(default_factory=list)


def _dims_mm(text: str) -> list[float]:
    nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", text)]
    return nums


def parse_pack(name: str, unit: str | None, chars: dict[str, str], work_type: str | None) -> Pack:
    """Определяет фасовку по характеристикам, затем по названию."""
    p = Pack()
    lname = name.lower()

    # --- площадь упаковки
    area = _in_range(to_float(chars.get("Площадь покрытия упаковкой")), 0.05, 200)
    if area:
        p.area_m2, p.sources = area, p.sources + ["Площадь покрытия упаковкой"]
    in_pack = chars.get("В упаковке") or ""
    m = _RE_AREA.search(in_pack)
    if not p.area_m2 and m:
        p.area_m2 = _in_range(_num(m), 0.05, 200)
        if p.area_m2:
            p.sources.append("В упаковке")
    m = _RE_PCS.search(in_pack)
    if m:
        p.quantity = int(m.group(1))

    # --- штук в упаковке
    for key in ("Количество в упаковке", "Кол-во в упаковке", "Штук в упаковке"):
        q = to_float(chars.get(key))
        if q and q >= 1 and p.quantity is None:
            p.quantity = int(q)

    # --- обои / рулонные материалы: длина × ширина рулона в метрах
    if work_type in ("wallpaper",) and not p.area_m2:
        m = _RE_ROLL.search(name)
        if m:
            a, b = _num(m, 1), _num(m, 2)
            if a and b:
                p.area_m2 = round(a * b, 3)
                p.sources.append("размер рулона в названии")
        else:
            length = to_float(chars.get("Длина"))
            width = to_float(chars.get("Ширина"))
            if length and width and 3 <= length <= 100 and 0.3 <= width <= 3:
                p.area_m2 = round(length * width, 3)
                p.sources.append("Длина×Ширина рулона")

    # --- листовые панели и потолочные плиты: размер листа в мм (× штук в упаковке)
    if work_type in ("wall_panels", "ceiling_tile") and not p.area_m2:
        dims = _dims_mm(chars.get("Размер") or "")
        if len(dims) < 2:
            m = re.search(r"(\d{3,4})\s*[xх×]\s*(\d{2,4})", name)
            dims = [float(m.group(1)), float(m.group(2))] if m else []
        if len(dims) >= 2 and dims[0] >= 100 and dims[1] >= 100:
            p.area_m2 = round(dims[0] / 1000 * dims[1] / 1000, 4)
            if p.quantity and p.quantity > 1 and re.search(r"\d+\s*шт", lname):
                p.area_m2 = round(p.area_m2 * p.quantity, 4)
            p.sources.append("размер листа")

    # --- площадь, указанная в названии ("2,233м2", "7кв.м")
    if not p.area_m2:
        m = _RE_AREA.search(name)
        v = _in_range(_num(m), 0.05, 200) if m else None
        if v and work_type not in ("underfloor_heating",):
            p.area_m2 = v
            p.sources.append("площадь в названии")

    # --- товары, продаваемые квадратными метрами
    if not p.area_m2 and unit and unit.startswith("кв.м"):
        p.area_m2 = 1.0
        p.sources.append("единица продажи м²")

    # --- вес (кг). "Вес" у клея для обоев указан в граммах
    weight = to_float(chars.get("Вес"))
    m_kg, m_g = _RE_KG.search(name), _RE_G.search(name)
    grams = _num(m_g) if m_g else None
    name_kg = _num(m_kg) if m_kg else (grams / 1000 if grams else None)
    if name_kg:
        p.weight_kg = name_kg
        p.sources.append("вес в названии")
    elif weight:
        p.weight_kg = weight / 1000 if weight > 60 and work_type == "wallpaper_glue" else weight
        p.sources.append("Вес")

    # --- объём (л)
    m_l, m_ml = _RE_L.search(name), _RE_ML.search(name)
    vol = to_float(chars.get("Литраж банки")) or to_float(chars.get("Объем"))
    if m_l:
        p.volume_l = _num(m_l)
    elif m_ml:
        p.volume_l = (_num(m_ml) or 0) / 1000 or None
    elif work_type == "wall_paint" and name_kg:
        # краска в килограммах: пересчёт в литры по плотности ~1,4 кг/л
        p.volume_l = round(name_kg / 1.4, 2)
        p.sources.append("объём по массе (1,4 кг/л)")
    elif vol:
        p.volume_l = vol / 1000 if vol > 60 else vol
    if p.volume_l and "объём по массе (1,4 кг/л)" not in p.sources:
        p.sources.append("объём")

    # --- длина (ленты, плинтус): "10м", "Длина"=2000 мм
    if work_type in ("waterproofing_tape", "ceiling_molding"):
        m = re.search(r"[xх×]\s*" + _NUM + r"\s*м\b", name, re.I) or _RE_LEN_M.search(name)
        length = _num(m) if m else None
        if not length:
            raw = to_float(chars.get("Длина"))
            if raw:
                length = raw / 1000 if raw >= 100 else raw
        if not length:
            dims = _dims_mm(chars.get("Размер") or "")
            if dims and max(dims) >= 500:
                length = max(dims) / 1000
        p.length_m = _in_range(length, 0.2, 500)
        if p.length_m:
            p.sources.append("длина")

    return p


def parse_consumption(chars: dict[str, str], work_type: str | None) -> float | None:
    """Норма расхода из характеристик, приведённая к единицам правил.

    * краска — л/м² на один слой (в выгрузке бывает мл/м²: 140 → 0,14);
    * сухие смеси, клей, затирка — кг/м².
    Неправдоподобные значения отбрасываются (тогда берётся норма из правила).
    """
    raw = chars.get("Расход материала") or chars.get("Расход")
    v = to_float(raw)
    if v is None:
        return None
    if work_type == "wall_paint":
        v = v / 1000 if v > 1 else v
        return _in_range(v, 0.05, 0.4)
    if work_type == "tile_adhesive":
        # производители указывают расход на 1 мм слоя (1,1–1,5 кг/м²/мм); слой под плитку ~4 мм
        v = v * 4 if v <= 1.7 else v
        return _in_range(v, 2, 12)
    if work_type in ("wall_plaster", "wall_putty", "floor_leveler", "floor_waterproofing"):
        return _in_range(v, 0.3, 30)
    if work_type == "grout":
        return _in_range(v, 0.05, 3)
    return None


# ---------------------------------------------------------------- нормализация товара


def category_of(raw: dict[str, Any]) -> tuple[int | None, str | None]:
    cats = raw.get("categories") or {}
    for cid, name in cats.items():
        try:
            return int(cid), name
        except (TypeError, ValueError):
            continue
    return None, None


def category_slug(url_key: str | None) -> str | None:
    """'/catalog/<slug>/<cod_good>/' → '<slug>'."""
    if not url_key:
        return None
    parts = [x for x in url_key.split("/") if x]
    return parts[1] if len(parts) >= 3 and parts[0] == "catalog" else None


def normalize_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Строка таблицы product из исходного товара выгрузки."""
    chars_list = [
        {"name": str(c.get("name", "")).strip(), "value": c.get("value")}
        for c in (raw.get("characteristics") or [])
        if isinstance(c, dict) and c.get("name")
    ]
    chars = {c["name"]: str(c["value"]) for c in chars_list if c["value"] is not None}
    name = (raw.get("name") or "").strip()
    unit = raw.get("unit")
    cat_id, cat_name = category_of(raw)

    cls = classify(cat_name, name, chars)
    work_type = cls.work_type
    pack = parse_pack(name, unit, chars, work_type)
    price = to_decimal(raw.get("price") or 0)
    price_per_m2 = (price / Decimal(str(pack.area_m2))).quantize(Decimal("0.01")) if pack.area_m2 else None

    sku = chars.get("Артикул производителя")
    if not sku:
        m = _RE_ART.search(name)
        sku = m.group(1).rstrip(".,") if m else None

    return {
        "id": int(raw["id"]),
        "sku": sku[:128] if sku else None,
        "cod_good": str(raw.get("cod_good") or ""),
        "name": name,
        "description": raw.get("description"),
        "marketing_description": raw.get("marketing_description"),
        "type": "simple",
        "url_key": raw.get("url_key"),
        "price": price,
        "result_price": price,          # в выгрузке нет акций — итоговая цена = базовая
        "currency": raw.get("currency") or "RUB",
        "unit": unit,
        "weight": to_float(raw.get("weight")),
        "brand": raw.get("brand"),
        "collection": raw.get("collection"),
        "country": raw.get("country"),
        "status": True,
        "characteristics": chars_list,
        "category_id": cat_id,
        # фасовка и производные поля
        "package_area": pack.area_m2,
        "quantity_in_package": pack.quantity,
        "package_weight_kg": pack.weight_kg,
        "package_volume_l": pack.volume_l,
        "package_length_m": pack.length_m,
        "pack_source": ", ".join(dict.fromkeys(pack.sources)) or None,
        "price_per_m2": price_per_m2,
        "consumption_rate": parse_consumption(chars, work_type),
        "moisture_resistant": detect_moisture(name, chars, work_type),
        "work_type": work_type,
        "match_confidence": cls.confidence,
        "match_source": cls.source,
    }


@dataclass
class CategoryAcc:
    id: int
    name: str
    url_key: str
    product_count: int = 0
    work_types: dict[str, int] = field(default_factory=dict)


def collect_category(acc: dict[int, CategoryAcc], raw: dict[str, Any], row: dict[str, Any]) -> None:
    cat_id, cat_name = category_of(raw)
    if cat_id is None:
        return
    c = acc.get(cat_id)
    if c is None:
        slug = category_slug(raw.get("url_key")) or f"category-{cat_id}"
        c = acc[cat_id] = CategoryAcc(cat_id, cat_name or f"Категория {cat_id}", slug)
    c.product_count += 1
    if row.get("work_type"):
        c.work_types[row["work_type"]] = c.work_types.get(row["work_type"], 0) + 1


def category_rows(acc: dict[int, CategoryAcc]) -> list[dict[str, Any]]:
    """Строки таблицы category. В выгрузке нет иерархии: все категории — листья уровня 1."""
    rows = []
    used_slugs: set[str] = set()
    for c in sorted(acc.values(), key=lambda x: x.id):
        slug = c.url_key if c.url_key not in used_slugs else f"{c.url_key}-{c.id}"
        used_slugs.add(slug)
        wt = max(c.work_types, key=lambda k: c.work_types[k]) if c.work_types else None
        rows.append({
            "id": c.id,
            "parent_id": None,
            "name": c.name,
            "url_key": slug,
            "description": None,
            "status": True,
            "depth_level": 1,
            "product_count": c.product_count,
            # тип работ категории — если большинство товаров классифицировано одинаково
            "work_type": wt if wt and c.work_types[wt] * 2 > c.product_count else None,
        })
    return rows
