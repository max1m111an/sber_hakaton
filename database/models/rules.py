from decimal import Decimal

from sqlalchemy import Boolean, Float, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.db_engine import Base


class NormativeRule(Base):
    """Норматив расхода для одной работы (см. database/seed_rules.py)."""

    __tablename__ = "normative_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String)
    work_type: Mapped[str] = mapped_column(String(32), index=True)
    # типы материалов в порядке предпочтения
    recommended_materials: Mapped[list] = mapped_column(JSONB, default=list)
    # контекст: пустой список room_types — любое помещение
    room_types: Mapped[list] = mapped_column(JSONB, default=list)
    repair_levels: Mapped[list] = mapped_column(JSONB, default=list)
    min_humidity: Mapped[int] = mapped_column(Integer, default=0)
    requires_moisture_resistant: Mapped[bool] = mapped_column(Boolean, default=False)
    context_tags: Mapped[list] = mapped_column(JSONB, default=list)
    exclude_pattern: Mapped[str | None] = mapped_column(String, nullable=True)
    # расчёт
    surface: Mapped[str] = mapped_column(String(16))
    calc_basis: Mapped[str] = mapped_column(String(16))
    consumption_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    layers: Mapped[int] = mapped_column(Integer, default=1)
    waste_percent: Mapped[float] = mapped_column(Float, default=0)
    tiled: Mapped[bool] = mapped_column(Boolean, default=False)
    consumption_formula: Mapped[str] = mapped_column(Text)
    # работы (ориентировочно)
    labor_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    labor_unit: Mapped[str] = mapped_column(String(16), default="м²")
    priority: Mapped[int] = mapped_column(Integer, default=0)
