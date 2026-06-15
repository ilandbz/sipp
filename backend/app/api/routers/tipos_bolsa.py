from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List

from app.core.database import get_session
from app.models.tipo_bolsa import TipoBolsa

router = APIRouter(prefix="/tipos-bolsa", tags=["Tipos de Bolsa"])

@router.get("/", response_model=List[TipoBolsa])
async def list_tipos_bolsa(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(TipoBolsa).where(TipoBolsa.activo == True).order_by(TipoBolsa.numero))
    return result.scalars().all()

from pydantic import BaseModel
class TipoBolsaUpdate(BaseModel):
    ancho_std_mm: float | None = None
    alto_std_mm: float | None = None
    fuelle_std_mm: float | None = None

@router.patch("/{id}", response_model=TipoBolsa)
async def actualizar_tipo_bolsa(id: int, body: TipoBolsaUpdate, db: AsyncSession = Depends(get_session)):
    bolsa = await db.get(TipoBolsa, id)
    if not bolsa:
        raise HTTPException(status_code=404, detail="Tipo de bolsa no encontrado")
    
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(bolsa, key, value)
        
    db.add(bolsa)
    await db.flush()
    await db.refresh(bolsa)
    return bolsa
