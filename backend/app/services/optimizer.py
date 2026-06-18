from datetime import datetime, timedelta, timezone, date
from sqlmodel import select, text
from app.models.semana_programacion import SemanaProgramacion
from app.models.maquina import Maquina
from app.models.orden_fabricacion import OrdenFabricacion
from app.models.material import Material
from app.models.setup_penalizacion import SetupPenalizacion
from app.models.secuencia_produccion import SecuenciaProduccion
from app.models.icc_cache import IccCache
from app.models.log_optimizacion import LogOptimizacion
from app.models.ultimo_estado_maquina import UltimoEstadoMaquina
from app.services.icc import calcular_costo_cambio, calcular_icc, extraer_color_primario

async def cargar_penalizaciones(db) -> dict[str, float]:
    result = await db.execute(select(SetupPenalizacion).where(SetupPenalizacion.activo == True))
    return {p.tipo_cambio: float(p.minutos) for p in result.scalars().all()}

async def optimizar_semana(db, semana_id: int) -> dict:
    # Cargar semana
    result = await db.execute(text(
        "SELECT * FROM sipp.semanas_programacion WHERE id = :id"
    ), {"id": semana_id})
    semana = result.mappings().one_or_none()
    if not semana:
        raise ValueError(f"Semana {semana_id} no encontrada")

    penalizaciones = await cargar_penalizaciones(db)
    es_global = semana.get("es_global", False) or semana.get("maquina_id") is None

    if es_global:
        # Obtener máquinas que tienen OFs en esta semana
        result_maq = await db.execute(text("""
            SELECT DISTINCT m.id, m.codigo
            FROM sipp.maquinas m
            JOIN sipp.ordenes_fabricacion of ON of.maquina_asignada_id = m.id
            JOIN sipp.secuencias_produccion sp ON sp.orden_fabricacion_id = of.id
            WHERE sp.semana_id = :semana_id
            AND sp.estado != 'COMPLETADA'
            ORDER BY m.codigo
        """), {"semana_id": semana_id})
        maquinas = result_maq.mappings().all()

        if not maquinas:
            return {
                "ordenes_evaluadas": 0,
                "setup_antes_min": 0.0,
                "setup_despues_min": 0.0,
                "setup_antes_horas": 0.0,
                "setup_despues_horas": 0.0,
                "reduccion_pct": 0.0,
                "por_maquina": []
            }

        total_antes = 0.0
        total_despues = 0.0
        total_ofs = 0
        por_maquina = []

        for maq in maquinas:
            res = await _optimizar_maquina(
                db, semana_id, maq["id"], maq["codigo"], penalizaciones, semana["fecha_inicio"]
            )
            total_antes   += res.get("setup_antes_min", 0)
            total_despues += res.get("setup_despues_min", 0)
            total_ofs     += res.get("ordenes_evaluadas", 0)
            por_maquina.append({"maquina": maq["codigo"], **res})

        reduccion = round(
            (total_antes - total_despues) / total_antes * 100
            if total_antes > 0 else 0, 1
        )
        return {
            "ordenes_evaluadas":  total_ofs,
            "setup_antes_min":    round(total_antes, 1),
            "setup_despues_min":  round(total_despues, 1),
            "setup_antes_horas":  round(total_antes / 60, 2),
            "setup_despues_horas": round(total_despues / 60, 2),
            "reduccion_pct":      reduccion,
            "por_maquina":        por_maquina
        }
    else:
        # Semana específica
        return await _optimizar_maquina(
            db, semana_id, semana["maquina_id"], None, penalizaciones, semana["fecha_inicio"]
        )

async def _optimizar_maquina(db, semana_id, maquina_id, maquina_codigo, penalizaciones, fecha_inicio):
    """
    Optimiza las OFs de UNA máquina dentro de una semana.
    Funciona tanto para semanas globales como específicas.
    """
    maquina = await db.get(Maquina, maquina_id)
    if not maquina:
        return {
            "ordenes_evaluadas": 0, "setup_antes_min": 0.0, "setup_antes_horas": 0.0,
            "setup_despues_min": 0.0, "setup_despues_horas": 0.0, "reduccion_pct": 0.0, "secuencia": []
        }

    # Estado previo de la máquina
    res_estado = await db.execute(select(UltimoEstadoMaquina).where(UltimoEstadoMaquina.maquina_id == maquina_id))
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

    # Cargar OFs usando SQLModel para tener instancias
    res_ofs = await db.execute(
        select(OrdenFabricacion)
        .join(SecuenciaProduccion, SecuenciaProduccion.orden_fabricacion_id == OrdenFabricacion.id)
        .where(SecuenciaProduccion.semana_id == semana_id)
        .where(OrdenFabricacion.maquina_asignada_id == maquina_id)
        .where(SecuenciaProduccion.estado != 'COMPLETADA')
    )
    ofs = res_ofs.scalars().all()

    if not ofs:
        return {
            "ordenes_evaluadas": 0, "setup_antes_min": 0.0, "setup_antes_horas": 0.0,
            "setup_despues_min": 0.0, "setup_despues_horas": 0.0, "reduccion_pct": 0.0, "secuencia": []
        }

    ofs_base = sorted(ofs, key=lambda x: x.fecha_entrega or date.max)
    setup_antes = 0.0
    # Para el "antes", si hay estado previo, el primero asume el costo con ese estado
    if of_previa_mock and len(ofs_base) > 0:
        c, _ = calcular_costo_cambio(of_previa_mock, ofs_base[0], penalizaciones)
        setup_antes += c

    for i in range(len(ofs_base) - 1):
        costo, _ = calcular_costo_cambio(ofs_base[i], ofs_base[i+1], penalizaciones)
        setup_antes += costo

    # Agrupación Comercial + Urgencia
    key_grouping = lambda of: (
        getattr(of, "franquicia_nivel", 4),  # 1° prioridad comercial
        of.prioridad or 3,                   # 2° urgencia del pedido
        of.fecha_entrega or date.max         # 3° fecha más cercana
    )

    ofs_ordenadas = sorted(ofs_base, key=key_grouping)

    # Cálculo de tiempos
    for of in ofs_ordenadas:
        if not of.horas_produccion:
            factor_vel = 1.0
            if of.material_id:
                mat = await db.get(Material, of.material_id)
                if mat and mat.factor_velocidad is not None:
                    factor_vel = float(mat.factor_velocidad)
            
            bolsas_por_minuto = (maquina.velocidad_bpm_max or 100.0) * factor_vel
            if of.cantidad_programada and bolsas_por_minuto > 0:
                minutos = (of.cantidad_programada * 1000) / bolsas_por_minuto
                of.horas_produccion = round(minutos / 60, 2)
            else:
                of.horas_produccion = 0.0
            db.add(of)
    await db.flush()

    # Eliminar previas (solo para esta máquina en esta semana)
    await db.execute(text("""
        DELETE FROM sipp.secuencias_produccion 
        WHERE id IN (
            SELECT sp.id FROM sipp.secuencias_produccion sp
            JOIN sipp.ordenes_fabricacion of ON of.id = sp.orden_fabricacion_id
            WHERE sp.semana_id = :semana_id AND of.maquina_asignada_id = :maquina_id
        )
    """), {"semana_id": semana_id, "maquina_id": maquina_id})

    setup_despues = 0.0
    fin_anterior = datetime.combine(fecha_inicio, datetime.min.time())
    secuencia_resultado = []

    for pos, of in enumerate(ofs_ordenadas, start=1):
        setup_min = 0.0
        motivo = ""
        
        # El primero asume setup desde el ultimo_estado_maquina
        if pos == 1 and of_previa_mock:
            setup_min, res_cambios = calcular_costo_cambio(of_previa_mock, of, penalizaciones)
            motivo = " | ".join(res_cambios["detalle"])
            setup_despues += setup_min
        elif pos > 1:
            of_prev = ofs_ordenadas[pos - 2]
            setup_min, res_cambios = calcular_costo_cambio(of_prev, of, penalizaciones)
            motivo = " | ".join(res_cambios["detalle"])
            setup_despues += setup_min

            # Cachear ICC
            icc = calcular_icc(setup_min)
            res_cache = await db.execute(
                select(IccCache)
                .where(IccCache.of_origen_id == of_prev.id)
                .where(IccCache.of_destino_id == of.id)
            )
            cache_item = res_cache.scalars().first()
            if cache_item:
                cache_item.icc_score = icc
                cache_item.setup_total_min = setup_min
                cache_item.detalle_json = res_cambios
                db.add(cache_item)
            else:
                cache_item = IccCache(
                    of_origen_id=of_prev.id,
                    of_destino_id=of.id,
                    icc_score=icc,
                    setup_total_min=setup_min,
                    detalle_json=res_cambios
                )
                db.add(cache_item)

        inicio_estimado = fin_anterior + timedelta(minutes=setup_min)
        fin_estimado = inicio_estimado + timedelta(hours=float(of.horas_produccion or 0.0))
        fin_anterior = fin_estimado

        seq = SecuenciaProduccion(
            semana_id=semana_id,
            orden_fabricacion_id=of.id,
            posicion=pos,
            costo_setup_min=setup_min,
            motivo_setup=motivo,
            inicio_estimado=inicio_estimado,
            fin_estimado=fin_estimado,
            estado="PENDIENTE"
        )
        db.add(seq)
        
        secuencia_resultado.append({
            "posicion": pos,
            "codigo_of": of.codigo_of,
            "medida_texto": of.medida_texto,
            "setup_min": setup_min,
            "inicio_estimado": inicio_estimado.isoformat(),
            "fin_estimado": fin_estimado.isoformat()
        })

    # Log corrida
    reduccion = ((setup_antes - setup_despues) / setup_antes * 100.0) if setup_antes > 0 else 0.0
    
    log = LogOptimizacion(
        semana_id=semana_id,
        maquina_id=maquina_id,
        ordenes_evaluadas=len(ofs_ordenadas),
        setup_total_antes_min=setup_antes,
        setup_total_despues_min=setup_despues,
        reduccion_pct=round(reduccion, 2),
        resultado_json={"secuencia": secuencia_resultado},
        ejecutado_en=datetime.utcnow()
    )
    db.add(log)

    # Actualizar ultimo_estado_maquina con la ultima OF de la secuencia
    if len(ofs_ordenadas) > 0:
        ultima_of = ofs_ordenadas[-1]
        if not estado_previo:
            estado_previo = UltimoEstadoMaquina(maquina_id=maquina_id)
            db.add(estado_previo)
        estado_previo.ultima_of_id = ultima_of.id
        estado_previo.ancho_mm = ultima_of.ancho_mm
        estado_previo.alto_mm = ultima_of.alto_mm
        estado_previo.fuelle_mm = ultima_of.fuelle_mm
        estado_previo.cilindro_id = ultima_of.cilindro_id
        estado_previo.material_id = ultima_of.material_id
        estado_previo.color_principal = extraer_color_primario(ultima_of.colores_detalle)
        estado_previo.tipo_bolsa_num = ultima_of.tipo_bolsa_id
        estado_previo.actualizado_en = datetime.utcnow()

    await db.commit()

    return {
        "ordenes_evaluadas": len(ofs_ordenadas),
        "setup_antes_min": setup_antes,
        "setup_antes_horas": round(setup_antes / 60.0, 2),
        "setup_despues_min": setup_despues,
        "setup_despues_horas": round(setup_despues / 60.0, 2),
        "reduccion_pct": round(reduccion, 2),
        "secuencia": secuencia_resultado
    }
