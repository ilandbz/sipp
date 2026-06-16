from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, text

class Sesion(SQLModel, table=True):
    __tablename__ = "sesiones"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="sipp.usuarios.id")
    token: str = Field(max_length=100, unique=True, index=True)
    expira_en: datetime = Field(sa_column=Column(DateTime, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(DateTime, nullable=False, server_default=text("now()")),
        default_factory=datetime.utcnow
    )
