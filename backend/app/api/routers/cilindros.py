from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.core.database import get_session
from app.models.cilindro import Cilindro
from app.schemas.maestros import CilindroRead, CilindroCreate, CilindroUpdate

router = APIRouter(prefix="/cilindros", tags=["Cilindros"])

@router.get("/", response_model=list[CilindroRead])
async def listar_cilindros(db: AsyncSession = Depends(get_session)):
    query = select(Cilindro).where(Cilindro.activo == True)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{id}", response_model=CilindroRead)
async def obtener_cilindro(id: int, db: AsyncSession = Depends(get_session)):
    cilindro = await db.get(Cilindro, id)
    if not cilindro:
        raise HTTPException(status_code=404, detail="Cilindro no encontrado")
    return cilindro

@router.post("/", response_model=CilindroRead, status_code=status.HTTP_201_CREATED)
async def crear_cilindro(body: CilindroCreate, db: AsyncSession = Depends(get_session)):
    cilindro = Cilindro(**body.model_dump())
    db.add(cilindro)
    await db.flush()
    await db.refresh(cilindro)
    return cilindro

@router.patch("/{id}", response_model=CilindroRead)
async def actualizar_cilindro(id: int, body: CilindroUpdate, db: AsyncSession = Depends(get_session)):
    cilindro = await db.get(Cilindro, id)
    if not cilindro:
        raise HTTPException(status_code=404, detail="Cilindro no encontrado")
    
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(cilindro, key, value)
        
    db.add(cilindro)
    await db.flush()
    await db.refresh(cilindro)
    return cilindro
