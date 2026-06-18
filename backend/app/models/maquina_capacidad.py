from typing import Optional
from sqlmodel import SQLModel, Field

class MaquinaCapacidad(SQLModel, table=True):
    __tablename__ = "maquina_capacidades"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    maquina_id: int = Field(foreign_key="sipp.maquinas.id", unique=True)
    ancho_min_mm: Optional[float] = Field(default=None)
    ancho_max_mm: Optional[float] = Field(default=None)
    alto_min_mm: Optional[float] = Field(default=None)
    alto_max_mm: Optional[float] = Field(default=None)
    fuelle_max_mm: Optional[float] = Field(default=None)
    descripcion: Optional[str] = Field(default=None)
