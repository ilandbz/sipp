from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class Usuario(SQLModel, table=True):
    __tablename__ = "usuarios"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, unique=True, index=True)
    password_hash: Optional[str] = Field(default=None, max_length=200)
    nombre_completo: Optional[str] = Field(default=None, max_length=150)
    rol: str = Field(max_length=30)
    activo: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
