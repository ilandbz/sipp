# Skill: Formulario de Orden de Fabricación (Streamlit)
# Archivo: .claude/skills/05_formulario_of.md
# Cuándo usarlo: al crear o modificar
# frontend/pages/ordenes.py  (lista + formulario de nueva OF)
# frontend/pages/orden_detalle.py  (editar una OF existente)

---

## Propósito
Registrar y editar Órdenes de Fabricación manualmente desde Streamlit.
Es el flujo operacional principal — NO se importa CSV para esto.

---

## Campos del formulario (mapean 1:1 con `sipp.ordenes_fabricacion`)

### Bloque 1 — Identificación
| Campo UI | Widget Streamlit | Campo BD | Validación |
|---|---|---|---|
| Código OF | `st.text_input` | `codigo_of` | Requerido, único |
| Código PT | `st.text_input` | `codigo_pt` | Opcional |
| Descripción | `st.text_area` | `descripcion` | Opcional |
| Referencia | `st.text_input` | `referencia` | Opcional |
| Tipo de producción | `st.selectbox` | `tipo_produccion` | "Stock" / "Pedido" |

### Bloque 2 — Asignación
| Campo UI | Widget Streamlit | Campo BD | Notas |
|---|---|---|---|
| Máquina | `st.selectbox` | `maquina_asignada_id` | Carga desde `GET /api/v1/maquinas/` |
| Cliente | `st.selectbox` + búsqueda | `cliente_id` | Carga desde `GET /api/v1/clientes/` |
| Material | `st.selectbox` | `material_id` | Carga desde `GET /api/v1/materiales/` |
| Cilindro | `st.selectbox` | `cilindro_id` | Carga desde `GET /api/v1/cilindros/` |

### Bloque 3 — Dimensiones del producto
| Campo UI | Widget Streamlit | Campo BD | Notas |
|---|---|---|---|
| Medida (texto libre) | `st.text_input` | `medida_texto` | Ej: "18X32X10.5" |
| Ancho (mm) | `st.number_input` | `ancho_mm` | Auto-rellenar si parsea Medida |
| Alto (mm) | `st.number_input` | `alto_mm` | Auto-rellenar |
| Fuelle (mm) | `st.number_input` | `fuelle_mm` | Auto-rellenar |
| Leva requerida | `st.text_input` | `leva_requerida` | |
| Distancia de base | `st.number_input` | `distancia_base_mm` | |

### Bloque 4 — Impresión
| Campo UI | Widget Streamlit | Campo BD | Notas |
|---|---|---|---|
| Gramaje | `st.number_input` | `gramaje` | |
| Número de colores | `st.number_input(min=1,max=6)` | `num_colores` | |
| Colores (detalle) | `st.text_area` | `colores_detalle` | "AZUL(P286U), ROJO..." |
| Tipo de bolsa | `st.text_input` | `tipo_bolsa` | |

### Bloque 5 — Cantidades
| Campo UI | Widget Streamlit | Campo BD | Notas |
|---|---|---|---|
| Cantidad pedido | `st.number_input` | `cantidad_pedido` | |
| Unidad de medida | `st.selectbox` | `unidad_medida` | "MIL" / "KG" / "UND" |
| Cantidad a producir (MT) | `st.number_input` | `cantidad_programada` | Miles |
| Peso por millar | `st.number_input` | `peso_por_millar` | |

### Bloque 6 — Fechas y planificación
| Campo UI | Widget Streamlit | Campo BD | Notas |
|---|---|---|---|
| Fecha de emisión | `st.date_input` | `fecha_emision` | |
| Fecha de entrega | `st.date_input` | `fecha_entrega` | **Campo crítico para el optimizador** |
| Inicio producción | `st.date_input` | `inicio_prod` | |

### Bloque 7 — Observaciones
| Campo UI | Widget Streamlit | Campo BD |
|---|---|---|
| Observación | `st.text_area` | `observacion` |

---

## Estructura del formulario en Streamlit

```python
# frontend/pages/ordenes.py
import streamlit as st
from utils.api_client import (
    get_maquinas, get_clientes, get_materiales, get_cilindros,
    crear_orden, actualizar_orden, get_ordenes
)

st.set_page_config(layout="wide")
st.title("📋 Órdenes de Fabricación")

# ── Tabs: Lista | Nueva OF ────────────────────────────────
tab_lista, tab_nueva = st.tabs(["Lista de OFs", "➕ Nueva OF"])

with tab_lista:
    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    filtro_maq    = col_f1.selectbox("Máquina", ["Todas"] + [m["codigo"] for m in (get_maquinas() or [])])
    filtro_estado = col_f2.selectbox("Estado", ["Todos", "PENDIENTE", "EN_PROCESO", "COMPLETADA"])
    filtro_buscar = col_f3.text_input("Buscar OF o descripción")

    ordenes = get_ordenes(maquina=filtro_maq, estado=filtro_estado, buscar=filtro_buscar) or []

    if not ordenes:
        st.info("No hay órdenes que coincidan con los filtros.")
    else:
        import pandas as pd
        df = pd.DataFrame(ordenes)
        st.dataframe(
            df[["codigo_of", "descripcion", "medida_texto", "material_nombre",
                "maquina_codigo", "fecha_entrega", "estado"]],
            use_container_width=True,
            hide_index=True,
        )

with tab_nueva:
    _formulario_of()   # función definida abajo


def _formulario_of(of_existente: dict = None):
    """
    Renderiza el formulario. Si of_existente tiene datos, modo edición.
    """
    es_edicion = of_existente is not None
    maquinas   = get_maquinas()   or []
    clientes   = get_clientes()   or []
    materiales = get_materiales() or []
    cilindros  = get_cilindros()  or []

    with st.form("form_of", clear_on_submit=not es_edicion):

        st.subheader("Identificación")
        c1, c2 = st.columns(2)
        codigo_of    = c1.text_input("Código OF *",  value=of_existente.get("codigo_of","") if es_edicion else "")
        codigo_pt    = c2.text_input("Código PT",    value=of_existente.get("codigo_pt","") if es_edicion else "")
        descripcion  = st.text_area("Descripción",   value=of_existente.get("descripcion","") if es_edicion else "")
        tipo_prod    = st.selectbox("Tipo de producción", ["Stock","Pedido","Reproceso"],
                                    index=["Stock","Pedido","Reproceso"].index(of_existente.get("tipo_produccion","Stock")) if es_edicion else 0)

        st.subheader("Asignación")
        c1, c2 = st.columns(2)
        maq_opciones  = {m["codigo"]: m["id"] for m in maquinas}
        mat_opciones  = {m["tipo"]:   m["id"] for m in materiales}
        cil_opciones  = {str(c["codigo"]): c["id"] for c in cilindros}
        cli_opciones  = {c["razon_social"]: c["id"] for c in clientes}

        maq_sel = c1.selectbox("Máquina *", list(maq_opciones.keys()))
        mat_sel = c2.selectbox("Material",  list(mat_opciones.keys()))
        cil_sel = c1.selectbox("Cilindro",  ["(ninguno)"] + list(cil_opciones.keys()))
        cli_sel = c2.selectbox("Cliente",   ["(ninguno)"] + list(cli_opciones.keys()))

        st.subheader("Dimensiones")
        c1, c2, c3, c4 = st.columns(4)
        medida_txt = c1.text_input("Medida", placeholder="18X32X10.5")
        ancho      = c2.number_input("Ancho (mm)",  min_value=0.0, step=0.1)
        alto       = c3.number_input("Alto (mm)",   min_value=0.0, step=0.1)
        fuelle     = c4.number_input("Fuelle (mm)", min_value=0.0, step=0.1)

        st.subheader("Impresión")
        c1, c2 = st.columns(2)
        gramaje    = c1.number_input("Gramaje",         min_value=0.0, step=1.0)
        num_colores= c2.number_input("Núm. colores",    min_value=0,   max_value=6, step=1)
        colores    = st.text_input("Detalle de colores", placeholder="AZUL(P286U), ROJO(P2347U)")

        st.subheader("Cantidades")
        c1, c2, c3 = st.columns(3)
        cant_pedido = c1.number_input("Cantidad pedido", min_value=0.0)
        unidad      = c2.selectbox("Unidad", ["MIL","KG","UND"])
        cant_mt     = c3.number_input("A producir (MT)", min_value=0.0, step=0.1)

        st.subheader("Fechas")
        c1, c2 = st.columns(2)
        import datetime
        fecha_emision  = c1.date_input("Fecha emisión",  value=datetime.date.today())
        fecha_entrega  = c2.date_input("Fecha entrega *", value=datetime.date.today())

        observacion = st.text_area("Observaciones")

        submitted = st.form_submit_button(
            "💾 Guardar" if es_edicion else "➕ Crear OF",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not codigo_of.strip():
            st.error("El Código OF es obligatorio.")
            return

        payload = {
            "codigo_of":            codigo_of.strip(),
            "codigo_pt":            codigo_pt.strip() or None,
            "descripcion":          descripcion.strip() or None,
            "tipo_produccion":      tipo_prod,
            "maquina_asignada_id":  maq_opciones.get(maq_sel),
            "material_id":          mat_opciones.get(mat_sel),
            "cilindro_id":          cil_opciones.get(cil_sel) if cil_sel != "(ninguno)" else None,
            "cliente_id":           cli_opciones.get(cli_sel) if cli_sel != "(ninguno)" else None,
            "medida_texto":         medida_txt.strip() or None,
            "ancho_mm":             ancho or None,
            "alto_mm":              alto or None,
            "fuelle_mm":            fuelle or None,
            "gramaje":              gramaje or None,
            "num_colores":          int(num_colores) or None,
            "colores_detalle":      colores.strip() or None,
            "cantidad_pedido":      cant_pedido or None,
            "unidad_medida":        unidad,
            "cantidad_programada":  cant_mt or None,
            "fecha_emision":        str(fecha_emision),
            "fecha_entrega":        str(fecha_entrega),
            "observacion":          observacion.strip() or None,
            "estado":               "PENDIENTE",
        }

        if es_edicion:
            resultado = actualizar_orden(of_existente["id"], payload)
            msg = "OF actualizada correctamente ✓"
        else:
            resultado = crear_orden(payload)
            msg = f"OF {codigo_of} creada correctamente ✓"

        if resultado:
            st.success(msg)
            st.rerun()
        else:
            st.error("Error al guardar. Verifique que el backend esté disponible.")
```

---

## Endpoints FastAPI necesarios para el formulario

Asegurarse de que estos endpoints existan en los routers:

```
GET  /api/v1/maquinas/           → lista de máquinas activas
GET  /api/v1/clientes/           → lista de clientes
GET  /api/v1/materiales/         → lista de materiales
GET  /api/v1/cilindros/          → lista de cilindros
GET  /api/v1/ordenes/            → lista con filtros ?maquina=&estado=&buscar=
POST /api/v1/ordenes/            → crear nueva OF
PATCH /api/v1/ordenes/{id}       → actualizar OF existente
DELETE /api/v1/ordenes/{id}      → eliminar OF (con confirmación)
```

---

## Funciones `api_client.py` necesarias

```python
def get_ordenes(maquina=None, estado=None, buscar=None):
    params = {}
    if maquina and maquina != "Todas":  params["maquina"] = maquina
    if estado  and estado  != "Todos":  params["estado"]  = estado
    if buscar:                          params["buscar"]  = buscar
    return _get("/api/v1/ordenes/", params=params)

def get_clientes():
    return _get("/api/v1/clientes/")

def get_materiales():
    return _get("/api/v1/materiales/")

def get_cilindros():
    return _get("/api/v1/cilindros/")

def crear_orden(payload: dict):
    try:
        r = requests.post(f"{BASE_URL}/api/v1/ordenes/", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def actualizar_orden(id: int, payload: dict):
    try:
        r = requests.patch(f"{BASE_URL}/api/v1/ordenes/{id}", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
```

---

## Checklist antes de dar por terminado el formulario

- [ ] Todos los selectbox cargan datos desde el backend (no listas hardcodeadas)
- [ ] `fecha_entrega` es campo obligatorio (el optimizador lo usa para prioridad)
- [ ] `codigo_of` validado como no vacío antes de enviar
- [ ] Payload no incluye campos `None` innecesarios (limpiar con dict comprehension si hace falta)
- [ ] Modo edición y modo creación usan el mismo `_formulario_of()`
- [ ] Después de guardar → `st.rerun()` para refrescar la lista
- [ ] Errores del backend mostrados con `st.error(...)` sin crashear la app
- [ ] El campo `estado` se inicializa siempre en `"PENDIENTE"` al crear
