import streamlit as st
import pandas as pd
import datetime
from utils.api_client import (
    get_kpi_por_semana_id, get_cola_maquina, get_maquinas,
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
    st.markdown("""
    <style>
    [data-testid="stApp"] {
        background: linear-gradient(135deg, #0f1923 0%, #1a2e1a 100%);
    }
    </style>
    """, unsafe_allow_html=True)
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
        es_global = s.get("es_global", False)
        maquina = "🌐 Global" if es_global else s.get("maquina_codigo", s.get("maquina", ""))
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

def _render_tabla_cola(cola):
    df = pd.DataFrame(cola)
    
    def badge_estado(estado: str) -> str:
        estilos = {
            "PENDIENTE":  ("⚪", "#607D8B", "#E0F2F1"),
            "EN_PROCESO": ("🔵", "#1565C0", "#E3F2FD"),
            "COMPLETADA": ("✅", "#2E7D32", "#E8F5E9"),
            "OMITIDA":    ("⚫", "#424242", "#F5F5F5"),
        }
        icono, color_txt, color_bg = estilos.get(estado, ("⚪", "#607D8B", "#E0F2F1"))
        return f'<span style="background:{color_bg}20; color:{color_txt}; padding:2px 8px; border-radius:12px; font-size:11px; border:1px solid {color_txt}40;">{icono} {estado}</span>'
    
    if "estado_secuencia" in df.columns:
        df["estado"] = df["estado_secuencia"].apply(badge_estado)
    else:
        df["estado"] = badge_estado("PENDIENTE")
        
    def color_setup_fila(setup_min: float) -> str:
        if setup_min == 0:
            return ""  # sin color
        elif setup_min >= 480:
            return "background-color: rgba(239,83,80,0.15);"   # rojo suave
        elif setup_min >= 105:
            return "background-color: rgba(255,167,38,0.15);"  # naranja suave
        elif setup_min >= 45:
            return "background-color: rgba(255,238,88,0.10);"  # amarillo suave
        else:
            return "background-color: rgba(76,175,80,0.10);"   # verde suave

    def row_style(row):
        color = color_setup_fila(float(row.get("costo_setup_min", 0)))
        return [color] * len(row)

    if "posicion" in df.columns:
        df = df.sort_values("posicion")

    df_show = df[["posicion", "codigo_of", "medida_texto", "material",
                  "colores_detalle", "costo_setup_min", "fecha_entrega", "estado"]]
    
    styled_df = df_show.style.apply(row_style, axis=1)
    
    st.write(styled_df.hide(axis="index").to_html(escape=False), unsafe_allow_html=True)
    
    st.caption("""
        🟢 Verde: setup ≤ 44 min (cambio menor) |
        🟡 Amarillo: 45-104 min (cambio de color/material) |
        🟠 Naranja: 105-479 min (jugada corta) |
        🔴 Rojo: ≥ 480 min (cambio de formato completo)
    """)

# ── Sidebar ──────────────────────────────────────────────
semanas_opciones = opciones_semanas()

if "semana_defecto_seteada" not in st.session_state:
    from utils.api_client import get_semana_activa
    semana_activa = get_semana_activa()
    if semana_activa:
        st.session_state["semana_defecto"] = semana_activa["id"]
    st.session_state["semana_defecto_seteada"] = True

semana_sel = render_sidebar(semanas_opciones)

# Verificar disponibilidad del backend (usando el endpoint de maquinas que ya funciona)
maquinas = get_maquinas()
if maquinas is None:
    st.error("⚠ Backend no disponible. Verifique que FastAPI esté corriendo en localhost:8000")
    st.stop()

# Cargar KPIs
if semana_sel:
    kpi_data = get_kpi_por_semana_id(semana_sel)
    if kpi_data:
        total_ofs    = kpi_data.get("total_ofs", 0)
        setup_horas  = kpi_data.get("setup_total_horas", 0.0)
        utilizacion  = kpi_data.get("utilizacion_pct", 0.0)
    else:
        total_ofs, setup_horas, utilizacion = 0, 0.0, 0.0
else:
    total_ofs, setup_horas, utilizacion = 0, 0.0, 0.0

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
    semana_info = st.session_state.get("semana_info", {})
    fecha_i = semana_info.get("fecha_inicio", "")
    fecha_f = semana_info.get("fecha_fin", "")

    if fecha_i and fecha_f:
        try:
            from datetime import datetime
            fi = datetime.strptime(str(fecha_i)[:10], "%Y-%m-%d").strftime("%d/%m")
            ff = datetime.strptime(str(fecha_f)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
            titulo_semana = f"Semana {fi} — {ff}"
        except:
            titulo_semana = "Semana en curso"
    else:
        titulo_semana = semana_label

    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
        <span style="font-size:2rem;">🏭</span>
        <div>
            <div style="font-size:1.4rem; font-weight:600; color:#F0F4F0;">
                {titulo_semana}
            </div>
            <div style="font-size:0.8rem; color:#4CAF50;">
                VYGPACK — Sistema Inteligente de Programación de Producción
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

if get_rol() in ["PROGRAMADOR", "JEFE_PRODUCCION"]:
    st.info(
        "💡 Recuerda cambiar tu contraseña inicial en "
        "[Mi Perfil](/perfil)",
        icon="🔒"
    )

if "optimizer_success_msg" in st.session_state:
    st.success(st.session_state.pop("optimizer_success_msg"))
# Fila de KPIs con estilo mejorado
st.markdown("""
<style>
.kpi-card {
    background: linear-gradient(135deg, #1a2632 0%, #243447 100%);
    border: 1px solid #2d4a3e;
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
}
.kpi-valor { font-size: 2rem; font-weight: 700; color: #4CAF50; }
.kpi-label { font-size: 0.75rem; color: #8a9ba8; text-transform: uppercase; 
             letter-spacing: 0.05em; margin-top: 4px; }
.kpi-delta { font-size: 0.8rem; color: #81C784; }
</style>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-valor">{total_ofs}</div>
        <div class="kpi-label">📦 OFs Programadas</div>
    </div>""", unsafe_allow_html=True)
with col2:
    color_setup = "#ef5350" if setup_horas > 20 else "#FFA726" if setup_horas > 10 else "#4CAF50"
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-valor" style="color:{color_setup}">{setup_horas:.1f}h</div>
        <div class="kpi-label">⏱ Setup Total</div>
    </div>""", unsafe_allow_html=True)
with col3:
    color_util = "#ef5350" if utilizacion > 100 else "#FFA726" if utilizacion > 85 else "#4CAF50"
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-valor" style="color:{color_util}">{utilizacion:.1f}%</div>
        <div class="kpi-label">📊 Utilización</div>
    </div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-valor">3</div>
        <div class="kpi-label">🏭 Máquinas M8·M10·M14</div>
    </div>""", unsafe_allow_html=True)

st.divider()

# ── Cuerpo: Cola de máquinas | Matriz ICC ─────────────────
col_cola, col_icc = st.columns([3, 2])

with col_cola:
    st.subheader("Cola de producción")
    if not maquinas:
        st.info("No hay máquinas registradas.")
    else:
        from utils.api_client import get_semana_detalle
        semana_data = get_semana_detalle(semana_sel) if semana_sel else None
        
        if not semana_data:
            st.info("Sin órdenes programadas para esta semana.")
        else:
            semana = semana_data.get("semana", {})
            es_global = semana.get("es_global", False)
            
            if es_global:
                st.markdown(f"#### Semana global — {semana.get('fecha_inicio', '')} al {semana.get('fecha_fin', '')}")
                maquinas_tabs = [m for m in maquinas if m["codigo"] in ["M8", "M10", "M14"]]
            else:
                maquina_codigo = semana.get("maquina_codigo")
                if not maquina_codigo or maquina_codigo == "Todas las máquinas" or maquina_codigo == "GLOBAL":
                    maquina_codigo = "M8"
                st.markdown(f"#### Máquina: {maquina_codigo}")
                maquinas_tabs = [m for m in maquinas if m["id"] == semana.get("maquina_id")]
            
            if not maquinas_tabs:
                st.warning("Máquina no encontrada.")
            else:
                from utils.api_client import get_cola_semana
                cola_semana = get_cola_semana(semana_sel) or []
                
                maquinas_con_ofs = []
                todas_las_colas = {}
                for maq in maquinas_tabs:
                    cola_maq = [
                        item for item in cola_semana
                        if item.get("maquina") == maq["codigo"]
                        or item.get("maquina_codigo") == maq["codigo"]
                    ]
                    todas_las_colas[maq["codigo"]] = cola_maq
                    if cola_maq:
                        maquinas_con_ofs.append(maq["codigo"])

                # Labels con indicador de cuántas OFs tiene cada máquina
                tab_labels = []
                for maq in maquinas_tabs:
                    cola = todas_las_colas.get(maq["codigo"], [])
                    n = len(cola)
                    if n > 0:
                        tab_labels.append(f"{maq['codigo']} ({n} OFs)")
                    else:
                        tab_labels.append(maq["codigo"])

                tabs = st.tabs(tab_labels)

                for tab, maq in zip(tabs, maquinas_tabs):
                    with tab:
                        cola = todas_las_colas.get(maq["codigo"], [])
                        if not cola:
                            if maq["codigo"] in maquinas_con_ofs:
                                st.info(f"Sin órdenes en {maq['codigo']} esta semana")
                            else:
                                st.caption(f"🔘 {maq['codigo']} sin órdenes esta semana")
                        else:
                            _render_tabla_cola(cola)

with col_icc:
    st.subheader("Matriz de compatibilidad (ICC)")
    
    st.caption("""
        **Matriz de Compatibilidad (ICC):** Muestra qué tan eficiente 
        es producir una OF seguida de otra.
        🟢 Verde = compatible (poco setup) | 🔴 Rojo = incompatible (mucho setup)
        La diagonal siempre es 100 (misma OF). 
        El optimizador agrupa las OFs más compatibles juntas.
    """)
    
    if semana_sel:
        render_matriz_icc(semana_id=semana_sel)
    
    st.divider()
    if can("optimizar"):
        if st.button("▶ Ejecutar Optimizador", type="primary", use_container_width=True):
            semana_id = st.session_state.get("semana_id_activa", semana_sel)
            if not semana_id:
                st.error("Selecciona una semana primero")
            else:
                with st.spinner("Optimizando secuencias..."):
                    resultado = ejecutar_optimizador(semana_id=semana_id)
                if resultado is None:
                    st.error("❌ Sin respuesta del backend")
                elif resultado.get("error"):
                    st.error(f"❌ {resultado['error']}")
                elif resultado.get("ordenes_evaluadas", 0) == 0:
                    st.warning("⚠ No hay OFs pendientes para optimizar")
                else:
                    if resultado and resultado.get("ordenes_evaluadas", 0) > 0:
                        reduccion = resultado.get("reduccion_pct", 0)
                        dist = resultado.get("distribucion", {})
                        
                        # Mostrar distribución por máquina
                        dist_texto = " | ".join([
                            f"{maq}: {n} OFs" 
                            for maq, n in dist.items() if n > 0
                        ])
                        
                        st.session_state["optimizer_success_msg"] = (
                            f"✓ {resultado['ordenes_evaluadas']} órdenes distribuidas y secuenciadas\n\n"
                            f"📊 {dist_texto}\n\n"
                            f"⏱ Setup: {resultado.get('setup_antes_horas',0):.1f}h → "
                            f"{resultado.get('setup_despues_horas',0):.1f}h "
                            f"({'↓ ' + str(reduccion) + '% reducción' if reduccion > 0 else 'orden óptimo'})"
                        )
                    st.cache_data.clear()
                    st.rerun()
    else:
        st.info("🔒 No tienes permisos para ejecutar el optimizador.")
