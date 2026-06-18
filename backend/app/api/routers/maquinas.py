from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from sqlalchemy import text
from datetime import date
from app.core.database import get_session
from app.models.maquina import Maquina
from app.schemas.maestros import MaquinaRead, MaquinaCreate, MaquinaUpdate
from app.schemas.secuencia import ColaItemRead

router = APIRouter(prefix="/maquinas", tags=["Máquinas"])

@router.get("/", response_model=list[MaquinaRead])
async def listar_maquinas(db: AsyncSession = Depends(get_session)):
    query = select(Maquina).where(Maquina.activa == True)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{id}", response_model=MaquinaRead)
async def obtener_maquina(id: int, db: AsyncSession = Depends(get_session)):
    maquina = await db.get(Maquina, id)
    if not maquina:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")
    return maquina

@router.post("/", response_model=MaquinaRead, status_code=status.HTTP_201_CREATED)
async def crear_maquina(body: MaquinaCreate, db: AsyncSession = Depends(get_session)):
    maquina = Maquina(**body.model_dump())
    db.add(maquina)
    await db.flush()
    await db.refresh(maquina)
    return maquina

@router.patch("/{id}", response_model=MaquinaRead)
async def actualizar_maquina(id: int, body: MaquinaUpdate, db: AsyncSession = Depends(get_session)):
    maquina = await db.get(Maquina, id)
    if not maquina:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")
    
    old_speed = maquina.velocidad_bpm_max
    
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(maquina, key, value)
        
    db.add(maquina)
    
    if "velocidad_bpm_max" in update_data and update_data["velocidad_bpm_max"] != old_speed:
        from app.models.orden_fabricacion import OrdenFabricacion
        query = select(OrdenFabricacion).where(OrdenFabricacion.maquina_asignada_id == id).where(OrdenFabricacion.estado == "PENDIENTE")
        pending_orders = await db.execute(query)
        for order in pending_orders.scalars().all():
            if order.cantidad_programada and maquina.velocidad_bpm_max:
                order.horas_produccion = (order.cantidad_programada * 1000) / (maquina.velocidad_bpm_max * 60)
            db.add(order)
            
    await db.flush()
    await db.refresh(maquina)
    return maquina

@router.get("/{id}/capacidad")
async def obtener_capacidad(id: int, db: AsyncSession = Depends(get_session)):
    from app.models.maquina_capacidad import MaquinaCapacidad
    query = select(MaquinaCapacidad).where(MaquinaCapacidad.maquina_id == id)
    res = await db.execute(query)
    cap = res.scalars().first()
    if not cap:
        return {} # Retornar un diccionario vacío si no hay capacidades definidas
    return cap

from pydantic import BaseModel
class MaquinaCapacidadUpdate(BaseModel):
    ancho_min_mm: float | None = None
    ancho_max_mm: float | None = None
    alto_min_mm: float | None = None
    alto_max_mm: float | None = None
    fuelle_max_mm: float | None = None

@router.patch("/{id}/capacidad")
async def actualizar_capacidad(id: int, body: MaquinaCapacidadUpdate, db: AsyncSession = Depends(get_session)):
    from app.models.maquina_capacidad import MaquinaCapacidad
    query = select(MaquinaCapacidad).where(MaquinaCapacidad.maquina_id == id)
    res = await db.execute(query)
    cap = res.scalars().first()
    if not cap:
        cap = MaquinaCapacidad(maquina_id=id)
        db.add(cap)
        
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(cap, key, value)
        
    db.add(cap)
    await db.flush()
    await db.commit()
    await db.refresh(cap)
    return cap

@router.get("/{id}/cola")
async def cola_maquina(id: int,
                       semana_id: int = None,
                       semana: str = None,
                       db: AsyncSession = Depends(get_session)):
    from sqlalchemy import text
    
    filtros = ["of.maquina_asignada_id = :maq_id"]
    params  = {"maq_id": id}
    
    if semana_id:
        filtros.append("sp.semana_id = :semana_id")
        params["semana_id"] = semana_id
    
    sql = text(f"""
        SELECT
            sp.posicion,
            of.codigo_of,
            of.medida_texto,
            mat.tipo        AS material,
            of.colores_detalle,
            sp.costo_setup_min,
            sp.motivo_setup,
            of.fecha_entrega,
            of.horas_produccion,
            sp.estado       AS estado_secuencia,
            of.estado       AS estado_of,
            m.codigo        AS maquina
        FROM sipp.secuencias_produccion sp
        JOIN sipp.ordenes_fabricacion   of  ON of.id  = sp.orden_fabricacion_id
        JOIN sipp.semanas_programacion  s   ON s.id   = sp.semana_id
        JOIN sipp.maquinas              m   ON m.id   = of.maquina_asignada_id
        LEFT JOIN sipp.materiales       mat ON mat.id = of.material_id
        WHERE {" AND ".join(filtros)}
        ORDER BY sp.posicion
    """)
    
    result = await db.execute(sql, params)
    return result.mappings().all()
