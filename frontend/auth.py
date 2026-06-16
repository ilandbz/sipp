import streamlit as st
import requests
import os

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def login(username: str, password: str) -> bool:
    try:
        r = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            st.session_state["token"] = data["token"]
            st.session_state["usuario"] = data["usuario"]
            st.session_state["rol"] = data["rol"]
            st.session_state["nombre"] = data["usuario"]["nombre_completo"]
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

def is_logged_in() -> bool:
    return "token" in st.session_state and st.session_state["token"] is not None

def get_rol() -> str:
    return st.session_state.get("rol", "")

def require_login():
    """Llama esto al inicio de cada página."""
    if not is_logged_in():
        st.switch_page("app.py")
        st.stop()

def can(accion: str) -> bool:
    """
    Verifica si el rol actual puede hacer una acción.
    Acciones: 'crear_of', 'editar_of', 'optimizar', 
              'ver_reportes', 'gestionar_maestros',
              'registrar_parada', 'ver_dashboard'
    """
    rol = get_rol()
    permisos = {
        "PROGRAMADOR": [
            "crear_of", "editar_of", "optimizar",
            "ver_reportes", "gestionar_maestros",
            "registrar_parada", "ver_dashboard"
        ],
        "JEFE_PRODUCCION": [
            "optimizar", "ver_reportes",
            "registrar_parada", "ver_dashboard",
            "crear_of"
        ],
        "OPERADOR": [
            "registrar_parada", "ver_dashboard"
        ],
    }
    return accion in permisos.get(rol, [])

def render_sidebar(opciones_semanas=None):
    """
    Dibuja la barra lateral común con información del usuario, botón de logout y navegación.
    Si se pasa `opciones_semanas` (lista de strings), renderiza el selector de semanas y retorna la seleccionada.
    """
    import streamlit as st
    from pathlib import Path
    
    semana_sel = None
    
    with st.sidebar:
        # 1. Info del usuario y Perfil
        col_user, col_perfil = st.columns([2, 1])
        with col_user:
            st.markdown(f"👤 **{st.session_state.get('nombre', 'Usuario')}**")
            st.caption(f"Rol: {get_rol()}")
        with col_perfil:
            if st.button("⚙️", key="perfil_btn", help="Mi perfil y cambio de contraseña"):
                st.switch_page("pages/perfil.py")
        
        if st.button("🚪 Cerrar sesión", key="logout_btn", use_container_width=True):
            logout()
            st.switch_page("app.py")
            st.stop()
        st.divider()

        # 2. Logo y Título
        logo_path = Path("static/logo_vygpack.png")
        if not logo_path.exists():
            logo_path = Path("frontend/static/logo_vygpack.png")
            
        if logo_path.exists():
            st.image(str(logo_path.absolute()), width=150)
            st.title("SIPP - VYGPACK")
        else:
            st.title("🏭 SIPP - VYGPACK")
            
        # 3. Selector de semana opcional
        if opciones_semanas is not None:
            semana_sel = st.selectbox("Semana", opciones_semanas)
            st.divider()

        # 4. Navegación
        st.markdown("### 📌 Flujo de trabajo")
        st.page_link("pages/ordenes.py",  label="1️⃣ Órdenes de Fabricación")
        st.page_link("pages/semanas.py",  label="2️⃣ Semanas de Programación")
        st.page_link("app.py",            label="3️⃣ Dashboard / Optimizador")
        if can("ver_reportes"):
            st.page_link("pages/reportes.py", label="4️⃣ Reportes y Plan Semanal")
        
        if can("gestionar_maestros"):
            st.divider()
            st.markdown("### ⚙️ Configuración")
            st.page_link("pages/clientes.py",  label="👥 Clientes")
            st.page_link("pages/maestros.py",  label="🗂️ Maestros")
            
    return semana_sel
