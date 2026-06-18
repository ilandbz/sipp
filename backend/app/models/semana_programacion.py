from typing import Optional
from datetime import date, datetime, timezone
from sqlmodel import SQLModel, Field

class SemanaProgramacion(SQLModel, table=True):
    __tablename__ = "semanas_programacion"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    maquina_id: Optional[int] = Field(default=None, foreign_key="sipp.maquinas.id")
    fecha_inicio: date
    fecha_fin: date
    horas_disponibles: Optional[float] = Field(default=None)
    estado: str = Field(default="BORRADOR", max_length=20)
    es_global: bool = Field(default=False)
    created_by: Optional[str] = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
