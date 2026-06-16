from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class SetupHistorial(SQLModel, table=True):
    __tablename__ = "setups_historial"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    secuencia_id: Optional[int] = Field(default=None, foreign_key="sipp.secuencias_produccion.id")
    of_anterior_id: Optional[int] = Field(default=None, foreign_key="sipp.ordenes_fabricacion.id")
    of_siguiente_id: Optional[int] = Field(default=None, foreign_key="sipp.ordenes_fabricacion.id")
    maquina_id: Optional[int] = Field(default=None, foreign_key="sipp.maquinas.id")
    setup_estimado_min: Optional[float] = Field(default=None)
    setup_real_min: Optional[float] = Field(default=None)
    inicio_setup: Optional[datetime] = Field(default=None)
    fin_setup: Optional[datetime] = Field(default=None)
    hubo_cambio_formato: bool = Field(default=False)
    hubo_cambio_color: bool = Field(default=False)
    hubo_cambio_cilindro: bool = Field(default=False)
    hubo_cambio_clise: bool = Field(default=False)
    hubo_cambio_material: bool = Field(default=False)
    observacion: Optional[str] = Field(default=None)
    registrado_por: Optional[str] = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
