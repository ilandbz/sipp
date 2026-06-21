import streamlit as st
from datetime import date, datetime, timedelta
import pandas as pd
from utils.api_client import (
    get_maquinas, get_clientes, get_materiales, get_cilindros,
    get_ordenes, crear_orden, actualizar_orden, get_tipos_bolsa, eliminar_orden
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

@st.cache_data(ttl=10)  # Solo 10 segundos de cache
def cargar_ordenes(maquina, estado, buscar):
    return get_ordenes(maquina=maquina, estado=estado, buscar=buscar)

tab_lista, tab_nueva, tab_editar = st.tabs([
    "📋 Lista de OFs",
    "➕ Nueva OF", 
    "✏️ Editar OF"
])

with tab_lista:
    st.subheader("Filtrar y Buscar Órdenes")
    col_filtros, col_refresh = st.columns([10, 1])
    with col_filtros:
        col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 4, 1])
        filtro_maq = col_f1.selectbox("Máquina", ["Todas"] + [m["codigo"] for m in maquinas])
        filtro_estado = col_f2.selectbox("Estado", ["Todos", "PENDIENTE", "PROGRAMADA", "EN_PROCESO", "COMPLETADA", "CANCELADA"])
        filtro_buscar = col_f3.text_input("Buscar OF, descripción o código PT")
        items_por_pagina = col_f4.selectbox("Items/Pág.", [10, 20, 50, 100], index=1)
    
    with col_refresh:
        if st.button("🔄", help="Actualizar lista", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.caption(f"Última actualización: {datetime.now().strftime('%H:%M:%S')}")
    
    ordenes = cargar_ordenes(filtro_maq, filtro_estado, filtro_buscar) or []
    
    if not ordenes:
        st.info("No hay órdenes que coincidan con los filtros seleccionados.")
    else:
        # Configuración de paginación
        ITEMS_POR_PAGINA = items_por_pagina

        # Estado de página actual
        if "pagina_ordenes" not in st.session_state:
            st.session_state["pagina_ordenes"] = 1

        # IMPORTANTE: Resetear a página 1 cuando cambian los filtros
        filtros_actuales = f"{filtro_maq}_{filtro_estado}_{filtro_buscar}"
        if st.session_state.get("filtros_prev") != filtros_actuales:
            st.session_state["pagina_ordenes"] = 1
            st.session_state["filtros_prev"] = filtros_actuales

        # Aplicar paginación a la lista
        total_items = len(ordenes)
        total_paginas = max(1, (total_items + ITEMS_POR_PAGINA - 1) // ITEMS_POR_PAGINA)

        # Asegurar página válida
        pagina_actual = st.session_state["pagina_ordenes"]
        if pagina_actual > total_paginas:
            pagina_actual = 1
            st.session_state["pagina_ordenes"] = 1

        inicio = (pagina_actual - 1) * ITEMS_POR_PAGINA
        fin = inicio + ITEMS_POR_PAGINA
        ordenes_pagina = ordenes[inicio:fin]

        # Mostrar info de paginación
        st.caption(
            f"Mostrando {inicio+1}–{min(fin, total_items)} "
            f"de {total_items} órdenes | "
            f"Página {pagina_actual} de {total_paginas}"
        )

        # Cabecera de la tabla
        cols = st.columns([1, 1.5, 2, 4, 2, 1.5, 1, 2, 2, 2, 1.5, 1.5])
        headers = ["ID","Prioridad","Código OF","Descripción",
                   "Medida","Cantidad","U.M.","Material","Máquina","F.Entrega","Estado","Acciones"]
        for col, h in zip(cols, headers):
            col.markdown(f"**{h}**")
        st.divider()

        # Filas
        for of in ordenes_pagina:
            of_id = of.get("id")
            estado = of.get("estado", "")
            
            cols = st.columns([1, 1.5, 2, 4, 2, 1.5, 1, 2, 2, 2, 1.5, 1.5])
            cols[0].write(of_id)
            
            # Badge prioridad
            p = of.get("prioridad", 3)
            badge = "🔴" if p == 1 else "🟡" if p == 2 else "🟢"
            cols[1].write(f"{badge} {'Alta' if p==1 else 'Media' if p==2 else 'Baja'}")
            
            cols[2].write(of.get("codigo_of", ""))
            cols[3].write(of.get("descripcion", "")[:50])
            
            medida_display = of.get("medida_display") or of.get("medida_texto") or ""
            if medida_display in ["0X0X0", "0x0x0", "0X0", "0", ""]:
                medida_display = "--"
            cols[4].write(medida_display)
            
            cols[5].write(f"{of.get('cantidad_pedido') or of.get('cantidad_programada') or '-'}")
            cols[6].write(of.get("unidad_medida") or "MIL")
            
            cols[7].write(of.get("material_nombre", ""))
            cols[8].write(of.get("maquina_codigo") or "Sin asignar")
            
            fecha = of.get("fecha_entrega")
            if fecha:
                try:
                    from datetime import datetime
                    fecha_fmt = datetime.strptime(str(fecha)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception:
                    fecha_fmt = str(fecha)[:10]
            else:
                fecha_fmt = ""
            cols[9].write(fecha_fmt)
            
            # Badge estado
            estado_badge = {
                "PENDIENTE": "⚪",
                "EN_PROCESO": "🔵", 
                "COMPLETADA": "🟢",
                "CANCELADA": "⚫"
            }
            cols[10].write(f"{estado_badge.get(estado,'⚪')} {estado}")
            
            # Botones acciones
            with cols[11]:
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("✏️", key=f"edit_{of_id}", 
                                help="Editar esta orden"):
                        st.session_state["of_editar_id"] = of_id
                        st.session_state.of_para_editar = of
                        st.rerun()
                with btn_col2:
                    if estado == "PENDIENTE":
                        if st.button("🗑️", key=f"del_{of_id}",
                                    help="Eliminar orden"):
                            st.session_state[f"confirmar_del_{of_id}"] = True
                            st.rerun()
            
            # Confirmación eliminación
            if st.session_state.get(f"confirmar_del_{of_id}"):
                with st.container():
                    st.warning(
                        f"⚠️ ¿Eliminar **{of.get('codigo_of')}** - "
                        f"{of.get('descripcion','')[:40]}?"
                    )
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c2:
                        if st.button("✅ Sí", key=f"si_{of_id}",
                                    type="primary"):
                            resultado = eliminar_orden(of_id)
                            if resultado and resultado.get("ok"):
                                st.success(f"✓ OF eliminada")
                                st.session_state.pop(f"confirmar_del_{of_id}", None)
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                error = resultado.get("error","Error") if resultado else "Error"
                                st.error(f"❌ {error}")
                    with c3:
                        if st.button("❌ No", key=f"no_{of_id}"):
                            st.session_state.pop(f"confirmar_del_{of_id}", None)
                            st.rerun()
            
            st.divider()

        # Controles de navegación al final
        st.divider()
        col_prev, col_info, col_next = st.columns([1, 3, 1])

        with col_prev:
            if st.button("◀ Anterior", 
                         disabled=(pagina_actual <= 1),
                         use_container_width=True):
                st.session_state["pagina_ordenes"] -= 1
                st.rerun()

        with col_info:
            # Selector de página directa
            nueva_pag = st.number_input(
                "Ir a página",
                min_value=1,
                max_value=total_paginas,
                value=pagina_actual,
                step=1,
                label_visibility="collapsed"
            )
            if nueva_pag != pagina_actual:
                st.session_state["pagina_ordenes"] = int(nueva_pag)
                st.rerun()

        with col_next:
            if st.button("Siguiente ▶",
                         disabled=(pagina_actual >= total_paginas),
                         use_container_width=True):
                st.session_state["pagina_ordenes"] += 1
                st.rerun()

def _formulario_of(of_existente: dict = None):
    es_ed = of_existente is not None
    
    # Mapeos de catálogos
    maq_opciones = {"🤖 Asignar automáticamente (recomendado)": None}
    for m in maquinas:
        maq_opciones[m["codigo"]] = m["id"]
    cli_opciones = {c["razon_social"]: c["id"] for c in clientes}
    mat_opciones = {}
    materiales_gramaje = {}
    for m in materiales:
        nombre = m.get("tipo") or m.get("nombre", "")
        mid = m.get("id")
        mat_opciones[nombre] = mid
        materiales_gramaje[mid] = float(m.get("gramaje_min") or 0.0)
    cil_opciones = {str(c["codigo"]): c["id"] for c in cilindros}
    bolsa_opciones = {str(tb["numero"]): tb["id"] for tb in tipos_bolsa}
    
    # Encontrar indices seleccionados
    idx_maq = 0
    if es_ed and of_existente.get("maquina_codigo") and of_existente.get("maquina_codigo") != "Sin asignar":
        if of_existente["maquina_codigo"] in maq_opciones:
            idx_maq = list(maq_opciones.keys()).index(of_existente["maquina_codigo"])
        
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

    val_entrega = date.today() + timedelta(days=7)
    if es_ed and of_existente.get("fecha_entrega"):
        val_entrega = datetime.strptime(of_existente["fecha_entrega"], "%Y-%m-%d").date()

    if "of_resultado" in st.session_state:
        resultado_msg = st.session_state.pop("of_resultado")
        if resultado_msg["ok"]:
            st.success(resultado_msg["msg"])
            col1, col2 = st.columns(2)
            with col1:
                if st.button("➕ Crear otra OF"):
                    st.rerun()
            with col2:
                if st.button("📅 Ir a Semanas para asignarla"):
                    st.switch_page("pages/semanas.py")
        else:
            st.error(resultado_msg["msg"])

    prefix = f"ed_{of_existente.get('id', 0)}_" if es_ed else "new_"
    form_key = f"form_editar_of_{of_existente.get('id', 0)}" if es_ed else "form_nueva_of"
    
    if es_ed and of_existente:
        from utils.api_client import get_sugerencia_maquina
        sugerencias = get_sugerencia_maquina(of_existente["id"])
        if sugerencias:
            mejor = sugerencias[0]
            st.info(f"💡 Máquina sugerida: **{mejor['codigo']}** "
                    f"(Carga: {mejor['carga_pct']:.0f}% | "
                    f"Compatibilidad: {mejor['icc']:.0f}/100)")
    
    with st.form(form_key, clear_on_submit=not es_ed):
        st.subheader("🌟 Datos Obligatorios")
        if es_ed:
            st.text_input("Código OF", value=of_existente.get("codigo_of", ""), disabled=True, key=f"{prefix}codigo_of_disabled")
            codigo_of = of_existente.get("codigo_of", "")
        else:
            st.info("📋 El código OF se genera automáticamente al guardar")
            with st.expander("🔧 Código manual (avanzado)"):
                codigo_of_manual = st.text_input(
                    "Código OF manual",
                    placeholder="Dejar vacío para autogenerar (ej: 2606-0001)",
                    help="Solo usar si necesitas un código específico del sistema anterior",
                    key=f"{prefix}codigo_of_manual"
                )
            codigo_of = codigo_of_manual.strip()

        descripcion = st.text_input("Descripción / Producto *", value=of_existente.get("descripcion", "") if es_ed else "", key=f"{prefix}descripcion")
        
        # Campo medida texto (referencia rápida)
        medida_val = of_existente.get("medida_texto", "") if es_ed else ""
        if medida_val in ["0X0X0", "0x0x0", "0X0", "0x0"]:
            medida_val = ""
        medida_texto = st.text_input(
            "Medida (referencia)",
            value=medida_val,
            placeholder="Ej: 18X32X10.5 — se actualiza al guardar si ingresas Ancho/Alto/Fuelle",
            help="Si ingresas Ancho, Alto y Fuelle, la medida se calcula automáticamente",
            key=f"{prefix}medida_texto"
        )
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        maq_sel = col_m1.selectbox("Máquina", list(maq_opciones.keys()), index=idx_maq, key=f"{prefix}maq_sel")
        if es_ed:
            col_m1.caption("💡 La máquina sugerida se calcula automáticamente al guardar si dejas 'Asignar automáticamente'")
            
        mat_sel = col_m2.selectbox("Material *", list(mat_opciones.keys()), index=idx_mat, key=f"{prefix}mat_sel")
        mat_sel_id = mat_opciones.get(mat_sel)
        gramaje_auto = materiales_gramaje.get(mat_sel_id, 0.0)
        bolsa_sel = col_m3.selectbox("N° de Bolsa *", ["(ninguno)"] + list(bolsa_opciones.keys()), index=idx_bolsa, key=f"{prefix}bolsa_sel")
        cil_sel = col_m4.selectbox("Cilindro", ["(ninguno)"] + list(cil_opciones.keys()), index=idx_cil, key=f"{prefix}cil_sel")
        col_m4.caption("🔧 Cambiar de cilindro entre OFs = +30 min de setup")
        
        st.write("**Medida (mm) ***")
        col_dim1, col_dim2, col_dim3 = st.columns(3)
        
        ancho_val = float(of_existente.get("ancho_mm") or 0.0) if es_ed else 0.0
        ancho = col_dim1.number_input("Ancho (mm)", min_value=0.0, step=0.5, value=ancho_val if ancho_val > 0 else None, placeholder="ej: 16.0", key=f"{prefix}ancho")
        
        alto_val = float(of_existente.get("alto_mm") or 0.0) if es_ed else 0.0
        alto = col_dim2.number_input("Alto (mm)", min_value=0.0, step=0.5, value=alto_val if alto_val > 0 else None, placeholder="ej: 28.5", key=f"{prefix}alto")
        
        fuelle_val = float(of_existente.get("fuelle_mm") or 0.0) if es_ed else 0.0
        fuelle = col_dim3.number_input("Fuelle (mm)", min_value=0.0, step=0.5, value=fuelle_val if fuelle_val > 0 else None, placeholder="ej: 10.0", key=f"{prefix}fuelle")
        
        col_c1, col_c2, col_c3 = st.columns(3)
        num_colores = col_c1.number_input("Número de colores", min_value=0, max_value=6, step=1, value=int(of_existente.get("num_colores") or 0) if es_ed else 0, key=f"{prefix}num_colores")
        col_c1.caption("🎨 Cambiar colores entre OFs = +45 min de setup")
        colores_det = col_c2.text_input("Colores / Impresión *", value=of_existente.get("colores_detalle", "") if es_ed else "", key=f"{prefix}colores_det")
        fecha_entrega = col_c3.date_input("Fecha de entrega *", value=val_entrega, key=f"{prefix}fecha_entrega")
        
        col_c4, col_c5, col_c6 = st.columns(3)
        cant_prog = col_c4.number_input("Cantidad a producir (Millares) *", min_value=0.0, step=0.1, value=float(of_existente.get("cantidad_programada") or 0.0) if es_ed else 0.0, key=f"{prefix}cant_prog")
        cli_sel = col_c5.selectbox("Cliente", ["Sin cliente"] + list(cli_opciones.keys()), index=idx_cli, key=f"{prefix}cli_sel")
        prioridad_sel = col_c6.selectbox(
            "Urgencia del pedido *", 
            ["1 - Alta", "2 - Media", "3 - Baja"], 
            index=idx_prio,
            help="Úsalo solo para pedidos urgentes independiente del cliente. La prioridad del cliente viene de su Franquicia.",
            key=f"{prefix}prioridad_sel"
        )

        with st.expander("➕ Datos adicionales"):
            st.info(
                "💡 **Datos técnicos opcionales** — Completa estos campos para "
                "mejorar la precisión del cálculo de setup y el peso de producción. "
                "El **Cilindro** y **Número de colores** (en la vista principal) "
                "son los más importantes para el optimizador."
            )
            col_o1, col_o2 = st.columns(2)
            codigo_pt = col_o1.text_input(
                "Código PT", 
                value=of_existente.get("codigo_pt", "") if es_ed else "", 
                help="Código interno del Producto Terminado. Usado para trazabilidad y despacho en almacén.",
                key=f"{prefix}codigo_pt"
            )
            gramaje_prev = float(of_existente.get("gramaje") or 0.0) if es_ed else 0.0
            gramaje_auto = float(materiales_gramaje.get(mat_sel_id, 0.0)) if mat_sel_id else 0.0
            gramaje_val = gramaje_auto if gramaje_auto > 0 else gramaje_prev
            gramaje_final = gramaje_val if gramaje_val > 0 else 0.0
            
            gramaje = col_o2.number_input(
                "Gramaje (g/m²)",
                value=gramaje_final,
                min_value=0.0,
                step=0.5,
                key=f"gramaje_input_{mat_sel_id}",
                help="Peso del papel en gramos por metro cuadrado. Se completa automáticamente según el material seleccionado."
            )
            
            if gramaje_auto > 0:
                col_o2.caption(f"✅ Autocompletado desde {mat_sel}: {gramaje_auto} g/m²")
            else:
                col_o2.caption("⚠ Este material no tiene gramaje definido. Ingresa el valor manualmente.")
            
            col_o3, col_o4 = st.columns(2)
            peso_mil = col_o3.number_input(
                "Peso por millar (kg)", 
                min_value=0.0, 
                step=0.1, 
                value=float(of_existente.get("peso_por_millar") or 0.0) if es_ed else 0.0, 
                help="Peso en kilogramos de 1,000 bolsas terminadas. Referencia: Área bolsa × Gramaje / 1,000,000 × 2 caras",
                key=f"{prefix}peso_mil"
            )
            if gramaje_final > 0 and ancho > 0 and alto > 0:
                area_m2 = ((ancho + fuelle) * 2 * alto) / 1_000_000
                peso_estimado = round(area_m2 * gramaje_final * 1000, 2)
                col_o3.caption(f"📐 Estimado automático: {peso_estimado} kg/millar "
                           f"(Área {round(area_m2*10000,2)} cm² × {gramaje_final} g/m²)")
            
            OPCIONES_LEVA = [
                "",
                "Leva #1 — Bolsa #1 (pequeña)",
                "Leva #2 — Bolsa #2",
                "Leva #3 — Bolsa #4",
                "Leva #4 — Bolsa #5",
                "Leva #5 — Bolsa #6",
                "Leva #6 — Bolsa #8",
                "Leva #7 — Bolsa #10",
                "Leva #8 — Bolsa #12 (grande)",
                "Leva especial — Formato no estándar",
            ]
            
            leva_actual = of_existente.get("leva_requerida", "") if es_ed else ""
            try:
                idx_leva = OPCIONES_LEVA.index(leva_actual) if leva_actual else 0
            except ValueError:
                idx_leva = 0

            leva_req = col_o4.selectbox(
                "Leva requerida", 
                options=OPCIONES_LEVA, 
                index=idx_leva,
                format_func=lambda x: "— Seleccionar leva —" if x == "" else x,
                help="Pieza mecánica que controla el movimiento del fuelle. Cada tamaño de bolsa requiere una leva específica. Cambiar de leva implica tiempo adicional de setup.",
                key=f"{prefix}leva_req"
            )
            
            dist_base = st.number_input(
                "Distancia de base (mm)", 
                min_value=0.0, 
                step=0.1, 
                value=float(of_existente.get("distancia_base_mm") or 0.0) if es_ed else 0.0, 
                help="Paso del cilindro en milímetros. Distancia que avanza el papel por cada vuelta del cilindro de impresión.",
                key=f"{prefix}dist_base"
            )
            
            observacion = st.text_area("Observación", value=of_existente.get("observacion", "") if es_ed else "", key=f"{prefix}observacion")

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
        if es_ed and not codigo_of.strip():
            st.error("El Código OF es obligatorio en edición.")
            return
        if not descripcion.strip():
            st.error("La descripción es obligatoria.")
            return
        if bolsa_sel == "(ninguno)":
            st.error("Debe seleccionar un N° de Bolsa válido.")
            return

        payload = {
            "codigo_of": codigo_of,
            "codigo_pt": codigo_pt.strip() or None,
            "descripcion": descripcion.strip() or None,
            "cliente_id": int(cli_opciones[cli_sel]) if cli_sel != "Sin cliente" else None,
            "maquina_asignada_id": int(maq_opciones[maq_sel]) if maq_opciones[maq_sel] is not None else None,
            "material_id": int(mat_opciones[mat_sel]),
            "cilindro_id": int(cil_opciones[cil_sel]) if cil_sel != "(ninguno)" else None,
            "ancho_mm": float(ancho) if ancho and ancho > 0 else None,
            "alto_mm": float(alto) if alto and alto > 0 else None,
            "fuelle_mm": float(fuelle) if fuelle and fuelle > 0 else None,
            "distancia_base_mm": float(dist_base) if dist_base > 0 else None,
            "leva_requerida": leva_req.strip() or None,
            "gramaje": float(gramaje) if gramaje > 0 else None,
            "num_colores": int(num_colores) if num_colores > 0 else None,
            "colores_detalle": colores_det.strip() or None,
            "unidad_medida": "MIL",
            "cantidad_programada": float(cant_prog) if cant_prog > 0 else None,
            "peso_por_millar": float(peso_mil) if peso_mil > 0 else None,
            "fecha_entrega": str(fecha_entrega),
            "observacion": observacion.strip() or None,
            "estado": of_existente.get("estado", "PENDIENTE") if es_ed else "PENDIENTE",
            "prioridad": int(prioridad_sel.split(" - ")[0]),
            "tipo_bolsa_id": int(bolsa_opciones[bolsa_sel]) if bolsa_sel != "(ninguno)" else None,
        }

        # Si el usuario llenó ancho/alto/fuelle, generar medida_texto automático
        if ancho and alto and ancho > 0 and alto > 0:
            if fuelle and fuelle > 0:
                medida_calculada = f"{ancho}X{alto}X{fuelle}"
            else:
                medida_calculada = f"{ancho}X{alto}"
            payload["medida_texto"] = medida_calculada
        elif medida_texto.strip():
            payload["medida_texto"] = medida_texto.strip()
        else:
            payload["medida_texto"] = None

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        payload["fecha_entrega"] = str(fecha_entrega)

        # Calculo optimista para el UI message
        ancho_bobina = 0.0
        if ancho and fuelle:
            ancho_bobina = (ancho + fuelle) * 2 + 25

        if es_ed:
            resultado = actualizar_orden(of_existente["id"], payload)
            if resultado and resultado.get("ok"):
                st.cache_data.clear()  # Limpiar cache para forzar recarga
                st.session_state["of_resultado"] = {
                    "ok": True,
                    "msg": f"✓ OF actualizada correctamente"
                }
                st.session_state.pop("of_editar_id", None)
                st.session_state.of_para_editar = None
                st.rerun()
            else:
                error = resultado.get("error", "Error desconocido") if resultado else "Sin respuesta"
                st.error(f"❌ Error al actualizar: {error}")
        else:
            st.write("Payload enviado:", payload)
            res = crear_orden(payload)
            if res and res.get("ok"):
                st.cache_data.clear()  # Limpiar cache para forzar recarga
                codigo_generado = res["data"].get("codigo_of", "")
                st.session_state["of_resultado"] = {
                    "ok": True,
                    "msg": f"✓ OF **{codigo_generado}** creada correctamente | Ancho bobina: {ancho_bobina} mm"
                }
            else:
                error_msg = res.get("error", "Error desconocido") if res else "Sin respuesta del servidor"
                st.session_state["of_resultado"] = {
                    "ok": False,
                    "msg": f"❌ Error: {error_msg}"
                }
            st.rerun()

with tab_nueva:
    if can("crear_of"):
        st.subheader("Crear una Nueva Orden de Fabricación")
        _formulario_of()
    else:
        st.info("No tienes permisos para crear órdenes.")

with tab_editar:
    if st.session_state.of_para_editar:
        st.info("Editando Orden de Fabricación seleccionada.")
        if can("editar_of"):
            if st.button("❌ Cancelar Edición"):
                st.session_state.of_para_editar = None
                st.rerun()
            _formulario_of(st.session_state.of_para_editar)
        else:
            st.error("No tienes permisos para editar órdenes.")
    else:
        st.info("ℹ️ Para editar una Orden de Fabricación, selecciónala en la pestaña '📋 Lista de OFs'.")
