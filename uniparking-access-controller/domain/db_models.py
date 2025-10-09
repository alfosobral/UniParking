from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Index

class Base(DeclarativeBase): pass

class PlateAuthorization(Base):
    __tablename__ = "plate_authorizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plate: Mapped[str] = mapped_column(String(16), nullable=False)   # normalizada (upper, sin espacios)
    active: Mapped[int] = mapped_column(Integer, default=1)          # 1=activo, 0=inactivo

Index("ix_plate_authorizations_plate", PlateAuthorization.plate, unique=True)
