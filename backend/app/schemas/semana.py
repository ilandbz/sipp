from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class SemanaProgramacionBase(BaseModel):
    maquina_id: int
    fecha_inicio: date
    fecha_fin: date
    horas_disponibles: Optional[float] = None
    estado: str = "BORRADOR"
    created_by: Optional[str] = None

class SemanaProgramacionCreate(SemanaProgramacionBase):
    pass

class SemanaProgramacionUpdate(BaseModel):
    maquina_id: Optional[int] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    horas_disponibles: Optional[float] = None
    estado: Optional[str] = None
    created_by: Optional[str] = None

class SemanaProgramacionRead(SemanaProgramacionBase):
    id: int
    maquina_codigo: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
