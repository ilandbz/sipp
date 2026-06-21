import streamlit as st
import pandas as pd
import datetime
import io
from utils.api_client import (
    get_plan_semanal, get_kpi_semanal, get_semanas, get_optimizaciones_log
)
from auth import require_login, can, render_sidebar

require_login()

if not can("ver_reportes"):
    st.error("Acceso restringido")
    st.stop()

st.set_page_config(layout="wide", page_title="SIPP — Reportes", page_icon="🏭")
render_sidebar()

def opciones_semanas():
    semanas = get_semanas() or []
    opciones = {}
    for s in semanas:
        es_global = s.get("es_global", False)
        maquina = "🌐 Global" if es_global else s.get("maquina_codigo", "")
        inicio = s.get("fecha_inicio", "")
        fin = s.get("fecha_fin", "")
        estado = s.get("estado", "")
        try:
            from datetime import datetime
            fi = datetime.strptime(str(inicio)[:10], "%Y-%m-%d").strftime("%d/%m")
            ff = datetime.strptime(str(fin)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
            label = f"{maquina} — {fi} al {ff} ({estado})"
        except Exception:
            label = f"Semana ID {s.get('id')}"
        opciones[label] = s.get("id")
    return opciones if opciones else {"Sin semanas": None}

def to_excel(df):
    output = io.BytesIO()
    # openpyxl engine is standard for pandas to write xlsx
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plan Semanal')
    return output.getvalue()

# ── Sidebar ──────────────────────────────────────────────
with st.sidebar:
    st.title("🏭 SIPP - VYGPACK")
    opciones = opciones_semanas()
    etiqueta_sel = st.selectbox("Semana para Reportes", list(opciones.keys()))
    semana_sel = opciones.get(etiqueta_sel)  # Ahora es un integer ID
    st.divider()
    st.page_link("app.py", label="🏠 Dashboard Principal")
    st.page_link("pages/ordenes.py", label="📋 Órdenes")
    st.page_link("pages/semanas.py", label="📅 Semanas")

st.title("📊 Reportes y Control Semanal")
st.write(f"Visualizando datos para la semana: **{etiqueta_sel}**")

# Cargar la data del plan semanal
plan_data = get_plan_semanal(semana_id=semana_sel) or []

# Cargar los KPI semanales para Carga y Capacidad
kpi_data = get_kpi_semanal(semana_id=semana_sel) or []

# Cargar semanas del backend para obtener las horas disponibles netas
semanas_todas = get_semanas() or []

# Crear las pestañas
tab_prog, tab_setup, tab_carga, tab_historial, tab_ejecutiva = st.tabs([
    "📋 Programa Semanal",
    "⏱ Tiempos de Setup",
    "⚡ Carga y Capacidad",
    "📜 Histórico de Cambios",
    "🎯 Vista Ejecutiva"
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
        
        if "Setup (min)" in df_setup_show.columns:
            df_setup_show["Setup (min)"] = pd.to_numeric(df_setup_show["Setup (min)"], errors="coerce").fillna(0)
            
        def colorear_severidad(val):
            try:
                v = float(val)
            except (TypeError, ValueError):
                return ""
            if v <= 0:
                return ""
            elif v <= 90:
                return "background-color: #1b5e20; color: white"
            elif v <= 300:
                return "background-color: #f9a825; color: black"
            elif v <= 480:
                return "background-color: #e65100; color: white"
            else:
                return "background-color: #b71c1c; color: white"
            
        styled_setup = df_setup_show.style.map(colorear_severidad, subset=["Setup (min)"])
        st.dataframe(styled_setup, width='stretch', hide_index=True)

# ─────────────────────────────────────────────────────────
# TAB 3: Carga y Capacidad
# ─────────────────────────────────────────────────────────
with tab_carga:
    st.subheader("Carga de Trabajo vs Capacidad Disponible")
    
    maquinas_objetivo = ["M8", "M10", "M14"]
    
    # Intentar obtener la fecha de inicio de la semana seleccionada
    semana_start = None
    if semana_sel:
        sem_reg = next((s for s in semanas_todas if s["id"] == semana_sel), None)
        if sem_reg and sem_reg.get("fecha_inicio"):
            try:
                from datetime import datetime
                semana_start = datetime.strptime(str(sem_reg["fecha_inicio"])[:10], "%Y-%m-%d").date()
            except Exception:
                pass
        
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

# ─────────────────────────────────────────────────────────
# TAB 5: Vista Ejecutiva
# ─────────────────────────────────────────────────────────
with tab_ejecutiva:
    st.markdown("### 🎯 Vista Ejecutiva — Plan de Producción")
    st.caption("Tabla resumen para presentaciones y reuniones de producción.")

    if not plan_data:
        st.info("No hay datos para esta semana. Ejecute el optimizador primero.")
    else:
        import pandas as pd
        from datetime import date

        hoy = date.today()

        # Construir DataFrame enriquecido
        filas = []
        for i, of in enumerate(plan_data, 1):
            setup_min = float(of.get("setup_min") or 0)
            fecha_ent = of.get("fecha_entrega")
            estado_seq = of.get("estado_secuencia", "PENDIENTE")

            # Prioridad basada en fecha
            prioridad = "Baja"
            alerta_fecha = ""
            if fecha_ent:
                try:
                    fe = date.fromisoformat(str(fecha_ent)[:10])
                    dias = (fe - hoy).days
                    if dias < 0:
                        prioridad = "Alta"
                        alerta_fecha = f"⚠ Vencida ({abs(dias)}d)"
                    elif dias <= 3:
                        prioridad = "Alta"
                        alerta_fecha = f"⚠ Urgente ({dias}d)"
                    elif dias <= 7:
                        prioridad = "Media"
                        alerta_fecha = f"({dias}d)"
                    else:
                        alerta_fecha = str(fe.strftime("%d/%m"))
                except Exception:
                    alerta_fecha = str(fecha_ent)[:10] if fecha_ent else "—"
            else:
                alerta_fecha = "—"

            # Setup display
            if setup_min == 0:
                setup_display = "0 min"
                setup_clase = "sin cambio"
            elif setup_min < 480:
                setup_display = f"{int(setup_min)} min ({setup_min/60:.1f}h)"
                setup_clase = "medio"
            else:
                setup_display = f"{int(setup_min)} min ({setup_min/60:.1f}h)"
                setup_clase = "crítico"

            # Estado display
            estado_display = {
                "PENDIENTE": "⏳ Pendiente",
                "EN_PROCESO": "🔄 En proceso",
                "COMPLETADA": "✅ Completada",
                "BLOQUEADA": "🔒 Bloqueada"
            }.get(estado_seq, estado_seq)

            filas.append({
                "#": i,
                "Orden": of.get("codigo_of", "—"),
                "Descripción": (of.get("descripcion") or "—")[:45] + (
                    "..." if len(of.get("descripcion") or "") > 45 else ""
                ),
                "Máquina": of.get("maquina", "—"),
                "Medida": of.get("medida_texto", "—"),
                "Prioridad": prioridad,
                "Setup estimado": setup_display,
                "Entrega": alerta_fecha,
                "Estado": estado_display,
                "_setup_min": setup_min,
                "_prioridad_orden": 0 if prioridad == "Alta" else (
                    1 if prioridad == "Media" else 2
                )
            })

        df = pd.DataFrame(filas)

        # KPIs rápidos arriba
        col1, col2, col3, col4 = st.columns(4)
        total = len(df)
        alta = len(df[df["Prioridad"] == "Alta"])
        en_proceso = len(df[df["Estado"].str.contains("proceso", case=False, na=False)])
        completadas = len(df[df["Estado"].str.contains("Completada", case=False, na=False)])

        col1.metric("Total OFs", total)
        col2.metric("Alta prioridad", alta,
                    delta="urgentes" if alta > 0 else None,
                    delta_color="inverse")
        col3.metric("En proceso", en_proceso)
        col4.metric("Completadas", completadas,
                    delta=f"{round(completadas/total*100)}%" if total > 0 else None)

        st.divider()

        # Colorear según prioridad y setup
        def colorear_fila(row):
            if "Alta" in str(row.get("Prioridad", "")):
                return ["background-color: #FFEBEE"] * len(row)
            elif "Media" in str(row.get("Prioridad", "")):
                return ["background-color: #FFF8E1"] * len(row)
            return [""] * len(row)

        def colorear_setup(val):
            try:
                mins = float(str(val).split(" ")[0])
                if mins == 0:
                    return "color: #2E7D32; font-weight: 500"
                elif mins < 480:
                    return "color: #E65100; font-weight: 500"
                else:
                    return "color: #C62828; font-weight: 500"
            except Exception:
                return ""

        # Mostrar tabla sin columnas internas
        df_display = df.drop(columns=["_setup_min", "_prioridad_orden"])

        styled = (
            df_display.style
            .apply(colorear_fila, axis=1)
            .map(colorear_setup, subset=["Setup estimado"])
        )

        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            height=min(400, 40 + len(df) * 38)
        )

        # Leyenda
        st.caption(
            "🔴 Alta prioridad (entrega vencida o ≤3 días) · "
            "🟡 Media prioridad (entrega en 4-7 días) · "
            "⬜ Baja prioridad · "
            "Setup: verde=0min · naranja=<8h · rojo=≥8h"
        )

        st.divider()

        # Exportar a Excel
        st.markdown("#### 📥 Exportar")
        col_exp1, col_exp2 = st.columns([1, 3])
        with col_exp1:
            try:
                import io
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_display.to_excel(
                        writer,
                        sheet_name="Plan Producción",
                        index=False
                    )
                output.seek(0)
                st.download_button(
                    label="⬇ Descargar Excel",
                    data=output,
                    file_name=f"Plan_Produccion_Semana_{semana_sel}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error al generar Excel: {e}")

