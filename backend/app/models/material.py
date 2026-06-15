from typing import Optional
from sqlmodel import SQLModel, Field

class Material(SQLModel, table=True):
    __tablename__ = "materiales"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    tipo: str = Field(max_length=80, unique=True)
    gramaje_min: Optional[float] = Field(default=None)
    gramaje_max: Optional[float] = Field(default=None)
    factor_velocidad: float = Field(default=1.000)
    descripcion: Optional[str] = Field(default=None)
