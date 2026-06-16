import streamlit as st
import requests
import os

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def _verificar_token(token: str) -> dict | None:
    try:
        r = requests.get(
            f"{BASE_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None

def restaurar_sesion() -> bool:
    if is_logged_in():
        return True
    token = st.query_params.get("_t", None)
    if token:
        usuario = _verificar_token(token)
        if usuario:
            st.session_state["token"]   = token
            st.session_state["usuario"] = usuario
            st.session_state["rol"]     = usuario.get("rol", "")
            st.session_state["nombre"]  = usuario.get("nombre_completo", "")
            return True
        else:
            try:
                st.query_params.clear()
            except Exception:
                pass
    return False

def login(username: str, password: str) -> bool:
    try:
        r = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            token = data["token"]
            usuario = data["usuario"]
            st.session_state["token"]   = token
            st.session_state["usuario"] = usuario
            st.session_state["rol"]     = data["rol"]
            st.session_state["nombre"]  = usuario["nombre_completo"]
            st.query_params["_t"] = token
            return True
        return False
    except Exception:
        return False

def logout():
    token = st.session_state.get("token")
    if token:
        try:
            requests.post(
                f"{BASE_URL}/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
        except Exception:
            pass
    for key in ["token", "usuario", "rol", "nombre"]:
        st.session_state.pop(key, None)
    try:
        st.query_params.clear()
    except Exception:
        pass

def is_logged_in() -> bool:
    return bool(st.session_state.get("token"))

def get_rol() -> str:
    return st.session_state.get("rol", "")

def require_login():
    restaurar_sesion()
    if not is_logged_in():
        st.switch_page("app.py")
        st.stop()

def can(accion: str) -> bool:
    rol = get_rol()
    permisos = {
        "PROGRAMADOR": [
            "crear_of", "editar_of", "optimizar",
            "ver_reportes", "gestionar_maestros",
            "registrar_parada", "ver_dashboard"
        ],
        "JEFE_PRODUCCION": [
            "optimizar", "ver_reportes",
            "registrar_parada", "ver_dashboard", "crear_of"
        ],
        "OPERADOR": [
            "registrar_parada", "ver_dashboard"
        ],
    }
    return accion in permisos.get(rol, [])

def render_sidebar():
    """Llama esto en app.py y en cada página para el sidebar."""
    from pathlib import Path
    logo = Path(__file__).parent / "static" / "logo_vygpack.png"
    if logo.exists():
        st.image(str(logo), width=150)
    st.markdown("### SIPP - VYGPACK")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**{st.session_state.get('nombre', 'Usuario')}**")
        st.caption(f"Rol: {get_rol()}")
    with col2:
        if st.button("⚙️", help="Mi perfil"):
            st.switch_page("pages/perfil.py")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        logout()
        st.rerun()
