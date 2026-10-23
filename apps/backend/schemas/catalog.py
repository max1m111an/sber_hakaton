"""Схемы каталожного API в формате раздела 1 ТЗ («Источники данных»)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from apps.backend.schemas.common import Money


class NamedRef(BaseModel):
    id: int | None = None
    name: str | None = None


class CategoryNode(BaseModel):
    id: int
    parent_id: int | None = None
    name: str
    url_key: str
    status: bool
    depth_level: int
    product_count: int
    product_count_all_children: int
    work_type: str | None = Field(default=None, description="Тип работ (матчинг RepairCalc), если определён")
    children: list[CategoryNode] = []


class CategoryTreeResponse(BaseModel):
    data: list[CategoryNode]


class CategoryInfo(BaseModel):
    id: int
    parent_id: int | None = None
    name: str
    url_key: str
    status: bool
    depth_level: int
    product_count: int
    product_count_all_children: int
    description: str | None = None
    is_hide: str = "no"
    dat_show_b: str | None = None
    dat_show_e: str | None = None
    work_type: str | None = None


class CategoryListResponse(BaseModel):
    data: list[CategoryInfo]


class CategoryTreeItem(BaseModel):
    id: int
    name: str
    depth: int


class Property(BaseModel):
    name: str
    value: Any = None


class Characteristic(BaseModel):
    code: str | None = None
    name: str
    value: Any = None


class ProductListItem(BaseModel):
    id: int
    sku: str | None = None
    cod_good: str
    name: str
    marketing_description: str | None = None
    type: str = "simple"
    url_key: str | None = None
    price: Money
    result_price: Money
    currency: str
    quantity_in_package: int | None = None
    package_area: float | None = None
    price_per_m2: Money | None = None
    price_per_m2_unit: str | None = None
    status: bool
    brand: NamedRef | None = None
    collection: NamedRef | None = None
    country: NamedRef | None = None
    categories: dict[str, str] = {}
    categories_tree: list[CategoryTreeItem] | None = None
    unit: str | None = None
    propertiesBottom: list[Property] = []
    # поля RepairCalc
    work_type: str | None = None
    moisture_resistant: bool | None = None


class ProductCard(ProductListItem):
    description: str | None = None
    weight: float | None = None
    characteristics: list[Characteristic] = []
    package_weight_kg: float | None = None
    package_volume_l: float | None = None
    package_length_m: float | None = None
    pack_source: str | None = None
    consumption_rate: float | None = None
    match_confidence: float = 0
    match_source: str | None = None


class ProductCardResponse(BaseModel):
    data: ProductCard


class FilterValue(BaseModel):
    value: str
    label: str
    count: int
    is_available: bool = True


class FilterProperty(BaseModel):
    code: str
    name: str
    type: str = "text"
    values: list[FilterValue]


class Meta(BaseModel):
    total: int
    per_page: int
    current_page: int
    last_page: int


class ProductListResponse(BaseModel):
    items: list[ProductListItem]
    properties: list[FilterProperty] = []
    generated_url: str
    meta: Meta


class RegionOut(BaseModel):
    id: int
    code: str
    name: str
    oracle_cod_city: int | None = None
    priority: int = 0
    status: bool = True
    is_default: bool = False
    warehouses_count: int = 0


class RegionListResponse(BaseModel):
    data: list[RegionOut]
