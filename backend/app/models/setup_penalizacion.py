from typing import Optional
from sqlmodel import SQLModel, Field

class SetupPenalizacion(SQLModel, table=True):
    __tablename__ = "setup_penalizaciones"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    tipo_cambio: str = Field(max_length=80, unique=True)
    minutos: float
    descripcion: Optional[str] = Field(default=None)
    activo: bool = Field(default=True)
