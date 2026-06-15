from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class DisponibilidadMaquina(SQLModel, table=True):
    __tablename__ = "disponibilidad_maquinas"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    maquina_id: int = Field(foreign_key="sipp.maquinas.id")
    fecha_inicio: datetime
    fecha_fin: datetime
    tipo: str = Field(max_length=40)
    descripcion: Optional[str] = Field(default=None)
    horas_bloqueadas: Optional[float] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
