import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from auth import require_login
from utils.api_client import get_ordenes, get_semana_activa, get_cola_semana

require_login()
st.set_page_config(page_title="Simulador ICC | SIPP", layout="wide")
st.title("🔬 Simulador de Compatibilidad (ICC)")

st.markdown("## 📚 Teoría de Setup — VYGPACK")

# Tabla de variables
st.markdown("### Variables de cambio")
df_teoria = pd.DataFrame({
    "Variable de cambio": [
        "Cambio de material / bobina",
        "Cambio de medida (solo altura)",
        "Cambio de medida (ancho o fuelle)",
        "Cambio de color / lavado",
        "Cambio de clisé",
        "Pruebas y reajustes"
    ],
    "Tiempo base": [
        "0.30 h (18 min)",
        "1 h (60 min)",
        "6–8 h (360–480 min)",
        "0.50 h (30 min)",
        "2 h × N° colores",
        "2 h fijos (si hay setup)"
    ],
    "¿Cuándo aplica?": [
        "Cambia tipo de papel, bobina o ancho de bobina",
        "Solo cambia el alto de la bolsa",
        "Cambia ancho o fuelle — cambio completo de formato",
        "Cambia color de tinta, diseño, logo o número de colores",
        "Cambia diseño o número de colores del clisé",
        "Aplica cuando existe cualquier setup"
    ]
})
st.dataframe(df_teoria, use_container_width=True, hide_index=True)

# Fórmula
st.markdown("### Fórmula del Índice de Complejidad")
st.info(
    "**IC = T_material + T_formato + T_color + T_clisé + T_pruebas**\n\n"
    "- Si no cambia material → T_material = 0\n"
    "- Si cambia material/bobina → T_material = 18 min\n"
    "- Si cambia solo altura → T_formato = 60 min\n"
    "- Si cambia ancho o fuelle → T_formato = 480 min\n"
    "- Si cambia color → T_color = 30 min\n"
    "- Si cambia clisé → T_clisé = 120 × N° colores\n"
    "- Si hay setup → T_pruebas = 120 min (siempre)"
)

# Tabla de clasificación
st.markdown("### Clasificación del Índice")
df_clasif = pd.DataFrame({
    "Índice de complejidad": [
        "0 – 90 min",
        "> 90 – 300 min",
        "> 300 – 480 min",
        "> 480 min"
    ],
    "Clasificación": ["Bajo", "Medio", "Alto", "Crítico"],
    "ICC resultante": ["100 – 81", "80 – 38", "37 – 1", "0"],
    "Interpretación": [
        "Cambio menor: solo altura o bobina",
        "Cambio de impresión simple o color",
        "Cambio de medida / formato",
        "Cambio de formato + impresión / clisé / color"
    ]
})

def color_clasif(val):
    colores = {
        "Bajo": "background-color: #1b5e20; color: white",
        "Medio": "background-color: #f9a825; color: black",
        "Alto": "background-color: #e65100; color: white",
        "Crítico": "background-color: #b71c1c; color: white"
    }
    return colores.get(val, "")

styled = df_clasif.style.map(color_clasif, subset=["Clasificación"])
st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()
st.markdown("## 🔬 Simulador interactivo")
st.caption("""
    Selecciona dos órdenes para ver cuánto tiempo de setup habría entre ellas
    y qué tan compatibles son según las reglas SMED de VYGPACK.
""")

# Cargar OFs disponibles
semana = get_semana_activa()
if semana:
    cola = get_cola_semana(semana["id"]) or []
    ofs_disponibles = {
        f"{item['codigo_of']} — {item.get('medida_texto','')} {item.get('material','')}": item
        for item in cola
    }
else:
    ofs_disponibles = {}

if not ofs_disponibles:
    st.warning("No hay OFs en la semana activa. Agrega OFs a la semana primero.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    st.subheader("OF Anterior")
    sel_a = st.selectbox("Selecciona la OF que termina", 
                         list(ofs_disponibles.keys()),
                         key="of_a")
with col2:
    st.subheader("OF Siguiente")
    sel_b = st.selectbox("Selecciona la OF que empieza",
                         list(ofs_disponibles.keys()),
                         index=1 if len(ofs_disponibles) > 1 else 0,
                         key="of_b")

of_a = ofs_disponibles.get(sel_a, {})
of_b = ofs_disponibles.get(sel_b, {})

# Calcular cambios
PENALIZACIONES = {
    "formato": 480,
    "jugada_corta": 105,
    "color": 45,
    "cilindro": 30,
    "clise": 17.5,
    "material": 25,
}

CONTIG = [(5,6),(6,8),(8,10),(10,12)]

def es_contiguo(a, b):
    return any((a==x and b==y) or (a==y and b==x) for x,y in CONTIG)

ancho_a = float(of_a.get("ancho_mm") or 0)
ancho_b = float(of_b.get("ancho_mm") or 0)
num_a = int(of_a.get("tipo_bolsa_num") or 0)
num_b = int(of_b.get("tipo_bolsa_num") or 0)
mat_a = str(of_a.get("material") or "")
mat_b = str(of_b.get("material") or "")
col_a = str(of_a.get("colores_detalle") or "").split(",")[0].strip().upper()
col_b = str(of_b.get("colores_detalle") or "").split(",")[0].strip().upper()
cil_a = of_a.get("cilindro_id")
cil_b = of_b.get("cilindro_id")

mismo_formato = ancho_a == ancho_b and ancho_a > 0
contiguo = not mismo_formato and es_contiguo(num_a, num_b)
formato_distinto = not mismo_formato and not contiguo

cambios = {
    "Cambio de formato completo": (formato_distinto, 480, "🔴"),
    "Jugada corta (tamaño contiguo)": (contiguo, 105, "🟠"),
    "Cambio de color": (col_a != col_b and col_a and col_b, 45, "🟡"),
    "Cambio de cilindro": (cil_a != cil_b and cil_a and cil_b, 30, "🟡"),
    "Cambio de material": (mat_a != mat_b and mat_a and mat_b, 25, "🟡"),
}

total_setup = sum(min for nombre, (aplica, min, _) in cambios.items() if aplica)
icc = max(0, round(100 - (total_setup / 480) * 100))

# Mostrar resultado
st.divider()
col_r1, col_r2, col_r3 = st.columns(3)
with col_r1:
    color_setup = "🔴" if total_setup >= 480 else "🟠" if total_setup >= 105 else "🟡" if total_setup > 0 else "🟢"
    st.metric("Setup total", f"{total_setup} min", f"{total_setup/60:.1f} horas")
with col_r2:
    st.metric("ICC", f"{icc} / 100")
with col_r3:
    if icc >= 80:
        st.success("Compatible — poco tiempo perdido")
    elif icc >= 50:
        st.warning("Moderado — jugada corta o material")
    elif icc >= 20:
        st.warning("Costoso — cambio de altura")
    else:
        st.error("Incompatible — cambio de formato completo (8 horas)")

# Detalle de cambios
st.subheader("Detalle de cambios detectados")
for nombre, (aplica, minutos, icono) in cambios.items():
    col_check, col_nombre, col_min = st.columns([1, 6, 2])
    with col_check:
        st.write("✅" if aplica else "⬜")
    with col_nombre:
        st.write(nombre)
    with col_min:
        if aplica:
            st.write(f"**+{minutos} min**")
        else:
            st.write("—")

# Mostrar datos de las OFs
st.divider()
st.subheader("Comparación de OFs")
col_d1, col_d2 = st.columns(2)
campos = ["codigo_of", "medida_texto", "material", "colores_detalle", "cilindro_id"]
labels = ["Código OF", "Medida", "Material", "Colores", "Cilindro"]
with col_d1:
    st.markdown(f"**{sel_a.split('—')[0].strip()}**")
    for campo, label in zip(campos, labels):
        val = of_a.get(campo, "—") or "—"
        mismo = of_a.get(campo) == of_b.get(campo)
        color = "" if mismo else "color:orange"
        st.markdown(f"<span style='font-size:13px;color:var(--color-text-secondary)'>{label}:</span> "
                   f"<span style='{color}'>{val}</span>", unsafe_allow_html=True)
with col_d2:
    st.markdown(f"**{sel_b.split('—')[0].strip()}**")
    for campo, label in zip(campos, labels):
        val = of_b.get(campo, "—") or "—"
        mismo = of_a.get(campo) == of_b.get(campo)
        color = "" if mismo else "color:orange"
        st.markdown(f"<span style='font-size:13px;color:var(--color-text-secondary)'>{label}:</span> "
                   f"<span style='{color}'>{val}</span>", unsafe_allow_html=True)

st.info("💡 Los valores en naranja indican diferencias entre las dos OFs que generan tiempo de setup.")
