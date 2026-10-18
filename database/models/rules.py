from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.db_engine import Base


class NormativeRule(Base):
    __tablename__ = "normative_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    context_tags: Mapped[list] = mapped_column(JSONB, default=list)
    recommended_materials: Mapped[list] = mapped_column(JSONB, default=list)
    consumption_formula: Mapped[str] = mapped_column(Text)
