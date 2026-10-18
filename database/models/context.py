from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from database.db_engine import Base


class RoomContext(Base):
    __tablename__ = "room_context"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_type: Mapped[str] = mapped_column(String)
    repair_type: Mapped[str] = mapped_column(String)
    area: Mapped[float] = mapped_column(Float)
    humidity_level: Mapped[str] = mapped_column(String)
    load_level: Mapped[str] = mapped_column(String)
