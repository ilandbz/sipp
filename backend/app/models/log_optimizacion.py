from typing import Optional, Any
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

class LogOptimizacion(SQLModel, table=True):
    __tablename__ = "log_optimizaciones"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    semana_id: Optional[int] = Field(default=None, foreign_key="sipp.semanas_programacion.id")
    maquina_id: Optional[int] = Field(default=None, foreign_key="sipp.maquinas.id")
    algoritmo: str = Field(default="HEURISTICO_PRIORIDAD_SMED", max_length=50)
    ordenes_evaluadas: Optional[int] = Field(default=None)
    setup_total_antes_min: Optional[float] = Field(default=None)
    setup_total_despues_min: Optional[float] = Field(default=None)
    reduccion_pct: Optional[float] = Field(default=None)
    duracion_ms: Optional[int] = Field(default=None)
    resultado_json: Optional[Any] = Field(default=None, sa_column=Column(JSONB))
    ejecutado_por: Optional[str] = Field(default=None, max_length=100)
    ejecutado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
