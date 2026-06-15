from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class SecuenciaProduccion(SQLModel, table=True):
    __tablename__ = "secuencias_produccion"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    semana_id: int = Field(foreign_key="sipp.semanas_programacion.id", index=True)
    orden_fabricacion_id: int = Field(foreign_key="sipp.ordenes_fabricacion.id", index=True)
    posicion: int
    
    costo_setup_min: float = Field(default=0.0)
    motivo_setup: Optional[str] = Field(default=None)

    inicio_estimado: Optional[datetime] = Field(default=None)
    fin_estimado: Optional[datetime] = Field(default=None)

    estado: str = Field(default="PENDIENTE", max_length=20)
    bloqueada_por: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
