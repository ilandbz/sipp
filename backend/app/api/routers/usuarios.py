from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List

from app.core.database import get_session
from app.models.usuario import Usuario

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

@router.get("/", response_model=List[Usuario])
async def list_usuarios(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Usuario).where(Usuario.activo == True).order_by(Usuario.username))
    return result.scalars().all()
