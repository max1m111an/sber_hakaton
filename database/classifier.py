"""Baseline-матчинг товаров каталога к типам работ (п. 3.1 ТЗ).

Правила на ключевых словах: сначала по названию категории (уверенность 0.95),
затем по началу названия товара (0.75). Это точка, которую ML-модель
(эмбеддинги + классификатор) заменит без изменения API: на выходе тот же
work_type + confidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Тип работ → человекочитаемое название
WORK_TYPES: dict[str, str] = {
    "floor_tile": "Напольная плитка и керамогранит",
    "floor_spc": "SPC и модульные напольные покрытия",
    "floor_leveler": "Смеси для выравнивания пола",
    "floor_waterproofing": "Гидроизоляционные смеси",
    "waterproofing_tape": "Гидроизоляционные ленты и манжеты",
    "bitumen_mastic": "Мастики и праймеры",
    "floor_glue": "Клей для напольных покрытий",
    "underlay": "Подложка",
    "underfloor_heating": "Тёплый пол",
    "wall_tile": "Настенная плитка",
    "wall_paint": "Краски для стен и потолков",
    "wallpaper": "Обои под покраску, стеклообои",
    "wallpaper_glue": "Клей для обоев",
    "wall_panels": "Стеновые панели",
    "wall_plaster": "Штукатурка",
    "wall_putty": "Шпатлёвка",
    "cement_mix": "Цементно-песчаные смеси",
    "tile_adhesive": "Клей для плитки",
    "grout": "Затирка для швов",
    "tile_accessories": "Крестики, СВП, уголки для плитки",
    "ceiling_tile": "Потолочная плитка",
    "ceiling_molding": "Потолочный плинтус",
    "electrical": "Электроустановочные изделия",
}

# (регулярное выражение по названию категории, тип работ)
_CATEGORY_RULES: list[tuple[str, str]] = [
    (r"^керамогранит напольн|^напольная плитка", "floor_tile"),
    (r"^плитка spc|^модульные напольные покрытия", "floor_spc"),
    (r"^смеси для выравнивания полов", "floor_leveler"),
    (r"^смеси для гидроизоляции", "floor_waterproofing"),
    (r"^аксессуары для гидроизоляции", "waterproofing_tape"),
    (r"^мастики", "bitumen_mastic"),
    (r"^клей для напольных покрытий", "floor_glue"),
    (r"^подложка", "underlay"),
    (r"^теплый пол", "underfloor_heating"),
    (r"^настенная плитка", "wall_tile"),
    (r"^краски для стен и потолков", "wall_paint"),
    (r"^обои под покраску|^стеклообои", "wallpaper"),
    (r"^клей, средства для обоев", "wallpaper_glue"),
    (r"^стеновые панели|^панели листовые декоративные|^декоративные стеновые панели", "wall_panels"),
    (r"^штукатурка", "wall_plaster"),
    (r"^шпатлевки", "wall_putty"),
    (r"^смеси цементно-песчаные", "cement_mix"),
    (r"^клеи для плитки", "tile_adhesive"),
    (r"^затирки для плитки", "grout"),
    (r"^крестики для|^системы выравнивания плитки|^уголки и бордюры для плитки", "tile_accessories"),
    (r"^плитки потолочные", "ceiling_tile"),
    (r"^плинтусы потолочные", "ceiling_molding"),
    (r"^рамки для розеток|^вилки и розетки бытовые|розетки, выключатели", "electrical"),
]

# (регулярное выражение по началу названия товара, тип работ) — для «сборных» категорий
_PRODUCT_RULES: list[tuple[str, str]] = [
    (r"^керамогранит|^плитка напольная|^плитка для пола", "floor_tile"),
    (r"^плитка spc|^кварцвинил|^плитка lvt", "floor_spc"),
    (r"^плитка настенная|^плитка облицовочная", "wall_tile"),
    (r"^краска\b.*(стен|потол|интерьер|в/д|водно-дисперс)", "wall_paint"),
    (r"^обои|^стеклообои|^стеклохолст|^флизелин строительный", "wallpaper"),
    (r"^клей обойный", "wallpaper_glue"),
    (r"^клей плиточный|^клей для плитки", "tile_adhesive"),
    (r"^затирка", "grout"),
    (r"^штукатурка", "wall_plaster"),
    (r"^шпатлевка", "wall_putty"),
    (r"^пол наливной|^ровнитель|^наливной пол", "floor_leveler"),
    (r"^гидроизоляция", "floor_waterproofing"),
    (r"^лента гидроизоляц|^лента герметик|^манжета гидроизоляц", "waterproofing_tape"),
    (r"^плинтус потолочный", "ceiling_molding"),
    (r"^плита потолочная|^плитка потолочная", "ceiling_tile"),
]

_CAT_RE = [(re.compile(p, re.I), wt) for p, wt in _CATEGORY_RULES]
_PROD_RE = [(re.compile(p, re.I), wt) for p, wt in _PRODUCT_RULES]

# Материалы, влагостойкие по своей природе
_INHERENTLY_WET = {
    "floor_tile", "floor_spc", "wall_tile", "floor_waterproofing", "waterproofing_tape",
    "bitumen_mastic", "grout", "tile_adhesive", "cement_mix", "floor_leveler",
}


@dataclass(frozen=True)
class Classification:
    work_type: str | None
    confidence: float
    source: str  # category | name | none


def classify(category_name: str | None, product_name: str, chars: dict[str, str] | None = None) -> Classification:
    cat = (category_name or "").strip().lstrip("% ").strip()
    for rx, wt in _CAT_RE:
        if rx.search(cat):
            return Classification(wt, 0.95, "category")
    name = (product_name or "").strip()
    for rx, wt in _PROD_RE:
        if rx.search(name):
            return Classification(wt, 0.75, "name")
    return Classification(None, 0.0, "none")


_YES = {"да", "повышенная влагостойкость", "влагостойкие", "моющиеся", "супермоющиеся"}
_NO = {"нет", "не влагостойкие"}


def detect_moisture(name: str, chars: dict[str, str], work_type: str | None) -> bool | None:
    """Влагостойкость: True — подходит для влажных помещений, False — нет, None — неизвестно."""
    for key in ("Влагостойкость", "Влагостойкость краски", "Влагостойкость обоев"):
        v = (chars.get(key) or "").strip().lower()
        if v in _YES:
            return True
        if v in _NO:
            return False
    room = (chars.get("Тип помещения") or "").lower()
    if "влажн" in room:
        return True
    lname = name.lower()
    if re.search(r"влагост|влагозащ|для ванн|аквастат|гидро", lname):
        return True
    if work_type in _INHERENTLY_WET:
        return True
    if work_type in ("wall_plaster", "wall_putty") and "цемент" in lname:
        return True
    if work_type == "wall_panels":
        if "пвх" in lname or "пластик" in (chars.get("Материал") or "").lower():
            return True
        if "мдф" in lname or "двп" in lname:
            return False
    return None


# Помещения, для которых подходит материал (для админки / матчинга)
ROOMS_DRY = ["Детская", "Спальня", "Гостиная", "Коридор"]
ROOMS_WET = ["Санузел", "Кухня", "Балкон"]

_ROOMS_BY_TYPE: dict[str, list[str]] = {
    "floor_tile": ["Санузел", "Кухня", "Коридор", "Балкон"],
    "floor_spc": ["Кухня", "Коридор", "Детская", "Спальня", "Гостиная"],
    "floor_waterproofing": ["Санузел", "Балкон"],
    "waterproofing_tape": ["Санузел"],
    "wall_tile": ["Санузел", "Кухня"],
    "underfloor_heating": ["Санузел", "Кухня", "Балкон"],
    "ceiling_tile": ["Коридор", "Кладовая", "Балкон"],
}


def suitable_rooms(work_type: str | None, moisture: bool | None) -> list[str]:
    if work_type in _ROOMS_BY_TYPE:
        return _ROOMS_BY_TYPE[work_type]
    if work_type is None or work_type in ("bitumen_mastic", "tile_accessories", "electrical"):
        return []
    if moisture:
        return ROOMS_DRY + ROOMS_WET
    return ROOMS_DRY + (["Кухня"] if moisture is None else [])
