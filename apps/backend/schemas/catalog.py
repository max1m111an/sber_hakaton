from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None = None
    name: str
    url_key: str
    description: str | None = None
    status: bool
    depth_level: int
    product_count: int


class CategoryTreeNode(CategoryOut):
    subcategories: list["CategoryTreeNode"] = []


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    cod_good: str
    name: str
    description: str
    marketing_description: str | None = None
    price: Decimal
    result_price: Decimal
    currency: str
    package_area: float
    quantity_in_package: int
    price_per_m2: Decimal
    unit: str
    status: bool
    characteristics: list[Any] = []
    category_id: int | None = None
