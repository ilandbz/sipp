import os
import requests
from dotenv import load_dotenv
import streamlit as st

load_dotenv()
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def _get_headers():
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}

def _get(ruta: str, params: dict = None):
    try:
        r = requests.get(f"{BASE_URL}{ruta}", params=params, headers=_get_headers(), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def _post(ruta: str, payload: dict = None, files=None, timeout=15):
    try:
        headers = _get_headers()
        if files:
            r = requests.post(f"{BASE_URL}{ruta}", files=files, headers=headers, timeout=timeout)
        else:
            r = requests.post(f"{BASE_URL}{ruta}", json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
        # Limpiar caché si la petición modifica datos
        st.cache_data.clear()
        return r.json()
    except Exception:
        return None

def _patch(ruta: str, payload: dict):
    try:
        r = requests.patch(f"{BASE_URL}{ruta}", json=payload, headers=_get_headers(), timeout=15)
        r.raise_for_status()
        st.cache_data.clear()
        return r.json()
    except Exception:
        return None

def _delete(ruta: str):
    try:
        r = requests.delete(
            f"{BASE_URL}{ruta}",
            headers=_get_headers(),
            timeout=15
        )
        if r.status_code in [200, 204]:
            st.cache_data.clear()
            return True
        return False
    except Exception:
        return False

def _put(ruta: str, payload: dict):
    try:
        r = requests.put(f"{BASE_URL}{ruta}", json=payload, headers=_get_headers(), timeout=15)
        r.raise_for_status()
        st.cache_data.clear()
        return r.json()
    except Exception:
        return None

# ── Máquinas ──────────────────────────────────────────
@st.cache_data(ttl=300)
def get_maquinas():
    return _get("/api/v1/maquinas/")

def actualizar_maquina(id: int, payload: dict):
    return _patch(f"/api/v1/maquinas/{id}", payload)

def get_capacidad_maquina(id: int):
    return _get(f"/api/v1/maquinas/{id}/capacidad")

def actualizar_capacidad_maquina(id: int, payload: dict):
    return _patch(f"/api/v1/maquinas/{id}/capacidad", payload)

# ── Materiales ────────────────────────────────────────
@st.cache_data(ttl=300)
def get_materiales():
    return _get("/api/v1/materiales/")

def crear_material(payload: dict):
    return _post("/api/v1/materiales/", payload)

def actualizar_material(id: int, payload: dict):
    return _patch(f"/api/v1/materiales/{id}", payload)

def eliminar_material(id: int):
    return _delete(f"/api/v1/materiales/{id}")

# ── Cilindros ─────────────────────────────────────────
@st.cache_data(ttl=30)
def get_cilindros():
    return _get("/api/v1/cilindros/")

def crear_cilindro(payload: dict):
    return _post("/api/v1/cilindros/", payload)

def actualizar_cilindro(id: int, payload: dict):
    return _patch(f"/api/v1/cilindros/{id}", payload)

def eliminar_cilindro(id: int):
    return _delete(f"/api/v1/cilindros/{id}")

# ── Tipos de Bolsa ────────────────────────────────────
@st.cache_data(ttl=300)
def get_tipos_bolsa():
    return _get("/api/v1/tipos-bolsa/")

def actualizar_tipo_bolsa(id: int, payload: dict):
    return _patch(f"/api/v1/tipos-bolsa/{id}", payload)

# ── Franquicias ───────────────────────────────────────
@st.cache_data(ttl=300)
def get_franquicias():
    return _get("/api/v1/franquicias/")

def actualizar_franquicia(id: int, payload: dict):
    return _patch(f"/api/v1/franquicias/{id}", payload)

# ── Clientes ──────────────────────────────────────────
@st.cache_data(ttl=30)
def get_clientes(buscar: str = None):
    params = {"buscar": buscar} if buscar else None
    return _get("/api/v1/clientes/", params)

def get_cliente(id: int):
    return _get(f"/api/v1/clientes/{id}")

def get_cliente_detalle(id: int):
    return _get(f"/api/v1/clientes/{id}")

def crear_cliente(payload: dict):
    return _post("/api/v1/clientes/", payload)

def actualizar_cliente(id: int, payload: dict):
    return _patch(f"/api/v1/clientes/{id}", payload)

def eliminar_cliente(id: int):
    try:
        r = requests.delete(
            f"{BASE_URL}/api/v1/clientes/{id}",
            headers=_get_headers(),
            timeout=15
        )
        if r.status_code in [200, 204]:
            st.cache_data.clear()
            return {"ok": True}
        else:
            try:
                detalle = r.json().get("detail", f"Error {r.status_code}")
            except Exception:
                detalle = f"Error HTTP {r.status_code}"
            return {"ok": False, "error": detalle}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ── Órdenes de Fabricación ────────────────────────────
def get_ordenes(maquina=None, estado=None, buscar=None):
    params = {}
    if maquina and maquina != "Todas": params["maquina"] = maquina
    if estado  and estado  != "Todos": params["estado"]  = estado
    if buscar:                          params["buscar"]  = buscar
    return _get("/api/v1/ordenes/", params)

def get_orden(id: int):
    return _get(f"/api/v1/ordenes/{id}")

def crear_orden(payload: dict):
    try:
        r = requests.post(
            f"{BASE_URL}/api/v1/ordenes/",
            json=payload,
            headers=_get_headers(),
            timeout=15
        )
        if r.status_code in [200, 201]:
            st.cache_data.clear()
            return {"ok": True, "data": r.json()}
        else:
            # Capturar el mensaje de error del backend
            try:
                detalle = r.json().get("detail", f"Error {r.status_code}")
            except Exception:
                detalle = f"Error HTTP {r.status_code}"
            return {"ok": False, "error": detalle}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def actualizar_orden(id: int, payload: dict):
    try:
        r = requests.patch(
            f"{BASE_URL}/api/v1/ordenes/{id}",
            json=payload,
            headers=_get_headers(),
            timeout=15
        )
        if r.status_code in [200, 201]:
            return {"ok": True, "data": r.json()}
        else:
            try:
                detalle = r.json().get("detail", f"Error {r.status_code}")
            except Exception:
                detalle = f"Error HTTP {r.status_code}"
            return {"ok": False, "error": detalle}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def eliminar_orden(id: int):
    try:
        r = requests.delete(
            f"{BASE_URL}/api/v1/ordenes/{id}",
            headers=_get_headers(),
            timeout=15
        )
        if r.status_code in [200, 204]:
            st.cache_data.clear()
            return {"ok": True}
        else:
            try:
                detalle = r.json().get("detail", f"Error {r.status_code}")
            except Exception:
                detalle = f"Error HTTP {r.status_code}"
            return {"ok": False, "error": detalle}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def importar_csv(file):
    files = {"file": file}
    return _post("/api/v1/ordenes/importar", files=files, timeout=60)

def get_sugerencia_maquina(of_id: int):
    return _get(f"/api/v1/ordenes/{of_id}/sugerir-maquina")

# ── Semanas ───────────────────────────────────────────
def get_semanas():
    return _get("/api/v1/semanas/")

def get_semana_activa():
    return _get("/api/v1/semanas/activa")

def crear_semana(payload: dict):
    try:
        r = requests.post(
            f"{BASE_URL}/api/v1/semanas/",
            json=payload,
            headers=_get_headers(),
            timeout=15
        )
        if r.status_code in [200, 201]:
            st.cache_data.clear()
            return r.json()
        else:
            try:
                print(f"Error crear semana: {r.status_code} - {r.text}")
            except:
                pass
            return None
    except Exception as e:
        print(f"Exception crear semana: {e}")
        return None

def actualizar_estado_semana(id: int, estado: str):
    return _patch(f"/api/v1/semanas/{id}/estado", {"estado": estado})

def agregar_of_a_semana(semana_id: int, of_id: int):
    return _post(f"/api/v1/semanas/{semana_id}/agregar-of", {"of_id": of_id})

def reordenar_semana(semana_id: int, orden: list[int]):
    return _put(f"/api/v1/semanas/{semana_id}/reordenar", {"orden": orden})

def get_ofs_disponibles(semana_id: int):
    return _get(f"/api/v1/semanas/{semana_id}/ofs-disponibles")

def get_semana_detalle(semana_id: int):
    return _get(f"/api/v1/semanas/{semana_id}")

def get_cola_semana(semana_id: int):
    return _get(f"/api/v1/semanas/{semana_id}/cola-completa")

def actualizar_estado_secuencia(secuencia_id: int, estado: str, fin_real: str = None):
    body = {"estado": estado}
    if fin_real:
        body["fin_real"] = fin_real
    return _patch(f"/api/v1/semanas/secuencias/{secuencia_id}/estado", body)

def eliminar_of_semana(semana_id: int, secuencia_id: int):
    return _delete(f"/api/v1/semanas/{semana_id}/secuencias/{secuencia_id}")

def eliminar_semana(id: int):
    try:
        r = requests.delete(
            f"{BASE_URL}/api/v1/semanas/{id}",
            headers=_get_headers(),
            timeout=15
        )
        if r.status_code in [200, 204]:
            st.cache_data.clear()
            return {"ok": True}
        else:
            try:
                detalle = r.json().get("detail", f"Error {r.status_code}")
            except Exception:
                detalle = f"Error HTTP {r.status_code}"
            return {"ok": False, "error": detalle}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ── Optimizador ───────────────────────────────────────
def ejecutar_optimizador(semana_id: int):
    try:
        r = requests.post(
            f"{BASE_URL}/api/v1/optimizador/ejecutar",
            json={"semana_id": semana_id},
            headers=_get_headers(),
            timeout=60
        )
        if r.status_code in [200, 201]:
            return r.json()
        else:
            try:
                detalle = r.json().get("detail", f"Error {r.status_code}")
            except Exception:
                detalle = f"Error HTTP {r.status_code}: {r.text[:200]}"
            return {"error": detalle, "ordenes_evaluadas": 0}
    except Exception as e:
        return {"error": str(e), "ordenes_evaluadas": 0}

def calcular_tiempos(of_ids: list[int]):
    return _post("/api/v1/optimizador/calcular-tiempos", {"of_ids": of_ids})

# ── KPIs ──────────────────────────────────────────────
def get_kpi_semanal(semana: str = None, semana_id: int = None):
    params = {}
    if semana_id:
        params["semana_id"] = semana_id
    elif semana:
        params["semana"] = semana
    return _get("/api/v1/kpi/semanal", params)

def get_kpi_por_semana_id(semana_id: int):
    return _get(f"/api/v1/kpi/semana/{semana_id}")

def get_cola_maquina(maquina_id: int, semana: str = None, semana_id: int = None):
    params = {}
    if semana_id:
        params["semana_id"] = semana_id
    elif semana:
        params["semana"] = semana
    return _get(f"/api/v1/maquinas/{maquina_id}/cola", params)

def get_icc_matrix(semana: str = None, semana_id: int = None):
    params = {}
    if semana_id:
        params["semana_id"] = semana_id
    elif semana:
        params["semana"] = semana
    return _get("/api/v1/kpi/icc_matrix", params)

def get_icc_semana(semana_id: int):
    if not semana_id:
        return []
    result = _get(f"/api/v1/kpi/icc/{semana_id}")
    return result if isinstance(result, list) else []

def max_icc_con_ofs_de_semana(of_id: int, semana_id: int):
    res = _get(f"/api/v1/kpi/icc/{semana_id}/max_of/{of_id}")
    if res and "max_icc" in res:
        return float(res["max_icc"])
    return 0.0

def get_setup_detalle(semana_id: int):
    return _get(f"/api/v1/kpi/semana/{semana_id}/setup-detalle")

def get_plan_semanal(semana: str = None):
    params = {"semana": semana} if semana else None
    return _get("/api/v1/kpi/plan-semanal", params)

# ── Paradas ───────────────────────────────────────────
def registrar_parada(payload: dict):
    return _post("/api/v1/paradas/", payload)

@st.cache_data(ttl=30)
def get_paradas(maquina_id: int = None):
    params = {"maquina_id": maquina_id} if maquina_id else None
    return _get("/api/v1/paradas/", params)

# ── Reportes ──────────────────────────────────────────
@st.cache_data(ttl=30)
def get_optimizaciones_log():
    return _get("/api/v1/optimizador/log")

def cambiar_password(payload: dict):
    token = st.session_state.get("token", "")
    try:
        r = requests.put(
            f"{BASE_URL}/api/v1/auth/cambiar-password",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None

def actualizar_perfil(payload: dict):
    token = st.session_state.get("token", "")
    try:
        r = requests.put(
            f"{BASE_URL}/api/v1/auth/actualizar-perfil",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None