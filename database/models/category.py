from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db_engine import Base


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String)
    url_key: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[bool] = mapped_column(Boolean)
    depth_level: Mapped[int] = mapped_column(Integer)
    product_count: Mapped[int] = mapped_column(Integer, default=0)

    parent: Mapped["Category | None"] = relationship(
        back_populates="subcategories",
        remote_side=[id],
    )
    subcategories: Mapped[list["Category"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
    )
