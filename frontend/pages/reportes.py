import streamlit as st
import pandas as pd
import datetime
import io
from utils.api_client import (
    get_plan_semanal, get_kpi_semanal, get_semanas, get_optimizaciones_log
)

st.set_page_config(layout="wide", page_title="SIPP — Reportes", page_icon="🏭")

def opciones_semanas():
    today = datetime.date.today()
    weeks = []
    for i in range(-5, 10):
        d = today + datetime.timedelta(weeks=i)
        year, week_num, _ = d.isocalendar()
        weeks.append(f"{year}-W{week_num:02d}")
    return sorted(list(set(weeks)))

def to_excel(df):
    output = io.BytesIO()
    # openpyxl engine is standard for pandas to write xlsx
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plan Semanal')
    return output.getvalue()

# ── Sidebar ──────────────────────────────────────────────
with st.sidebar:
    st.title("🏭 SIPP - VYGPACK")
    semana_sel = st.selectbox("Semana para Reportes", opciones_semanas())
    st.divider()
    st.page_link("app.py", label="🏠 Dashboard Principal")
    st.page_link("pages/ordenes.py", label="📋 Órdenes")
    st.page_link("pages/semanas.py", label="📅 Semanas")

st.title("📊 Reportes y Control Semanal")
st.write(f"Visualizando datos para la semana: **{semana_sel}**")

# Cargar la data del plan semanal
plan_data = get_plan_semanal(semana_sel) or []

# Cargar los KPI semanales para Carga y Capacidad
kpi_data = get_kpi_semanal(semana_sel) or []

# Cargar semanas del backend para obtener las horas disponibles netas
semanas_todas = get_semanas() or []

# Crear las pestañas
tab_prog, tab_setup, tab_carga, tab_historial = st.tabs([
    "📅 Programa Semanal",
    "⏱ Tiempos de Setup",
    "⚡ Carga y Capacidad",
    "📜 Histórico de Cambios"
])

# ─────────────────────────────────────────────────────────
# TAB 1: Programa Semanal
# ─────────────────────────────────────────────────────────
with tab_prog:
    st.subheader("Programa Semanal de Producción")
    if not plan_data:
        st.info("No hay datos de programación para esta semana. Asegúrese de haber ejecutado el optimizador en el Dashboard.")
    else:
        df_plan = pd.DataFrame(plan_data)
        
        # Mapeo y selección de columnas para mostrar
        # pos | OF | medida | MT | setup(h) | producción(h) | total(h) | entrega
        df_show = df_plan[[
            "posicion", "codigo_of", "medida_texto", "mt_a_producir",
            "setup_horas", "horas_produccion", "horas_total_of", "fecha_entrega"
        ]].copy()
        
        df_show.columns = [
            "pos", "OF", "medida", "MT", "setup(h)", "producción(h)", "total(h)", "entrega"
        ]
        
        st.dataframe(df_show, width='stretch', hide_index=True)
        
        # Botón para descargar Excel
        excel_bytes = to_excel(df_show)
        st.download_button(
            label="📄 Exportar a Excel",
            data=excel_bytes,
            file_name=f"Plan_Semanal_{semana_sel}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

# ─────────────────────────────────────────────────────────
# TAB 2: Tiempos de Setup
# ─────────────────────────────────────────────────────────
with tab_setup:
    st.subheader("Estimación de Tiempos de Setup")
    if not plan_data:
        st.info("No hay datos de setups estimados para esta semana.")
    else:
        df_setup = pd.DataFrame(plan_data)
        
        # Seleccionar columnas relevantes para setup
        # Incluir maquina, pos, OF, setup (minutos), motivo
        df_setup_show = df_setup[[
            "maquina", "posicion", "codigo_of", "setup_min", "motivo_setup"
        ]].copy()
        
        df_setup_show.columns = [
            "Máquina", "Posición", "OF", "Setup (min)", "Motivo de Setup"
        ]
        
        def colorear_severidad(row):
            # Asignar color según los minutos de setup
            val = row["Setup (min)"]
            color = ""
            if val > 120:
                color = "background-color: #f8d7da; color: #721c24;" # Rojo
            elif val > 45:
                color = "background-color: #fff3cd; color: #856404;" # Amarillo
            else:
                color = "background-color: #d4edda; color: #155724;" # Verde
            
            return [color] * len(row)
            
        styled_setup = df_setup_show.style.apply(colorear_severidad, axis=1)
        st.dataframe(styled_setup, width='stretch', hide_index=True)

# ─────────────────────────────────────────────────────────
# TAB 3: Carga y Capacidad
# ─────────────────────────────────────────────────────────
with tab_carga:
    st.subheader("Carga de Trabajo vs Capacidad Disponible")
    
    maquinas_objetivo = ["M8", "M10", "M14"]
    
    # Intentar parsear las fechas de inicio de la semana
    try:
        year, week_num = map(int, semana_sel.split("-W"))
        semana_start = datetime.date.fromisocalendar(year, week_num, 1)
    except ValueError:
        semana_start = None
        
    for maq_code in maquinas_objetivo:
        # Encontrar datos en el KPI semanal
        kpi_maq = next((k for k in kpi_data if k["maquina"] == maq_code), None)
        
        # Encontrar horas disponibles en la tabla de semanas programadas
        horas_disponibles = 40.0 # Valor por defecto de 5 días de 8 horas si no existe registro
        if semana_start:
            sem_reg = next((s for s in semanas_todas if s["maquina_codigo"] == maq_code and s["fecha_inicio"] == str(semana_start)), None)
            if sem_reg:
                horas_disponibles = float(sem_reg["horas_disponibles"])
        
        total_setup_h = 0.0
        total_prod_h = 0.0
        utilizacion_pct = 0.0
        
        if kpi_maq:
            total_setup_h = float(kpi_maq.get("setup_total_horas", 0.0) or 0.0)
            total_prod_h = float(kpi_maq.get("horas_produccion_total", 0.0) or 0.0)
            
        # Sumar tiempos para obtener el total de horas usadas
        horas_usadas = total_setup_h + total_prod_h
        
        # Calcular porcentaje de utilización real sobre las horas disponibles
        if horas_disponibles > 0:
            utilizacion_pct = (horas_usadas / horas_disponibles) * 100
        else:
            utilizacion_pct = 0.0
            
        st.write(f"### Máquina {maq_code}")
        col_c1, col_c2, col_c3 = st.columns(3)
        col_c1.metric("Horas Disponibles", f"{horas_disponibles:.1f} h")
        col_c2.metric("Horas Usadas (Setup + Prod)", f"{horas_usadas:.2f} h")
        col_c3.metric("Utilización", f"{utilizacion_pct:.1f} %")
        
        # st.progress requiere valor entre 0.0 y 1.0. Clampear para evitar errores.
        pct_clamp = min(1.0, max(0.0, utilizacion_pct / 100.0))
        st.progress(pct_clamp)
        st.divider()

# ─────────────────────────────────────────────────────────
# TAB 4: Histórico de Cambios
# ─────────────────────────────────────────────────────────
with tab_historial:
    st.subheader("Histórico de Optimización de Secuencias")
    logs = get_optimizaciones_log()
    if not logs:
        st.info("No hay registros de optimizaciones realizadas en el sistema.")
    else:
        df_logs = pd.DataFrame(logs)
        # Mostrar columnas requeridas: fecha | máquina | órdenes evaluadas | setup antes(h) | setup después(h) | reducción(%)
        df_logs_show = df_logs[[
            "fecha", "maquina", "ordenes_evaluadas", "setup_antes_h", "setup_despues_h", "reduccion_pct"
        ]].copy()
        
        df_logs_show.columns = [
            "Fecha", "Máquina", "Órdenes Evaluadas", "Setup Antes (h)", "Setup Después (h)", "Reducción (%)"
        ]
        
        st.dataframe(df_logs_show, width='stretch', hide_index=True)
