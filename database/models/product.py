from decimal import Decimal

from sqlalchemy import Boolean, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db_engine import Base
from database.models.category import Category


class Product(Base):
    """Товар каталога.

    Поля 1-в-1 из выгрузки (id, cod_good, name, ...), плюс производные поля,
    которые импорт вычисляет из характеристик: фасовка, влагостойкость, тип работ.
    """

    __tablename__ = "product"

    # --- поля выгрузки / API каталога
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    cod_good: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    marketing_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(32), default="simple")
    url_key: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    result_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), index=True)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    brand: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    collection: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    country: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, default=True)
    characteristics: Mapped[list] = mapped_column(JSONB, default=list)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # --- фасовка (из характеристик и названия)
    package_area: Mapped[float | None] = mapped_column(Float, nullable=True)        # м² в упаковке
    quantity_in_package: Mapped[int | None] = mapped_column(Integer, nullable=True)
    package_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    package_volume_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    package_length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    pack_source: Mapped[str | None] = mapped_column(String, nullable=True)          # откуда взята фасовка
    price_per_m2: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    consumption_rate: Mapped[float | None] = mapped_column(Float, nullable=True)    # расход из карточки

    # --- матчинг к типам работ
    moisture_resistant: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    work_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    match_confidence: Mapped[float] = mapped_column(Float, default=0)
    match_source: Mapped[str | None] = mapped_column(String(16), nullable=True)

    category: Mapped[Category | None] = relationship(back_populates="products")
