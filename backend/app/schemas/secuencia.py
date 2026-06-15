from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class ColaItemRead(BaseModel):
    secuencia_id: int
    maquina: str
    semana_inicio: date
    posicion: int
    codigo_of: str
    descripcion: Optional[str] = None
    medida_texto: Optional[str] = None
    material_id: Optional[int] = None
    material: Optional[str] = None
    gramaje: Optional[float] = None
    cilindro_id: Optional[int] = None
    num_colores: Optional[int] = None
    colores_detalle: Optional[str] = None
    cantidad_programada: Optional[float] = None
    fecha_entrega: Optional[date] = None
    costo_setup_min: float
    motivo_setup: Optional[str] = None
    inicio_estimado: Optional[datetime] = None
    fin_estimado: Optional[datetime] = None
    estado_secuencia: str
    estado_of: str

    model_config = {"from_attributes": True}
