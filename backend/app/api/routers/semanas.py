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

@router.post("/", status_code=201)
async def crear_semana(body: SemanaProgramacionCreate,
                       db: AsyncSession = Depends(get_session)):
    try:
        from sqlalchemy import text
        from datetime import date, timedelta

        fecha_inicio = body.fecha_inicio
        fecha_fin    = body.fecha_fin
        es_global    = getattr(body, 'es_global', False)
        maquina_id   = None if es_global else body.maquina_id

        # Validar máquina si no es global
        if not es_global and not maquina_id:
            raise HTTPException(400, "Máquina requerida para semana específica")

        # Calcular días hábiles
        dias_habiles = sum(
            1 for i in range((fecha_fin - fecha_inicio).days + 1)
            if (fecha_inicio + timedelta(days=i)).weekday() < 5
        )
        factor = 3 if es_global else 1
        horas_disponibles = dias_habiles * 8.0 * factor

        # Insertar con SQL directo para evitar problemas de FK con NULL
        result = await db.execute(text("""
            INSERT INTO sipp.semanas_programacion
                (maquina_id, fecha_inicio, fecha_fin,
                 horas_disponibles, estado, es_global, created_by)
            VALUES
                (:maquina_id, :fecha_inicio, :fecha_fin,
                 :horas_disponibles, 'BORRADOR', :es_global, 'admin')
            RETURNING id, maquina_id, fecha_inicio, fecha_fin,
                      horas_disponibles, estado, es_global
        """), {
            "maquina_id":       maquina_id,
            "fecha_inicio":     fecha_inicio,
            "fecha_fin":        fecha_fin,
            "horas_disponibles": horas_disponibles,
            "es_global":        es_global,
        })
        await db.commit()
        row = result.mappings().one()
        return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, f"Error interno: {str(e)}")

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

@router.post("/{semana_id}/agregar-of")
async def agregar_of(semana_id: int, body: AgregarOfRequest,
                     db: AsyncSession = Depends(get_session)):
    try:
        semana = await db.execute(text(
            "SELECT * FROM sipp.semanas_programacion WHERE id = :id"
        ), {"id": semana_id})
        semana = semana.mappings().one_or_none()
        if not semana:
            raise HTTPException(404, "Semana no encontrada")

        of_result = await db.execute(text(
            "SELECT * FROM sipp.ordenes_fabricacion WHERE id = :id"
        ), {"id": body.of_id})
        of = of_result.mappings().one_or_none()
        if not of:
            raise HTTPException(404, "Orden no encontrada")

        # Verificar que no está ya en esta semana
        existe = await db.execute(text("""
            SELECT id FROM sipp.secuencias_produccion
            WHERE semana_id = :semana_id AND orden_fabricacion_id = :of_id
        """), {"semana_id": semana_id, "of_id": body.of_id})
        if existe.scalar_one_or_none():
            raise HTTPException(400, "Esta OF ya está en esta semana")

        # Si la semana es global Y la OF no tiene máquina asignada
        # → asignar automáticamente la mejor máquina
        maquina_id = of.get("maquina_asignada_id")
        
        es_global = semana.get("es_global", False)
        
        if es_global and not maquina_id:
            # Llamar al asignador para sugerir máquina
            from app.services.asignador import sugerir_maquina
            sugerencias = await sugerir_maquina(db, body.of_id)
            if sugerencias:
                maquina_id = sugerencias[0]["maquina_id"]
                # Actualizar la OF con la máquina asignada
                await db.execute(text("""
                    UPDATE sipp.ordenes_fabricacion
                    SET maquina_asignada_id = :maq_id,
                        updated_at = NOW()
                    WHERE id = :of_id
                """), {"maq_id": maquina_id, "of_id": body.of_id})
        
        if not maquina_id:
            raise HTTPException(400,
                "La OF no tiene máquina asignada y no se pudo sugerir una. "
                "Asigna una máquina a la OF antes de agregarla.")

        # Calcular posición
        count = await db.execute(text("""
            SELECT COUNT(*) FROM sipp.secuencias_produccion
            WHERE semana_id = :semana_id
        """), {"semana_id": semana_id})
        siguiente_pos = (count.scalar() or 0) + 1

        # Crear secuencia
        await db.execute(text("""
            INSERT INTO sipp.secuencias_produccion
                (semana_id, orden_fabricacion_id, posicion, 
                 costo_setup_min, estado, motivo_setup)
            VALUES
                (:semana_id, :of_id, :pos, 0, 'PENDIENTE', 'Asignación manual')
        """), {"semana_id": semana_id, "of_id": body.of_id, "pos": siguiente_pos})

        await db.commit()
        
        return {
            "ok": True,
            "posicion": siguiente_pos,
            "maquina_asignada_id": maquina_id,
            "mensaje": f"OF agregada en posición {siguiente_pos}"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, f"Error: {str(e)}")

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
