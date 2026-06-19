from datetime import date, datetime, timezone
from sqlmodel import select, text
from app.models.maquina import Maquina
from app.models.orden_fabricacion import OrdenFabricacion
from app.models.semana_programacion import SemanaProgramacion
from app.models.setup_penalizacion import SetupPenalizacion
from app.models.maquina_capacidad import MaquinaCapacidad
from app.models.ultimo_estado_maquina import UltimoEstadoMaquina
from app.services.icc import calcular_costo_cambio, calcular_icc

async def sugerir_maquina_logica(of_id: int, db) -> list[dict]:
    # 1. Cargar la OF
    of = await db.get(OrdenFabricacion, of_id)
    if not of:
        return []

    # Cargar penalizaciones
    res_pen = await db.execute(select(SetupPenalizacion).where(SetupPenalizacion.activo == True))
    penalizaciones = {p.tipo_cambio: float(p.minutos) for p in res_pen.scalars().all()}

    # 2. Obtener todas las máquinas activas
    res_maqs = await db.execute(select(Maquina).where(Maquina.activa == True))
    maquinas = res_maqs.scalars().all()
    
    ranking = []

    for maq in maquinas:
        # a. Verificar capacidades
        res_cap = await db.execute(select(MaquinaCapacidad).where(MaquinaCapacidad.maquina_id == maq.id))
        cap = res_cap.scalars().first()
        
        if cap:
            if of.ancho_mm is not None:
                if cap.ancho_min_mm is not None and of.ancho_mm < cap.ancho_min_mm:
                    continue
                if cap.ancho_max_mm is not None and of.ancho_mm > cap.ancho_max_mm:
                    continue
            if of.alto_mm is not None:
                if cap.alto_min_mm is not None and of.alto_mm < cap.alto_min_mm:
                    continue
                if cap.alto_max_mm is not None and of.alto_mm > cap.alto_max_mm:
                    continue
            if of.fuelle_mm is not None:
                if cap.fuelle_max_mm is not None and of.fuelle_mm > cap.fuelle_max_mm:
                    continue

        # b. Calcular carga actual en la semana EN_EJECUCION
        q_carga = text("""
            SELECT COALESCE(SUM(of2.horas_produccion), 0)
            FROM sipp.secuencias_produccion sp
            JOIN sipp.semanas_programacion s ON s.id = sp.semana_id
            JOIN sipp.ordenes_fabricacion of2 ON of2.id = sp.orden_fabricacion_id
            WHERE s.estado = 'EN_EJECUCION'
            AND of2.maquina_asignada_id = :maquina_id
            AND sp.estado != 'COMPLETADA'
        """)
        res_carga = await db.execute(q_carga, {"maquina_id": maq.id})
        horas_usadas = float(res_carga.scalar() or 0.0)

        # c. Calcular carga_pct
        carga_pct = min((horas_usadas / 40.0 * 100.0), 100.0)

        # d. Cargar último estado
        res_ultimo = await db.execute(select(UltimoEstadoMaquina).where(UltimoEstadoMaquina.maquina_id == maq.id))
        ultimo_estado = res_ultimo.scalars().first()
        
        icc = 100.0
        if ultimo_estado:
            of_mock = OrdenFabricacion(
                ancho_mm=ultimo_estado.ancho_mm,
                alto_mm=ultimo_estado.alto_mm,
                fuelle_mm=ultimo_estado.fuelle_mm,
                cilindro_id=ultimo_estado.cilindro_id,
                material_id=ultimo_estado.material_id,
                colores_detalle=ultimo_estado.color_principal
            )
            costo_min, _ = calcular_costo_cambio(of_mock, of, penalizaciones)
            icc = calcular_icc(costo_min)

        # f. Score
        score = (100.0 - carga_pct) * 0.4 + icc * 0.6

        ranking.append({
            "maquina_id": maq.id,
            "codigo": maq.codigo,
            "score": round(score, 1),
            "carga_pct": round(carga_pct, 1),
            "icc": round(icc, 1),
            "recomendada": False
        })

    # Ordenar ranking por score desc
    ranking.sort(key=lambda x: x["score"], reverse=True)
    if ranking:
        ranking[0]["recomendada"] = True
        
    return ranking

from sqlmodel.ext.asyncio.session import AsyncSession

async def sugerir_maquina(db, of_id: int) -> list[dict]:
    from sqlalchemy import text
    
    # Cargar la OF
    result = await db.execute(text(
        "SELECT * FROM sipp.ordenes_fabricacion WHERE id = :id"
    ), {"id": of_id})
    of = result.mappings().one_or_none()
    if not of:
        return []
    
    # Cargar máquinas activas
    result2 = await db.execute(text("""
        SELECT m.id, m.codigo, m.velocidad_bpm_max
        FROM sipp.maquinas m
        WHERE m.codigo IN ('M8','M10','M14') AND m.activa = TRUE
        ORDER BY m.codigo
    """))
    maquinas = result2.mappings().all()
    
    # Obtener semana global activa
    result3 = await db.execute(text("""
        SELECT id FROM sipp.semanas_programacion
        WHERE es_global = TRUE
        AND estado IN ('BORRADOR','EN_EJECUCION','CONFIRMADA')
        ORDER BY fecha_inicio DESC LIMIT 1
    """))
    semana = result3.scalar_one_or_none()
    
    ranking = []
    for maq in maquinas:
        # Contar OFs ya asignadas a esta máquina en la semana activa
        if semana:
            result4 = await db.execute(text("""
                SELECT COUNT(*) as total,
                       COALESCE(SUM(of2.horas_produccion), 0) as horas
                FROM sipp.secuencias_produccion sp
                JOIN sipp.ordenes_fabricacion of2
                     ON of2.id = sp.orden_fabricacion_id
                WHERE sp.semana_id = :semana_id
                AND of2.maquina_asignada_id = :maq_id
                AND sp.estado != 'COMPLETADA'
            """), {"semana_id": semana, "maq_id": maq["id"]})
            row = result4.mappings().one()
            n_ofs = int(row["total"] or 0)
            horas = float(row["horas"] or 0)
        else:
            n_ofs, horas = 0, 0.0
        
        carga_pct = min(100.0, (horas / 40.0) * 100)
        
        # Score: máquina con MENOS OFs asignadas tiene ventaja
        # (no solo menos horas — para balancear el conteo)
        score = (100 - carga_pct) * 0.5 + (100 - n_ofs * 10) * 0.5
        score = max(0, score)
        
        ranking.append({
            "maquina_id":  maq["id"],
            "codigo":      maq["codigo"],
            "score":       round(score, 1),
            "carga_pct":   round(carga_pct, 1),
            "n_ofs":       n_ofs,
            "horas_usadas": round(horas, 2),
            "recomendada": False
        })
    
    ranking.sort(key=lambda x: x["score"], reverse=True)
    if ranking:
        ranking[0]["recomendada"] = True
    
    return ranking
