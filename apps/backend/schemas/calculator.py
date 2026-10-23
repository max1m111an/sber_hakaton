"""Схемы калькуляторов RepairCalc (сценарии из п. 2 ТЗ)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.backend.schemas.common import Money

# ------------------------------------------------------------------ запросы


class RoomInput(BaseModel):
    room_type: str = Field(..., min_length=1, examples=["санузел"])
    area: float = Field(..., gt=0, le=500, description="Площадь пола, м²")
    ceiling_height: float | None = Field(default=None, ge=2, le=6, description="Высота потолка, м (по умолчанию 2,7)")
    openings_area: float | None = Field(default=None, ge=0, le=100, description="Окна и двери, м²")
    length: float | None = Field(default=None, gt=0, le=100, description="Длина комнаты, м — для точного периметра")
    width: float | None = Field(default=None, gt=0, le=100)
    humidity_level: str | None = Field(default=None, examples=["высокая"], description="низкая / средняя / высокая")
    load_level: str | None = Field(default=None, examples=["средняя"])
    picks: dict[str, int] = Field(default={}, description="Ручной выбор товара: {код правила: id товара}")
    disabled: list[str] = Field(default=[], description="Коды правил (работ), исключённых из сметы")


class RoomCalcRequest(RoomInput):
    repair_type: str = Field(default="капитальный", examples=["капитальный"],
                             description="косметический / капитальный / дизайнерский")
    tier: str | None = Field(default=None, description="economy / balance / premium (по умолчанию — от уровня ремонта)")


class GeneralCalcRequest(BaseModel):
    object_type: str = Field(..., min_length=1, examples=["квартира"], description="квартира / дом / студия")
    repair_variant: str = Field(..., min_length=1, examples=["капитальный"])
    area: float = Field(..., gt=0, le=2000, description="Общая площадь, м²")
    rooms: list[RoomInput] | None = Field(default=None, description="Помещения; если не заданы — типовая раскладка площади")
    ceiling_height: float = Field(default=2.7, ge=2, le=6)
    tier: str | None = None


class ProductCalcRequest(BaseModel):
    """Размеры задаются одним из способов: area; length+width (пол, потолок); width+height (стена)."""

    area: float | None = Field(default=None, gt=0, le=2000, description="Площадь поверхности, м²")
    length: float | None = Field(default=None, gt=0, le=200, description="Длина помещения, м (или длина для погонажа)")
    width: float | None = Field(default=None, gt=0, le=200, description="Ширина помещения или стены, м")
    height: float | None = Field(default=None, gt=0, le=20, description="Высота стены, м")
    openings_area: float = Field(default=0, ge=0, le=500, description="Вычесть окна и двери, м²")
    waste_percent: float | None = Field(default=None, ge=0, le=50, description="Запас; по умолчанию — из норматива")
    extra_waste_percent: float = Field(default=0, ge=0, le=30,
                                       description="Доп. запас к нормативу (укладка по диагонали +5%, рисунок +10%)")
    layers: int | None = Field(default=None, ge=1, le=5, description="Слоёв (краска, гидроизоляция)")

    @model_validator(mode="after")
    def _has_size(self):
        if not (self.area or (self.length and self.width) or (self.width and self.height) or self.length):
            raise ValueError("Укажите area, либо length и width, либо width и height")
        return self


# ------------------------------------------------------------------ ответы


class ProductBrief(BaseModel):
    product_id: int
    sku: str | None = None
    name: str
    url_key: str | None = None
    price: Money
    currency: str = "RUB"
    unit: str | None = None
    pack: str = Field(..., description="Фасовка: «1,44 м²», «25 кг», «9 л»")
    coverage_per_package: float = Field(..., description="Сколько м² (или п.м.) закрывает одна упаковка")
    coverage_unit: str
    moisture_resistant: bool | None = None
    match_confidence: float | None = Field(default=None, description="Уверенность ML-модели в типе работ товара")
    match_source: str | None = Field(default=None, description="ml | manager")


class Alternative(ProductBrief):
    packages_needed: int
    material_cost: Money


class EstimateLine(BaseModel):
    rule_code: str
    title: str
    work_type: str
    work_type_name: str | None = None
    recommended_materials: list[str] = []
    enabled: bool = True
    manual: bool = Field(default=False, description="Товар выбран пользователем")
    pick_rejected: str | None = None
    surface: float
    surface_unit: str
    quantity_with_waste: float | None = None
    waste_percent: float
    consumption_rate: float | None = None
    consumption_source: str | None = None
    product: ProductBrief | None = None
    packages_needed: int = 0
    material_cost: Money = Decimal("0")
    labor_cost: Money = Decimal("0")
    formula: str
    explanation: str
    alternatives: list[Alternative] = []


class Geometry(BaseModel):
    floor_area: float
    ceiling_height: float
    perimeter: float
    wall_area: float
    openings_area: float
    ceiling_area: float


class RuleMatch(BaseModel):
    rule_id: int
    code: str
    title: str
    matched_tags: list[str]
    recommended_materials: list[str]
    consumption_formula: str | None = None


class RoomCalcResponse(BaseModel):
    room_type: str
    repair_type: str
    area: float
    humidity_level: str
    load_level: str | None = None
    tier: str
    geometry: Geometry
    items: list[EstimateLine]
    matched_rules: list[RuleMatch] = []
    materials_cost: Money
    labor_cost: Money
    total_cost: Money
    currency: str = "RUB"
    notes: list[str] = []


class ShoppingItem(BaseModel):
    product_id: int
    sku: str | None = None
    name: str
    pack: str
    packages_needed: int
    price_per_package: Money
    subtotal: Money
    rooms: list[str]


class GeneralCalcResponse(BaseModel):
    object_type: str
    repair_variant: str
    area: float
    tier: str
    rooms: list[RoomCalcResponse]
    items: list[ShoppingItem] = Field(default=[], description="Сводный список покупок по всем помещениям")
    materials_cost: Money
    labor_cost: Money
    total_cost: Money
    currency: str = "RUB"
    notes: list[str] = []


class ProductCalcResponse(BaseModel):
    product_id: int
    sku: str | None = None
    name: str
    area: float = Field(..., description="Объём работ без запаса (м² или п.м.)")
    calc_basis: str
    rule_code: str | None = None
    waste_percent: float
    need_with_waste: float
    package_area: float | None = None
    coverage_per_package: float
    coverage_unit: str
    pack: str
    quantity_in_package: int | None = None
    packages_needed: int
    units_needed: int | None = None
    consumption_rate: float | None = None
    consumption_source: str | None = None
    price_per_package: Money
    price_per_m2: Money | None = None
    total_cost: Money
    currency: str
    formula_hint: str
    detail: dict[str, Any] = {}


# ------------------------------------------------------------------ матчинг / справочники


class MatchRequest(BaseModel):
    name: str = Field(..., min_length=2, examples=["керамогранит CERSANIT Infinity 29,7x59,8 темно-серый"])
    category_name: str | None = None
    description: str | None = None
    characteristics: list[dict[str, Any]] = []


class MatchAlternative(BaseModel):
    work_type: str | None
    work_type_name: str
    confidence: float


class MatchResponse(BaseModel):
    work_type_id: int = Field(..., description="id типа работ (0 — товар не относится к работам)")
    work_type: str | None
    work_type_name: str | None
    confidence: float = Field(..., description="Вероятность предсказанного класса")
    accepted: bool = Field(..., description="Уверенность выше порога — товар участвует в подборе")
    threshold: float
    source: str
    alternatives: list[MatchAlternative] = []
    moisture_resistant: bool | None
    suitable_rooms: list[str]
    package_area: float | None = None
    package_weight_kg: float | None = None
    package_volume_l: float | None = None
    package_length_m: float | None = None


class MatchedProduct(BaseModel):
    id: int
    name: str
    category_id: int | None
    work_type: str | None
    work_type_name: str | None
    confidence: float
    source: str | None = Field(..., description="ml — предсказание модели, manager — решение менеджера")
    accepted: bool
    label_work_type: str | None = Field(None, description="Метка обучающей выборки (rules / manager)")
    label_source: str | None = None
    agrees_with_label: bool | None = None
    moisture_resistant: bool | None
    suitable_rooms: list[str]
    price: Money


class MatchedProductList(BaseModel):
    items: list[MatchedProduct]
    total: int
    page: int
    per_page: int
    threshold: float


class WorkTypeOut(BaseModel):
    id: int
    code: str
    name: str
    products: int = Field(..., description="Товаров, принятых в подбор (уверенность ≥ порога или менеджер)")
    predicted: int = Field(..., description="Всего товаров, отнесённых моделью к типу")


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    work_type: str
    recommended_materials: list[str]
    room_types: list[str]
    repair_levels: list[str]
    min_humidity: int
    requires_moisture_resistant: bool
    surface: str
    calc_basis: str
    consumption_rate: float | None
    layers: int
    waste_percent: float
    consumption_formula: str
    labor_price: Money
    labor_unit: str


class MatchUpdate(BaseModel):
    work_type: str | None = Field(default=None,
                                  description="Новый тип работ или 'other' (не относится к работам); без поля — подтвердить")


class ConfirmRequest(BaseModel):
    """Какие товары подтвердить: список id и/или фильтр (уверенность, тип работ, поиск)."""

    ids: list[int] | None = Field(default=None, max_length=500)
    min_confidence: float | None = Field(default=None, ge=0, le=1)
    work_type: str | None = None
    q: str | None = None

    @model_validator(mode="after")
    def _has_filter(self):
        if not self.ids and self.min_confidence is None:
            raise ValueError("Укажите ids или min_confidence")
        return self


class ConfirmResponse(BaseModel):
    confirmed: int


class StatsResponse(BaseModel):
    products: int
    categories: int
    classified: int = Field(..., description="Товары, принятые в подбор: уверенность модели ≥ порога или менеджер")
    predicted: int = Field(..., description="Товары, которые модель отнесла к какому-либо типу работ")
    with_package: int = Field(..., description="Принятые товары с распознанной фасовкой")
    by_source: dict[str, int]
    rules: int
    import_state: str | None = None
    ml: dict[str, Any] = Field(default={}, description="Модель: энкодер, порог, метрики на отложенной выборке, распределение уверенности")
