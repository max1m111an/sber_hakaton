from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.db_engine import Base


class WorkType(Base):
    """Справочник типов работ (постоянные id из database/work_types.py)."""

    __tablename__ = "work_type"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String)


class MLModel(Base):
    """Обученные версии ML-матчинга: метрики на отложенной выборке и статистика предсказаний."""

    __tablename__ = "ml_model"

    id: Mapped[int] = mapped_column(primary_key=True)
    encoder: Mapped[str] = mapped_column(String)
    trained_at: Mapped[float] = mapped_column(Float)
    train_size: Mapped[int] = mapped_column(Integer)
    threshold: Mapped[float] = mapped_column(Float)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    prediction_stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
