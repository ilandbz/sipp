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

@router.get("/semanal", response_model=List[dict])
async def kpi_semanal(
    semana: str | None = None,
    semana_id: int | None = None,
    db: AsyncSession = Depends(get_session)
):
    params = {}
    if semana_id:
        query = text("""
            SELECT * FROM sipp.v_kpi_semanal
            WHERE semana_id = :semana_id
            ORDER BY maquina
        """)
        params["semana_id"] = semana_id
    elif semana:
        try:
            year, week_num = map(int, semana.split("-W"))
            fecha_inicio = date.fromisocalendar(year, week_num, 1)
            query = text("""
                SELECT * FROM sipp.v_kpi_semanal
                WHERE fecha_inicio = :fecha_inicio
                ORDER BY maquina
            """)
            params["fecha_inicio"] = fecha_inicio
        except ValueError:
            return []
    else:
        return []
    result = await db.execute(query, params)
    rows = result.mappings().all()
    return [dict(r) for r in rows]

@router.get("/plan-semanal", response_model=List[dict])
async def kpi_plan_semanal(
    semana: str | None = None,
    semana_id: int | None = None,
    db: AsyncSession = Depends(get_session)
):
    params = {}
    if semana_id:
        query = text("""
            SELECT * FROM sipp.v_plan_semanal
            WHERE semana_id = :semana_id
            ORDER BY maquina, posicion
        """)
        params["semana_id"] = semana_id
    elif semana:
        try:
            year, week_num = map(int, semana.split("-W"))
            fecha_inicio = date.fromisocalendar(year, week_num, 1)
            query = text("""
                SELECT * FROM sipp.v_plan_semanal
                WHERE semana_inicio = :fecha_inicio
                ORDER BY maquina, posicion
            """)
            params["fecha_inicio"] = fecha_inicio
        except ValueError:
            return []
    else:
        return []
    result = await db.execute(query, params)
    rows = result.mappings().all()
    return [dict(r) for r in rows]

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

@router.get("/icc/{semana_id}/max_of/{of_id}")
async def max_icc_con_ofs_de_semana(semana_id: int, of_id: int, db: AsyncSession = Depends(get_session)):
    query = text("""
        SELECT COALESCE(MAX(icc_score), 0)
        FROM sipp.icc_cache ic
        WHERE ic.of_origen_id = :of_id
        AND ic.of_destino_id IN (
            SELECT orden_fabricacion_id
            FROM sipp.secuencias_produccion
            WHERE semana_id = :semana_id
        )
    """)
    res = await db.execute(query, {"of_id": of_id, "semana_id": semana_id})
    val = res.scalar()
    return {"max_icc": float(val) if val else 0.0}

@router.get("/semana/{semana_id}/setup-detalle")
async def get_setup_detalle(semana_id: int, db: AsyncSession = Depends(get_session)):
    query = text("""
        SELECT 
            sp.posicion,
            of.maquina_asignada_id,
            m.nombre AS maquina_nombre,
            of.codigo_of,
            of.medida_texto AS medida,
            of.cantidad_programada,
            of.unidad_medida,
            CONCAT(mat.tipo, ' ', mat.gramaje_min, 'gr') AS material_nombre,
            of.colores_detalle AS colores,
            sp.costo_setup_min AS setup_minutos,
            sp.motivo_setup
        FROM sipp.secuencias_produccion sp
        JOIN sipp.ordenes_fabricacion of ON of.id = sp.orden_fabricacion_id
        LEFT JOIN sipp.maquinas m ON m.id = of.maquina_asignada_id
        LEFT JOIN sipp.materiales mat ON mat.id = of.material_id
        WHERE sp.semana_id = :semana_id
        ORDER BY of.maquina_asignada_id, sp.posicion
    """)
    result = await db.execute(query, {"semana_id": semana_id})
    rows = result.mappings().all()

    maquinas = {}
    for row in rows:
        mid = row["maquina_asignada_id"]
        if mid not in maquinas:
            maquinas[mid] = {
                "maquina_id": mid,
                "maquina_nombre": row["maquina_nombre"] or f"Máquina {mid}",
                "ofs": [],
                "transiciones": [],
                "setup_total_min": 0
            }
        maquinas[mid]["ofs"].append(dict(row))

    for mid, data in maquinas.items():
        ofs = data["ofs"]
        for i in range(1, len(ofs)):
            anterior = ofs[i-1]
            actual = ofs[i]
            setup_min = float(actual["setup_minutos"] or 0)
            motivo = actual["motivo_setup"] or "Sin información"

            # Calcular ICC desde setup_min
            icc = max(0, round(100 - (setup_min / 480 * 100)))

            # Color por severidad
            if setup_min == 0:
                color = "verde"
            elif setup_min <= 44:
                color = "verde"
            elif setup_min <= 104:
                color = "amarillo"
            elif setup_min < 480:
                color = "naranja"
            else:
                color = "rojo"

            data["transiciones"].append({
                "posicion": i,
                "of_origen_codigo": anterior["codigo_of"],
                "of_origen_medida": anterior["medida"] or "—",
                "of_destino_codigo": actual["codigo_of"],
                "of_destino_medida": actual["medida"] or "—",
                "icc": icc,
                "setup_minutos": int(setup_min),
                "setup_horas": round(setup_min / 60, 2),
                "motivo": motivo,
                "color": color
            })
            data["setup_total_min"] += setup_min

    resumen = []
    grand_total_min = 0
    for mid, data in maquinas.items():
        subtotal = data["setup_total_min"]
        grand_total_min += subtotal
        resumen.append({
            "maquina_id": mid,
            "maquina_nombre": data["maquina_nombre"],
            "n_ofs": len(data["ofs"]),
            "n_transiciones": len(data["transiciones"]),
            "setup_total_min": subtotal,
            "setup_total_horas": round(subtotal / 60, 2),
            "transiciones": data["transiciones"]
        })

    return {
        "semana_id": semana_id,
        "setup_grand_total_min": grand_total_min,
        "setup_grand_total_horas": round(grand_total_min / 60, 2),
        "por_maquina": resumen
    }

@router.post("/analisis-ia")
async def analisis_ia_semana(
    body: dict,
    db: AsyncSession = Depends(get_session)
):
    """
    Genera un análisis ejecutivo de la semana usando Claude API.
    """
    import httpx
    import os

    semana_id    = body.get("semana_id")
    kpi          = body.get("kpi", {})
    cola_resumen = body.get("cola_resumen", [])
    setup_detalle = body.get("setup_detalle", [])

    # Construir prompt con datos reales
    fecha_ini = kpi.get("fecha_inicio", "")
    fecha_fin = kpi.get("fecha_fin", "")
    total_ofs = kpi.get("total_ofs", 0)
    setup_h   = kpi.get("setup_total_horas", 0)
    util_pct  = kpi.get("utilizacion_pct", 0)
    estado    = kpi.get("estado", "")
    horas_dis = kpi.get("horas_disponibles", 120)
    horas_pro = kpi.get("horas_produccion", 0)

    # Construir resumen de cola
    resumen_ofs = ""
    alertas_entrega = []
    alertas_matiz = []
    from datetime import date
    hoy = date.today()
    for of in cola_resumen:
        codigo = of.get("codigo_of", "")
        maquina = of.get("maquina", "")
        setup_min = float(of.get("costo_setup_min") or 0)
        colores = str(of.get("colores_detalle") or "").upper()
        fecha_ent = of.get("fecha_entrega")
        motivo = of.get("motivo_setup", "")

        resumen_ofs += f"  - {codigo} ({maquina}): setup {setup_min:.0f}min | {motivo}\n"

        # Alertas entrega vencida
        if fecha_ent:
            try:
                fe = date.fromisoformat(str(fecha_ent)[:10])
                if fe < hoy:
                    alertas_entrega.append(f"{codigo} (venció {fe})")
            except Exception:
                pass

        # Alertas matizado
        palabras = ["MATIZ", "PANTONE", "GCMI", "POR CONFIRMAR"]
        if any(p in colores for p in palabras):
            alertas_matiz.append(f"{codigo} ({colores[:40]})")

    alertas_txt = ""
    if alertas_entrega:
        alertas_txt += f"\nOFs con fecha vencida: {', '.join(alertas_entrega)}"
    if alertas_matiz:
        alertas_txt += f"\nOFs con colores de riesgo matizado: {', '.join(alertas_matiz)}"

    prompt = f"""Eres el asistente de planificación de producción de VYGPACK,
una fábrica de bolsas de papel kraft en Lima, Perú.

Analiza los siguientes datos de la semana de producción y genera un
resumen ejecutivo conciso en español para el jefe de producción.
El tono debe ser profesional pero directo. Máximo 200 palabras.

DATOS DE LA SEMANA {fecha_ini} al {fecha_fin}:
- Estado: {estado}
- OFs programadas: {total_ofs}
- Horas disponibles: {horas_dis}h (3 máquinas × 5 días × 8h)
- Horas de producción: {horas_pro}h
- Setup total: {setup_h}h
- Utilización: {util_pct}%
{alertas_txt}

DETALLE DE OFs POR MÁQUINA:
{resumen_ofs}

Estructura tu respuesta con:
1. Una línea de resumen general
2. Puntos de alerta (si los hay)
3. Una recomendación concreta

Usa emojis para facilitar la lectura rápida.
No repitas los números exactos que ya ve el usuario en los KPIs."""

    # Llamar a Claude API
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"analisis": "⚠ API key de Anthropic no configurada en el servidor."}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            data = resp.json()
            texto = data["content"][0]["text"]
            return {"analisis": texto}
    except Exception as e:
        return {"analisis": f"⚠ Error al generar análisis: {str(e)}"}
