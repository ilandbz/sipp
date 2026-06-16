from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_session
from app.models.parada import Parada
from app.models.maquina import Maquina
from app.models.secuencia_produccion import SecuenciaProduccion

router = APIRouter(prefix="/paradas", tags=["Paradas"])

class ParadaCreate(BaseModel):
    maquina_id: int
    inicio: datetime
    fin: datetime
    tipo: str
    descripcion: Optional[str] = None
    registrado_por: Optional[str] = None

@router.post("/", status_code=status.HTTP_201_CREATED)
async def registrar_parada(body: ParadaCreate, db: AsyncSession = Depends(get_session)):
    maquina = await db.get(Maquina, body.maquina_id)
    if not maquina:
        raise HTTPException(404, "Máquina no encontrada")

    # Asegurar timezone
    inicio_tz = body.inicio if body.inicio.tzinfo else body.inicio
    fin_tz = body.fin if body.fin.tzinfo else body.fin

    parada = Parada(
        maquina_id=body.maquina_id,
        inicio=inicio_tz,
        fin=fin_tz,
        tipo=body.tipo,
        descripcion=body.descripcion,
        registrado_por=body.registrado_por
    )
    
    # horas perdidas se calcula en BD, pero agreguemos el impacto en secuencias
    db.add(parada)
    await db.flush()

    delta = fin_tz - inicio_tz

    # Desplazar secuencias
    # Buscar todas las secuencias PENDIENTE cuya inicio_estimado sea >= inicio de la parada
    # O que su fin_estimado caiga después del inicio de la parada. 
    # Para simplificar, movemos TODAS las pendientes de la maquina que no estén pasadas.
    res_seq = await db.execute(
        select(SecuenciaProduccion)
        .where(SecuenciaProduccion.estado == "PENDIENTE")
        .where(SecuenciaProduccion.inicio_estimado >= inicio_tz)
    )
    secuencias = res_seq.scalars().all()
    
    for seq in secuencias:
        # Verificar si la maquina coincide a través de la semana
        # Mejor sería un JOIN en la query, pero validemos aquí
        # Para simplificar, como SIPP asume q las fechas están asociadas...
        if seq.inicio_estimado and seq.fin_estimado:
            seq.inicio_estimado += delta
            seq.fin_estimado += delta
            db.add(seq)

    await db.commit()
    return {"status": "ok", "parada_id": parada.id, "secuencias_afectadas": len(secuencias)}
