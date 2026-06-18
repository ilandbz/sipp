from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# --- FRANQUICIA ---
class FranquiciaBase(BaseModel):
    nombre: str
    nivel: int
    descripcion: Optional[str] = None

class FranquiciaUpdate(BaseModel):
    descripcion: Optional[str] = None

class FranquiciaRead(FranquiciaBase):
    id: int
    model_config = {"from_attributes": True}

# --- MAQUINA ---
class MaquinaBase(BaseModel):
    codigo: str
    nombre: str
    activa: bool = True
    velocidad_bpm_max: Optional[float] = None
    turno_horas: float = 8.0
    dias_semana: int = 5

class MaquinaCreate(MaquinaBase):
    pass

class MaquinaUpdate(BaseModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    activa: Optional[bool] = None
    velocidad_bpm_max: Optional[float] = None
    turno_horas: Optional[float] = None
    dias_semana: Optional[int] = None

class MaquinaRead(MaquinaBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

# --- MAQUINA CAPACIDAD ---
class MaquinaCapacidadBase(BaseModel):
    ancho_min_mm: Optional[float] = None
    ancho_max_mm: Optional[float] = None
    alto_min_mm: Optional[float] = None
    alto_max_mm: Optional[float] = None
    fuelle_max_mm: Optional[float] = None
    descripcion: Optional[str] = None

class MaquinaCapacidadUpdate(MaquinaCapacidadBase):
    pass

class MaquinaCapacidadRead(MaquinaCapacidadBase):
    id: int
    maquina_id: int
    model_config = {"from_attributes": True}


# --- CLIENTE ---
class ClienteBase(BaseModel):
    razon_social: str
    marca: Optional[str] = None
    vendedor: Optional[str] = None
    prioridad: int = 3
    ruc: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    franquicia_id: Optional[int] = 4

class ClienteCreate(ClienteBase):
    pass

class ClienteUpdate(BaseModel):
    razon_social: Optional[str] = None
    marca: Optional[str] = None
    vendedor: Optional[str] = None
    prioridad: Optional[int] = None
    ruc: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    franquicia_id: Optional[int] = None

class ClienteRead(ClienteBase):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}


# --- MATERIAL ---
class MaterialBase(BaseModel):
    tipo: str
    gramaje_min: Optional[float] = None
    gramaje_max: Optional[float] = None
    factor_velocidad: float = 1.000
    descripcion: Optional[str] = None

class MaterialCreate(MaterialBase):
    pass

class MaterialUpdate(BaseModel):
    tipo: Optional[str] = None
    gramaje_min: Optional[float] = None
    gramaje_max: Optional[float] = None
    factor_velocidad: Optional[float] = None
    descripcion: Optional[str] = None

class MaterialRead(MaterialBase):
    id: int
    model_config = {"from_attributes": True}


# --- CILINDRO ---
class CilindroBase(BaseModel):
    codigo: str
    descripcion: Optional[str] = None
    activo: bool = True

class CilindroCreate(CilindroBase):
    pass

class CilindroUpdate(BaseModel):
    codigo: Optional[str] = None
    descripcion: Optional[str] = None
    activo: Optional[bool] = None

class CilindroRead(CilindroBase):
    id: int
    model_config = {"from_attributes": True}


# --- CLISE ---
class CliseBase(BaseModel):
    codigo: str
    descripcion: Optional[str] = None
    activo: bool = True

class CliseCreate(CliseBase):
    pass

class CliseUpdate(BaseModel):
    codigo: Optional[str] = None
    descripcion: Optional[str] = None
    activo: Optional[bool] = None

class CliseRead(CliseBase):
    id: int
    model_config = {"from_attributes": True}
