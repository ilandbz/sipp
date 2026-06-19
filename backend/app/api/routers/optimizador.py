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
        resultado = await optimizar_semana(db, body.semana_id)
        return resultado
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"ERROR OPTIMIZADOR: {str(e)}\n{tb}")
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
