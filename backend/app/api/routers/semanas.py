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
        Material.tipo.label("material_nombre"),
        OrdenFabricacion.cantidad_pedido,
        OrdenFabricacion.cantidad_programada,
        OrdenFabricacion.unidad_medida
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
        sp_data["cantidad_pedido"] = r[6]
        sp_data["cantidad_programada"] = r[7]
        sp_data["unidad_medida"] = r[8]
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
async def eliminar_semana(id: int,
                          db: AsyncSession = Depends(get_session)):
    try:
        from sqlalchemy import text
        
        result = await db.execute(text(
            "SELECT id, estado, es_global FROM sipp.semanas_programacion WHERE id = :id"
        ), {"id": id})
        semana = result.mappings().one_or_none()
        
        if not semana:
            raise HTTPException(404, "Semana no encontrada")
        
        if semana["estado"] != "BORRADOR":
            raise HTTPException(400,
                f"Solo se pueden eliminar semanas en estado BORRADOR. "
                f"Esta semana está en estado: {semana['estado']}")
        
        # 1. Restaurar OFs a PENDIENTE
        await db.execute(text("""
            UPDATE sipp.ordenes_fabricacion
            SET estado = 'PENDIENTE', updated_at = NOW()
            WHERE id IN (
                SELECT orden_fabricacion_id
                FROM sipp.secuencias_produccion
                WHERE semana_id = :id
            )
        """), {"id": id})

        # 2. Limpiar icc_cache de las OFs de esta semana
        await db.execute(text("""
            DELETE FROM sipp.icc_cache
            WHERE of_origen_id IN (
                SELECT orden_fabricacion_id
                FROM sipp.secuencias_produccion
                WHERE semana_id = :id
            )
            OR of_destino_id IN (
                SELECT orden_fabricacion_id
                FROM sipp.secuencias_produccion
                WHERE semana_id = :id
            )
        """), {"id": id})

        # 3. Eliminar secuencias
        await db.execute(text(
            "DELETE FROM sipp.secuencias_produccion WHERE semana_id = :id"
        ), {"id": id})

        # 4. Eliminar logs de optimización (FK que faltaba)
        await db.execute(text(
            "DELETE FROM sipp.log_optimizaciones WHERE semana_id = :id"
        ), {"id": id})

        # 5. Finalmente eliminar la semana
        await db.execute(text(
            "DELETE FROM sipp.semanas_programacion WHERE id = :id"
        ), {"id": id})
        
        await db.commit()
        return {"ok": True, "mensaje": "Semana eliminada correctamente"}
        
    except HTTPException:
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

@router.get("/{id}/cola-completa")
async def obtener_cola_completa(id: int, db: AsyncSession = Depends(get_session)):
    try:
        from sqlalchemy import text
        query = """
            SELECT sp.id AS secuencia_id, sp.posicion, of.codigo_of, of.medida_texto,
                   mat.tipo as material, of.colores_detalle,
                   sp.costo_setup_min, sp.motivo_setup,
                   of.fecha_entrega, sp.estado,
                   m.codigo as maquina,
                   of.cantidad_pedido, of.cantidad_programada, of.unidad_medida
            FROM sipp.secuencias_produccion sp
            JOIN sipp.ordenes_fabricacion of ON of.id = sp.orden_fabricacion_id
            LEFT JOIN sipp.materiales mat ON mat.id = of.material_id
            LEFT JOIN sipp.maquinas m ON m.id = of.maquina_asignada_id
            WHERE sp.semana_id = :semana_id
            ORDER BY m.codigo, sp.posicion
        """
        result = await db.execute(text(query), {"semana_id": id})
        return [dict(row) for row in result.mappings().all()]
    except Exception as e:
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
async def eliminar_semana(id: int,
                          db: AsyncSession = Depends(get_session)):
    try:
        from sqlalchemy import text
        
        result = await db.execute(text(
            "SELECT id, estado, es_global FROM sipp.semanas_programacion WHERE id = :id"
        ), {"id": id})
        semana = result.mappings().one_or_none()
        
        if not semana:
            raise HTTPException(404, "Semana no encontrada")
        
        if semana["estado"] != "BORRADOR":
            raise HTTPException(400,
                f"Solo se pueden eliminar semanas en estado BORRADOR. "
                f"Esta semana está en estado: {semana['estado']}")
        
        # 1. Restaurar OFs a PENDIENTE
        await db.execute(text("""
            UPDATE sipp.ordenes_fabricacion
            SET estado = 'PENDIENTE', updated_at = NOW()
            WHERE id IN (
                SELECT orden_fabricacion_id
                FROM sipp.secuencias_produccion
                WHERE semana_id = :id
            )
        """), {"id": id})

        # 2. Limpiar icc_cache de las OFs de esta semana
        await db.execute(text("""
            DELETE FROM sipp.icc_cache
            WHERE of_origen_id IN (
                SELECT orden_fabricacion_id
                FROM sipp.secuencias_produccion
                WHERE semana_id = :id
            )
            OR of_destino_id IN (
                SELECT orden_fabricacion_id
                FROM sipp.secuencias_produccion
                WHERE semana_id = :id
            )
        """), {"id": id})

        # 3. Eliminar secuencias
        await db.execute(text(
            "DELETE FROM sipp.secuencias_produccion WHERE semana_id = :id"
        ), {"id": id})

        # 4. Eliminar logs de optimización (FK que faltaba)
        await db.execute(text(
            "DELETE FROM sipp.log_optimizaciones WHERE semana_id = :id"
        ), {"id": id})

        # 5. Finalmente eliminar la semana
        await db.execute(text(
            "DELETE FROM sipp.semanas_programacion WHERE id = :id"
        ), {"id": id})
        
        await db.commit()
        return {"ok": True, "mensaje": "Semana eliminada correctamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, f"Error: {str(e)}")

@router.patch("/secuencias/{secuencia_id}/estado")
async def actualizar_estado_secuencia(
    secuencia_id: int,
    body: dict,
    db: AsyncSession = Depends(get_session)
):
    """
    Cambia el estado de una secuencia (OF en cola).
    body: {"estado": "EN_PROCESO" | "COMPLETADA" | "PENDIENTE" | "BLOQUEADA",
           "fin_real": "2026-06-20T10:30:00" (opcional, solo para COMPLETADA)}
    """
    nuevo_estado = body.get("estado")
    estados_validos = ["PENDIENTE", "EN_PROCESO", "COMPLETADA", "BLOQUEADA"]
    if nuevo_estado not in estados_validos:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Válidos: {estados_validos}")

    # Obtener la secuencia con su semana y máquina
    result = await db.execute(text("""
        SELECT sp.id, sp.estado, sp.semana_id,
               of.maquina_asignada_id,
               s.estado AS estado_semana
        FROM sipp.secuencias_produccion sp
        JOIN sipp.ordenes_fabricacion of ON of.id = sp.orden_fabricacion_id
        JOIN sipp.semanas_programacion s ON s.id = sp.semana_id
        WHERE sp.id = :sid
    """), {"sid": secuencia_id})
    seq = result.mappings().one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Secuencia no encontrada")

    # Validar que semana esté EN_EJECUCION para avanzar
    if nuevo_estado in ["EN_PROCESO", "COMPLETADA"]:
        if seq["estado_semana"] != "EN_EJECUCION":
            raise HTTPException(status_code=400, detail="La semana debe estar EN_EJECUCION para avanzar OFs")

    # Validar que no haya otra OF EN_PROCESO en la misma máquina
    if nuevo_estado == "EN_PROCESO":
        result2 = await db.execute(text("""
            SELECT COUNT(*) as cnt
            FROM sipp.secuencias_produccion sp2
            JOIN sipp.ordenes_fabricacion of2 ON of2.id = sp2.orden_fabricacion_id
            WHERE sp2.semana_id = :semana_id
              AND of2.maquina_asignada_id = :maquina_id
              AND sp2.estado = 'EN_PROCESO'
              AND sp2.id != :sid
        """), {"semana_id": seq["semana_id"], "maquina_id": seq["maquina_asignada_id"], "sid": secuencia_id})
        cnt = result2.scalar()
        if cnt > 0:
            raise HTTPException(status_code=400, detail="Ya hay una OF EN_PROCESO en esta máquina. Complétala antes de iniciar otra.")

    now_utc = datetime.utcnow()
    if nuevo_estado == "EN_PROCESO":
        await db.execute(text("""
            UPDATE sipp.secuencias_produccion
            SET estado = 'EN_PROCESO',
                inicio_estimado = COALESCE(inicio_estimado, :ahora),
                updated_at = :ahora
            WHERE id = :sid
        """), {"sid": secuencia_id, "ahora": now_utc})

    elif nuevo_estado == "COMPLETADA":
        fin_real = body.get("fin_real")
        fin_dt = datetime.fromisoformat(fin_real) if fin_real else now_utc
        await db.execute(text("""
            UPDATE sipp.secuencias_produccion
            SET estado = 'COMPLETADA',
                fin_estimado = :fin_dt,
                updated_at = :ahora
            WHERE id = :sid
        """), {"sid": secuencia_id, "fin_dt": fin_dt, "ahora": now_utc})

        # Actualizar estado de la OF también
        await db.execute(text("""
            UPDATE sipp.ordenes_fabricacion
            SET estado = 'COMPLETADA', updated_at = :ahora
            WHERE id = (
                SELECT orden_fabricacion_id
                FROM sipp.secuencias_produccion
                WHERE id = :sid
            )
        """), {"sid": secuencia_id, "ahora": now_utc})

    else:
        await db.execute(text("""
            UPDATE sipp.secuencias_produccion
            SET estado = :estado, updated_at = :ahora
            WHERE id = :sid
        """), {"estado": nuevo_estado, "sid": secuencia_id, "ahora": now_utc})

    await db.commit()

    # Verificar si todas las OFs de la semana están COMPLETADAS
    result3 = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE estado != 'COMPLETADA') AS pendientes,
            COUNT(*) AS total
        FROM sipp.secuencias_produccion
        WHERE semana_id = :semana_id
    """), {"semana_id": seq["semana_id"]})
    resumen = result3.mappings().one()
    auto_cerrada = False
    if resumen["pendientes"] == 0 and resumen["total"] > 0:
        await db.execute(text("""
            UPDATE sipp.semanas_programacion
            SET estado = 'CERRADA', updated_at = :ahora
            WHERE id = :semana_id
        """), {"semana_id": seq["semana_id"], "ahora": now_utc})
        await db.commit()
        auto_cerrada = True

    return {
        "ok": True,
        "secuencia_id": secuencia_id,
        "nuevo_estado": nuevo_estado,
        "semana_auto_cerrada": auto_cerrada
    }
