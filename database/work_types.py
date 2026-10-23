"""Справочник типов работ и атрибутные правила (влагостойкость, помещения).

Отнесение товара к типу работ делает ML-модель (ml/matching.py). Здесь —
только справочник с постоянными id (их возвращает MLMatcher.predict) и
разбор атрибутов, которые явно указаны в карточке.
"""
from __future__ import annotations

import re

# (id, код, название). id постоянные: на них ссылаются предсказания модели и таблица work_type.
# Новые типы добавляются в конец со следующим id.
WORK_TYPE_LIST: list[tuple[int, str, str]] = [
    (1, "floor_tile", "Напольная плитка и керамогранит"),
    (2, "floor_spc", "SPC и модульные напольные покрытия"),
    (3, "floor_leveler", "Смеси для выравнивания пола"),
    (4, "floor_waterproofing", "Гидроизоляционные смеси"),
    (5, "waterproofing_tape", "Гидроизоляционные ленты и манжеты"),
    (6, "bitumen_mastic", "Мастики и праймеры"),
    (7, "floor_glue", "Клей для напольных покрытий"),
    (8, "underlay", "Подложка"),
    (9, "underfloor_heating", "Тёплый пол"),
    (10, "wall_tile", "Настенная плитка"),
    (11, "wall_paint", "Краски для стен и потолков"),
    (12, "wallpaper", "Обои под покраску, стеклообои"),
    (13, "wallpaper_glue", "Клей для обоев"),
    (14, "wall_panels", "Стеновые панели"),
    (15, "wall_plaster", "Штукатурка"),
    (16, "wall_putty", "Шпатлёвка"),
    (17, "cement_mix", "Цементно-песчаные смеси"),
    (18, "tile_adhesive", "Клей для плитки"),
    (19, "grout", "Затирка для швов"),
    (20, "tile_accessories", "Крестики, СВП, уголки для плитки"),
    (21, "ceiling_tile", "Потолочная плитка"),
    (22, "ceiling_molding", "Потолочный плинтус"),
    (23, "electrical", "Электроустановочные изделия"),
    (24, "rough_plumbing", "Черновая сантехника: арматура, соединители, изоляция труб"),
    (25, "drywall_profile", "Профили и комплектующие для гипсокартона"),
]

# id 0 — «нет подходящего типа работ» (класс «прочее» у модели)
OTHER_ID = 0

WORK_TYPES: dict[str, str] = {code: name for _, code, name in WORK_TYPE_LIST}
CODE_BY_ID: dict[int, str] = {wid: code for wid, code, _ in WORK_TYPE_LIST}
ID_BY_CODE: dict[str, int] = {code: wid for wid, code, _ in WORK_TYPE_LIST}


def work_type_rows() -> list[dict]:
    return [{"id": wid, "code": code, "name": name} for wid, code, name in WORK_TYPE_LIST]


# ------------------------------------------------------------------ влагостойкость

# Материалы, влагостойкие по своей природе
_INHERENTLY_WET = {
    "floor_tile", "floor_spc", "wall_tile", "floor_waterproofing", "waterproofing_tape",
    "bitumen_mastic", "grout", "tile_adhesive", "cement_mix", "floor_leveler",
}
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


# ------------------------------------------------------------------ помещения

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
    "rough_plumbing": ["Санузел", "Кухня"],
}


def suitable_rooms(work_type: str | None, moisture: bool | None) -> list[str]:
    if work_type in _ROOMS_BY_TYPE:
        return _ROOMS_BY_TYPE[work_type]
    if work_type is None or work_type in ("bitumen_mastic", "tile_accessories", "electrical", "drywall_profile"):
        return []
    if moisture:
        return ROOMS_DRY + ROOMS_WET
    return ROOMS_DRY + (["Кухня"] if moisture is None else [])
