import streamlit as st
import pandas as pd
from utils.api_client import (
    get_clientes,
    crear_cliente,
    actualizar_cliente,
    eliminar_cliente,
    get_franquicias,
    actualizar_franquicia
)
from auth import require_login, can, render_sidebar

require_login()

if not can("gestionar_maestros"):
    st.error("Acceso restringido — Solo Programador")
    st.stop()

st.set_page_config(page_title="Clientes | SIPP", page_icon="🏭", layout="wide")
render_sidebar()

st.title("👥 Gestión de Clientes")

if "cliente_editando" not in st.session_state:
    st.session_state.cliente_editando = None

tab_lista, tab_nuevo, tab_franq = st.tabs(["📋 Lista de Clientes", "➕ Nuevo Cliente", "🏆 Franquicias"])

with tab_lista:
    st.subheader("Clientes Registrados")
    buscar = st.text_input("🔍 Buscar cliente por Razón Social")
    
    clientes = get_clientes()
    if clientes:
        if buscar:
            clientes = [c for c in clientes if buscar.lower() in c["razon_social"].lower()]
            
        if not clientes:
            st.info("No se encontraron clientes con esa búsqueda.")
        else:
            # Encabezados
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 3, 2])
            c1.write("**Razón Social**")
            c2.write("**Marca**")
            c3.write("**Vendedor**")
            c4.write("**Franquicia**")
            c5.write("**Acciones**")
            st.divider()
            
            for cli in clientes:
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 3, 2])
                col1.write(cli["razon_social"])
                col2.write(cli.get("marca") or "-")
                col3.write(cli.get("vendedor") or "-")
                
                franq_nivel = cli.get('franquicia_nivel') or 4
                colores_franq = {
                    1: "🔴 Prioritario",
                    2: "🟠 Alto",
                    3: "🟡 Normal",
                    4: "⚪ Estándar"
                }
                col4.write(colores_franq.get(franq_nivel, "⚪ Estándar"))
                
                with col5:
                    btn1, btn2 = st.columns(2)
                    if btn1.button("✏️", key=f"edit_{cli['id']}", help="Editar cliente"):
                        st.session_state.cliente_editando = cli
                        st.rerun()
                    if btn2.button("🗑️", key=f"del_{cli['id']}", help="Eliminar cliente"):
                        res_del = eliminar_cliente(cli["id"])
                        if isinstance(res_del, dict) and res_del.get("ok"):
                            st.success("Cliente eliminado exitosamente.")
                            st.cache_data.clear()
                            st.rerun()
                        elif isinstance(res_del, bool) and res_del:
                            st.success("Cliente eliminado exitosamente.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Error al eliminar: {res_del.get('error') if isinstance(res_del, dict) else 'Desconocido'}")
    else:
        st.info("No hay clientes registrados en el sistema.")

with tab_nuevo:
    es_edicion = st.session_state.cliente_editando is not None
    if es_edicion:
        st.info("✏️ Modo Edición")
        if st.button("❌ Cancelar edición"):
            st.session_state.cliente_editando = None
            st.rerun()
            
    cli_data = st.session_state.cliente_editando or {}
    
    with st.form("form_cliente"):
        st.subheader("Datos del Cliente")
        col1, col2 = st.columns(2)
        razon_social = col1.text_input("Razón Social *", value=cli_data.get("razon_social", ""))
        marca = col2.text_input("Marca", value=cli_data.get("marca", "") or "")
        
        col3, col4 = st.columns(2)
        vendedor = col3.text_input("Vendedor", value=cli_data.get("vendedor", "") or "")
        
        # Franquicias
        franqs = get_franquicias() or []
        franq_options = {f"{f['nivel']} - {f['nombre']}": f["id"] for f in franqs}
        idx_franq = 3 # Nivel 4 default
        if es_edicion and cli_data.get("franquicia_id"):
            for i, fid in enumerate(franq_options.values()):
                if fid == cli_data["franquicia_id"]:
                    idx_franq = i
                    break
        franquicia_sel = col4.selectbox("Franquicia", list(franq_options.keys()), index=idx_franq)
        
        col5, col6 = st.columns(2)
        ruc = col5.text_input("RUC", value=cli_data.get("ruc", "") or "")
        
        col7, col8 = st.columns(2)
        telefono = col7.text_input("Teléfono", value=cli_data.get("telefono", "") or "")
        direccion = col8.text_area("Dirección", value=cli_data.get("direccion", "") or "")
        
        label_btn = "💾 Guardar Cambios" if es_edicion else "➕ Crear Cliente"
        submitted = st.form_submit_button(label_btn, type="primary")
        
        if submitted:
            if not razon_social.strip():
                st.error("La Razón Social es obligatoria.")
            else:
                payload = {
                    "razon_social": razon_social.strip(),
                    "marca": marca.strip() or None,
                    "vendedor": vendedor.strip() or None,
                    "franquicia_id": franq_options.get(franquicia_sel),
                    "ruc": ruc.strip() or None,
                    "telefono": telefono.strip() or None,
                    "direccion": direccion.strip() or None
                }
                
                if es_edicion:
                    if actualizar_cliente(cli_data["id"], payload):
                        st.success("Cliente actualizado exitosamente.")
                        st.session_state.cliente_editando = None
                        st.cache_data.clear()
                        st.rerun()
                else:
                    if crear_cliente(payload):
                        st.success(f"Cliente '{razon_social}' creado exitosamente.")
                        st.session_state.cliente_editando = None
                        st.cache_data.clear()
                        st.rerun()

with tab_franq:
    st.subheader("Niveles de Franquicia")
    st.info("Las franquicias determinan la prioridad de los clientes en el Optimizador del sistema.")
    
    franqs = get_franquicias()
    if franqs:
        for f in franqs:
            with st.expander(f"Nivel {f['nivel']} - {f['nombre']}", expanded=True):
                col1, col2 = st.columns([4, 1])
                desc = col1.text_area("Descripción", value=f.get("descripcion", "") or "", key=f"desc_{f['id']}")
                if col2.button("💾 Guardar", key=f"btn_f_{f['id']}", use_container_width=True):
                    if actualizar_franquicia(f["id"], {"descripcion": desc}):
                        st.success("Guardado ✓")
                        st.rerun()
    else:
        st.warning("No hay franquicias registradas en el sistema.")
