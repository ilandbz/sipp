from sqlalchemy import text
from datetime import datetime
from app.services.icc import calcular_costo_cambio, calcular_icc

async def cargar_penalizaciones(db) -> dict:
    result = await db.execute(text(
        "SELECT tipo_cambio, minutos FROM sipp.setup_penalizaciones WHERE activo = TRUE"
    ))
    return {r["tipo_cambio"]: float(r["minutos"]) for r in result.mappings().all()}

async def optimizar_semana(db, semana_id: int) -> dict:
    # Cargar semana
    result = await db.execute(text(
        "SELECT * FROM sipp.semanas_programacion WHERE id = :id"
    ), {"id": semana_id})
    semana = result.mappings().one_or_none()
    if not semana:
        raise ValueError(f"Semana {semana_id} no encontrada")

    penalizaciones = await cargar_penalizaciones(db)
    es_global = bool(semana.get("es_global")) or semana.get("maquina_id") is None

    # Cargar TODAS las OFs de la semana
    result2 = await db.execute(text("""
        SELECT of.id, of.codigo_of, of.ancho_mm, of.alto_mm, of.fuelle_mm,
               of.material_id, of.cilindro_id, of.clise_id,
               of.colores_detalle, of.fecha_entrega, of.horas_produccion,
               of.maquina_asignada_id,
               mat.factor_velocidad,
               m_actual.codigo as maquina_actual
        FROM sipp.secuencias_produccion sp
        JOIN sipp.ordenes_fabricacion of ON of.id = sp.orden_fabricacion_id
        LEFT JOIN sipp.materiales mat ON mat.id = of.material_id
        LEFT JOIN sipp.maquinas m_actual ON m_actual.id = of.maquina_asignada_id
        WHERE sp.semana_id = :semana_id
        AND sp.estado != 'COMPLETADA'
        ORDER BY of.fecha_entrega ASC NULLS LAST
    """), {"semana_id": semana_id})
    todas_ofs = [dict(r) for r in result2.mappings().all()]

    if not todas_ofs:
        return {
            "ordenes_evaluadas": 0, "setup_antes_min": 0.0,
            "setup_despues_min": 0.0, "setup_antes_horas": 0.0,
            "setup_despues_horas": 0.0, "reduccion_pct": 0.0,
            "distribucion": {}
        }

    # Cargar máquinas M8, M10, M14
    result3 = await db.execute(text("""
        SELECT id, codigo, velocidad_bpm_max, turno_horas
        FROM sipp.maquinas
        WHERE codigo IN ('M8','M10','M14') AND activa = TRUE
        ORDER BY codigo
    """))
    maquinas = [dict(r) for r in result3.mappings().all()]

    if es_global:
        # === DISTRIBUCIÓN INTELIGENTE ENTRE 3 MÁQUINAS ===
        
        # Agrupar OFs por ancho (mismo ancho = mismo formato → misma máquina)
        grupos_por_ancho = {}
        for of in todas_ofs:
            ancho = round(float(of.get("ancho_mm") or 0))
            if ancho not in grupos_por_ancho:
                grupos_por_ancho[ancho] = []
            grupos_por_ancho[ancho].append(of)
        
        # Ordenar grupos por fecha entrega más urgente
        grupos = sorted(
            grupos_por_ancho.values(),
            key=lambda g: str(min(
                of.get("fecha_entrega") or "9999-12-31"
                for of in g
            ))
        )
        
        # Distribuir grupos entre máquinas balanceando carga
        asignacion = {m["id"]: [] for m in maquinas}
        horas_por_maq = {m["id"]: 0.0 for m in maquinas}
        
        for grupo in grupos:
            # Elegir máquina con menos horas acumuladas
            maq_elegida = min(maquinas, key=lambda m: horas_por_maq[m["id"]])
            for of in grupo:
                asignacion[maq_elegida["id"]].append(of)
                horas_por_maq[maq_elegida["id"]] += float(of.get("horas_produccion") or 1.0)
        
        # Actualizar maquina_asignada_id en BD
        for maq_id, ofs in asignacion.items():
            for of in ofs:
                await db.execute(text("""
                    UPDATE sipp.ordenes_fabricacion
                    SET maquina_asignada_id = :maq_id, updated_at = NOW()
                    WHERE id = :of_id
                """), {"maq_id": maq_id, "of_id": of["id"]})
        
    else:
        # Semana específica: todas las OFs van a la máquina de la semana
        maq_id_especifica = semana["maquina_id"]
        asignacion = {m["id"]: [] for m in maquinas}
        for of in todas_ofs:
            asignacion.setdefault(maq_id_especifica, []).append(of)

    # === OPTIMIZAR ORDEN DENTRO DE CADA MÁQUINA ===
    
    # PASO 1: Commit/rollback cualquier transacción pendiente
    await db.rollback()

    # PASO 2: Limpiar en transacción separada y commitear
    async with db.begin():
        # Limpiar icc_cache relacionado ANTES de borrar las secuencias
        await db.execute(text("""
            DELETE FROM sipp.icc_cache
            WHERE of_origen_id IN (
                SELECT orden_fabricacion_id FROM sipp.secuencias_produccion
                WHERE semana_id = :id
            ) OR of_destino_id IN (
                SELECT orden_fabricacion_id FROM sipp.secuencias_produccion
                WHERE semana_id = :id
            )
        """), {"id": semana_id})

        # Limpiar secuencias existentes
        await db.execute(text(
            "DELETE FROM sipp.secuencias_produccion WHERE semana_id = :id"
        ), {"id": semana_id})

    # PASO 3: Insertar en nueva transacción
    total_setup = 0.0
    total_ofs_count = 0
    
    async with db.begin():
        for maquina in maquinas:
            maq_id = maquina["id"]
            ofs_maq = asignacion.get(maq_id, [])
            if not ofs_maq:
                continue
            
            # Ordenar: mismo color juntos, luego por fecha entrega
            ofs_ordenadas = sorted(ofs_maq, key=lambda o: (
                str(o.get("fecha_entrega") or "9999-12-31"),
                (o.get("colores_detalle") or "").split(",")[0].strip().upper()
            ))
            
            for pos, of in enumerate(ofs_ordenadas, start=1):
                setup_min = 0.0
                motivo = "Primera OF de la máquina"
                
                if pos > 1:
                    of_prev = ofs_ordenadas[pos - 2]
                    try:
                        setup_min, cambios = calcular_costo_cambio(
                            of_prev, of, penalizaciones
                        )
                        motivo = " | ".join(cambios.get("detalle", ["Sin cambio"]))
                    except Exception:
                        setup_min = 0.0
                        motivo = "No calculado"
                    total_setup += setup_min
                
                await db.execute(text("""
                    INSERT INTO sipp.secuencias_produccion
                        (semana_id, orden_fabricacion_id, posicion,
                         costo_setup_min, estado, motivo_setup)
                    VALUES
                        (:semana_id, :of_id, :pos,
                         :setup, 'PENDIENTE', :motivo)
                    ON CONFLICT (semana_id, posicion) 
                    DO UPDATE SET
                        orden_fabricacion_id = EXCLUDED.orden_fabricacion_id,
                        costo_setup_min = EXCLUDED.costo_setup_min,
                        motivo_setup = EXCLUDED.motivo_setup
                """), {
                    "semana_id": semana_id,
                    "of_id": of["id"],
                    "pos": pos,
                    "setup": setup_min,
                    "motivo": motivo
                })
            
            total_ofs_count += len(ofs_ordenadas)
    
    distribucion = {}
    for maquina in maquinas:
        n = len(asignacion.get(maquina["id"], []))
        if n > 0:
            distribucion[maquina["codigo"]] = n
    
    return {
        "ordenes_evaluadas":   total_ofs_count,
        "setup_antes_min":     total_setup,  # simplificado
        "setup_despues_min":   total_setup,
        "setup_antes_horas":   round(total_setup / 60, 2),
        "setup_despues_horas": round(total_setup / 60, 2),
        "reduccion_pct":       0.0,
        "distribucion":        distribucion
    }
