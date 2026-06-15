from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.core.database import get_session
from app.models.franquicia import Franquicia
from app.schemas.maestros import FranquiciaRead, FranquiciaUpdate

router = APIRouter(prefix="/franquicias", tags=["Franquicias"])

@router.get("/", response_model=list[FranquiciaRead])
async def listar_franquicias(db: AsyncSession = Depends(get_session)):
    query = select(Franquicia).order_by(Franquicia.nivel)
    result = await db.execute(query)
    return result.scalars().all()

@router.patch("/{id}", response_model=FranquiciaRead)
async def actualizar_franquicia(id: int, body: FranquiciaUpdate, db: AsyncSession = Depends(get_session)):
    franquicia = await db.get(Franquicia, id)
    if not franquicia:
        raise HTTPException(status_code=404, detail="Franquicia no encontrada")
    
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(franquicia, key, value)
        
    db.add(franquicia)
    await db.flush()
    await db.refresh(franquicia)
    return franquicia
