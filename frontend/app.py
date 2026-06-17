import streamlit as st
import pandas as pd
import datetime
from utils.api_client import (
    get_kpi_semanal, get_cola_maquina, get_maquinas,
    ejecutar_optimizador, get_semanas, get_icc_matrix
)
from auth import restaurar_sesion, is_logged_in, login, logout, get_rol, can, render_sidebar
from pathlib import Path

st.set_page_config(
    page_title="SIPP — VYGPACK",
    page_icon="🏭",
    layout="wide",
)

# Intentar restaurar sesión desde cookie PRIMERO
restaurar_sesion()

# Si no está logueado → mostrar login
if not is_logged_in():
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("---")
        # Logo si existe
        logo = Path(__file__).parent / "static" / "logo_vygpack.png"
        if logo.exists():
            st.image(str(logo), width=200)
        else:
            st.markdown("# 🏭 SIPP")
        
        st.markdown("### Sistema de Programación de Producción")
        st.markdown("**VYGPACK**")
        st.markdown("---")
        
        with st.form("login_form"):
            usuario = st.text_input("👤 Usuario")
            clave   = st.text_input("🔒 Contraseña", type="password")
            entrar  = st.form_submit_button("Iniciar Sesión",
                        type="primary", use_container_width=True)
        
        if entrar:
            if login(usuario, clave):
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
        
        st.markdown("---")
        st.caption("© 2026 VYGPACK — Acceso restringido al personal autorizado")
    st.stop()

def opciones_semanas():
    semanas = get_semanas() or []
    if not semanas:
        return ["Sin semanas registradas"]
    
    opciones = {}
    for s in semanas:
        # Formato legible: "M8 — 16/06 al 20/06/2026 (BORRADOR)"
        maquina = s.get("maquina_codigo", s.get("maquina", ""))
        inicio = s.get("fecha_inicio", "")
        fin = s.get("fecha_fin", "")
        estado = s.get("estado", "")
        horas = s.get("horas_disponibles", 0)
        
        # Formatear fechas a DD/MM/YYYY
        try:
            from datetime import datetime
            fi = datetime.strptime(str(inicio)[:10], "%Y-%m-%d").strftime("%d/%m")
            ff = datetime.strptime(str(fin)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
            label = f"{maquina} — {fi} al {ff} ({estado})"
        except Exception:
            label = f"Semana ID {s.get('id')} - {maquina}"
        
        opciones[label] = s.get("id")
    
    return opciones

def render_matriz_icc(semana: str = None, semana_id: int = None):
    datos = get_icc_matrix(semana=semana, semana_id=semana_id)
    if not datos or "matrix" not in datos or not datos["matrix"]:
        st.info("Sin datos de compatibilidad. Ejecute el optimizador primero.")
        return
    df = pd.DataFrame(datos["matrix"])
    if df.empty:
        st.info("Sin datos de compatibilidad. Ejecute el optimizador primero.")
        return
    df = df.set_index("of_origen")
    
    def colorear_icc(val):
        try:
            v = float(val)
        except (TypeError, ValueError):
            return ""
        if v >= 80:
            return "background-color: #d4edda; color: #155724;"
        if v >= 50:
            return "background-color: #fff3cd; color: #856404;"
        return "background-color: #f8d7da; color: #721c24;"
        
    styled = df.style.map(colorear_icc).format(precision=0)
    st.dataframe(styled, width='stretch')

# ── Sidebar ──────────────────────────────────────────────
semanas_opciones = opciones_semanas()
semana_sel = render_sidebar(semanas_opciones)

# Verificar disponibilidad del backend (usando el endpoint de maquinas que ya funciona)
maquinas = get_maquinas()
if maquinas is None:
    st.error("⚠ Backend no disponible. Verifique que FastAPI esté corriendo en localhost:8000")
    st.stop()

# Cargar KPIs (si el endpoint no existe o retorna 404/None, se usa una lista vacía)
if semana_sel:
    kpis_raw = get_kpi_semanal(semana_id=semana_sel)
    kpis = kpis_raw if kpis_raw is not None else []
else:
    kpis = []

# ── KPIs (fila superior) ──────────────────────────────────
if isinstance(semanas_opciones, list):
    st.info("""
    📅 No hay semanas de programación registradas aún.
    
    **Para comenzar:**
    1. Ve a **Órdenes de Fabricación** y registra los pedidos
    2. Ve a **Semanas de Programación** y crea una semana
    3. Agrega las órdenes a la semana
    4. Regresa aquí y ejecuta el **Optimizador**
    """)
elif not semana_sel:
    st.warning("Selecciona una semana en el menú de la izquierda")
else:
    semana_label = ""
    for label, id_ in semanas_opciones.items():
        if id_ == semana_sel:
            semana_label = label
            break
    st.subheader(f"Semana en curso: {semana_label}")

if get_rol() in ["PROGRAMADOR", "JEFE_PRODUCCION"]:
    st.info(
        "💡 Recuerda cambiar tu contraseña inicial en "
        "[Mi Perfil](/perfil)",
        icon="🔒"
    )

if "optimizer_success_msg" in st.session_state:
    st.success(st.session_state.pop("optimizer_success_msg"))
col1, col2, col3, col4 = st.columns(4)

total_ofs = sum(k.get("total_ordenes", 0) for k in kpis)
setup_horas = sum(k.get("setup_total_horas", 0.0) or 0.0 for k in kpis)
utilizacion = 0.0
if kpis:
    utilizacion = sum(k.get("utilizacion_pct", 0.0) or 0.0 for k in kpis) / len(kpis)

col1.metric("Total OFs programadas", total_ofs)
col2.metric("Setup total (h)", f"{setup_horas:.1f} h")
col3.metric("Utilización promedio", f"{utilizacion:.1f} %")
col4.metric("Máquinas activas", len([m for m in maquinas if m.get("activa")]))

st.divider()

# ── Cuerpo: Cola de máquinas | Matriz ICC ─────────────────
col_cola, col_icc = st.columns([3, 2])

with col_cola:
    st.subheader("Cola de producción")
    if not maquinas:
        st.info("No hay máquinas registradas.")
    else:
        maquinas_objetivo = ["M8", "M10", "M14"]
        tabs = st.tabs(maquinas_objetivo)
        for tab, maq_code in zip(tabs, maquinas_objetivo):
            with tab:
                maq = next((m for m in maquinas if m["codigo"] == maq_code), None)
                if not maq:
                    st.warning(f"Máquina {maq_code} no disponible.")
                    continue
                if semana_sel:
                    cola = get_cola_maquina(maq["id"], semana_id=semana_sel)
                else:
                    cola = []
                if not cola:
                    st.info("Sin órdenes programadas para esta semana.")
                    continue
                
                df = pd.DataFrame(cola)
                
                def badge(estado: str) -> str:
                    colores = {
                        "PENDIENTE": "🔘",
                        "EN_PROCESO": "🔵",
                        "COMPLETADA": "🟢",
                        "OMITIDA": "⚫",
                    }
                    return f"{colores.get(estado, '⚪')} {estado}"
                
                if "estado_secuencia" in df.columns:
                    df["estado"] = df["estado_secuencia"].apply(badge)
                else:
                    df["estado"] = "⚪ PENDIENTE"
                    
                st.dataframe(
                    df[["posicion", "codigo_of", "medida_texto", "material",
                        "colores_detalle", "costo_setup_min", "fecha_entrega", "estado"]],
                    column_config={
                        "posicion": st.column_config.NumberColumn("#", width="small"),
                        "codigo_of": st.column_config.TextColumn("OF"),
                        "medida_texto": st.column_config.TextColumn("Medida"),
                        "material": st.column_config.TextColumn("Material"),
                        "colores_detalle": st.column_config.TextColumn("Colores"),
                        "costo_setup_min": st.column_config.NumberColumn("Setup (min)", format="%.0f"),
                        "fecha_entrega": st.column_config.DateColumn("F. Entrega"),
                        "estado": st.column_config.TextColumn("Estado"),
                    },
                    hide_index=True,
                    width='stretch',
                )

with col_icc:
    st.subheader("Matriz de compatibilidad (ICC)")
    if semana_sel:
        render_matriz_icc(semana_id=semana_sel)
    
    st.divider()
    if can("optimizar"):
        if st.button("▶ Ejecutar Optimizador", type="primary", use_container_width=True):
            with st.spinner("Optimizando secuencias para la semana..."):
                try:
                    year, week_num = map(int, semana_sel.split("-W"))
                    fecha_inicio_str = str(datetime.date.fromisocalendar(year, week_num, 1))
                except ValueError:
                    st.error("Formato de semana inválido.")
                    st.stop()
                
                semanas_registradas = get_semanas() or []
                semanas_a_optimizar = [
                    s for s in semanas_registradas 
                    if s["fecha_inicio"] == fecha_inicio_str and s["maquina_codigo"] in ["M8", "M10", "M14"]
                ]
                
                if not semanas_a_optimizar:
                    st.warning("No se encontraron semanas programadas para M8, M10 o M14 en esta fecha. Regístrelas en la página de Semanas.")
                else:
                    total_evaluadas = 0
                    total_antes_h = 0.0
                    total_despues_h = 0.0
                    optimizados_con_exito = 0
                    
                    for sem in semanas_a_optimizar:
                        semanas = get_semanas() or []
                        semana_obj = next((s for s in semanas if s.get("id") == 1), None)
                        semana_id = semana_obj["id"] if semana_obj else 1
                        resultado = ejecutar_optimizador(semana_id=semana_id)
                        if resultado:
                            total_evaluadas += resultado.get("ordenes_evaluadas", 0)
                            total_antes_h += resultado.get("setup_antes_horas", 0.0)
                            total_despues_h += resultado.get("setup_despues_horas", 0.0)
                            optimizados_con_exito += 1
                            
                    if optimizados_con_exito > 0:
                        reduccion_pct = round(((total_antes_h - total_despues_h) / total_antes_h * 100.0), 1) if total_antes_h > 0 else 0.0
                        st.session_state["optimizer_success_msg"] = (
                            f"✓ {total_evaluadas} órdenes secuenciadas | "
                            f"Setup reducido de {total_antes_h:.1f}h a {total_despues_h:.1f}h "
                            f"({reduccion_pct}% mejora)"
                        )
                        st.rerun()
                    else:
                        st.error("Error al ejecutar el optimizador en las semanas correspondientes.")
    else:
        st.info("🔒 No tienes permisos para ejecutar el optimizador.")
