from decimal import Decimal

from sqlalchemy import Boolean, Float, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.db_engine import Base


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String, unique=True, index=True)
    cod_good: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    marketing_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    result_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String)
    package_area: Mapped[float] = mapped_column(Float)
    quantity_in_package: Mapped[int] = mapped_column(Integer)
    price_per_m2: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(String)
    status: Mapped[bool] = mapped_column(Boolean)
    characteristics: Mapped[list] = mapped_column(JSONB, default=list)
