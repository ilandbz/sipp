from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class Parada(SQLModel, table=True):
    __tablename__ = "paradas"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    maquina_id: int = Field(foreign_key="sipp.maquinas.id")
    inicio: datetime
    fin: datetime
    tipo: str = Field(max_length=40)
    descripcion: Optional[str] = Field(default=None)
    
    # horas_perdidas is GENERATED ALWAYS in the db, so we can make it optional and not insert it.
    horas_perdidas: Optional[float] = Field(default=None)
    
    registrado_por: Optional[str] = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
