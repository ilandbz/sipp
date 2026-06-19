from sqlalchemy import text
from datetime import datetime
from app.services.icc import calcular_costo_cambio_async, calcular_icc

async def cargar_penalizaciones(db) -> dict:
    result = await db.execute(text(
        "SELECT tipo_cambio, minutos FROM sipp.setup_penalizaciones WHERE activo = TRUE"
    ))
    return {r["tipo_cambio"]: float(r["minutos"]) for r in result.mappings().all()}

async def _ordenar_greedy(db, ofs: list, penalizaciones: dict) -> list:
    """Ordena OFs minimizando el setup entre consecutivas."""
    if len(ofs) <= 1:
        return ofs
    
    # Para elegir la primera OF de la máquina, podríamos elegir la que tenga fecha de entrega más urgente
    ofs_sorted_por_fecha = sorted(ofs, key=lambda o: str(o.get("fecha_entrega") or "9999-12-31"))
    
    resultado = [ofs_sorted_por_fecha[0]]
    restantes = list(ofs_sorted_por_fecha[1:])
    
    while restantes:
        actual = resultado[-1]
        mejor_idx = 0
        mejor_costo = float('inf')
        
        for i, candidata in enumerate(restantes):
            try:
                costo, _ = await calcular_costo_cambio_async(db, actual, candidata, penalizaciones)
            except Exception:
                costo = 9999
            if costo < mejor_costo:
                mejor_costo = costo
                mejor_idx = i
        
        resultado.append(restantes.pop(mejor_idx))
    
    return resultado

async def optimizar_semana(db, semana_id: int) -> dict:
    # El optimizador NO redistribuye máquinas.
    # Solo optimiza el ORDEN dentro de cada máquina.
    # La asignación de máquina ocurre en agregar-of (una sola vez).
    
    # 1. Cargar semana
    result = await db.execute(text(
        "SELECT * FROM sipp.semanas_programacion WHERE id = :id"
    ), {"id": semana_id})
    semana = result.mappings().one_or_none()
    if not semana:
        raise ValueError(f"Semana {semana_id} no encontrada")

    penalizaciones = await cargar_penalizaciones(db)

    # 2. Cargar TODAS las OFs de la semana con su máquina actual
    result2 = await db.execute(text("""
        SELECT 
            of.id,
            of.codigo_of,
            of.ancho_mm,
            of.alto_mm,
            of.fuelle_mm,
            of.material_id,
            of.cilindro_id,
            of.clise_id,
            of.colores_detalle,
            of.fecha_entrega,
            of.horas_produccion,
            of.maquina_asignada_id,
            COALESCE(m.codigo, 'SIN_MAQUINA') as maquina_codigo
        FROM sipp.secuencias_produccion sp
        JOIN sipp.ordenes_fabricacion of ON of.id = sp.orden_fabricacion_id
        LEFT JOIN sipp.maquinas m ON m.id = of.maquina_asignada_id
        WHERE sp.semana_id = :semana_id
        ORDER BY of.fecha_entrega ASC NULLS LAST
    """), {"semana_id": semana_id})
    todas_ofs = [dict(r) for r in result2.mappings().all()]

    if not todas_ofs:
        return {
            "ordenes_evaluadas": 0,
            "setup_antes_min": 0.0,
            "setup_despues_min": 0.0,
            "setup_antes_horas": 0.0,
            "setup_despues_horas": 0.0,
            "reduccion_pct": 0.0,
            "distribucion": {}
        }

    # 3. Agrupar por máquina asignada (RESPETAR asignación existente)
    # NO redistribuir — solo optimizar el orden
    grupos_por_maquina = {}
    ofs_sin_maquina = []
    
    for of in todas_ofs:
        maq_id = of.get("maquina_asignada_id")
        if maq_id:
            if maq_id not in grupos_por_maquina:
                grupos_por_maquina[maq_id] = []
            grupos_por_maquina[maq_id].append(of)
        else:
            ofs_sin_maquina.append(of)
    
    # Si hay OFs sin máquina, asignarlas a la menos cargada
    if ofs_sin_maquina:
        result3 = await db.execute(text("""
            SELECT id, codigo FROM sipp.maquinas
            WHERE codigo IN ('M8','M10','M14') AND activa = TRUE
            ORDER BY codigo
        """))
        maquinas_disponibles = [dict(r) for r in result3.mappings().all()]
        
        for of in ofs_sin_maquina:
            # Elegir máquina con menos OFs
            maq_elegida = min(
                maquinas_disponibles,
                key=lambda m: len(grupos_por_maquina.get(m["id"], []))
            )
            maq_id = maq_elegida["id"]
            
            # Asignar en BD
            await db.execute(text("""
                UPDATE sipp.ordenes_fabricacion
                SET maquina_asignada_id = :maq_id, updated_at = NOW()
                WHERE id = :of_id
            """), {"maq_id": maq_id, "of_id": of["id"]})
            
            if maq_id not in grupos_por_maquina:
                grupos_por_maquina[maq_id] = []
            grupos_por_maquina[maq_id].append(of)
    
    # 4. Flush la asignación de máquinas
    await db.flush()

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

    # 6. Para cada máquina, optimizar el orden con algoritmo greedy
    total_setup = 0.0
    total_ofs_count = 0
    pos_global = 1
    distribucion = {}

    async with db.begin():
        for maq_id, ofs_maq in grupos_por_maquina.items():
            if not ofs_maq:
                continue
            
            # Obtener código de máquina para el resumen
            maq_codigo = ofs_maq[0].get("maquina_codigo", str(maq_id))
            
            # Ordenar con greedy (vecino más compatible)
            ofs_ordenadas = await _ordenar_greedy(db, ofs_maq, penalizaciones)
            
            # Insertar secuencias optimizadas
            for idx, of in enumerate(ofs_ordenadas):
                setup_min = 0.0
                motivo = "Primera OF de la máquina"
                
                if idx > 0:
                    of_prev = ofs_ordenadas[idx - 1]
                    try:
                        setup_min, cambios = await calcular_costo_cambio_async(
                            db, of_prev, of, penalizaciones
                        )
                        motivo = " | ".join(
                            cambios.get("detalle", ["Sin detalle"])
                        ) or "Sin cambio"
                    except Exception as e:
                        setup_min = 0.0
                        motivo = f"Error: {str(e)[:50]}"
                    total_setup += setup_min
                
                await db.execute(text("""
                    INSERT INTO sipp.secuencias_produccion
                        (semana_id, orden_fabricacion_id, posicion,
                         costo_setup_min, estado, motivo_setup)
                    VALUES
                        (:semana_id, :of_id, :pos,
                         :setup, 'PENDIENTE', :motivo)
                """), {
                    "semana_id": semana_id,
                    "of_id":     of["id"],
                    "pos":       pos_global,
                    "setup":     round(setup_min, 2),
                    "motivo":    motivo
                })
                
                pos_global += 1
            
            distribucion[maq_codigo] = len(ofs_ordenadas)
            total_ofs_count += len(ofs_ordenadas)
            
    # 7. Calcular y guardar el ICC para cada par
    async with db.begin():
        from app.services.icc import calcular_icc
        for i, of_a in enumerate(todas_ofs):
            for j, of_b in enumerate(todas_ofs):
                if i == j:
                    icc_val = 100.0
                else:
                    try:
                        setup, _ = await calcular_costo_cambio_async(db, of_a, of_b, penalizaciones)
                        icc_val = calcular_icc(setup)
                    except Exception:
                        icc_val = 0.0
                
                await db.execute(text("""
                    INSERT INTO sipp.icc_cache
                        (of_origen_id, of_destino_id, icc_score,
                         costo_setup_min, calculado_en)
                    VALUES (:a, :b, :icc, :setup, NOW())
                    ON CONFLICT (of_origen_id, of_destino_id)
                    DO UPDATE SET icc_score = EXCLUDED.icc_score,
                                 costo_setup_min = EXCLUDED.costo_setup_min,
                                 calculado_en = NOW()
                """), {
                    "a": of_a["id"], "b": of_b["id"],
                    "icc": icc_val,
                    "setup": 0.0 if i == j else setup
                })
    
    return {
        "ordenes_evaluadas":   total_ofs_count,
        "setup_antes_min":     total_setup,
        "setup_despues_min":   total_setup,
        "setup_antes_horas":   round(total_setup / 60, 2),
        "setup_despues_horas": round(total_setup / 60, 2),
        "reduccion_pct":       0.0,
        "distribucion":        distribucion
    }
