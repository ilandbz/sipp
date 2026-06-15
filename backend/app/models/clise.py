from typing import Optional
from sqlmodel import SQLModel, Field

class Clise(SQLModel, table=True):
    __tablename__ = "clises"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    codigo: str = Field(max_length=50, unique=True)
    descripcion: Optional[str] = Field(default=None, max_length=200)
    activo: bool = Field(default=True)
