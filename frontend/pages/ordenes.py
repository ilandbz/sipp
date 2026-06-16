import streamlit as st
import datetime
import pandas as pd
from utils.api_client import (
    get_maquinas, get_clientes, get_materiales, get_cilindros,
    get_ordenes, crear_orden, actualizar_orden, get_tipos_bolsa
)
from auth import require_login, can, render_sidebar

require_login()

st.set_page_config(layout="wide", page_icon="🏭")
render_sidebar()
st.title("📋 Órdenes de Fabricación")

# Cargar catálogos al inicio y validar disponibilidad del backend
maquinas = get_maquinas()
clientes = get_clientes()
materiales = get_materiales()
cilindros = get_cilindros()
tipos_bolsa = get_tipos_bolsa()

if maquinas is None or clientes is None or materiales is None or cilindros is None or tipos_bolsa is None:
    st.error("⚠ Backend no disponible. Verifique que FastAPI esté corriendo en localhost:8000")
    st.stop()

# Manejo de estado de edición en session_state
if "of_para_editar" not in st.session_state:
    st.session_state.of_para_editar = None

# Determinar nombre del tab dinámicamente
es_edicion = st.session_state.of_para_editar is not None
tab_nueva_nombre = "✏️ Editar OF" if es_edicion else "➕ Nueva OF"

tab_lista, tab_nueva = st.tabs(["Lista de OFs", tab_nueva_nombre])

with tab_lista:
    st.subheader("Filtrar y Buscar Órdenes")
    col_f1, col_f2, col_f3 = st.columns(3)
    
    filtro_maq = col_f1.selectbox("Máquina", ["Todas"] + [m["codigo"] for m in maquinas])
    filtro_estado = col_f2.selectbox("Estado", ["Todos", "PENDIENTE", "PROGRAMADA", "EN_PROCESO", "COMPLETADA", "CANCELADA"])
    filtro_buscar = col_f3.text_input("Buscar OF, descripción o código PT")
    
    ordenes = get_ordenes(maquina=filtro_maq, estado=filtro_estado, buscar=filtro_buscar) or []
    
    if not ordenes:
        st.info("No hay órdenes que coincidan con los filtros seleccionados.")
    else:
        # Preparar dataframe
        df_data = []
        for of in ordenes:
            prioridad_map = {
                1: "🔴 Alta",
                2: "🟡 Media",
                3: "🟢 Baja"
            }
            prio_badge = prioridad_map.get(of.get("prioridad"), "🟢 Baja")
            df_data.append({
                "ID": of["id"],
                "Prioridad": prio_badge,
                "Código OF": of["codigo_of"],
                "Código PT": of["codigo_pt"] or "",
                "Descripción": of["descripcion"] or "",
                "Medida": of["medida_texto"] or "",
                "Material": of["material_nombre"] or "",
                "Máquina": of["maquina_codigo"] or "",
                "Fecha Atención": of.get("fecha_atencion") or "",
                "Fecha Entrega": of["fecha_entrega"] or "",
                "Estado": of["estado"]
            })
        df = pd.DataFrame(df_data)
        
        # En Streamlit moderno (v1.30+), st.dataframe soporta selección de fila
        # Para garantizar compatibilidad, mostramos un selector numérico o un selectbox de ID debajo de la tabla
        st.dataframe(df, width='stretch', hide_index=True)
        
        if can("editar_of"):
            st.write("---")
            st.subheader("Seleccionar OF para Edición")
            selected_id = st.selectbox(
                "Selecciona una Orden de Fabricación para editar sus detalles:",
                options=[None] + [of["id"] for of in ordenes],
                format_func=lambda x: f"OF: {next((of['codigo_of'] for of in ordenes if of['id'] == x), '')} - {next((of['descripcion'][:50] for of in ordenes if of['id'] == x), '')}" if x is not None else "-- Seleccionar --"
            )
            
            if selected_id is not None:
                of_sel = next(of for of in ordenes if of["id"] == selected_id)
                st.session_state.of_para_editar = of_sel
                st.success(f"OF {of_sel['codigo_of']} seleccionada. Dirígete a la pestaña '{tab_nueva_nombre}' para continuar.")
                st.button("Ir a Editar", type="primary")

def _formulario_of(of_existente: dict = None):
    es_ed = of_existente is not None
    
    # Mapeos de catálogos
    maq_opciones = {m["codigo"]: m["id"] for m in maquinas}
    cli_opciones = {c["razon_social"]: c["id"] for c in clientes}
    mat_opciones = {m["tipo"]: m["id"] for m in materiales}
    cil_opciones = {str(c["codigo"]): c["id"] for c in cilindros}
    bolsa_opciones = {str(tb["numero"]): tb["id"] for tb in tipos_bolsa}
    
    # Encontrar indices seleccionados
    idx_maq = 0
    if es_ed and of_existente.get("maquina_codigo") in maq_opciones:
        idx_maq = list(maq_opciones.keys()).index(of_existente.get("maquina_codigo"))
        
    idx_cli = 0
    if es_ed and of_existente.get("cliente_nombre") in cli_opciones:
        idx_cli = list(cli_opciones.keys()).index(of_existente.get("cliente_nombre")) + 1
        
    idx_mat = 0
    if es_ed and of_existente.get("material_nombre") in mat_opciones:
        idx_mat = list(mat_opciones.keys()).index(of_existente.get("material_nombre"))
        
    idx_cil = 0
    cil_codigo_guardado = None
    if es_ed and of_existente.get("cilindro_id"):
        for c in cilindros:
            if c["id"] == of_existente["cilindro_id"]:
                cil_codigo_guardado = str(c["codigo"])
                break
    if es_ed and cil_codigo_guardado in cil_opciones:
        idx_cil = list(cil_opciones.keys()).index(cil_codigo_guardado) + 1

    idx_bolsa = 0
    if es_ed and of_existente.get("tipo_bolsa_id"):
        for i, bid in enumerate(bolsa_opciones.values()):
            if bid == of_existente["tipo_bolsa_id"]:
                idx_bolsa = i + 1
                break

    idx_prio = 2
    if es_ed and of_existente.get("prioridad"):
        prio_val = of_existente["prioridad"]
        if prio_val in [1, 2, 3]:
            idx_prio = prio_val - 1

    val_entrega = datetime.date.today() + datetime.timedelta(days=7)
    if es_ed and of_existente.get("fecha_entrega"):
        val_entrega = datetime.datetime.strptime(of_existente["fecha_entrega"], "%Y-%m-%d").date()

    with st.form("form_of", clear_on_submit=not es_ed):
        st.subheader("🌟 Datos Obligatorios")
        col_id1, col_id2 = st.columns(2)
        codigo_of = col_id1.text_input("Código OF *", value=of_existente.get("codigo_of", "") if es_ed else "")
        descripcion = col_id2.text_input("Descripción / Producto *", value=of_existente.get("descripcion", "") if es_ed else "")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        maq_sel = col_m1.selectbox("Máquina *", list(maq_opciones.keys()), index=idx_maq)
        mat_sel = col_m2.selectbox("Material *", list(mat_opciones.keys()), index=idx_mat)
        bolsa_sel = col_m3.selectbox("N° de Bolsa *", ["(ninguno)"] + list(bolsa_opciones.keys()), index=idx_bolsa)
        
        st.write("**Medida (mm) ***")
        col_dim1, col_dim2, col_dim3 = st.columns(3)
        ancho = col_dim1.number_input("Ancho", min_value=0.0, step=0.5, value=float(of_existente.get("ancho_mm") or 0.0) if es_ed else 0.0)
        alto = col_dim2.number_input("Alto", min_value=0.0, step=0.5, value=float(of_existente.get("alto_mm") or 0.0) if es_ed else 0.0)
        fuelle = col_dim3.number_input("Fuelle", min_value=0.0, step=0.5, value=float(of_existente.get("fuelle_mm") or 0.0) if es_ed else 0.0)
        
        col_c1, col_c2, col_c3 = st.columns(3)
        colores_det = col_c1.text_input("Colores / Impresión *", value=of_existente.get("colores_detalle", "") if es_ed else "")
        cant_prog = col_c2.number_input("Cantidad a producir (Millares) *", min_value=0.0, step=0.1, value=float(of_existente.get("cantidad_programada") or 0.0) if es_ed else 0.0)
        fecha_entrega = col_c3.date_input("Fecha de entrega *", value=val_entrega)
        
        col_c4, col_c5 = st.columns(2)
        cli_sel = col_c4.selectbox("Cliente", ["Sin cliente"] + list(cli_opciones.keys()), index=idx_cli)
        prioridad_sel = col_c5.selectbox(
            "Urgencia del pedido *", 
            ["1 - Alta", "2 - Media", "3 - Baja"], 
            index=idx_prio,
            help="Úsalo solo para pedidos urgentes independiente del cliente. La prioridad del cliente viene de su Franquicia."
        )

        with st.expander("➕ Datos adicionales"):
            col_o1, col_o2 = st.columns(2)
            codigo_pt = col_o1.text_input("Código PT", value=of_existente.get("codigo_pt", "") if es_ed else "")
            cil_sel = col_o2.selectbox("Cilindro", ["(ninguno)"] + list(cil_opciones.keys()), index=idx_cil)
            
            col_o3, col_o4 = st.columns(2)
            gramaje = col_o3.number_input("Gramaje", min_value=0.0, step=1.0, value=float(of_existente.get("gramaje") or 0.0) if es_ed else 0.0)
            num_colores = col_o4.number_input("Número de colores", min_value=0, max_value=6, step=1, value=int(of_existente.get("num_colores") or 0) if es_ed else 0)
            
            col_o5, col_o6 = st.columns(2)
            peso_mil = col_o5.number_input("Peso por millar", min_value=0.0, step=0.1, value=float(of_existente.get("peso_por_millar") or 0.0) if es_ed else 0.0)
            leva_req = col_o6.text_input("Leva requerida", value=of_existente.get("leva_requerida", "") if es_ed else "")
            
            dist_base = st.number_input("Distancia de base (mm)", min_value=0.0, step=0.1, value=float(of_existente.get("distancia_base_mm") or 0.0) if es_ed else 0.0)
            
            observacion = st.text_area("Observación", value=of_existente.get("observacion", "") if es_ed else "")

        st.info("""
        ℹ️ **Campos Calculados Automáticamente:**
        - **Ancho de bobina:** Se calcula al guardar.
        - **Horas de producción:** Se calcula en la optimización.
        - **Fecha de inicio:** Se ajusta al programar la semana.
        - **Estado:** Inicia siempre en PENDIENTE.
        """)

        label_btn = "💾 Guardar Cambios" if es_ed else "➕ Crear Orden de Fabricación"
        submitted = st.form_submit_button(label_btn, type="primary", use_container_width=True)

    if submitted:
        if not codigo_of.strip():
            st.error("El Código OF es obligatorio.")
            return
        if not descripcion.strip():
            st.error("La descripción es obligatoria.")
            return
        if bolsa_sel == "(ninguno)":
            st.error("Debe seleccionar un N° de Bolsa válido.")
            return

        payload = {
            "codigo_of": codigo_of.strip(),
            "codigo_pt": codigo_pt.strip() or None,
            "descripcion": descripcion.strip() or None,
            "cliente_id": cli_opciones.get(cli_sel) if cli_sel != "Sin cliente" else None,
            "maquina_asignada_id": maq_opciones.get(maq_sel),
            "material_id": mat_opciones.get(mat_sel),
            "cilindro_id": cil_opciones.get(cil_sel) if cil_sel != "(ninguno)" else None,
            "ancho_mm": ancho or None,
            "alto_mm": alto or None,
            "fuelle_mm": fuelle or None,
            "distancia_base_mm": dist_base or None,
            "leva_requerida": leva_req.strip() or None,
            "gramaje": gramaje or None,
            "num_colores": int(num_colores) or None,
            "colores_detalle": colores_det.strip() or None,
            "unidad_medida": "MIL",
            "cantidad_programada": cant_prog or None,
            "peso_por_millar": peso_mil or None,
            "fecha_entrega": str(fecha_entrega),
            "observacion": observacion.strip() or None,
            "estado": of_existente.get("estado", "PENDIENTE") if es_ed else "PENDIENTE",
            "prioridad": int(prioridad_sel.split(" - ")[0]),
            "tipo_bolsa_id": bolsa_opciones.get(bolsa_sel) if bolsa_sel != "(ninguno)" else None,
        }

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        payload["fecha_entrega"] = str(fecha_entrega)

        # Calculo optimista para el UI message
        ancho_bobina = 0.0
        if ancho and fuelle:
            ancho_bobina = (ancho + fuelle) * 2 + 25

        if es_ed:
            res = actualizar_orden(of_existente["id"], payload)
            if res:
                st.success(f"Orden actualizada correctamente ✓ | Ancho bobina: {ancho_bobina} mm")
                st.session_state.of_para_editar = None
                st.rerun()
        else:
            res = crear_orden(payload)
            if res:
                st.success(f"✓ OF {codigo_of} creada | Ancho bobina: {ancho_bobina} mm")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("➕ Crear otra OF"):
                        st.rerun()
                with col_btn2:
                    if st.button("📅 Ir a Semanas para asignarla"):
                        st.switch_page("pages/semanas.py")

with tab_nueva:
    if es_edicion:
        if can("editar_of"):
            st.info("Modo Edición Activado")
            if st.button("❌ Cancelar Edición y volver a Crear"):
                st.session_state.of_para_editar = None
                st.rerun()
            _formulario_of(st.session_state.of_para_editar)
        else:
            st.error("No tienes permisos para editar órdenes.")
    else:
        if can("crear_of"):
            st.subheader("Crear una Nueva Orden de Fabricación")
            _formulario_of()
        else:
            st.info("No tienes permisos para crear órdenes.")
