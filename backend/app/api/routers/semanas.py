from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, text
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime, timedelta, timezone
from pydantic import BaseModel

from app.core.database import get_session
from app.models.semana_programacion import SemanaProgramacion
from app.models.maquina import Maquina
from app.models.disponibilidad_maquina import DisponibilidadMaquina
from app.models.secuencia_produccion import SecuenciaProduccion
from app.models.orden_fabricacion import OrdenFabricacion
from app.models.material import Material
from app.schemas.semana import SemanaProgramacionRead, SemanaProgramacionCreate, SemanaProgramacionUpdate
from app.schemas.orden import OrdenFabricacionRead

router = APIRouter(prefix="/semanas", tags=["Semanas"])

@router.get("/", response_model=List[SemanaProgramacionRead])
async def listar_semanas(db: AsyncSession = Depends(get_session)):
    query = select(
        SemanaProgramacion,
        Maquina.codigo.label("maquina_codigo")
    ).join(
        Maquina, Maquina.id == SemanaProgramacion.maquina_id, isouter=True
    ).order_by(SemanaProgramacion.fecha_inicio.desc())
    
    result = await db.execute(query)
    rows = result.all()
    
    semanas_read = []
    for row in rows:
        sem = row[0]
        sem_data = sem.model_dump()
        if sem.es_global:
            sem_data["maquina_codigo"] = "GLOBAL"
        else:
            sem_data["maquina_codigo"] = row[1]
        semanas_read.append(SemanaProgramacionRead(**sem_data))
        
    return semanas_read

@router.post("/", response_model=SemanaProgramacionRead, status_code=status.HTTP_201_CREATED)
async def crear_semana(body: SemanaProgramacionCreate, db: AsyncSession = Depends(get_session)):
    if body.es_global:
        body.maquina_id = None
        maquina = None
        stmt_check = select(SemanaProgramacion).where(
            SemanaProgramacion.es_global == True,
            SemanaProgramacion.fecha_inicio == body.fecha_inicio
        )
    else:
        maquina = await db.get(Maquina, body.maquina_id)
        if not maquina:
            raise HTTPException(status_code=404, detail="Máquina no encontrada")
        stmt_check = select(SemanaProgramacion).where(
            SemanaProgramacion.maquina_id == body.maquina_id,
            SemanaProgramacion.fecha_inicio == body.fecha_inicio
        )
        
    res_check = await db.execute(stmt_check)
    if res_check.scalars().first():
        raise HTTPException(status_code=400, detail="Ya existe una semana para estas condiciones")

    # Calcular dias hábiles
    dias_habiles = 0
    curr = body.fecha_inicio
    while curr <= body.fecha_fin:
        if curr.weekday() < 5:
            dias_habiles += 1
        curr += timedelta(days=1)
        
    horas_disponibles = dias_habiles * 8.0
    if body.es_global:
        horas_disponibles *= 3
    
    semana = SemanaProgramacion(
        maquina_id=body.maquina_id,
        fecha_inicio=body.fecha_inicio,
        fecha_fin=body.fecha_fin,
        horas_disponibles=horas_disponibles,
        estado=body.estado or "BORRADOR",
        es_global=body.es_global,
        created_by=body.created_by
    )
    
    for field_name in ["created_at", "updated_at"]:
        val = getattr(semana, field_name, None)
        if isinstance(val, datetime) and val.tzinfo is not None:
            setattr(semana, field_name, val.replace(tzinfo=None))
            
    db.add(semana)
    await db.flush()
    await db.commit()
    
    sem_data = semana.model_dump()
    sem_data["maquina_codigo"] = "GLOBAL" if body.es_global else maquina.codigo
    return SemanaProgramacionRead(**sem_data)

@router.get("/activa")
async def obtener_semana_activa(db: AsyncSession = Depends(get_session)):
    stmt = select(SemanaProgramacion).where(
        SemanaProgramacion.estado.in_(['BORRADOR','EN_EJECUCION','CONFIRMADA'])
    ).order_by(SemanaProgramacion.fecha_inicio.desc()).limit(1)
    res = await db.execute(stmt)
    semana = res.scalars().first()
    
    if not semana:
        return None
        
    sem_data = semana.model_dump()
    if semana.es_global:
        sem_data["maquina_codigo"] = "GLOBAL"
    else:
        maquina = await db.get(Maquina, semana.maquina_id)
        sem_data["maquina_codigo"] = maquina.codigo if maquina else None
        
    # Calcular resumen
    stmt_seq = select(SecuenciaProduccion, OrdenFabricacion).join(
        OrdenFabricacion, OrdenFabricacion.id == SecuenciaProduccion.orden_fabricacion_id
    ).where(SecuenciaProduccion.semana_id == semana.id)
    res_seq = await db.execute(stmt_seq)
    
    resumen = {"total_ofs": 0, "horas_usadas": {}}
    for sp, of in res_seq.all():
        resumen["total_ofs"] += 1
        maq_id = of.maquina_asignada_id
        if maq_id not in resumen["horas_usadas"]:
            resumen["horas_usadas"][maq_id] = 0.0
        resumen["horas_usadas"][maq_id] += float(of.horas_produccion or 0) + (float(sp.costo_setup_min) / 60.0)
        
    sem_data["resumen"] = resumen
    return sem_data

@router.get("/{id}")
async def obtener_semana_detalle(id: int, db: AsyncSession = Depends(get_session)):
    semana = await db.get(SemanaProgramacion, id)
    if not semana:
        raise HTTPException(status_code=404, detail="Semana de programación no encontrada")
        
    maquina = await db.get(Maquina, semana.maquina_id)
    maquina_codigo = maquina.codigo if maquina else None
    
    # Obtener secuencias asociadas
    query_seq = select(
        SecuenciaProduccion,
        OrdenFabricacion.codigo_of,
        OrdenFabricacion.descripcion,
        OrdenFabricacion.medida_texto,
        OrdenFabricacion.estado.label("estado_of"),
        Material.tipo.label("material_nombre")
    ).join(
        OrdenFabricacion, OrdenFabricacion.id == SecuenciaProduccion.orden_fabricacion_id
    ).join(
        Material, Material.id == OrdenFabricacion.material_id, isouter=True
    ).where(
        SecuenciaProduccion.semana_id == id
    ).order_by(SecuenciaProduccion.posicion.asc())
    
    res_seq = await db.execute(query_seq)
    rows = res_seq.all()
    
    secuencias_list = []
    for r in rows:
        sp = r[0]
        sp_data = sp.model_dump()
        sp_data["codigo_of"] = r[1]
        sp_data["descripcion"] = r[2]
        sp_data["medida_texto"] = r[3]
        sp_data["estado_of"] = r[4]
        sp_data["material"] = r[5]
        secuencias_list.append(sp_data)
        
    sem_data = semana.model_dump()
    sem_data["maquina_codigo"] = maquina_codigo
    
    return {
        "semana": sem_data,
        "secuencias": secuencias_list
    }

class EstadoUpdate(BaseModel):
    estado: str

@router.patch("/{id}/estado")
async def cambiar_estado_semana(id: int, body: EstadoUpdate, db: AsyncSession = Depends(get_session)):
    semana = await db.get(SemanaProgramacion, id)
    if not semana:
        raise HTTPException(status_code=404, detail="Semana de programación no encontrada")
        
    semana.estado = body.estado
    db.add(semana)
    await db.flush()
    await db.commit()
    
    return {"status": "ok", "semana_id": id, "nuevo_estado": body.estado}

@router.get("/{semana_id}/ofs-disponibles", response_model=List[OrdenFabricacionRead])
async def ofs_disponibles(semana_id: int, db: AsyncSession = Depends(get_session)):
    semana = await db.get(SemanaProgramacion, semana_id)
    if not semana:
        raise HTTPException(status_code=404, detail="Semana de programación no encontrada")
    
    subquery = select(SecuenciaProduccion.orden_fabricacion_id)
    stmt = select(OrdenFabricacion).where(
        OrdenFabricacion.maquina_asignada_id == semana.maquina_id,
        OrdenFabricacion.estado == "PENDIENTE",
        OrdenFabricacion.id.not_in(subquery)
    ).order_by(OrdenFabricacion.fecha_entrega.asc(), OrdenFabricacion.codigo_of.asc())
    
    res = await db.execute(stmt)
    return res.scalars().all()

class AgregarOfRequest(BaseModel):
    of_id: int

@router.post("/{semana_id}/agregar-of", status_code=201)
async def agregar_of(
    semana_id: int,
    body: AgregarOfRequest,
    db: AsyncSession = Depends(get_session)
):
    try:
        # 1. Verificar que la semana existe
        semana = await db.get(SemanaProgramacion, semana_id)
        if not semana:
            raise HTTPException(404, "Semana no encontrada")
        
        # 2. Verificar que la OF existe
        of = await db.get(OrdenFabricacion, body.of_id)
        if not of:
            raise HTTPException(404, "Orden de fabricación no encontrada")
            
        # Asignar máquina automáticamente si no la tiene y la semana es global
        if semana.es_global and not of.maquina_asignada_id:
            from app.services.asignador import sugerir_maquina
            sugerencias = await sugerir_maquina(db, of.id)
            if sugerencias:
                mejor_maq_id = sugerencias[0]["maquina_id"]
                of.maquina_asignada_id = mejor_maq_id
                db.add(of)
                await db.flush()
        
        # 3. Verificar que la OF no está ya en una secuencia
        from sqlmodel import select
        existe = await db.execute(
            select(SecuenciaProduccion).where(
                SecuenciaProduccion.orden_fabricacion_id == body.of_id
            )
        )
        if existe.scalar_one_or_none():
            raise HTTPException(400, "Esta OF ya está asignada a una semana de producción")
        
        # 4. Calcular siguiente posición
        count_result = await db.execute(
            select(func.count(SecuenciaProduccion.id)).where(
                SecuenciaProduccion.semana_id == semana_id
            )
        )
        siguiente_pos = (count_result.scalar() or 0) + 1
        
        # 5. Crear la secuencia usando los nombres EXACTOS de campos del modelo
        nueva_secuencia = SecuenciaProduccion(
            semana_id=semana_id,
            orden_fabricacion_id=body.of_id,
            posicion=siguiente_pos,
            costo_setup_min=0.0,
            motivo_setup="Asignación manual",
            estado="PENDIENTE"
        )
        
        # Strip tz to avoid asyncpg DataError
        for field_name in ["created_at", "updated_at"]:
            val = getattr(nueva_secuencia, field_name, None)
            if isinstance(val, datetime) and val.tzinfo is not None:
                setattr(nueva_secuencia, field_name, val.replace(tzinfo=None))

        db.add(nueva_secuencia)
        await db.flush()
        await db.commit()
        await db.refresh(nueva_secuencia)
        return nueva_secuencia
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)} | {traceback.format_exc()}"
        )

class ReordenarRequest(BaseModel):
    orden: List[int]

@router.put("/{semana_id}/reordenar")
async def reordenar_semana(semana_id: int, body: ReordenarRequest, db: AsyncSession = Depends(get_session)):
    semana = await db.get(SemanaProgramacion, semana_id)
    if not semana:
        raise HTTPException(404, "Semana no encontrada")

    res_seq = await db.execute(select(SecuenciaProduccion).where(SecuenciaProduccion.semana_id == semana_id))
    secuencias = res_seq.scalars().all()
    seq_map = {s.orden_fabricacion_id: s for s in secuencias}

    # Verificar que vengan todos los of_id
    if len(body.orden) != len(secuencias):
        raise HTTPException(400, "El orden debe incluir todas las órdenes de la semana")

    from app.services.icc import calcular_costo_cambio
    from app.models.ultimo_estado_maquina import UltimoEstadoMaquina
    from app.services.optimizer import cargar_penalizaciones
    
    penalizaciones = await cargar_penalizaciones(db)

    res_estado = await db.execute(select(UltimoEstadoMaquina).where(UltimoEstadoMaquina.maquina_id == semana.maquina_id))
    estado_previo = res_estado.scalars().first()
    of_previa_mock = None
    if estado_previo:
        of_previa_mock = OrdenFabricacion(
            ancho_mm=estado_previo.ancho_mm,
            alto_mm=estado_previo.alto_mm,
            fuelle_mm=estado_previo.fuelle_mm,
            cilindro_id=estado_previo.cilindro_id,
            material_id=estado_previo.material_id,
            colores_detalle=estado_previo.color_principal
        )

    fin_anterior = datetime.combine(semana.fecha_inicio, datetime.min.time())
    
    ordenadas_of_ids = body.orden
    ofs_en_orden = []
    for of_id in ordenadas_of_ids:
        of = await db.get(OrdenFabricacion, of_id)
        ofs_en_orden.append((seq_map[of_id], of))

    for pos, (seq, of) in enumerate(ofs_en_orden, start=1):
        seq.posicion = pos
        setup_min = 0.0
        motivo = ""
        
        if pos == 1 and of_previa_mock:
            setup_min, res_cambios = calcular_costo_cambio(of_previa_mock, of, penalizaciones)
            motivo = " | ".join(res_cambios["detalle"])
        elif pos > 1:
            of_prev = ofs_en_orden[pos - 2][1]
            setup_min, res_cambios = calcular_costo_cambio(of_prev, of, penalizaciones)
            motivo = " | ".join(res_cambios["detalle"])

        seq.costo_setup_min = setup_min
        seq.motivo_setup = motivo
        
        inicio_estimado = fin_anterior + timedelta(minutes=setup_min)
        fin_estimado = inicio_estimado + timedelta(hours=float(of.horas_produccion or 0.0))
        fin_anterior = fin_estimado
        
        seq.inicio_estimado = inicio_estimado
        seq.fin_estimado = fin_estimado
        
        db.add(seq)

    await db.commit()
    return {"status": "ok", "message": "Secuencia reordenada correctamente"}

@router.delete("/{id}")
async def eliminar_semana(id: int, db: AsyncSession = Depends(get_session)):
    semana = await db.get(SemanaProgramacion, id)
    if not semana:
        raise HTTPException(status_code=404, detail="Semana no encontrada")
        
    if semana.estado != "BORRADOR":
        raise HTTPException(status_code=400, detail="Solo se pueden eliminar semanas en estado BORRADOR")
        
    # Restaurar OFs a PENDIENTE
    stmt_update = text("""
        UPDATE sipp.ordenes_fabricacion SET estado = 'PENDIENTE'
        WHERE id IN (
            SELECT orden_fabricacion_id FROM sipp.secuencias_produccion WHERE semana_id = :semana_id
        )
    """)
    await db.execute(stmt_update, {"semana_id": id})
    
    # Eliminar secuencias
    stmt_delete = text("DELETE FROM sipp.secuencias_produccion WHERE semana_id = :semana_id")
    await db.execute(stmt_delete, {"semana_id": id})
    
    # Eliminar semana
    await db.delete(semana)
    await db.commit()
    
    return {"mensaje": "Semana eliminada correctamente"}
