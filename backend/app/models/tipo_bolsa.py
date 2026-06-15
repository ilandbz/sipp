from typing import Optional
from sqlmodel import SQLModel, Field

class TipoBolsa(SQLModel, table=True):
    __tablename__ = "tipos_bolsa"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    numero: int = Field(unique=True, index=True)
    descripcion: Optional[str] = Field(default=None, max_length=100)
    ancho_std_mm: Optional[float] = Field(default=None)
    alto_std_mm: Optional[float] = Field(default=None)
    fuelle_std_mm: Optional[float] = Field(default=None)
    activo: bool = Field(default=True)
