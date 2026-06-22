import streamlit as st

st.set_page_config(page_title="Documentación Técnica — SIPP", layout="wide")

st.markdown("""
# 📘 Documentación Técnica — SIPP
### Sistema Inteligente de Programación de Producción
**VYGPACK** · Lima, Perú · 
[Ver repositorio en GitHub](https://github.com/ilandbz/sipp)
""")

st.info(
    "Este documento describe la lógica principal del sistema SIPP, "
    "incluyendo el motor de cálculo de setup, el optimizador de secuencias "
    "y los indicadores clave de producción."
)

st.divider()

# ── 1. FÓRMULA DE SETUP ─────────────────────────────────────────
st.markdown("## 1. Motor de Cálculo de Setup (ICC)")
st.markdown("""
El núcleo del sistema calcula el **Índice de Compatibilidad de Cambio (ICC)**
entre dos Órdenes de Fabricación consecutivas. La fórmula implementada
refleja los tiempos reales validados con el equipo de producción de VYGPACK:

> **IC = T_material + T_formato + T_color + T_clisé + T_pruebas**

Cada componente aplica solo si existe un cambio real entre la OF anterior
y la OF siguiente. Si hay cualquier tipo de cambio, se agregan 120 min
fijos de pruebas y reajustes.
""")

st.code("""
# backend/app/services/icc.py
# Función principal de cálculo de costo de cambio entre dos OFs

async def calcular_costo_cambio_async(db, of_a: dict, of_b: dict,
                                       penalizaciones: dict) -> tuple:
    total = 0.0
    detalle = []
    hay_setup = False

    # T_formato: detectar tipo de cambio de medida
    cambio_ancho_fuelle = (ancho_a != ancho_b or fuelle_a != fuelle_b)
    cambio_solo_alto    = (not cambio_ancho_fuelle and alto_a != alto_b)

    if cambio_ancho_fuelle:
        if maq_codigo == "M8":
            # M8 tiene excepciones por par de bolsa (tabla setup_cambio_medida_m8)
            costo_medida = obtener_excepcion_m8(num_a, num_b)
        elif maq_codigo in ("M10", "M14"):
            costo_medida = 240  # 4h fijas para M10 y M14
        total += costo_medida
        hay_setup = True

    # T_color: lavado de estación de impresión
    if col_a != col_b:
        total += 30  # 0.5h
        hay_setup = True

    # T_clisé: 120 min por cada color del diseño destino
    if cilindro_cambia:
        total += 120 * num_colores_destino
        hay_setup = True

    # T_material: cambio de tipo de papel o bobina
    if material_cambia:
        total += 18  # 0.3h
        hay_setup = True

    # Riesgo matizado: colores PANTONE/MATIZ/GCMI agregan 30 min extra
    if es_matizado and hay_setup:
        total += 30

    # T_pruebas: siempre si hay cualquier cambio
    if hay_setup:
        total += 120  # 2h fijas de pruebas y reajustes

    return total, {"detalle": detalle, "total_min": total}
""", language="python")

st.caption(
    "📁 Archivo: `backend/app/services/icc.py` · "
    "[Ver en GitHub](https://github.com/ilandbz/sipp/blob/main/backend/app/services/icc.py)"
)

st.divider()

# ── 2. OPTIMIZADOR GREEDY ───────────────────────────────────────
st.markdown("## 2. Optimizador de Secuencias (Greedy Nearest-Neighbor)")
st.markdown("""
El optimizador ordena las Órdenes de Fabricación dentro de cada máquina
para **minimizar el setup total semanal**. Usa el algoritmo
**Greedy Nearest-Neighbor**: para cada posición, elige la OF que tenga
el menor costo de cambio respecto a la OF anterior.

La primera OF de cada máquina se elige por **fecha de entrega más urgente**,
garantizando que las entregas críticas se produzcan primero.
""")

st.code("""
# backend/app/services/optimizer.py
# Algoritmo greedy para ordenar OFs minimizando setup

async def _ordenar_greedy(db, ofs: list, penalizaciones: dict) -> list:
    # Primera OF: la más urgente por fecha de entrega
    ofs_sorted = sorted(ofs,
        key=lambda o: str(o.get("fecha_entrega") or "9999-12-31"))
    
    resultado  = [ofs_sorted[0]]
    restantes  = list(ofs_sorted[1:])

    while restantes:
        actual      = resultado[-1]
        mejor_idx   = 0
        mejor_costo = float('inf')

        # Evaluar todas las OFs restantes y elegir la más compatible
        for i, candidata in enumerate(restantes):
            costo, _ = await calcular_costo_cambio_async(
                db, actual, candidata, penalizaciones
            )
            if costo < mejor_costo:
                mejor_costo = costo
                mejor_idx   = i

        resultado.append(restantes.pop(mejor_idx))

    return resultado
""", language="python")

st.caption(
    "📁 Archivo: `backend/app/services/optimizer.py` · "
    "[Ver en GitHub](https://github.com/ilandbz/sipp/blob/main/backend/app/services/optimizer.py)"
)

st.divider()

# ── 3. EXCEPCIONES M8 ──────────────────────────────────────────
st.markdown("## 3. Tabla de Excepciones de Setup — Máquina M8")
st.markdown("""
La máquina M8 tiene tiempos de cambio de medida específicos según el
**par de bolsas** (origen → destino). Esto refleja que ciertos cambios
en M8 son más rápidos que el estándar de 8h, como el cambio entre
Bolsa #5 y Bolsa #6 (solo ajuste de altura = 30 min).

Esta información se almacena en la tabla `sipp.setup_cambio_medida_m8`
y se consulta en tiempo real durante el cálculo de ICC.
""")

st.code("""
-- Base de datos PostgreSQL: sipp.setup_cambio_medida_m8
-- Tiempos reales validados con el equipo de producción VYGPACK

SELECT bolsa_origen, bolsa_destino, minutos, minutos/60.0 AS horas
FROM sipp.setup_cambio_medida_m8
ORDER BY bolsa_origen, bolsa_destino;

-- Ejemplos de excepciones M8:
-- BC#5 → BC#6 : 30 min  (solo ajuste de altura)
-- BC#5 → BC#8 : 120 min (cambio parcial)
-- BC#5 → BC#10: 180 min (cambio significativo)
-- BC#8 → BC#12: 240 min (cambio completo inferior)
-- Resto        : 480 min (cambio de formato completo = 8h)

-- M10 y M14: siempre 240 min (4h) para cualquier cambio de medida
""", language="sql")

st.caption(
    "📁 Base de datos: `sipp.setup_cambio_medida_m8` · "
    "Solo aplica para Máquina M8 · M10/M14 usan 240 min fijos"
)

st.divider()

# ── 4. KPI ENDPOINT ────────────────────────────────────────────
st.markdown("## 4. Endpoint de KPIs Semanales")
st.markdown("""
El backend expone un endpoint REST que calcula en tiempo real los
**indicadores clave de producción** de la semana seleccionada:
total de OFs, horas de setup, horas de producción y porcentaje
de utilización de las 3 máquinas.
""")

st.code("""
# backend/app/api/routers/kpi.py
# Endpoint: GET /api/v1/kpi/semana/{semana_id}

@router.get("/semana/{semana_id}")
async def kpi_por_semana(semana_id: int,
                          db: AsyncSession = Depends(get_session)):
    result = await db.execute(text(\"\"\"
        SELECT
            COUNT(sp.id)                              AS total_ofs,
            ROUND(SUM(sp.costo_setup_min) / 60, 2)   AS setup_total_horas,
            COALESCE(SUM(of.horas_produccion), 0)     AS horas_produccion,
            s.horas_disponibles,
            ROUND(
                (SUM(of.horas_produccion) +
                 SUM(sp.costo_setup_min) / 60)
                / s.horas_disponibles * 100, 1
            )                                         AS utilizacion_pct,
            s.estado, s.fecha_inicio, s.fecha_fin
        FROM sipp.semanas_programacion s
        LEFT JOIN sipp.secuencias_produccion sp ON sp.semana_id = s.id
        LEFT JOIN sipp.ordenes_fabricacion of   ON of.id = sp.orden_fabricacion_id
        WHERE s.id = :semana_id
        GROUP BY s.id, s.horas_disponibles, s.estado,
                 s.fecha_inicio, s.fecha_fin
    \"\"\"), {"semana_id": semana_id})
    return dict(result.mappings().one_or_none())
""", language="python")

st.caption(
    "📁 Archivo: `backend/app/api/routers/kpi.py` · "
    "[Ver en GitHub](https://github.com/ilandbz/sipp/blob/main/backend/app/api/routers/kpi.py)"
)

st.divider()

# ── 5. ANÁLISIS AUTOMÁTICO ──────────────────────────────────────
st.markdown("## 5. Análisis Automático de la Semana")
st.markdown("""
El sistema genera un **resumen ejecutivo automático** basado en reglas
de negocio aplicadas sobre los datos reales de la semana. Detecta:
utilización crítica, setup elevado, fechas de entrega vencidas,
colores de riesgo matizado y balance de carga por máquina.
No requiere API externa — toda la lógica corre en el servidor.
""")

st.code("""
# frontend/utils/analisis.py
# Generador de análisis ejecutivo automático

def generar_analisis_semanal(kpi: dict, cola: list,
                              setup_detalle: dict) -> str:
    # Detección de utilización crítica
    if util_pct >= 95:
        alerta("Semana sobrecargada — riesgo de no cumplir entregas")
    elif util_pct >= 85:
        alerta("Cerca del límite recomendado (85%) — poco margen")

    # Detección de OFs con entrega vencida
    for of in cola:
        if fecha_entrega < hoy:
            alertas.append(f"{codigo} vencida hace {dias} días")

    # Detección de colores de riesgo matizado
    palabras_riesgo = ["MATIZ", "PANTONE", "GCMI", "POR CONFIRMAR"]
    if any(p in colores for p in palabras_riesgo):
        alertas.append(f"{codigo} — riesgo de setup extendido")

    # Recomendación automática basada en combinación de indicadores
    if util_pct >= 85 and setup_h > 48:
        return "Semana con alta presión — evaluar mover OFs a siguiente semana"
    elif setup_h > 48:
        return "Setup elevado — agrupar OFs por tipo de bolsa en próxima semana"
    elif util_pct < 60:
        return "Capacidad disponible — considerar adelantar producción"
""", language="python")

st.caption(
    "📁 Archivo: `frontend/utils/analisis.py` · "
    "[Ver en GitHub](https://github.com/ilandbz/sipp/blob/main/frontend/utils/analisis.py)"
)

st.divider()

# ── 6. ARQUITECTURA GENERAL ─────────────────────────────────────
st.markdown("## 6. Arquitectura del Sistema")
st.markdown("""
SIPP usa una arquitectura cliente-servidor con separación clara
entre frontend y backend:
""")

st.code("""
vygpack-sipp/
├── backend/app/
│   ├── api/routers/          # Endpoints REST (FastAPI)
│   │   ├── kpi.py            # KPIs, análisis, plan semanal
│   │   ├── semanas.py        # Gestión de semanas y secuencias
│   │   ├── optimizador.py    # Trigger del optimizador
│   │   └── ordenes.py        # CRUD de Órdenes de Fabricación
│   └── services/
│       ├── icc.py            # Motor de cálculo de setup (ICC)
│       └── optimizer.py      # Algoritmo greedy de secuenciación
│
├── frontend/
│   ├── app.py                # Dashboard principal con KPIs
│   ├── pages/
│   │   ├── semanas.py        # Gestión y ejecución de semanas
│   │   ├── ordenes.py        # Formulario de OFs
│   │   ├── reportes.py       # Reportes y vista ejecutiva
│   │   └── icc_simulador.py  # Simulador interactivo de ICC
│   └── utils/
│       ├── api_client.py     # Cliente HTTP hacia el backend
│       └── analisis.py       # Análisis automático semanal
│
# Stack técnico:
# Backend:  FastAPI + SQLModel async + PostgreSQL 16
# Frontend: Streamlit (Python)
# Deploy:   VPS Ubuntu 24 + Apache + Gunicorn + systemd
# Repo:     https://github.com/ilandbz/sipp
""", language="bash")

st.markdown("""
---
**Repositorio:** [https://github.com/ilandbz/sipp](https://github.com/ilandbz/sipp)  
**Producción:** [https://sipp.macrocompany.net.pe](https://sipp.macrocompany.net.pe)  
**Stack:** FastAPI · PostgreSQL · Streamlit · Python 3.12 · Ubuntu 24  
**Cliente:** VYGPACK — Fábrica de Bolsas de Papel Kraft · Lima, Perú
""")
