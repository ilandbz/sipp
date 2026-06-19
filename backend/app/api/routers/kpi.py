from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text
from typing import List
from datetime import date
from app.core.database import get_session
from app.schemas.kpi import KpiSemanalRead, IccMatrixResponse, PlanSemanalRead

router = APIRouter(prefix="/kpi", tags=["KPIs"])

@router.get("/semana/{semana_id}")
async def kpi_por_semana(semana_id: int,
                         db: AsyncSession = Depends(get_session)):
    result = await db.execute(text("""
        SELECT
            COUNT(sp.id)                                    AS total_ofs,
            COALESCE(SUM(sp.costo_setup_min), 0)           AS setup_total_min,
            ROUND(COALESCE(SUM(sp.costo_setup_min),0)/60,2) AS setup_total_horas,
            COALESCE(SUM(of.horas_produccion), 0)          AS horas_produccion,
            s.horas_disponibles,
            CASE WHEN s.horas_disponibles > 0
                 THEN ROUND(
                     (COALESCE(SUM(of.horas_produccion),0) +
                      COALESCE(SUM(sp.costo_setup_min),0)/60)
                     / s.horas_disponibles * 100, 1)
                 ELSE 0 END                                 AS utilizacion_pct,
            s.estado,
            s.es_global,
            s.fecha_inicio,
            s.fecha_fin
        FROM sipp.semanas_programacion s
        LEFT JOIN sipp.secuencias_produccion sp ON sp.semana_id = s.id
        LEFT JOIN sipp.ordenes_fabricacion of ON of.id = sp.orden_fabricacion_id
        WHERE s.id = :semana_id
        GROUP BY s.id, s.horas_disponibles, s.estado,
                 s.es_global, s.fecha_inicio, s.fecha_fin
    """), {"semana_id": semana_id})
    
    row = result.mappings().one_or_none()
    if not row:
        return {"total_ofs": 0, "setup_total_horas": 0, "utilizacion_pct": 0}
    return dict(row)

@router.get("/semanal", response_model=List[KpiSemanalRead])
async def kpi_semanal(semana: str | None = None, semana_id: int | None = None, db: AsyncSession = Depends(get_session)):
    query = "SELECT k.* FROM sipp.v_kpi_semanal k"
    params = {}
    if semana_id:
        query += " JOIN sipp.maquinas m ON m.codigo = k.maquina JOIN sipp.semanas_programacion s ON s.fecha_inicio = k.fecha_inicio AND s.maquina_id = m.id WHERE s.id = :semana_id"
        params["semana_id"] = semana_id
    elif semana:
        try:
            year, week_num = map(int, semana.split("-W"))
            fecha_inicio = date.fromisocalendar(year, week_num, 1)
            query += " WHERE k.fecha_inicio = :fecha_inicio"
            params["fecha_inicio"] = fecha_inicio
        except ValueError:
            return []
    query += " ORDER BY k.maquina"
    
    result = await db.execute(text(query), params)
    rows = result.mappings().all()
    return rows

@router.get("/plan-semanal", response_model=List[PlanSemanalRead])
async def kpi_plan_semanal(semana: str | None = None, semana_id: int | None = None, db: AsyncSession = Depends(get_session)):
    query = "SELECT k.* FROM sipp.v_plan_semanal k"
    params = {}
    if semana_id:
        query += " JOIN sipp.maquinas m ON m.codigo = k.maquina JOIN sipp.semanas_programacion s ON s.fecha_inicio = k.semana_inicio AND s.maquina_id = m.id WHERE s.id = :semana_id"
        params["semana_id"] = semana_id
    elif semana:
        try:
            year, week_num = map(int, semana.split("-W"))
            fecha_inicio = date.fromisocalendar(year, week_num, 1)
            query += " WHERE k.semana_inicio = :fecha_inicio"
            params["fecha_inicio"] = fecha_inicio
        except ValueError:
            return []
    query += " ORDER BY k.maquina, k.posicion"
    
    result = await db.execute(text(query), params)
    rows = result.mappings().all()
    return rows

@router.get("/icc_matrix", response_model=IccMatrixResponse)
async def kpi_icc_matrix(semana: str | None = None, semana_id: int | None = None, db: AsyncSession = Depends(get_session)):
    if not semana and not semana_id:
        return {"matrix": []}
        
    params = {}
    if semana_id:
        where_clause = "WHERE s.id = :semana_id"
        params["semana_id"] = semana_id
    else:
        try:
            year, week_num = map(int, semana.split("-W"))
            fecha_inicio = date.fromisocalendar(year, week_num, 1)
            where_clause = "WHERE s.fecha_inicio = :fecha_inicio"
            params["fecha_inicio"] = fecha_inicio
        except ValueError:
            return {"matrix": []}
        
    # 1. Obtener todas las OFs planificadas para esa semana
    ofs_query = text(f"""
        SELECT DISTINCT of.id, of.codigo_of
        FROM sipp.secuencias_produccion sp
        JOIN sipp.semanas_programacion s ON s.id = sp.semana_id
        JOIN sipp.ordenes_fabricacion of ON of.id = sp.orden_fabricacion_id
        {where_clause}
        ORDER BY of.codigo_of
    """)
    ofs_res = await db.execute(ofs_query, params)
    of_list = ofs_res.mappings().all()
    
    if not of_list:
        return {"matrix": []}
        
    of_ids = [r["id"] for r in of_list]
    
    # 2. Consultar el cache de ICC
    icc_query = text("""
        SELECT of_orig.codigo_of AS of_origen, of_dest.codigo_of AS of_destino, icc.icc_score
        FROM sipp.icc_cache icc
        JOIN sipp.ordenes_fabricacion of_orig ON of_orig.id = icc.of_origen_id
        JOIN sipp.ordenes_fabricacion of_dest ON of_dest.id = icc.of_destino_id
        WHERE icc.of_origen_id = ANY(:of_ids) AND icc.of_destino_id = ANY(:of_ids)
    """)
    
    # NOTA: En postgres/asyncpg, pasar listas como parametro se hace usando un array
    icc_res = await db.execute(icc_query, {"of_ids": of_ids})
    icc_results = icc_res.mappings().all()
    
    # 3. Pivotear matriz en Python
    score_map = {}
    for r in icc_results:
        score_map[(r["of_origen"], r["of_destino"])] = float(r["icc_score"])
        
    matrix_data = []
    for of_orig in of_list:
        row = {"of_origen": of_orig["codigo_of"]}
        for of_dest in of_list:
            orig_code = of_orig["codigo_of"]
            dest_code = of_dest["codigo_of"]
            if orig_code == dest_code:
                row[dest_code] = 100.0
            else:
                row[dest_code] = score_map.get((orig_code, dest_code), None)
        matrix_data.append(row)
        
    return {"matrix": matrix_data}

@router.get("/optimizaciones-log")
async def kpi_optimizaciones_log(db: AsyncSession = Depends(get_session)):
    query = """
        SELECT 
            lo.ejecutado_en AS fecha,
            m.codigo AS maquina,
            lo.ordenes_evaluadas,
            ROUND(lo.setup_total_antes_min / 60.0, 2) AS setup_antes_h,
            ROUND(lo.setup_total_despues_min / 60.0, 2) AS setup_despues_h,
            lo.reduccion_pct
        FROM sipp.log_optimizaciones lo
        LEFT JOIN sipp.maquinas m ON m.id = lo.maquina_id
        ORDER BY lo.ejecutado_en DESC
    """
    result = await db.execute(text(query))
    return [dict(row) for row in result.mappings().all()]

@router.get("/icc/{semana_id}")
async def icc_semana(semana_id: int,
                     db: AsyncSession = Depends(get_session)):
    from sqlalchemy import text
    print(f"[ICC] Buscando datos para semana_id={semana_id}")
    
    # Primero verificar cuántas OFs hay en la semana
    r1 = await db.execute(text("""
        SELECT COUNT(*) as total
        FROM sipp.secuencias_produccion
        WHERE semana_id = :id
    """), {"id": semana_id})
    total_ofs = r1.scalar()
    print(f"[ICC] OFs en semana {semana_id}: {total_ofs}")
    
    # Verificar cuántos pares hay en icc_cache para esas OFs
    r2 = await db.execute(text("""
        SELECT COUNT(*) as total
        FROM sipp.icc_cache ic
        WHERE ic.of_origen_id IN (
            SELECT orden_fabricacion_id
            FROM sipp.secuencias_produccion
            WHERE semana_id = :id
        )
    """), {"id": semana_id})
    total_pares = r2.scalar()
    print(f"[ICC] Pares ICC disponibles: {total_pares}")
    
    if total_pares == 0:
        print(f"[ICC] Sin datos - retornando vacío")
        return []
    
    result = await db.execute(text("""
        SELECT 
            of_a.codigo_of AS of_origen,
            of_b.codigo_of AS of_destino,
            COALESCE(ROUND(ic.icc_score::numeric, 1), 0) AS icc_score
        FROM sipp.icc_cache ic
        JOIN sipp.ordenes_fabricacion of_a ON of_a.id = ic.of_origen_id
        JOIN sipp.ordenes_fabricacion of_b ON of_b.id = ic.of_destino_id
        WHERE ic.of_origen_id IN (
            SELECT orden_fabricacion_id
            FROM sipp.secuencias_produccion
            WHERE semana_id = :id
        )
        AND ic.of_destino_id IN (
            SELECT orden_fabricacion_id
            FROM sipp.secuencias_produccion
            WHERE semana_id = :id
        )
        ORDER BY of_a.codigo_of, of_b.codigo_of
    """), {"id": semana_id})
    
    rows = [dict(r) for r in result.mappings().all()]
    print(f"[ICC] Retornando {len(rows)} pares")
    return rows
