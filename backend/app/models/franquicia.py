from typing import Optional
from sqlmodel import SQLModel, Field

class Franquicia(SQLModel, table=True):
    __tablename__ = "franquicias"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(max_length=100)
    nivel: int = Field(unique=True)
    descripcion: Optional[str] = Field(default=None)
