from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.core.database import get_session
from app.models.material import Material
from app.schemas.maestros import MaterialRead, MaterialCreate, MaterialUpdate

router = APIRouter(prefix="/materiales", tags=["Materiales"])

@router.get("/", response_model=list[MaterialRead])
async def listar_materiales(db: AsyncSession = Depends(get_session)):
    query = select(Material)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{id}", response_model=MaterialRead)
async def obtener_material(id: int, db: AsyncSession = Depends(get_session)):
    material = await db.get(Material, id)
    if not material:
        raise HTTPException(status_code=404, detail="Material no encontrado")
    return material

@router.post("/", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def crear_material(body: MaterialCreate, db: AsyncSession = Depends(get_session)):
    material = Material(**body.model_dump())
    db.add(material)
    await db.flush()
    await db.refresh(material)
    return material

@router.patch("/{id}", response_model=MaterialRead)
async def actualizar_material(id: int, body: MaterialUpdate, db: AsyncSession = Depends(get_session)):
    from app.schemas.maestros import MaterialUpdate
    material = await db.get(Material, id)
    if not material:
        raise HTTPException(status_code=404, detail="Material no encontrado")
    
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(material, key, value)
        
    db.add(material)
    await db.flush()
    await db.refresh(material)
    return material

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_material(id: int, db: AsyncSession = Depends(get_session)):
    material = await db.get(Material, id)
    if not material:
        raise HTTPException(status_code=404, detail="Material no encontrado")
    await db.delete(material)
    await db.commit()
    return None
