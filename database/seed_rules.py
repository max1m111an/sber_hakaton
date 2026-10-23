"""Нормативные правила расхода — стартовое наполнение таблицы normative_rule.

Правило описывает одну работу: к каким помещениям и уровням ремонта она
относится, какие типы материалов подходят (recommended_materials — типы работ
из classifier.WORK_TYPES в порядке предпочтения), с какой поверхности
считается объём и по какой норме.

Поверхности (surface):
  floor      — площадь пола, м²
  walls      — площадь стен за вычетом проёмов, м²
  ceiling    — площадь потолка, м²
  perimeter  — периметр, п.м.
  wet_zone   — пол + примыкания к стенам на 0,3 м (гидроизоляция), м²
  tiled      — суммарная площадь облицовки плиткой в помещении, м²
  apron      — кухонный фартук, фиксированно 2,5 м²

База расчёта (calc_basis):
  area    — покрытие упаковки, м² (плитка, SPC, обои, панели)
  weight  — масса упаковки, кг, при норме consumption_rate кг/м² на слой
  volume  — объём упаковки, л, при норме consumption_rate л/м² на слой
  length  — длина единицы, м (плинтус, лента)

Нормы — усреднённые данные производителей; если в карточке товара указан
собственный расход, он имеет приоритет. Расценки на работы ориентировочные
(₽ за единицу поверхности для капитального ремонта) и правятся в таблице.
"""
from __future__ import annotations

COSMETIC, CAPITAL, DESIGNER = "косметический", "капитальный", "дизайнерский"
ALL_LEVELS = [COSMETIC, CAPITAL, DESIGNER]
DRY_ROOMS = ["Детская", "Спальня", "Гостиная", "Коридор", "Кладовая"]

_PAINT_EXCLUDE = r"фасад|наружн|аэрозол|по металлу|для дерева|по дереву|эмаль|декоративн|грунт|колер"

NORMATIVE_RULES: list[dict] = [
    {
        "code": "floor_leveling", "title": "Выравнивание пола: наливной пол, слой 10 мм",
        "recommended_materials": ["floor_leveler"], "surface": "floor", "calc_basis": "weight",
        "consumption_rate": 15.0, "layers": 1, "waste_percent": 5,
        "repair_levels": [CAPITAL, DESIGNER], "room_types": [], "min_humidity": 0,
        "labor_price": 450, "labor_unit": "м²", "priority": 10,
        "consumption_formula": "ceil(S_пола × 15 кг/м² × 1,05 / масса_мешка)",
    },
    {
        "code": "floor_waterproofing", "title": "Гидроизоляция пола и примыканий, 2 слоя",
        "recommended_materials": ["floor_waterproofing"], "surface": "wet_zone", "calc_basis": "weight",
        "consumption_rate": 1.5, "layers": 2, "waste_percent": 10,
        "repair_levels": [CAPITAL, DESIGNER], "room_types": [], "min_humidity": 2,
        "requires_moisture_resistant": True, "exclude_pattern": r"рулонн|кровел|наплавл|битум",
        "labor_price": 500, "labor_unit": "м²", "priority": 20,
        "consumption_formula": "ceil((S_пола + P × 0,3) × 1,5 кг/м² × 2 слоя × 1,1 / масса_упаковки)",
    },
    {
        "code": "waterproofing_tape", "title": "Гидроизоляционная лента в углы и стыки",
        "recommended_materials": ["waterproofing_tape"], "surface": "perimeter", "calc_basis": "length",
        "waste_percent": 10, "repair_levels": [CAPITAL, DESIGNER], "room_types": [], "min_humidity": 2,
        "requires_moisture_resistant": True, "exclude_pattern": r"манжета",
        "labor_price": 0, "labor_unit": "п.м.", "priority": 21,
        "consumption_formula": "ceil(P × 1,1 / длина_рулона)",
    },
    {
        "code": "floor_tile", "title": "Пол: керамогранит / плитка",
        "recommended_materials": ["floor_tile"], "surface": "floor", "calc_basis": "area",
        "waste_percent": 10, "repair_levels": ALL_LEVELS,
        "room_types": ["Санузел", "Кухня", "Коридор", "Балкон"], "min_humidity": 0,
        "labor_price": 1200, "labor_unit": "м²", "priority": 30, "tiled": True,
        "consumption_formula": "ceil(S_пола × 1,10 / площадь_упаковки)",
    },
    {
        "code": "floor_spc", "title": "Пол: SPC-покрытие",
        "recommended_materials": ["floor_spc"], "surface": "floor", "calc_basis": "area",
        "waste_percent": 7, "repair_levels": ALL_LEVELS,
        "room_types": ["Детская", "Спальня", "Гостиная", "Кладовая"], "min_humidity": 0,
        "labor_price": 450, "labor_unit": "м²", "priority": 31,
        "consumption_formula": "ceil(S_пола × 1,07 / площадь_упаковки)",
    },
    {
        "code": "underlay", "title": "Подложка под SPC",
        "recommended_materials": ["underlay"], "surface": "floor", "calc_basis": "area",
        "waste_percent": 5, "repair_levels": [CAPITAL, DESIGNER],
        "room_types": ["Детская", "Спальня", "Гостиная", "Кладовая"], "min_humidity": 0,
        "labor_price": 0, "labor_unit": "м²", "priority": 32,
        "consumption_formula": "ceil(S_пола × 1,05 / площадь_упаковки)",
    },
    {
        "code": "wall_plaster", "title": "Выравнивание стен: штукатурка, слой 10 мм",
        "recommended_materials": ["wall_plaster"], "surface": "walls", "calc_basis": "weight",
        "consumption_rate": 16.0, "layers": 1, "waste_percent": 5,
        "repair_levels": [CAPITAL, DESIGNER], "room_types": [], "min_humidity": 0,
        "exclude_pattern": r"декор|венециан|короед|микроцемент|фактур|шелк|мрамор|камешк",
        "labor_price": 650, "labor_unit": "м²", "priority": 40,
        "consumption_formula": "ceil(S_стен × 16 кг/м² × 1,05 / масса_мешка)",
    },
    {
        "code": "wall_putty", "title": "Финишная шпатлёвка стен",
        "recommended_materials": ["wall_putty"], "surface": "walls", "calc_basis": "weight",
        "consumption_rate": 1.2, "layers": 1, "waste_percent": 5,
        "repair_levels": [CAPITAL, DESIGNER], "room_types": ["Кухня", *DRY_ROOMS], "min_humidity": 0,
        "exclude_pattern": r"дерев|авто|для швов",
        "labor_price": 350, "labor_unit": "м²", "priority": 41,
        "consumption_formula": "ceil(S_стен × 1,2 кг/м² × 1,05 / масса_упаковки)",
    },
    {
        "code": "wall_tile", "title": "Стены: облицовочная плитка",
        "recommended_materials": ["wall_tile", "floor_tile"], "surface": "walls", "calc_basis": "area",
        "waste_percent": 10, "repair_levels": ALL_LEVELS, "room_types": ["Санузел"], "min_humidity": 0,
        "labor_price": 1400, "labor_unit": "м²", "priority": 50, "tiled": True,
        "consumption_formula": "ceil(S_стен × 1,10 / площадь_упаковки)",
    },
    {
        "code": "kitchen_apron", "title": "Кухонный фартук: плитка",
        "recommended_materials": ["wall_tile"], "surface": "apron", "calc_basis": "area",
        "waste_percent": 10, "repair_levels": ALL_LEVELS, "room_types": ["Кухня"], "min_humidity": 0,
        "labor_price": 1600, "labor_unit": "м²", "priority": 51, "tiled": True,
        "consumption_formula": "ceil(2,5 м² × 1,10 / площадь_упаковки)",
    },
    {
        "code": "wallpaper", "title": "Стены: обои",
        "recommended_materials": ["wallpaper"], "surface": "walls", "calc_basis": "area",
        "waste_percent": 15, "repair_levels": [COSMETIC, CAPITAL], "room_types": DRY_ROOMS, "min_humidity": 0,
        "exclude_pattern": r"стеклохолст|флизелин строительный|паутинк",
        "labor_price": 350, "labor_unit": "м²", "priority": 60,
        "consumption_formula": "ceil(S_стен × 1,15 / площадь_рулона)  (запас 15% на подгонку рисунка)",
    },
    {
        "code": "wallpaper_glue", "title": "Клей для обоев",
        "recommended_materials": ["wallpaper_glue"], "surface": "walls", "calc_basis": "weight",
        "consumption_rate": 0.01, "layers": 1, "waste_percent": 0,
        "repair_levels": [COSMETIC, CAPITAL], "room_types": DRY_ROOMS, "min_humidity": 0,
        "exclude_pattern": r"готов|для стеклообоев|бордюр",
        "labor_price": 0, "labor_unit": "м²", "priority": 61,
        "consumption_formula": "ceil(S_стен × 10 г/м² / масса_пачки)  (сухой клей)",
    },
    {
        "code": "wall_paint_kitchen", "title": "Стены: моющаяся краска, 2 слоя",
        "recommended_materials": ["wall_paint"], "surface": "walls", "calc_basis": "volume",
        "consumption_rate": 0.15, "layers": 2, "waste_percent": 5,
        "repair_levels": ALL_LEVELS, "room_types": ["Кухня"], "min_humidity": 0,
        "requires_moisture_resistant": True, "exclude_pattern": _PAINT_EXCLUDE,
        "labor_price": 300, "labor_unit": "м²", "priority": 62,
        "consumption_formula": "ceil(S_стен × 0,15 л/м² × 2 слоя × 1,05 / объём_банки)",
    },
    {
        "code": "wall_paint", "title": "Стены: окраска, 2 слоя",
        "recommended_materials": ["wall_paint"], "surface": "walls", "calc_basis": "volume",
        "consumption_rate": 0.15, "layers": 2, "waste_percent": 5,
        "repair_levels": [DESIGNER], "room_types": DRY_ROOMS, "min_humidity": 0,
        "exclude_pattern": _PAINT_EXCLUDE,
        "labor_price": 300, "labor_unit": "м²", "priority": 63,
        "consumption_formula": "ceil(S_стен × 0,15 л/м² × 2 слоя × 1,05 / объём_банки)",
    },
    {
        "code": "balcony_panels", "title": "Стены балкона: панели ПВХ",
        "recommended_materials": ["wall_panels"], "surface": "walls", "calc_basis": "area",
        "waste_percent": 10, "repair_levels": ALL_LEVELS, "room_types": ["Балкон"], "min_humidity": 0,
        "requires_moisture_resistant": True,
        "labor_price": 500, "labor_unit": "м²", "priority": 64,
        "consumption_formula": "ceil(S_стен × 1,10 / площадь_панели)",
    },
    {
        "code": "tile_adhesive", "title": "Клей для плитки",
        "recommended_materials": ["tile_adhesive"], "surface": "tiled", "calc_basis": "weight",
        "consumption_rate": 5.0, "layers": 1, "waste_percent": 5,
        "repair_levels": ALL_LEVELS, "room_types": [], "min_humidity": 0,
        "labor_price": 0, "labor_unit": "м²", "priority": 70,
        "consumption_formula": "ceil(S_облицовки × 5 кг/м² × 1,05 / масса_мешка)",
    },
    {
        "code": "grout", "title": "Затирка швов",
        "recommended_materials": ["grout"], "surface": "tiled", "calc_basis": "weight",
        "consumption_rate": 0.5, "layers": 1, "waste_percent": 5,
        "repair_levels": ALL_LEVELS, "room_types": [], "min_humidity": 0,
        "exclude_pattern": r"эпокс",
        "labor_price": 0, "labor_unit": "м²", "priority": 71,
        "consumption_formula": "ceil(S_облицовки × 0,5 кг/м² × 1,05 / масса_упаковки)",
    },
    {
        "code": "ceiling_paint", "title": "Потолок: окраска, 2 слоя",
        "recommended_materials": ["wall_paint"], "surface": "ceiling", "calc_basis": "volume",
        "consumption_rate": 0.15, "layers": 2, "waste_percent": 5,
        "repair_levels": ALL_LEVELS, "room_types": [], "min_humidity": 0,
        "exclude_pattern": _PAINT_EXCLUDE,
        "labor_price": 350, "labor_unit": "м²", "priority": 80,
        "consumption_formula": "ceil(S_потолка × 0,15 л/м² × 2 слоя × 1,05 / объём_банки)",
    },
    {
        "code": "ceiling_molding", "title": "Потолочный плинтус",
        "recommended_materials": ["ceiling_molding"], "surface": "perimeter", "calc_basis": "length",
        "waste_percent": 10, "repair_levels": [CAPITAL, DESIGNER], "room_types": ["Кухня", *DRY_ROOMS],
        "min_humidity": 0, "exclude_pattern": r"для панелей|натяжн",
        "labor_price": 250, "labor_unit": "п.м.", "priority": 81,
        "consumption_formula": "ceil(P × 1,10 / длина_плинтуса)",
    },
]

# Значения по умолчанию для необязательных полей правила
RULE_DEFAULTS: dict = {
    "consumption_rate": None,
    "layers": 1,
    "requires_moisture_resistant": False,
    "exclude_pattern": None,
    "tiled": False,
    "context_tags": None,
}


def rule_rows() -> list[dict]:
    rows = []
    for r in NORMATIVE_RULES:
        row = {**RULE_DEFAULTS, **r}
        row["work_type"] = row["recommended_materials"][0]
        # теги контекста — для обратной совместимости и поиска правил по тегам
        row["context_tags"] = [*row["room_types"], *row["repair_levels"]]
        rows.append(row)
    return rows
