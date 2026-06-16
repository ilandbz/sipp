from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class Maquina(SQLModel, table=True):
    __tablename__ = "maquinas"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    codigo: str = Field(max_length=20, unique=True, index=True)
    nombre: str = Field(max_length=100)
    activa: bool = Field(default=True)
    velocidad_bpm_max: Optional[float] = Field(default=None)
    turno_horas: float = Field(default=8.0)
    dias_semana: int = Field(default=5)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
