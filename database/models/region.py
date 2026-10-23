from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.db_engine import Base


class Region(Base):
    """Справочник регионов (формат /api/regions из ТЗ).

    В products_final.json регионов и остатков нет — таблица пустая, пока
    организаторы не дадут выгрузку регионов.
    """

    __tablename__ = "region"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String)
    oracle_cod_city: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    warehouses_count: Mapped[int] = mapped_column(Integer, default=0)
