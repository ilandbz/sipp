# Skill: Optimizador SMED + ICC
# Archivo: .claude/skills/02_optimizer.md
# Cuándo usarlo: cada vez que el agente deba crear o modificar
# backend/app/services/optimizer.py  o  backend/app/services/icc.py

---

## Propósito
Secuenciar las órdenes de fabricación (OFs) pendientes de una máquina
para una semana dada, minimizando los tiempos de setup según las reglas SMED de VYGPACK.

---

## Penalizaciones SMED (leer SIEMPRE desde BD — nunca hardcodear)

```python
from sqlmodel import select
from app.models.setup_penalizacion import SetupPenalizacion

async def cargar_penalizaciones(db) -> dict[str, float]:
    result = await db.execute(select(SetupPenalizacion).where(SetupPenalizacion.activo == True))
    return {p.tipo_cambio: float(p.minutos) for p in result.scalars().all()}
```

Valores actuales en `sipp.setup_penalizaciones`:

| tipo_cambio | minutos |
|---|---|
| `MISMO_FORMATO_MISMO_COLOR` | 0 |
| `CAMBIO_COLOR_LAVADO_ESTACION` | 45 |
| `CAMBIO_CLISE` | 17.5 |
| `CAMBIO_CILINDRO_IMPRESION` | 30 |
| `CAMBIO_MATERIAL` | 25 |
| `CAMBIO_FORMATO_MEDIDA_COMPLETA` | 480 |

Las penalizaciones son **acumulables** en una misma transición.

---

## Cálculo de costo de cambio entre dos OFs

```python
def calcular_setup(of_a, of_b, penalizaciones: dict) -> tuple[float, list[str]]:
    """
    Retorna (minutos_totales, lista_de_cambios_aplicados).
    of_a y of_b son instancias de OrdenFabricacion.
    """
    total = 0.0
    cambios = []

    # 1. Cambio de formato (medida completa) — penalización más alta, evaluar primero
    if of_a.ancho_mm != of_b.ancho_mm or of_a.alto_mm != of_b.alto_mm:
        costo = penalizaciones["CAMBIO_FORMATO_MEDIDA_COMPLETA"]
        total += costo
        cambios.append(f"Cambio formato → +{costo:.0f} min")

    # 2. Cambio de cilindro
    if of_a.cilindro_id != of_b.cilindro_id and of_b.cilindro_id is not None:
        costo = penalizaciones["CAMBIO_CILINDRO_IMPRESION"]
        total += costo
        cambios.append(f"Cambio cilindro → +{costo:.0f} min")

    # 3. Cambio de clisé
    if of_a.clise_id != of_b.clise_id and of_b.clise_id is not None:
        costo = penalizaciones["CAMBIO_CLISE"]
        total += costo
        cambios.append(f"Cambio clisé → +{costo:.0f} min")

    # 4. Cambio de color (si hay colores distintos → lavado de estación)
    color_a = (of_a.colores_detalle or "").split(",")[0].strip().upper()
    color_b = (of_b.colores_detalle or "").split(",")[0].strip().upper()
    if color_a and color_b and color_a != color_b:
        costo = penalizaciones["CAMBIO_COLOR_LAVADO_ESTACION"]
        total += costo
        cambios.append(f"Cambio color → +{costo:.0f} min")

    # 5. Cambio de material
    if of_a.material_id != of_b.material_id and of_b.material_id is not None:
        costo = penalizaciones["CAMBIO_MATERIAL"]
        total += costo
        cambios.append(f"Cambio material → +{costo:.0f} min")

    return total, cambios
```

---

## Cálculo del ICC (Índice de Compatibilidad de Cambio)

```python
def calcular_icc(setup_total_min: float) -> float:
    """
    Score 0–100. 100 = sin cambio. 0 = cambio de formato completo (480 min).
    """
    return max(0.0, min(100.0, 100.0 - (setup_total_min / 480.0 * 100.0)))
```

Interpretar el score:
- 80–100 → verde (compatible, bajo setup)
- 50–79  → amarillo (setup moderado)
- 0–49   → rojo (setup alto, evitar en lo posible)

---

## Algoritmo heurístico completo

```python
from datetime import datetime, timezone
from sqlmodel import select
from app.models.orden_fabricacion import OrdenFabricacion
from app.models.semana_programacion import SemanaProgramacion
from app.models.secuencia_produccion import SecuenciaProduccion
from app.models.icc_cache import IccCache
from app.models.log_optimizacion import LogOptimizacion

async def optimizar_semana(db, semana_id: int) -> dict:
    # 1. Cargar semana y penalizaciones
    semana = await db.get(SemanaProgramacion, semana_id)
    penalizaciones = await cargar_penalizaciones(db)

    # 2. OFs pendientes asignadas a esta máquina
    result = await db.execute(
        select(OrdenFabricacion)
        .where(
            OrdenFabricacion.maquina_asignada_id == semana.maquina_id,
            OrdenFabricacion.estado == "PENDIENTE",
        )
        .order_by(OrdenFabricacion.fecha_entrega.asc().nullslast())
    )
    ofs = result.scalars().all()

    if not ofs:
        return {"ordenes": 0, "setup_total_min": 0}

    # 3. Agrupación por compatibilidad:
    #    primero agrupar por cilindro_id, luego por color principal
    def clave_agrupacion(of):
        color = (of.colores_detalle or "").split(",")[0].strip().upper()
        return (of.cilindro_id or 0, color)

    ofs_ordenadas = sorted(ofs, key=clave_agrupacion)

    # 4. Calcular setup acumulado antes (para el log)
    setup_antes = sum(
        calcular_setup(ofs[i], ofs[i+1], penalizaciones)[0]
        for i in range(len(ofs)-1)
    )

    # 5. Eliminar secuencias previas de esta semana
    await db.execute(
        SecuenciaProduccion.__table__.delete()
        .where(SecuenciaProduccion.semana_id == semana_id)
    )

    # 6. Insertar nueva secuencia + cachear ICC
    setup_despues = 0.0
    for pos, of in enumerate(ofs_ordenadas, start=1):
        setup_min = 0.0
        motivo = ""
        if pos > 1:
            of_prev = ofs_ordenadas[pos - 2]
            setup_min, cambios = calcular_setup(of_prev, of, penalizaciones)
            motivo = " | ".join(cambios)
            setup_despues += setup_min

            # Cachear ICC par
            icc = calcular_icc(setup_min)
            cache = IccCache(
                of_origen_id=of_prev.id,
                of_destino_id=of.id,
                icc_score=icc,
                setup_total_min=setup_min,
                detalle_json={"cambios": cambios, "total_min": setup_min},
            )
            db.add(cache)

        seq = SecuenciaProduccion(
            semana_id=semana_id,
            orden_fabricacion_id=of.id,
            posicion=pos,
            costo_setup_min=setup_min,
            motivo_setup=motivo,
        )
        db.add(seq)

    # 7. Log de la corrida
    reduccion = ((setup_antes - setup_despues) / setup_antes * 100) if setup_antes else 0
    log = LogOptimizacion(
        semana_id=semana_id,
        maquina_id=semana.maquina_id,
        ordenes_evaluadas=len(ofs),
        setup_total_antes_min=setup_antes,
        setup_total_despues_min=setup_despues,
        reduccion_pct=round(reduccion, 2),
        ejecutado_en=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()

    return {
        "ordenes": len(ofs),
        "setup_antes_min": setup_antes,
        "setup_despues_min": setup_despues,
        "reduccion_pct": round(reduccion, 2),
    }
```

---

## Cálculo de tiempo de producción (BPM)

```python
def calcular_horas_produccion(cantidad_mt: float, velocidad_bpm_max: float, factor_velocidad: float) -> float:
    """
    cantidad_mt     = miles a producir (columna MT del CSV)
    velocidad_bpm_max = BPM máximo de la máquina
    factor_velocidad  = factor del material (1.0 Kraft, <1.0 papeles delgados)
    Retorna horas decimales.
    """
    if not cantidad_mt or not velocidad_bpm_max or not factor_velocidad:
        return 0.0
    bolsas_por_minuto = velocidad_bpm_max * factor_velocidad
    minutos = (cantidad_mt * 1000) / bolsas_por_minuto
    return round(minutos / 60, 2)
```

---

## Checklist antes de dar por terminado el optimizador

- [ ] Las penalizaciones se leen de `sipp.setup_penalizaciones` (no hardcodeadas)
- [ ] El cálculo de `calcular_setup()` evalúa los 5 tipos de cambio
- [ ] Las OFs se ordenan primero por `fecha_entrega`, luego reagrupadas por cilindro+color
- [ ] Se eliminan secuencias previas de la semana antes de insertar las nuevas
- [ ] Cada par de OFs consecutivas genera un registro en `sipp.icc_cache`
- [ ] Se registra la corrida en `sipp.log_optimizaciones` con setup antes/después
- [ ] `calcular_icc()` está clampeado a [0, 100]
- [ ] `calcular_horas_produccion()` usa `velocidad_bpm_max × factor_velocidad`
