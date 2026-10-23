from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db_engine import Base


class Category(Base):
    """Категория каталога. ID и url_key — из выгрузки maxidom.ru."""

    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String, index=True)
    url_key: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, default=True)
    depth_level: Mapped[int] = mapped_column(Integer, default=1)
    product_count: Mapped[int] = mapped_column(Integer, default=0)
    # тип работ, если большинство товаров категории к нему отнесено (classifier.py)
    work_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    parent: Mapped["Category | None"] = relationship(
        back_populates="subcategories",
        remote_side=[id],
    )
    subcategories: Mapped[list["Category"]] = relationship(back_populates="parent")
    products: Mapped[list["Product"]] = relationship(back_populates="category")  # noqa: F821
