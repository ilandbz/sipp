from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from typing import Optional
from app.core.database import get_session
from app.models.cliente import Cliente
from app.schemas.maestros import ClienteRead, ClienteCreate, ClienteUpdate

router = APIRouter(prefix="/clientes", tags=["Clientes"])

@router.get("/", response_model=list[ClienteRead])
async def listar_clientes(buscar: Optional[str] = None, db: AsyncSession = Depends(get_session)):
    query = select(Cliente)
    if buscar:
        # Búsqueda insensible a mayúsculas usando ilike en razon_social
        query = query.where(Cliente.razon_social.ilike(f"%{buscar}%"))
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{id}", response_model=ClienteRead)
async def obtener_cliente(id: int, db: AsyncSession = Depends(get_session)):
    cliente = await db.get(Cliente, id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente

@router.post("/", response_model=ClienteRead, status_code=status.HTTP_201_CREATED)
async def crear_cliente(body: ClienteCreate, db: AsyncSession = Depends(get_session)):
    data = body.model_dump()
    data.pop("prioridad", None)
    cliente = Cliente(**data)
    db.add(cliente)
    await db.flush()
    await db.refresh(cliente)
    return cliente

@router.patch("/{id}", response_model=ClienteRead)
async def actualizar_cliente(id: int, body: ClienteUpdate, db: AsyncSession = Depends(get_session)):
    cliente = await db.get(Cliente, id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    update_data = body.model_dump(exclude_unset=True)
    update_data.pop("prioridad", None)
    for key, value in update_data.items():
        setattr(cliente, key, value)
        
    db.add(cliente)
    await db.flush()
    await db.refresh(cliente)
    return cliente

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_cliente(id: int, db: AsyncSession = Depends(get_session)):
    cliente = await db.get(Cliente, id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    from app.models.orden_fabricacion import OrdenFabricacion
    query_ofs = select(OrdenFabricacion).where(OrdenFabricacion.cliente_id == id)
    result = await db.execute(query_ofs)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="No se puede eliminar el cliente porque tiene Órdenes de Fabricación asociadas.")
        
    await db.delete(cliente)
    await db.commit()
    return None
