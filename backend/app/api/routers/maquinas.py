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

@router.get("/{id}/cola", response_model=list[ColaItemRead])
async def cola_maquina(id: int, semana: str | None = None, semana_id: int | None = None, db: AsyncSession = Depends(get_session)):
    # Verificar si la máquina existe (si no existe, retornar 404)
    maquina = await db.get(Maquina, id)
    if not maquina:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")

    params = {"maquina_codigo": maquina.codigo}
    filtro = ""
    joins = ""
    if semana_id:
        joins = "JOIN sipp.maquinas m ON m.codigo = c.maquina JOIN sipp.semanas_programacion s ON s.fecha_inicio = c.semana_inicio AND s.maquina_id = m.id"
        filtro = "AND s.id = :semana_id"
        params["semana_id"] = semana_id
    elif semana:
        try:
            year, week_num = map(int, semana.split("-W"))
            fecha_inicio = date.fromisocalendar(year, week_num, 1)
            filtro = "AND c.semana_inicio = :semana_inicio"
            params["semana_inicio"] = fecha_inicio
        except ValueError:
            return []

    sql = text(f"""
        SELECT c.* FROM sipp.v_cola_produccion c
        {joins}
        WHERE c.maquina = :maquina_codigo
        {filtro}
        ORDER BY c.posicion
    """)
    result = await db.execute(sql, params)
    return result.mappings().all()
