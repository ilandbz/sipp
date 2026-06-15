from typing import Optional, Any
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

class IccCache(SQLModel, table=True):
    __tablename__ = "icc_cache"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    of_origen_id: int = Field(foreign_key="sipp.ordenes_fabricacion.id", index=True)
    of_destino_id: int = Field(foreign_key="sipp.ordenes_fabricacion.id", index=True)
    icc_score: float = Field(index=True)
    setup_total_min: float
    detalle_json: Optional[Any] = Field(default=None, sa_column=Column(JSONB))
    calculado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
