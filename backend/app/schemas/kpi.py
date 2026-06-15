from pydantic import BaseModel
from datetime import date
from typing import Optional, List

class KpiSemanalRead(BaseModel):
    maquina: str
    fecha_inicio: date
    fecha_fin: date
    total_ordenes: int
    setup_total_horas: float
    utilizacion_pct: Optional[float] = None
    estado_semana: str

    model_config = {"from_attributes": True}

class IccMatrixResponse(BaseModel):
    matrix: List[dict]

class PlanSemanalRead(BaseModel):
    maquina: str
    semana_inicio: date
    semana_fin: date
    posicion: int
    codigo_of: str
    descripcion: Optional[str] = None
    medida_texto: Optional[str] = None
    mt_a_producir: Optional[float] = None
    setup_min: float
    setup_horas: float
    horas_produccion: Optional[float] = None
    horas_total_of: float
    motivo_setup: Optional[str] = None
    fecha_entrega: Optional[date] = None
    estado_secuencia: str

    model_config = {"from_attributes": True}

