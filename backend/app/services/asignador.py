from datetime import date, datetime, timezone
from sqlmodel import select, text
from app.models.maquina import Maquina
from app.models.orden_fabricacion import OrdenFabricacion
from app.models.semana_programacion import SemanaProgramacion
from app.models.setup_penalizacion import SetupPenalizacion
from app.services.icc import calcular_costo_cambio, calcular_icc

async def sugerir_maquina(db, of_id: int) -> list[dict]:
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

    # Obtener fecha de inicio de la semana actual
    today = date.today()
    year, week_num, _ = today.isocalendar()
    semana_start = date.fromisocalendar(year, week_num, 1)

    ranking = []

    for maq in maquinas:
        # a. Obtener la semana programada para esta máquina
        res_sem = await db.execute(
            select(SemanaProgramacion)
            .where(SemanaProgramacion.maquina_id == maq.id)
            .where(SemanaProgramacion.fecha_inicio == semana_start)
        )
        sem = res_sem.scalars().first()

        horas_disponibles = 40.0  # default
        if sem and sem.horas_disponibles is not None:
            horas_disponibles = float(sem.horas_disponibles)

        # Cargar las OFs asignadas
        if sem:
            # OFs en la secuencia de esta semana
            q_ofs = text("""
                SELECT of.* 
                FROM sipp.secuencias_produccion sp
                JOIN sipp.ordenes_fabricacion of ON of.id = sp.orden_fabricacion_id
                WHERE sp.semana_id = :semana_id AND of.estado = 'PENDIENTE'
            """)
            res_ofs = await db.execute(q_ofs, {"semana_id": sem.id})
            ofs_asignadas = [OrdenFabricacion(**row) for row in res_ofs.mappings().all()]
        else:
            # Si no hay semana en BD, buscar OFs PENDIENTEs asignadas directamente a la máquina
            res_ofs = await db.execute(
                select(OrdenFabricacion)
                .where(OrdenFabricacion.maquina_asignada_id == maq.id)
                .where(OrdenFabricacion.estado == "PENDIENTE")
            )
            ofs_asignadas = res_ofs.scalars().all()

        # Calcular carga actual en horas
        horas_usadas = sum(float(o.horas_produccion or 0.0) for o in ofs_asignadas)
        carga_pct = (horas_usadas / horas_disponibles * 100.0) if horas_disponibles > 0 else 0.0
        # Clampear carga_pct a 100 máximo para el cálculo de score
        carga_pct_calc = min(100.0, carga_pct)

        # b. Calcular compatibilidad promedio ICC
        icc_scores = []
        for o_asig in ofs_asignadas:
            if o_asig.id == of.id:
                continue
            setup_min, _ = calcular_costo_cambio(o_asig, of, penalizaciones)
            icc_val = calcular_icc(setup_min)
            icc_scores.append(icc_val)

        icc_promedio = sum(icc_scores) / len(icc_scores) if icc_scores else 100.0

        # c. Score
        score = (100.0 - carga_pct_calc) * 0.4 + icc_promedio * 0.6

        ranking.append({
            "maquina": maq.codigo,
            "score": round(score, 1),
            "carga_pct": round(carga_pct, 1),
            "icc_promedio": round(icc_promedio, 1)
        })

    # Ordenar ranking por score desc
    ranking.sort(key=lambda x: x["score"], reverse=True)
    return ranking
