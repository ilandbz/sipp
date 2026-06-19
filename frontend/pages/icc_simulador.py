import streamlit as st
import streamlit.components.v1 as components
from auth import require_login
from utils.api_client import get_ordenes, get_semana_activa, get_cola_semana

require_login()
st.set_page_config(page_title="Simulador ICC | SIPP", layout="wide")
st.title("🔬 Simulador de Compatibilidad (ICC)")
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
