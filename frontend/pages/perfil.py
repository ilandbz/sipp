import streamlit as st
from auth import require_login, get_rol, render_sidebar
from utils.api_client import cambiar_password, actualizar_perfil

require_login()

st.set_page_config(page_title="Mi Perfil | SIPP", layout="wide")
render_sidebar()

st.title("👤 Mi Perfil")

usuario = st.session_state.get("usuario", {})

col1, col2 = st.columns(2)

with col1:
    st.subheader("Información de cuenta")
    st.info(f"""
    **Usuario:** {usuario.get('username', '')}
    **Nombre:** {usuario.get('nombre_completo', '')}
    **Rol:** {get_rol()}
    """)
    
    st.subheader("✏️ Actualizar nombre")
    with st.form("form_nombre"):
        nuevo_nombre = st.text_input(
            "Nombre completo", 
            value=usuario.get('nombre_completo', '')
        )
        if st.form_submit_button("Guardar nombre", type="primary"):
            resultado = actualizar_perfil({"nombre_completo": nuevo_nombre})
            if resultado:
                st.session_state["usuario"]["nombre_completo"] = nuevo_nombre
                st.session_state["nombre"] = nuevo_nombre
                st.success("✓ Nombre actualizado")
                st.rerun()
            else:
                st.error("Error al actualizar")

with col2:
    st.subheader("🔒 Cambiar contraseña")
    st.warning("⚠ Cambia tu contraseña inicial antes de usar el sistema.")
    
    with st.form("form_password"):
        pwd_actual  = st.text_input("Contraseña actual",  type="password")
        pwd_nuevo   = st.text_input("Nueva contraseña",   type="password",
                                    help="Mínimo 6 caracteres")
        pwd_confirm = st.text_input("Confirmar contraseña", type="password")
        
        if st.form_submit_button("🔒 Cambiar contraseña", type="primary",
                                  use_container_width=True):
            if not pwd_actual or not pwd_nuevo or not pwd_confirm:
                st.error("Completa todos los campos")
            elif pwd_nuevo != pwd_confirm:
                st.error("Las contraseñas nuevas no coinciden")
            elif len(pwd_nuevo) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres")
            else:
                resultado = cambiar_password({
                    "password_actual": pwd_actual,
                    "password_nuevo":  pwd_nuevo,
                    "confirmar":       pwd_confirm,
                })
                if resultado:
                    st.success("✓ Contraseña actualizada correctamente")
                else:
                    st.error("Contraseña actual incorrecta o error del servidor")
