from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class UltimoEstadoMaquina(SQLModel, table=True):
    __tablename__ = "ultimo_estado_maquina"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    maquina_id: int = Field(foreign_key="sipp.maquinas.id", unique=True)
    ultima_of_id: Optional[int] = Field(default=None, foreign_key="sipp.ordenes_fabricacion.id")
    
    ancho_mm: Optional[float] = Field(default=None)
    alto_mm: Optional[float] = Field(default=None)
    fuelle_mm: Optional[float] = Field(default=None)
    
    cilindro_id: Optional[int] = Field(default=None, foreign_key="sipp.cilindros.id")
    material_id: Optional[int] = Field(default=None, foreign_key="sipp.materiales.id")
    color_principal: Optional[str] = Field(default=None, max_length=80)
    tipo_bolsa_num: Optional[int] = Field(default=None)
    
    actualizado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
