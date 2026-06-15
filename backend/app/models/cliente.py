from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class Cliente(SQLModel, table=True):
    __tablename__ = "clientes"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    razon_social: str = Field(max_length=200)
    marca: Optional[str] = Field(default=None, max_length=100)
    vendedor: Optional[str] = Field(default=None, max_length=100)
    prioridad: int = Field(default=3)
    ruc: Optional[str] = Field(default=None, max_length=20)
    telefono: Optional[str] = Field(default=None, max_length=30)
    direccion: Optional[str] = Field(default=None)
    franquicia_id: Optional[int] = Field(default=4, foreign_key="sipp.franquicias.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
