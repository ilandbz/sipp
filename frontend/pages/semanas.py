import streamlit as st
import datetime
import pandas as pd
from utils.api_client import (
    get_maquinas, get_semanas, crear_semana, actualizar_estado_semana, get_semana_detalle,
    get_ofs_disponibles, agregar_of_a_semana, registrar_parada, reordenar_semana
)
from auth import require_login, can, render_sidebar

require_login()

st.set_page_config(layout="wide", page_icon="🏭")
render_sidebar()
st.title("📅 Semanas de Programación")

# Cargar catálogos y validar disponibilidad del backend
maquinas = get_maquinas()
semanas = get_semanas()

if maquinas is None or semanas is None:
    st.error("⚠ Backend no disponible. Verifique que FastAPI esté corriendo en localhost:8000")
    st.stop()

# Dividir la pantalla en 2 columnas para creación y listado
col_crear, col_lista = st.columns([1, 2])

with col_crear:
    st.subheader("➕ Nueva Semana")
    if can("optimizar"):
        if "semana_creada_msg" in st.session_state:
            st.success(st.session_state.pop("semana_creada_msg"))
        
        # Semana global activada por defecto
        es_global = st.checkbox(
            "🌐 Semana Global (todas las máquinas)",
            value=True,  # MARCADO POR DEFECTO
            help="Recomendado: una semana para M8, M10 y M14 juntas. "
                 "El optimizador asigna cada OF a la mejor máquina."
        )

        if es_global:
            st.info("✓ Se creará una semana para M8, M10 y M14. "
                    "Horas disponibles: 5 días × 8h × 3 máquinas = 120h")
            maquina_id = None
        else:
            # Solo mostrar selector de máquina si NO es global
            st.warning("Modo específico: solo una máquina en esta semana.")
            maq_opciones = {m["codigo"]: m["id"] for m in maquinas 
                           if m["codigo"] in ["M8","M10","M14"]}
            maq_sel = st.selectbox("Máquina", list(maq_opciones.keys()))
            maquina_id = maq_opciones.get(maq_sel)

        c1, c2 = st.columns(2)
        from datetime import date, timedelta
        hoy = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())
        viernes = lunes + timedelta(days=4)

        fecha_inicio = c1.date_input("Fecha de inicio *", value=lunes)
        fecha_fin    = c2.date_input("Fecha de fin *",    value=viernes)

        if st.button("📅 Crear Semana", type="primary", 
                     use_container_width=True):
            if fecha_fin <= fecha_inicio:
                st.error("La fecha de fin debe ser posterior al inicio")
            else:
                payload = {
                    "es_global":    es_global,
                    "maquina_id":   maquina_id,
                    "fecha_inicio": str(fecha_inicio),
                    "fecha_fin":    str(fecha_fin),
                }
                resultado = crear_semana(payload)
                if resultado:
                    dias = sum(1 for i in range((fecha_fin-fecha_inicio).days+1)
                              if (fecha_inicio+timedelta(days=i)).weekday()<5)
                    horas = dias * 8 * (3 if es_global else 1)
                    st.cache_data.clear()
                    st.session_state["semana_creada_msg"] = f"✓ Semana {'global' if es_global else maq_sel} creada — {dias} días hábiles = {horas}h disponibles"
                    st.rerun()
                else:
                    st.error("Error al crear la semana")
    else:
        st.info("No tienes permisos para crear nuevas semanas.")

with col_lista:
    col_titulo, col_refresh = st.columns([10, 1])
    with col_titulo:
        st.subheader("Lista de Semanas Registradas")
    with col_refresh:
        if st.button("🔄", help="Actualizar lista", key="refresh_semanas"):
            st.cache_data.clear()
            st.rerun()
    
    if not semanas:
        st.info("No hay semanas de programación registradas.")
    else:
        c1, c2, c3, c4, c5, c6 = st.columns([1, 2, 2, 2, 2, 3])
        c1.write("**ID**")
        c2.write("**Máquina**")
        c3.write("**Inicio**")
        c4.write("**Fin**")
        c5.write("**Horas Disp.**")
        c6.write("**Estado / Acciones**")
        st.divider()

        def badge_estado(est: str) -> str:
            colores = {
                "BORRADOR": "🔘 BORRADOR",
                "CONFIRMADA": "🟢 CONFIRMADA",
                "EN_EJECUCION": "🔵 EN EJECUCIÓN",
                "CERRADA": "⚫ CERRADA"
            }
            return colores.get(est, est)

        for semana in semanas:
            col1, col2, col3, col4, col5, col6 = st.columns([1, 2, 2, 2, 2, 3])
            col1.write(semana["id"])
            maq_cod = "🌐 Global" if semana.get("es_global") else (semana["maquina_codigo"] or f"ID: {semana.get('maquina_id', '')}")
            col2.write(maq_cod)
            col3.write(datetime.datetime.strptime(semana["fecha_inicio"], "%Y-%m-%d").strftime("%d/%m/%Y") if semana.get("fecha_inicio") else "")
            col4.write(datetime.datetime.strptime(semana["fecha_fin"], "%Y-%m-%d").strftime("%d/%m/%Y") if semana.get("fecha_fin") else "")
            col5.write(f"{semana['horas_disponibles'] or 0:.1f} h")
            
            with col6:
                estado_str = semana["estado"]
                badge = badge_estado(estado_str)
                if estado_str == "BORRADOR":
                    c_badge, c_btn = st.columns([2, 1])
                    c_badge.write(badge)
                    if c_btn.button("🗑️", key=f"del_semana_{semana['id']}", help="Eliminar semana (solo BORRADOR)"):
                        st.session_state[f"confirmar_del_{semana['id']}"] = True
                else:
                    st.write(badge)
            
            if st.session_state.get(f"confirmar_del_{semana['id']}"):
                st.warning(f"¿Eliminar semana {maq_cod} ({semana['fecha_inicio']} - {semana['fecha_fin']})? Las OFs asignadas volverán a estado PENDIENTE.")
                col_si, col_no = st.columns(2)
                with col_si:
                    if st.button("✅ Sí, eliminar", key=f"confirm_si_{semana['id']}", type="primary"):
                        from utils.api_client import eliminar_semana
                        resultado = eliminar_semana(semana['id'])
                        if resultado and resultado.get("ok"):
                            st.success("✓ Semana eliminada. Las OFs volvieron a estado PENDIENTE.")
                            st.session_state.pop(f"confirmar_del_{semana['id']}", None)
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            error = resultado.get("error", "Error") if resultado else "Sin respuesta"
                            st.error(f"❌ {error}")
                with col_no:
                    if st.button("❌ Cancelar", key=f"confirm_no_{semana['id']}"):
                        st.session_state.pop(f"confirmar_del_{semana['id']}", None)
                        st.rerun()
        # Selector para ver detalles y cambiar estados
        st.write("---")
        st.subheader("Acciones de Semana")
        def format_semana_selector(x):
            if x is None: return "-- Seleccionar --"
            s = next((sem for sem in semanas if sem["id"] == x), {})
            maq = "🌐 Global" if s.get("es_global") else s.get("maquina_codigo", "")
            try:
                fi = datetime.datetime.strptime(s.get("fecha_inicio", "")[:10], "%Y-%m-%d").strftime("%d/%m")
                ff = datetime.datetime.strptime(s.get("fecha_fin", "")[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                fi, ff = s.get("fecha_inicio", ""), s.get("fecha_fin", "")
            estado = s.get("estado", "")
            return f"{maq} — {fi} al {ff} ({estado})"

        selected_semana_id = st.selectbox(
            "Selecciona una semana para ver su cola de producción o cambiar su estado:",
            options=[None] + [s["id"] for s in semanas],
            format_func=format_semana_selector
        )
        
        if selected_semana_id is not None:
            # Buscar la semana seleccionada
            semana_sel = next(s for s in semanas if s["id"] == selected_semana_id)
            
            # Cambiar estado
            if can("optimizar"):
                col_est1, col_est2 = st.columns(2)
                nuevo_estado = col_est1.selectbox(
                    "Cambiar estado de la semana a:",
                    options=["BORRADOR", "CONFIRMADA", "EN_EJECUCION", "CERRADA"],
                    index=["BORRADOR", "CONFIRMADA", "EN_EJECUCION", "CERRADA"].index(semana_sel["estado"])
                )
                
                if col_est2.button("💾 Actualizar Estado", type="secondary", use_container_width=True):
                    res_est = actualizar_estado_semana(selected_semana_id, nuevo_estado)
                    if res_est:
                        st.success(f"Estado actualizado a {nuevo_estado} ✓")
                        st.cache_data.clear()
                        st.rerun()
            else:
                st.info(f"Estado actual de la semana: **{semana_sel['estado']}** (Solo lectura)")
            
            # Detalle de la semana y sus secuencias
            st.write("---")
            st.subheader(f"📋 Cola de Producción para Semana ID: {selected_semana_id}")
            
            detalles = get_semana_detalle(selected_semana_id)
            if not detalles or "secuencias" not in detalles or not detalles["secuencias"]:
                st.info("Esta semana no tiene secuencias de producción asignadas aún. Ejecuta el optimizador para programar OFs.")
            else:
                df_seq = pd.DataFrame(detalles["secuencias"])
                
                # Formatear estados en las secuencias
                def badge_seq(est: str) -> str:
                    colores = {
                        "PENDIENTE": "🔘 PENDIENTE",
                        "EN_PROCESO": "🔵 EN PROCESO",
                        "COMPLETADA": "🟢 COMPLETADA",
                        "OMITIDA": "⚫ OMITIDA",
                    }
                    return colores.get(est, est)
                df_seq["Estado Secuencia"] = df_seq["estado"].apply(badge_seq)
                
                st.dataframe(
                    df_seq[["posicion", "codigo_of", "medida_texto", "material", "costo_setup_min", "motivo_setup", "Estado Secuencia"]],
                    column_config={
                        "posicion": st.column_config.NumberColumn("#", width="small"),
                        "codigo_of": st.column_config.TextColumn("Código OF"),
                        "medida_texto": st.column_config.TextColumn("Medida"),
                        "material": st.column_config.TextColumn("Material"),
                        "costo_setup_min": st.column_config.NumberColumn("Setup (min)", format="%.0f"),
                        "motivo_setup": st.column_config.TextColumn("Detalle de Setup"),
                        "Estado Secuencia": st.column_config.TextColumn("Estado"),
                    },
                    hide_index=True,
                    width='stretch'
                )
                
                # Reordenamiento Manual
                st.write("---")
                st.subheader("⬆⬇ Reordenar Secuencias (Manual)")
                if can("optimizar"):
                    with st.expander("Modificar orden de la cola"):
                        ofs_actuales = [seq["codigo_of"] for seq in detalles["secuencias"]]
                        seq_map = {seq["codigo_of"]: seq["orden_fabricacion_id"] for seq in detalles["secuencias"]}
                        
                        st.write("Selecciona una orden y usa las flechas para moverla, luego guarda.")
                        
                        if "orden_temporal" not in st.session_state:
                            st.session_state["orden_temporal"] = ofs_actuales.copy()
                            
                        of_sel_mover = st.selectbox("Seleccionar OF a mover:", options=st.session_state["orden_temporal"])
                        
                        c_arriba, c_abajo, c_guardar = st.columns(3)
                        
                        if c_arriba.button("⬆ Subir", use_container_width=True):
                            idx = st.session_state["orden_temporal"].index(of_sel_mover)
                            if idx > 0:
                                st.session_state["orden_temporal"].insert(idx - 1, st.session_state["orden_temporal"].pop(idx))
                                st.rerun()
                                
                        if c_abajo.button("⬇ Bajar", use_container_width=True):
                            idx = st.session_state["orden_temporal"].index(of_sel_mover)
                            if idx < len(st.session_state["orden_temporal"]) - 1:
                                st.session_state["orden_temporal"].insert(idx + 1, st.session_state["orden_temporal"].pop(idx))
                                st.rerun()
                                
                        st.write("Orden actual (Borrador):")
                        st.text(" -> ".join(st.session_state["orden_temporal"]))
                        
                        if c_guardar.button("💾 Guardar Nuevo Orden", type="primary", use_container_width=True):
                            nuevos_ids = [seq_map[codigo] for codigo in st.session_state["orden_temporal"]]
                            res = reordenar_semana(selected_semana_id, nuevos_ids)
                            if res:
                                st.success("Orden actualizado y setups recalculados.")
                                del st.session_state["orden_temporal"]
                                st.cache_data.clear()
                                st.rerun()
                else:
                    st.info("🔒 No tienes permisos para reordenar secuencias.")
 
            # Paradas / Imprevistos
            if can("registrar_parada"):
                st.write("---")
                st.subheader("⚡ Registrar Parada / Imprevisto")
                with st.expander("Formulario de Paradas", expanded=False):
                    with st.form("form_parada"):
                        c1, c2 = st.columns(2)
                        inicio_p = c1.date_input("Día de inicio", value=datetime.date.today(), key="p_di")
                        inicio_t = c2.time_input("Hora de inicio", value=datetime.datetime.now().time(), key="p_ti")
                        
                        fin_p = c1.date_input("Día de fin", value=datetime.date.today(), key="p_df")
                        fin_t = c2.time_input("Hora de fin", value=datetime.datetime.now().time(), key="p_tf")
                        
                        tipo_p = st.selectbox("Tipo de Parada", ["AVERIA", "MANTENIMIENTO", "PERSONAL", "MATERIAL", "OTRO"])
                        desc_p = st.text_area("Descripción / Motivo")
                        
                        if st.form_submit_button("Registrar y Desplazar Tiempos", type="primary"):
                            inicio_dt = datetime.datetime.combine(inicio_p, inicio_t)
                            fin_dt = datetime.datetime.combine(fin_p, fin_t)
                            if fin_dt <= inicio_dt:
                                st.error("La fecha/hora de fin debe ser posterior a la de inicio.")
                            else:
                                payload_parada = {
                                    "maquina_id": semana_sel["maquina_id"],
                                    "inicio": inicio_dt.isoformat(),
                                    "fin": fin_dt.isoformat(),
                                    "tipo": tipo_p,
                                    "descripcion": desc_p,
                                    "registrado_por": st.session_state.get("nombre", "Operador")
                                }
                                res_par = registrar_parada(payload_parada)
                                if res_par:
                                    st.success(f"Parada registrada. {res_par.get('secuencias_afectadas', 0)} secuencias reprogramadas.")
                                    st.cache_data.clear()
                                    st.rerun()
            
            # Listado de OFs disponibles para agregar
            if can("optimizar"):
                st.write("---")
                st.subheader("➕ Agregar Órdenes de Fabricación Disponibles")
                
                st.info("""
                📋 **Flujo del sistema:**
                1. Registra tus Órdenes de Fabricación en **Órdenes** 
                2. Agrégalas aquí a la semana correspondiente
                3. Ejecuta el optimizador desde el **Dashboard**
                4. Revisa el plan en **Reportes**
                """)
                
                if st.button("➕ Crear nueva OF", use_container_width=True):
                    st.switch_page("pages/ordenes.py")
                
                ofs_disp = get_ofs_disponibles(selected_semana_id)
                if not ofs_disp:
                    st.info("No hay órdenes de fabricación pendientes para esta máquina.")
                else:
                    buscar = st.text_input("🔍 Buscar OF por código o descripción")
                    if buscar:
                        ofs_disp = [o for o in ofs_disp 
                                          if buscar.upper() in o['codigo_of'].upper() 
                                          or buscar.upper() in (o['descripcion'] or '').upper()]
                                          
                    if not ofs_disp:
                        st.info("No se encontraron resultados para la búsqueda.")
                    else:
                        # Encabezados
                        c_h1, c_h2, c_h3, c_h4, c_h5, c_h6, c_h7 = st.columns([1.5, 2.5, 2, 1.5, 1.5, 2, 1.5])
                        c_h1.write("**OF**")
                        c_h2.write("**Descripción**")
                        c_h3.write("**Medida**")
                        c_h4.write("**Material**")
                        c_h5.write("**F. Entrega**")
                        c_h6.write("**Máquina**")
                        c_h7.write("")
                        st.divider()

                        for of in ofs_disp:
                            col_of, col_desc, col_medida, col_material, col_entrega, col_maq, col_btn = st.columns([1.5, 2.5, 2, 1.5, 1.5, 2, 1.5])
                            col_of.write(f"**{of['codigo_of']}**")
                            col_desc.write(of['descripcion'] or "-")
                            col_medida.write(of['medida_texto'] or "-")
                            col_material.write(of.get('material_nombre') or "-")
                            col_entrega.write(of['fecha_entrega'] or "-")
                            
                            if of.get('maquina_asignada_id'):
                                maq_cod = of.get('maquina_codigo') or f"M{of.get('maquina_asignada_id')}"
                                col_maq.markdown(f":green[{maq_cod} ✓]")
                            else:
                                col_maq.caption("🤖 Se asignará automáticamente")
                            
                            btn_key = f"add_of_{selected_semana_id}_{of['id']}"
                            if col_btn.button("➕ Agregar", key=btn_key, use_container_width=True):
                                res_add = agregar_of_a_semana(selected_semana_id, of["id"])
                                if res_add:
                                    st.success(f"OF {of['codigo_of']} agregada ✓")
                                    st.cache_data.clear()
                                    st.rerun()
            else:
                st.write("---")
                st.info("🔒 No tienes permisos para agregar órdenes a esta semana.")
            
            # Botón para ir al dashboard principal
            st.write("---")
            st.page_link("app.py", label="▶ Ir al Dashboard para Optimizar", icon="⚙️")
