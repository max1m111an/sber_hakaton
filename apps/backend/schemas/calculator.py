from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GeneralCalcRequest(BaseModel):
    object_type: str = Field(..., min_length=1, examples=["квартира"])
    repair_variant: str = Field(..., min_length=1, examples=["капитальный"])
    area: float = Field(..., gt=0)


class EstimateItem(BaseModel):
    product_id: int
    sku: str
    name: str
    category_id: int | None = None
    category_name: str | None = None
    package_area: float
    packages_needed: int
    units_needed: int
    price_per_package: Decimal
    subtotal: Decimal


class GeneralCalcResponse(BaseModel):
    area: float
    object_type: str
    repair_variant: str
    items: list[EstimateItem] = []
    total_cost: Decimal = Decimal("0")
    currency: str = "RUB"
    notes: list[str] = []


class RoomCalcRequest(BaseModel):
    room_type: str = Field(..., min_length=1, examples=["санузел"])
    repair_type: str = Field(..., min_length=1, examples=["капитальный"])
    area: float = Field(..., gt=0)
    humidity_level: str = Field(..., min_length=1, examples=["высокая"])
    load_level: str = Field(..., min_length=1, examples=["высокая"])


class RuleMatch(BaseModel):
    rule_id: int
    matched_tags: list[str]
    context_tags: list[str]
    recommended_materials: list[str]
    consumption_formula: str | None = None


class RecommendedProduct(BaseModel):
    product_id: int
    sku: str
    name: str
    category_id: int | None = None
    category_name: str | None = None
    result_price: Decimal
    price_per_m2: Decimal
    package_area: float
    packages_needed: int
    units_needed: int
    subtotal: Decimal
    matched_tags: list[str] = []


class RoomCalcResponse(BaseModel):
    area: float
    room_type: str
    repair_type: str
    matched_rules: list[RuleMatch] = []
    products: list[RecommendedProduct] = []
    total_cost: Decimal = Decimal("0")
    currency: str = "RUB"
    notes: list[str] = []


class ProductCalcRequest(BaseModel):
    area: float = Field(..., gt=0)


class ProductCalcResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    sku: str
    area: float
    package_area: float
    quantity_in_package: int
    packages_needed: int
    units_needed: int
    price_per_package: Decimal
    price_per_m2: Decimal
    total_cost: Decimal
    currency: str
    formula_hint: str = "packages = ceil(area / package_area); total = packages * result_price"
    detail: dict[str, Any] = {}
