from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from typing import List

from app.core.database import get_session
from app.schemas.optimizacion import OptimizarRequest, CalcularTiemposRequest
from app.services.optimizer import optimizar_semana
from app.services.asignador import sugerir_maquina
from app.services.calculador_tiempos import calcular_horas_produccion
from app.models.orden_fabricacion import OrdenFabricacion
from app.models.maquina import Maquina
from app.models.material import Material
from app.models.log_optimizacion import LogOptimizacion

router = APIRouter(prefix="/optimizador", tags=["Optimizador"])

@router.post("/ejecutar", status_code=status.HTTP_200_OK)
async def ejecutar_optimizador(
    body: OptimizarRequest,
    db: AsyncSession = Depends(get_session)
):
    try:
        from app.services.optimizer import optimizar_semana
        from app.services.icc import calcular_icc
        from sqlalchemy import text
        
        # 1. Ejecutar optimizador
        resultado = await optimizar_semana(db, body.semana_id)
        
        # 2. Calcular ICC para todos los pares de la semana
        print(f"[ICC] Calculando pares para semana {body.semana_id}")
        
        r = await db.execute(text("""
            SELECT of.id, of.codigo_of, of.ancho_mm, of.alto_mm,
                   of.colores_detalle, of.material_id, of.cilindro_id
            FROM sipp.secuencias_produccion sp
            JOIN sipp.ordenes_fabricacion of ON of.id = sp.orden_fabricacion_id
            WHERE sp.semana_id = :semana_id
        """), {"semana_id": body.semana_id})
        ofs = [dict(row) for row in r.mappings().all()]
        
        print(f"[ICC] {len(ofs)} OFs encontradas en semana {body.semana_id}")
        
        # Penalizaciones básicas
        penalizaciones = {
            "CAMBIO_FORMATO_COMPLETO": 480.0,
            "CAMBIO_COLOR_LAVADO_ESTACION": 45.0,
            "CAMBIO_CILINDRO_IMPRESION": 30.0,
            "CAMBIO_MATERIAL": 25.0,
        }
        
        pares_calculados = 0
        for of_a in ofs:
            for of_b in ofs:
                if of_a["id"] == of_b["id"]:
                    icc_val = 100.0
                    setup_val = 0.0
                else:
                    setup_val = 0.0
                    
                    # Cambio de formato
                    ancho_a = float(of_a.get("ancho_mm") or 0)
                    ancho_b = float(of_b.get("ancho_mm") or 0)
                    if ancho_a != ancho_b:
                        setup_val += 480.0
                    
                    # Cambio de color
                    col_a = str(of_a.get("colores_detalle") or "").split(",")[0].strip().upper()
                    col_b = str(of_b.get("colores_detalle") or "").split(",")[0].strip().upper()
                    if col_a and col_b and col_a != col_b:
                        setup_val += 45.0
                    
                    # Cambio de cilindro
                    if (of_a.get("cilindro_id") and of_b.get("cilindro_id") and
                            of_a["cilindro_id"] != of_b["cilindro_id"]):
                        setup_val += 30.0
                    
                    # Cambio de material
                    if (of_a.get("material_id") and of_b.get("material_id") and
                            of_a["material_id"] != of_b["material_id"]):
                        setup_val += 25.0
                    
                    icc_val = max(0.0, 100.0 - (setup_val / 480.0 * 100.0))
                
                await db.execute(text("""
                    INSERT INTO sipp.icc_cache
                        (of_origen_id, of_destino_id, icc_score,
                         costo_setup_min, calculado_en)
                    VALUES (:a, :b, :icc, :setup, NOW())
                    ON CONFLICT (of_origen_id, of_destino_id)
                    DO UPDATE SET
                        icc_score = EXCLUDED.icc_score,
                        costo_setup_min = EXCLUDED.costo_setup_min,
                        calculado_en = NOW()
                """), {
                    "a": of_a["id"],
                    "b": of_b["id"],
                    "icc": round(icc_val, 1),
                    "setup": round(setup_val, 1)
                })
                pares_calculados += 1
        
        await db.commit()
        print(f"[ICC] {pares_calculados} pares guardados en icc_cache")
        
        resultado["icc_calculado"] = pares_calculados
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[ERROR OPTIMIZADOR] {str(e)}\n{tb}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en optimizador: {str(e)}"
        )

@router.post("/calcular-tiempos", status_code=status.HTTP_200_OK)
async def calcular_tiempos(body: CalcularTiemposRequest, db: AsyncSession = Depends(get_session)):
    updated_ofs = []
    for of_id in body.of_ids:
        of = await db.get(OrdenFabricacion, of_id)
        if not of:
            continue
        
        # Obtener máquina asignada
        maquina = None
        if of.maquina_asignada_id:
            maquina = await db.get(Maquina, of.maquina_asignada_id)
            
        # Obtener material
        material = None
        if of.material_id:
            material = await db.get(Material, of.material_id)
            
        factor_vel = 1.0
        if material and material.factor_velocidad is not None:
            factor_vel = float(material.factor_velocidad)
            
        velocidad_max = 100.0
        if maquina and maquina.velocidad_bpm_max is not None:
            velocidad_max = float(maquina.velocidad_bpm_max)
            
        horas = calcular_horas_produccion(
            of.cantidad_programada,
            velocidad_max,
            factor_vel
        )
        
        of.horas_produccion = horas
        db.add(of)
        updated_ofs.append(of)
        
    await db.commit()
    # Refresh all
    for of in updated_ofs:
        await db.refresh(of)
        
    return updated_ofs

@router.get("/sugerencia-asignacion/{of_id}", status_code=status.HTTP_200_OK)
async def sugerencia_asignacion(of_id: int, db: AsyncSession = Depends(get_session)):
    ranking = await sugerir_maquina(db, of_id)
    if not ranking:
        raise HTTPException(status_code=404, detail="Orden de fabricación no encontrada o no se pudo calcular ranking")
    return ranking

@router.get("/log", status_code=status.HTTP_200_OK)
async def get_log_optimizaciones(db: AsyncSession = Depends(get_session)):
    query = (
        select(LogOptimizacion, Maquina.codigo.label("maquina_codigo"))
        .join(Maquina, LogOptimizacion.maquina_id == Maquina.id, isouter=True)
        .order_by(LogOptimizacion.ejecutado_en.desc())
        .limit(50)
    )
    result = await db.execute(query)
    rows = result.all()
    
    response = []
    for log, m_codigo in rows:
        response.append({
            "id": log.id,
            "maquina_id": log.maquina_id,
            "maquina_codigo": m_codigo,
            "ordenes_evaluadas": log.ordenes_evaluadas,
            "setup_total_antes_min": log.setup_total_antes_min,
            "setup_total_despues_min": log.setup_total_despues_min,
            "reduccion_pct": log.reduccion_pct,
            "ejecutado_en": log.ejecutado_en
        })
    return response
