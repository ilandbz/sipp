import streamlit as st
import pandas as pd
from utils.api_client import (
    get_maquinas, actualizar_maquina,
    get_materiales, crear_material, actualizar_material, eliminar_material,
    get_cilindros, crear_cilindro, actualizar_cilindro,
    get_tipos_bolsa, actualizar_tipo_bolsa
)
from auth import require_login, can, render_sidebar

require_login()

if not can("gestionar_maestros"):
    st.error("Acceso restringido — Solo Programador")
    st.stop()

st.set_page_config(page_title="Maestros | SIPP", page_icon="🏭", layout="wide")
render_sidebar()

st.title("🗂️ Mantenimiento de Maestros")

tab_maq, tab_mat, tab_cil, tab_bolsa = st.tabs([
    "⚙️ Máquinas", "📦 Materiales", "🛢️ Cilindros", "🛍️ N° de Bolsa"
])

# --- MÁQUINAS ---
with tab_maq:
    st.subheader("Configuración de Máquinas")
    st.info("Nota: Al cambiar la Velocidad BPM Max, se recalcularán las horas de producción de todas las órdenes PENDIENTES asignadas a esa máquina.")
    
    maquinas = get_maquinas()
    if maquinas:
        for m in maquinas:
            with st.expander(f"Máquina: {m['codigo']} - {m['nombre']}", expanded=True):
                c1, c2, c3 = st.columns(3)
                nuevo_bpm = c1.number_input("Velocidad BPM Max", value=float(m.get("velocidad_bpm_max") or 0.0), key=f"bpm_{m['id']}")
                nuevo_turno = c2.number_input("Turno (Horas)", value=float(m.get("turno_horas") or 8.0), key=f"turno_{m['id']}")
                activa = c3.checkbox("Activa", value=m.get("activa", True), key=f"activa_{m['id']}")
                
                if st.button("💾 Actualizar Máquina", key=f"btn_maq_{m['id']}"):
                    payload = {
                        "velocidad_bpm_max": nuevo_bpm,
                        "turno_horas": nuevo_turno,
                        "activa": activa
                    }
                    if actualizar_maquina(m["id"], payload):
                        st.success("Máquina actualizada ✓")
                        st.rerun()
    else:
        st.warning("No hay máquinas registradas.")

# --- MATERIALES ---
with tab_mat:
    st.subheader("Materiales")
    
    if "mat_editando" not in st.session_state:
        st.session_state.mat_editando = None
        
    materiales = get_materiales()
    if materiales:
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
        c1.write("**Tipo**")
        c2.write("**Factor Velocidad**")
        c3.write("**Gramaje Min**")
        c4.write("**Gramaje Max**")
        c5.write("**Acciones**")
        st.divider()
        
        for mat in materiales:
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
            col1.write(mat["tipo"])
            col2.write(str(mat.get("factor_velocidad", 1.0)))
            col3.write(str(mat.get("gramaje_min") or "-"))
            col4.write(str(mat.get("gramaje_max") or "-"))
            
            with col5:
                b1, b2 = st.columns(2)
                if b1.button("✏️", key=f"edit_mat_{mat['id']}"):
                    st.session_state.mat_editando = mat
                    st.rerun()
                if b2.button("🗑️", key=f"del_mat_{mat['id']}"):
                    if eliminar_material(mat["id"]):
                        st.success("Material eliminado ✓")
                        st.rerun()
    else:
        st.info("No hay materiales registrados.")
        
    st.write("---")
    es_ed_mat = st.session_state.mat_editando is not None
    if es_ed_mat:
        st.info("Modo Edición")
        if st.button("❌ Cancelar edición Material"):
            st.session_state.mat_editando = None
            st.rerun()
            
    mat_data = st.session_state.mat_editando or {}
    with st.form("form_mat"):
        st.write("### " + ("Editar Material" if es_ed_mat else "Nuevo Material"))
        cm1, cm2 = st.columns(2)
        tipo_mat = cm1.text_input("Tipo de Material *", value=mat_data.get("tipo", ""))
        factor_v = cm2.number_input("Factor Velocidad", value=float(mat_data.get("factor_velocidad", 1.0)), step=0.1)
        
        cm3, cm4 = st.columns(2)
        g_min = cm3.number_input("Gramaje Mínimo", value=float(mat_data.get("gramaje_min") or 0.0))
        g_max = cm4.number_input("Gramaje Máximo", value=float(mat_data.get("gramaje_max") or 0.0))
        
        desc_mat = st.text_area("Descripción", value=mat_data.get("descripcion", "") or "")
        
        if st.form_submit_button("💾 Guardar Material", type="primary"):
            if not tipo_mat.strip():
                st.error("El tipo de material es obligatorio.")
            else:
                payload = {
                    "tipo": tipo_mat.strip(),
                    "factor_velocidad": factor_v,
                    "gramaje_min": g_min or None,
                    "gramaje_max": g_max or None,
                    "descripcion": desc_mat.strip() or None
                }
                if es_ed_mat:
                    if actualizar_material(mat_data["id"], payload):
                        st.success("Actualizado ✓")
                        st.session_state.mat_editando = None
                        st.rerun()
                else:
                    if crear_material(payload):
                        st.success("Creado ✓")
                        st.rerun()

# --- CILINDROS ---
with tab_cil:
    st.subheader("Cilindros")
    
    if "cil_editando" not in st.session_state:
        st.session_state.cil_editando = None
        
    cilindros = get_cilindros()
    if cilindros:
        c1, c2, c3, c4 = st.columns([2, 4, 2, 2])
        c1.write("**Código**")
        c2.write("**Descripción**")
        c3.write("**Estado**")
        c4.write("**Acciones**")
        st.divider()
        
        for cil in cilindros:
            col1, col2, col3, col4 = st.columns([2, 4, 2, 2])
            col1.write(cil["codigo"])
            col2.write(cil.get("descripcion") or "-")
            col3.write("✅ Activo" if cil.get("activo") else "❌ Inactivo")
            
            with col4:
                if st.button("✏️ Editar", key=f"edit_cil_{cil['id']}"):
                    st.session_state.cil_editando = cil
                    st.rerun()
    else:
        st.info("No hay cilindros registrados.")
        
    st.write("---")
    es_ed_cil = st.session_state.cil_editando is not None
    if es_ed_cil:
        st.info("Modo Edición")
        if st.button("❌ Cancelar edición Cilindro"):
            st.session_state.cil_editando = None
            st.rerun()
            
    cil_data = st.session_state.cil_editando or {}
    with st.form("form_cil"):
        st.write("### " + ("Editar Cilindro" if es_ed_cil else "Nuevo Cilindro"))
        cc1, cc2 = st.columns(2)
        codigo_cil = cc1.text_input("Código *", value=cil_data.get("codigo", ""))
        activo_cil = cc2.checkbox("Activo", value=cil_data.get("activo", True))
        desc_cil = st.text_area("Descripción", value=cil_data.get("descripcion", "") or "")
        
        if st.form_submit_button("💾 Guardar Cilindro", type="primary"):
            if not codigo_cil.strip():
                st.error("El código es obligatorio.")
            else:
                payload = {
                    "codigo": codigo_cil.strip(),
                    "activo": activo_cil,
                    "descripcion": desc_cil.strip() or None
                }
                if es_ed_cil:
                    if actualizar_cilindro(cil_data["id"], payload):
                        st.success("Actualizado ✓")
                        st.session_state.cil_editando = None
                        st.rerun()
                else:
                    if crear_cilindro(payload):
                        st.success("Creado ✓")
                        st.rerun()

# --- TIPOS DE BOLSA ---
with tab_bolsa:
    st.subheader("Configuración Estándar por N° de Bolsa")
    
    bolsas = get_tipos_bolsa()
    if bolsas:
        for b in bolsas:
            with st.expander(f"Bolsa N° {b['numero']}", expanded=False):
                st.write(b.get("descripcion") or f"Configuración para bolsa {b['numero']}")
                cb1, cb2, cb3 = st.columns(3)
                ancho_std = cb1.number_input("Ancho Std (mm)", value=float(b.get("ancho_std_mm") or 0.0), key=f"bancho_{b['id']}")
                alto_std = cb2.number_input("Alto Std (mm)", value=float(b.get("alto_std_mm") or 0.0), key=f"balto_{b['id']}")
                fuelle_std = cb3.number_input("Fuelle Std (mm)", value=float(b.get("fuelle_std_mm") or 0.0), key=f"bfuelle_{b['id']}")
                
                if st.button("💾 Actualizar Dimensiones", key=f"btn_bolsa_{b['id']}"):
                    payload = {
                        "ancho_std_mm": ancho_std or None,
                        "alto_std_mm": alto_std or None,
                        "fuelle_std_mm": fuelle_std or None
                    }
                    if actualizar_tipo_bolsa(b["id"], payload):
                        st.success("Actualizado ✓")
                        st.rerun()
    else:
        st.warning("No hay Tipos de Bolsa registrados.")
