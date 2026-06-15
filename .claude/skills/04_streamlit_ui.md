# Skill: Dashboard Streamlit (Anexo 20)
# Archivo: .claude/skills/04_streamlit_ui.md
# Cuándo usarlo: cada vez que el agente deba crear o modificar
# frontend/app.py  o  frontend/utils/api_client.py

---

## Propósito
Construir el HMI (interfaz de planta) de SIPP en Streamlit replicando
el diseño del Anexo 20 del documento. Toda la data viene del backend FastAPI
via HTTP — NUNCA conectar directo a PostgreSQL desde el frontend.

---

## Regla fundamental

```python
# ✅ CORRECTO — toda data via api_client
from utils.api_client import get_cola_maquina, get_kpi_semanal

# ❌ PROHIBIDO — nunca en el frontend
import psycopg2
from backend.app.models import ...
```

---

## Cliente HTTP (`frontend/utils/api_client.py`)

```python
import os
import requests
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def _get(ruta: str, params: dict = None):
    try:
        r = requests.get(f"{BASE_URL}{ruta}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None   # el llamador muestra st.error(...)
    except Exception:
        return None

def get_kpi_semanal(semana: str = None) -> list[dict] | None:
    return _get("/api/v1/kpi/semanal", params={"semana": semana} if semana else None)

def get_cola_maquina(maquina_id: int, semana: str = None) -> list[dict] | None:
    return _get(f"/api/v1/maquinas/{maquina_id}/cola", params={"semana": semana} if semana else None)

def get_maquinas() -> list[dict] | None:
    return _get("/api/v1/maquinas/")

def ejecutar_optimizador(semana_id: int) -> dict | None:
    try:
        r = requests.post(f"{BASE_URL}/api/v1/optimizador/ejecutar",
                          json={"semana_id": semana_id}, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def importar_csv(archivo_bytes: bytes, nombre: str) -> dict | None:
    try:
        r = requests.post(
            f"{BASE_URL}/api/v1/ordenes/importar",
            files={"archivo": (nombre, archivo_bytes, "text/csv")},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
```

---

## Layout del dashboard principal (`frontend/app.py`)

```python
import streamlit as st
import pandas as pd
from utils.api_client import get_kpi_semanal, get_cola_maquina, get_maquinas, ejecutar_optimizador

st.set_page_config(
    page_title="SIPP — VYGPACK",
    page_icon="🏭",
    layout="wide",
)

# ── Sidebar ──────────────────────────────────────────────
with st.sidebar:
    st.image("static/logo_vygpack.png", width=140)   # si existe
    st.title("SIPP")
    semana_sel = st.selectbox("Semana", opciones_semanas())  # función que llama al backend
    st.divider()
    st.page_link("pages/ordenes.py",     label="📋 Órdenes")
    st.page_link("pages/importar.py",    label="📥 Importar CSV")
    st.page_link("pages/setups.py",      label="⏱ Registrar Setup")
    st.page_link("pages/maestros.py",    label="🗂 Maestros")

# ── KPIs (fila superior) ──────────────────────────────────
st.subheader("Semana en curso")
kpis = get_kpi_semanal(semana_sel)

if kpis is None:
    st.error("⚠ Backend no disponible. Verifique que FastAPI esté corriendo en localhost:8000")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
total_ofs    = sum(k["total_ordenes"] for k in kpis)
setup_horas  = sum(k["setup_total_horas"] or 0 for k in kpis)
utilizacion  = round(sum(k["utilizacion_pct"] or 0 for k in kpis) / max(len(kpis), 1), 1)

col1.metric("Total OFs programadas", total_ofs)
col2.metric("Setup total (h)",        f"{setup_horas:.1f} h")
col3.metric("Utilización promedio",   f"{utilizacion:.1f} %")
col4.metric("Máquinas activas",       len(kpis))

st.divider()

# ── Cuerpo: Cola de máquinas | Matriz ICC ─────────────────
col_cola, col_icc = st.columns([3, 2])

with col_cola:
    st.subheader("Cola de producción")

    maquinas = get_maquinas() or []
    tabs = st.tabs([m["codigo"] for m in maquinas])

    for tab, maq in zip(tabs, maquinas):
        with tab:
            cola = get_cola_maquina(maq["id"], semana_sel)
            if not cola:
                st.info("Sin órdenes programadas para esta semana.")
                continue

            df = pd.DataFrame(cola)

            # Badge de estado con color
            def badge(estado: str) -> str:
                colores = {
                    "PENDIENTE":   "🔘",
                    "EN_PROCESO":  "🔵",
                    "COMPLETADA":  "🟢",
                    "OMITIDA":     "⚫",
                }
                return f"{colores.get(estado, '⚪')} {estado}"

            df["estado"] = df["estado_secuencia"].apply(badge)

            st.dataframe(
                df[["posicion", "codigo_of", "medida_texto", "material",
                    "colores_detalle", "costo_setup_min", "fecha_entrega", "estado"]],
                column_config={
                    "posicion":       st.column_config.NumberColumn("#", width="small"),
                    "codigo_of":      st.column_config.TextColumn("OF"),
                    "medida_texto":   st.column_config.TextColumn("Medida"),
                    "material":       st.column_config.TextColumn("Material"),
                    "colores_detalle":st.column_config.TextColumn("Colores"),
                    "costo_setup_min":st.column_config.NumberColumn("Setup (min)", format="%.0f"),
                    "fecha_entrega":  st.column_config.DateColumn("F. Entrega"),
                    "estado":         st.column_config.TextColumn("Estado"),
                },
                hide_index=True,
                use_container_width=True,
            )

with col_icc:
    st.subheader("Matriz de compatibilidad (ICC)")
    # La matriz ICC se construye con datos del cache
    # Ver función render_matriz_icc() abajo
    render_matriz_icc(semana_sel)

    st.divider()
    if st.button("▶ Ejecutar Optimizador", type="primary", use_container_width=True):
        with st.spinner("Optimizando secuencias..."):
            # obtener semana_id del backend
            resultado = ejecutar_optimizador(semana_id=get_semana_id(semana_sel))
        if resultado:
            st.success(f"✓ Reducción de setup: {resultado['reduccion_pct']}%")
            st.rerun()
        else:
            st.error("Error al ejecutar el optimizador.")
```

---

## Función: Matriz ICC coloreada

```python
import streamlit as st
import pandas as pd

def render_matriz_icc(semana: str):
    """
    Renderiza la matriz de compatibilidad como tabla HTML coloreada.
    Verde = ICC alto (bajo setup). Rojo = ICC bajo (alto setup).
    """
    from utils.api_client import _get
    datos = _get("/api/v1/kpi/icc_matrix", params={"semana": semana})

    if not datos:
        st.info("Sin datos de compatibilidad. Ejecute el optimizador primero.")
        return

    df = pd.DataFrame(datos["matrix"])
    df = df.set_index("of_origen")

    def colorear_icc(val):
        try:
            v = float(val)
        except (TypeError, ValueError):
            return ""
        if v >= 80:
            return "background-color: #d4edda; color: #155724"   # verde
        if v >= 50:
            return "background-color: #fff3cd; color: #856404"   # amarillo
        return "background-color: #f8d7da; color: #721c24"       # rojo

    styled = df.style.applymap(colorear_icc).format("{:.0f}")
    st.dataframe(styled, use_container_width=True)
```

---

## Página: Importar CSV (`frontend/pages/importar.py`)

```python
import streamlit as st
from utils.api_client import importar_csv

st.title("📥 Importar CSV de programación")
st.write("Suba el archivo mensual de VYGPACK (formato: `PROGRAMACIÓN_MES.csv`)")

archivo = st.file_uploader("Seleccionar CSV", type=["csv"])

if archivo and st.button("Importar", type="primary"):
    with st.spinner("Procesando CSV..."):
        resultado = importar_csv(archivo.read(), archivo.name)

    if resultado:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total filas",  resultado["total_filas"])
        col2.metric("Insertadas",   resultado["insertadas"])
        col3.metric("Actualizadas", resultado["actualizadas"])

        if resultado["errores"] > 0:
            st.warning(f"⚠ {resultado['errores']} filas con errores")
            with st.expander("Ver detalle de errores"):
                for err in resultado["detalle_errores"]:
                    st.text(err)
        else:
            st.success("✓ CSV importado sin errores")
    else:
        st.error("Error al conectar con el backend.")
```

---

## Caché de llamadas al backend

```python
import streamlit as st

@st.cache_data(ttl=30)   # 30 segundos — evita sobrecargar el backend
def get_kpi_semanal_cached(semana: str):
    from utils.api_client import get_kpi_semanal
    return get_kpi_semanal(semana)
```

Usar `@st.cache_data(ttl=30)` en TODAS las funciones que llamen al backend.
Llamar `st.rerun()` después de ejecutar el optimizador o importar CSV para refrescar.

---

## Checklist antes de dar por terminado el frontend

- [ ] Ningún `import` apunta a `backend/`
- [ ] Ninguna conexión directa a PostgreSQL
- [ ] Toda llamada al backend está envuelta en try/except en `api_client.py`
- [ ] Si `api_client` retorna `None` → mostrar `st.error(...)` y `st.stop()` o continuar sin datos
- [ ] `@st.cache_data(ttl=30)` en todas las llamadas al backend
- [ ] Tabs de máquinas con `st.tabs([...])` — una tab por máquina
- [ ] Matriz ICC usa colores: verde ≥80, amarillo ≥50, rojo <50
- [ ] Botón "Ejecutar Optimizador" llama al endpoint y hace `st.rerun()` al éxito
- [ ] Página de importación muestra métricas: total, insertadas, actualizadas, errores
- [ ] `st.set_page_config(layout="wide")` en `app.py`
