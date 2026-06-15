from typing import Optional
from sqlmodel import SQLModel, Field

class Cilindro(SQLModel, table=True):
    __tablename__ = "cilindros"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    codigo: str = Field(max_length=30, unique=True)
    descripcion: Optional[str] = Field(default=None, max_length=200)
    activo: bool = Field(default=True)
