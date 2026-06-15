# CLAUDE.md — Contexto Global del Proyecto `vygpack-sipp`

> **Leer este archivo completo antes de generar cualquier código.**
> Aplica a todo el ecosistema: backend, frontend, base de datos y servicios.

---

## 1. Identidad del Proyecto

| Campo | Valor |
|---|---|
| **Nombre** | SIPP — Sistema Inteligente de Programación de Producción |
| **Empresa** | VYGPACK |
| **Repositorio** | `vygpack-sipp` |
| **Desarrollador** | Cristian Figueroa — Senior Systems Architect / Software Developer |
| **Objetivo** | Secuenciar y optimizar órdenes de fabricación en las máquinas M8, M10 y M14 (y Flexo 1, Flexo 2) minimizando tiempos de setup mediante reglas SMED |

---

## 2. Stack Técnico Definitivo

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **ORM:** SQLModel + SQLAlchemy Async (`asyncpg` como driver)
- **Base de datos:** PostgreSQL 16 (schema `sipp`)
- **Validación:** Pydantic v2 (schemas separados de los modelos ORM)
- **Procesamiento CSV:** Pandas + NumPy
- **Servidor ASGI:** Uvicorn

### Frontend / HMI de Planta
- **Framework:** Streamlit (Python puro)
- **Comunicación:** Solo HTTP/JSON contra el backend FastAPI — NUNCA importa módulos del backend directamente
- **Cliente HTTP:** `httpx` o `requests`

### Infraestructura
- **Dev local:** PostgreSQL 16 nativo en Windows (`localhost:5432`)
- **Producción:** VPS Ubuntu (PostgreSQL instalado nativamente)
- **Variables de entorno:** `.env` con `python-dotenv`

---

## 3. Estructura de Carpetas (Definitiva)

```
vygpack-sipp/
├── CLAUDE.md                            ← este archivo
├── .env                                 ← variables de entorno (nunca al repo)
├── .env.example                         ← plantilla pública
├── .gitignore
├── bd.sql                               ← schema PostgreSQL completo (sipp)
│
├── backend/
│   ├── requirements.txt
│   ├── alembic/                         ← migraciones de BD
│   │   └── versions/
│   └── app/
│       ├── main.py                      ← punto de entrada FastAPI
│       ├── core/
│       │   ├── config.py                ← Settings (pydantic-settings)
│       │   └── database.py              ← engine async, get_session()
│       ├── models/                      ← tablas SQLModel (ORM)
│       │   ├── __init__.py
│       │   ├── maquina.py
│       │   ├── cliente.py
│       │   ├── material.py
│       │   ├── cilindro.py
│       │   ├── clise.py
│       │   ├── orden_fabricacion.py
│       │   ├── semana_programacion.py
│       │   ├── secuencia_produccion.py
│       │   ├── setup_penalizacion.py
│       │   ├── icc_cache.py
│       │   ├── setup_historial.py       ← BD_SetupsHistorial
│       │   ├── disponibilidad_maquina.py
│       │   └── log_optimizacion.py
│       ├── schemas/                     ← Pydantic v2 (request/response)
│       │   ├── orden.py
│       │   ├── secuencia.py
│       │   ├── kpi.py
│       │   └── optimizacion.py
│       ├── api/
│       │   └── routers/
│       │       ├── ordenes.py           ← CRUD de órdenes de fabricación
│       │       ├── maquinas.py          ← máquinas y disponibilidad
│       │       ├── secuencias.py        ← cola de producción por semana
│       │       ├── optimizador.py       ← trigger manual del algoritmo
│       │       └── kpi.py              ← métricas para el dashboard
│       └── services/
│           ├── importer.py              ← parser Pandas del CSV mensual
│           ├── optimizer.py             ← algoritmo heurístico SMED
│           └── icc.py                  ← cálculo Índice de Compatibilidad
│
└── frontend/
    ├── requirements.txt
    ├── app.py                           ← dashboard principal Streamlit
    └── utils/
        ├── __init__.py
        └── api_client.py               ← funciones requests/httpx → FastAPI
```

---

## 4. Base de Datos — Schema `sipp` (archivo `bd.sql`)

### Tablas principales

| Tabla | Equivalente diagrama | Rol |
|---|---|---|
| `sipp.maquinas` | BD_Maquinas | Catálogo de máquinas (M8, M10, M14, Flexo1, Flexo2) |
| `sipp.clientes` | BD_FichasMaestras | Razón social, marca, vendedor, prioridad |
| `sipp.materiales` | BD_FichasMaestras | Tipos de papel + factor de velocidad BPM |
| `sipp.cilindros` | BD_FichasMaestras | Cilindros de impresión |
| `sipp.clises` | BD_FichasMaestras | Clisés disponibles |
| `sipp.setup_penalizaciones` | BD_FichasMaestras | Las 6 penalizaciones SMED en tabla (no hardcodeadas) |
| `sipp.ordenes_fabricacion` | BD_OrdenesProduccion | Tabla central — importada desde CSV |
| `sipp.semanas_programacion` | BD_ProgramacionSemanal | Agrupa secuencias por semana y máquina |
| `sipp.secuencias_produccion` | BD_ProgramacionSemanal | Resultado del optimizador (posición en cola) |
| `sipp.icc_cache` | BD_OrdenesProduccion | Cache del ICC entre pares de OFs |
| `sipp.setups_historial` | BD_SetupsHistorial | Setup real registrado en planta vs estimado |
| `sipp.disponibilidad_maquinas` | BD_Maquinas | Mantenimientos, feriados, paros |
| `sipp.log_optimizaciones` | — | Trazabilidad de cada corrida del algoritmo |

### Vistas disponibles
- `sipp.v_cola_produccion` — cola por máquina con todos los datos para el HMI
- `sipp.v_kpi_semanal` — KPIs agregados por semana y máquina

### Reglas de BD
- Siempre usar `TIMESTAMPTZ` (nunca `TIMESTAMP`).
- PKs siempre `SERIAL` o `BIGSERIAL`. UUIDs solo si el cliente lo requiere explícitamente.
- Trigger `sipp.set_updated_at()` aplicado a todas las tablas con `updated_at`.
- Columnas calculadas con `GENERATED ALWAYS AS ... STORED` cuando sea posible.
- `JSONB` para campos semiestructurados (`detalle_json`, `resultado_json`).

---

## 5. Reglas de Negocio SMED — Penalizaciones de Setup

El optimizador calcula el costo de cambio entre dos OFs consecutivas consultando `sipp.setup_penalizaciones`. **Nunca hardcodear los minutos en código Python.**

| `tipo_cambio` | Minutos | Descripción |
|---|---|---|
| `MISMO_FORMATO_MISMO_COLOR` | 0 | Secuencia ideal — agrupar estas OFs siempre |
| `CAMBIO_COLOR_LAVADO_ESTACION` | 45 | Lavado de esmeriles |
| `CAMBIO_CLISE` | 17.5 | Sacar + montar clisé (promedio 15–20 min) |
| `CAMBIO_CILINDRO_IMPRESION` | 30 | Cambio de cilindro |
| `CAMBIO_MATERIAL` | 25 | Cambio de tipo/gramaje de papel (promedio 20–30 min) |
| `CAMBIO_FORMATO_MEDIDA_COMPLETA` | 480 | Cambio de formato completo — máxima penalización (8 h) |

**Las penalizaciones son acumulables.** Un cambio puede implicar simultáneamente cambio de formato (480) + cambio de color (45) + cambio de clisé (17.5) = 542.5 min total.

### Velocidad BPM por material
- Papel Kraft: `factor_velocidad = 1.0` (velocidad máxima estable)
- Papeles delgados (Antigrasa, etc.): `factor_velocidad < 1.0` (reducción automática para evitar roturas)
- `sipp.materiales.factor_velocidad` multiplica sobre `sipp.maquinas.velocidad_bpm_max`
- Tiempo producción = `(cantidad_MT * 1000) / (velocidad_bpm_max * factor_velocidad * 60)`

---

## 6. Variables del Sistema (inputs del optimizador)

Tomadas del documento de diseño (Tabla 9):

| Variable | Fuente | Uso en el optimizador |
|---|---|---|
| Fecha de atención / entrega | OF | Prioridad de programación |
| Tipo de bolsa / medida | OF | Detectar cambio de formato (+480 min) |
| Leva requerida | OF | Nivel de modificación mecánica |
| Distancia de base | OF | Ajuste de formato |
| Fuelle | OF | Ajuste dimensional |
| Número de colores | OF | Complejidad del cambio de impresión |
| Cilindro de impresión | OF | Cambio de cilindro (+30 min) |
| Tipo de papel y gramaje | OF | Velocidad BPM + cambio de material (+25 min) |
| Disponibilidad de máquina | `sipp.disponibilidad_maquinas` | Restricción de asignación |
| Carga semanal | `sipp.semanas_programacion` | Balanceo entre M8, M10, M14 |

---

## 7. Flujo de Registro de Órdenes de Fabricación

### Flujo operacional (día a día)
Las OFs se registran **manualmente mediante formulario en Streamlit** (`frontend/pages/ordenes.py`).
NO existe importación CSV como flujo operacional — cada orden se ingresa campo a campo.

### Seed inicial (una sola vez)
El archivo `PROGRAMACIÓN_ABRIL.csv` se usa ÚNICAMENTE para:
1. Poblar las tablas maestras iniciales (máquinas, materiales, clientes, cilindros)
2. Cargar las primeras OFs de referencia para entender el modelo de datos

Se ejecuta con el script `backend/app/management/seed_inicial.py`:
```bash
cd backend
python -m app.management.seed_inicial --archivo="../data/PROGRAMACIÓN_ABRIL.csv"
```
**No es un endpoint de la API.** No crear router para esto.

### Reglas obligatorias
- `pd.read_csv(..., encoding='utf-8-sig', sep=';')` — el CSV usa BOM UTF-8 y separador `;`
- La fila 0 del CSV es el header real: `df.columns = df.iloc[0]; df = df[1:]`
- Limpiar siempre con `df.columns = df.columns.str.strip()` — hay headers con espacios
- Reemplazar `#N/D` y `#¡VALOR!` por `None`: `df.replace(['#N/D', '#¡VALOR!'], None, inplace=True)`
- Descomponer `Medida` con regex: `"18X32X10.5"` → `ancho=18, alto=32, fuelle=10.5`
- Lookup de FKs contra tablas maestras antes de insertar (`material_id`, `cilindro_id`, `cliente_id`)
- Usar `INSERT ... ON CONFLICT (codigo_of) DO UPDATE` — nunca duplicar OFs
- Registrar nombre del archivo en `ordenes_fabricacion.fuente_archivo`

### Columnas clave CSV → campo en BD

| CSV | Campo BD | Nota |
|---|---|---|
| `MAQ` | `maquina_asignada_id` | lookup por código |
| `Orden de Fabricación` | `codigo_of` | `.strip()` obligatorio |
| `Código PT` | `codigo_pt` | |
| `Descricpción` | `descripcion` | errata en el CSV — así está escrito |
| `MATERIAL` | `material_id` | lookup |
| `GRAMAJE` | `gramaje` | |
| `ANCHO` | `ancho_mm` | |
| `ALTO` | `alto_mm` | |
| `CILINDRO` | `cilindro_id` | lookup por código numérico |
| `COLORES` | `colores_detalle` | texto libre |
| `Inicio Prod ` | `inicio_prod` | tiene espacio al final — usar `.strip()` |
| `FECHA DE ENTREGA` | `fecha_entrega` | parsear con `pd.to_datetime(..., errors='coerce')` |
| `CANT. PEDIDO` | `cantidad_pedido` | |
| `TP` | `tp_unidades` | |
| `Horas preparación de máquina` | `horas_preparacion` | |
| `Horas de Producción` | `horas_produccion` | |
| `Tipo de Producción` | `tipo_produccion` | |

---

## 8. Servicio Optimizador (`backend/app/services/optimizer.py`)

### Algoritmo heurístico (fase 1)
1. Filtrar OFs `PENDIENTE` asignadas a la máquina objetivo
2. Ordenar por `fecha_entrega ASC` (prioridad base)
3. Agrupar OFs con mismo `cilindro_id` + mismo color principal primero
4. Calcular `costo_setup_min` entre cada par consultando `sipp.setup_penalizaciones`
5. Insertar resultado en `sipp.secuencias_produccion` con `posicion = 1, 2, 3...`
6. Cachear ICC en `sipp.icc_cache` para cada par evaluado
7. Registrar corrida en `sipp.log_optimizaciones` con setup_total antes vs después

### ICC — Índice de Compatibilidad de Cambio (0–100)
```python
# Fórmula — clampeado a [0, 100]
icc_score = max(0, min(100, 100 - (setup_total_min / 480 * 100)))
```
- `100` = mismo formato + mismo color (0 min setup)
- `0` = cambio de formato completo (480 min)
- Cacheado en `sipp.icc_cache` con `detalle_json` del desglose por tipo de cambio

---

## 9. API REST — Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/ordenes/importar` | Importar CSV mensual |
| `GET` | `/api/v1/ordenes` | Listar OFs con filtros |
| `GET` | `/api/v1/maquinas` | Listar máquinas |
| `GET` | `/api/v1/maquinas/{id}/cola` | Cola de producción de una máquina |
| `POST` | `/api/v1/optimizador/ejecutar` | Lanzar el optimizador para una semana/máquina |
| `GET` | `/api/v1/kpi/semanal` | KPIs del dashboard |
| `POST` | `/api/v1/setups/registrar` | Operario registra setup real desde planta |

Todos los endpoints retornan `application/json`. Prefijo global `/api/v1/`.

---

## 10. Frontend Streamlit (`frontend/app.py`) — Anexo 20

### Layout del dashboard principal
```
┌─────────────────────────────────────────────────────────────────┐
│  NAVBAR: Logo VYGPACK · SIPP · [Semana selector] · Usuario      │
├──────────────────────────────────────────────────────────────────┤
│  KPI ROW (st.columns 4)                                          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────┐  │
│  │ Total OFs  │ │ Setup (h)  │ │ Utiliz.(%) │ │ OFs en riesgo│  │
│  └────────────┘ └────────────┘ └────────────┘ └─────────────┘  │
├─────────────────────────────┬────────────────────────────────────┤
│  COLAS DE MÁQUINAS (izq)    │  MATRIZ ICC / CAMBIOS (der)        │
│                             │                                    │
│  Tabs: [M8] [M10] [M14]     │  Tabla NxN coloreada:              │
│                             │  Verde  = ICC 80–100 (bajo setup)  │
│  Por tab:                   │  Amarillo = ICC 50–79              │
│  pos | OF | medida | colores│  Rojo   = ICC 0–49  (alto setup)   │
│  setup_min | fecha_entrega  │                                    │
│  badge estado               │                                    │
│                             │  Botón: ▶ Ejecutar Optimizador     │
└─────────────────────────────┴────────────────────────────────────┘
```

### Reglas del frontend
- **NUNCA** importar módulos de `backend/` ni conectarse directo a PostgreSQL
- Toda data viene de `utils/api_client.py` → llamadas HTTP al backend FastAPI
- Usar `st.cache_data(ttl=30)` en todas las llamadas a la API
- Si el backend no responde → `st.error("Backend no disponible")` sin crashear
- Selector de semana en el sidebar o navbar (`st.selectbox`)
- Tabs de máquinas con `st.tabs(["M8", "M10", "M14"])`
- Badges de estado: `PENDIENTE`=gris, `EN_PROCESO`=azul, `COMPLETADA`=verde (HTML en `st.markdown`)
- Matriz ICC: `st.dataframe` con `background_gradient` o tabla HTML con colores inline

---

## 11. Convenciones de Naming Python

### Archivos y módulos
- `snake_case` para archivos, funciones y variables
- Clases en `PascalCase`: `OrdenFabricacion`, `SecuenciaProduccion`, `SetupHistorial`
- Constantes en `UPPER_SNAKE_CASE`: `MAX_SETUP_MIN = 480`

### Modelos SQLModel
```python
class OrdenFabricacion(SQLModel, table=True):
    __tablename__ = "ordenes_fabricacion"
    __table_args__ = {"schema": "sipp"}   # siempre schema explícito
```
- Campos opcionales con `Optional[tipo] = None`
- Fechas siempre timezone-aware: `from datetime import datetime, timezone`

### Schemas Pydantic v2
```python
class OrdenFabricacionRead(BaseModel):    # respuesta GET
class OrdenFabricacionCreate(BaseModel):  # body POST
class OrdenFabricacionUpdate(BaseModel):  # body PATCH (todos Optional)
```

### Servicios
- Funciones async: `async def importar_csv(ruta: str, db: AsyncSession) -> ImportResult`
- Un archivo por dominio — nunca mezclar lógica de importación con optimización
- Retornar dataclasses o Pydantic models, nunca dicts crudos

### Routers FastAPI
```python
router = APIRouter(prefix="/ordenes", tags=["Órdenes"])
# Inyección de sesión:
async def endpoint(db: AsyncSession = Depends(get_session)):
```
- Siempre declarar `tags` para la documentación Swagger automática

---

## 12. Variables de Entorno (`.env`)

```env
# Base de datos
DATABASE_URL=postgresql+asyncpg://sipp_user:sipp2025@localhost:5432/sipp_db
POSTGRES_SCHEMA=sipp

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true

# Frontend
BACKEND_URL=http://localhost:8000

# Archivos
CSV_UPLOAD_DIR=./data/uploads
```

---

## 13. Instrucciones de Comportamiento para el Agente

1. **Desacoplamiento estricto:** el frontend nunca toca la BD ni importa módulos del backend. Solo HTTP/JSON.
2. **Schema siempre explícito:** toda tabla lleva prefijo `sipp.` en SQL y `schema="sipp"` en SQLModel.
3. **OFs se registran por formulario Streamlit** — NO hay importación CSV como flujo operacional. El CSV solo existe como seed inicial (una vez).
4. **Seed CSV — solo para datos iniciales:** `backend/app/management/seed_inicial.py` puebla maestros y OFs de referencia. No es un endpoint de la API.
5. **CSV — reglas de lectura (solo para el seed):** `encoding='utf-8-sig'`, `sep=';'`, `df.columns = df.iloc[0]; df = df[1:]`, `df.columns.str.strip()`, reemplazar `#N/D` y `#¡VALOR!` por `None`.
6. **Penalizaciones desde BD:** el optimizador NUNCA hardcodea minutos — siempre los lee de `sipp.setup_penalizaciones`.
7. **Factor de velocidad BPM:** multiplicar `velocidad_bpm_max × material.factor_velocidad` al calcular tiempo de producción.
8. **Async en todo el backend:** todas las funciones de BD son `async def` con `await session.execute(...)`. No mezclar sync con async.
9. **ICC siempre cacheado:** tras ejecutar el optimizador, guardar cada par en `sipp.icc_cache`. El frontend lee de ahí, nunca recalcula.
10. **Layout Anexo 20:** el dashboard Streamlit replica la estructura del documento — KPIs arriba, colas con tabs por máquina a la izquierda, matriz ICC a la derecha. No inventar layouts alternativos.
11. **Formulario OF:** `fecha_entrega` es campo obligatorio. `estado` siempre inicia en `PENDIENTE`. Después de guardar → `st.rerun()`.
12. **`errata` en CSV (seed):** la columna se llama `Descricpción` (con error tipográfico) — usar ese nombre exacto al procesar el seed.

---

## 15. Lógica de Negocio Real (Sesiones de Planta — Jefe de Producción)

> Esta sección tiene MAYOR PRIORIDAD que cualquier lógica anterior.
> Fue extraída de reuniones reales con el Jefe de Producción "Jaer".

### Alcance de Máquinas — ESTRICTO
- **SOLO M8, M10 y M14.** Ninguna otra máquina entra en el sistema.
- M8 y M14 pueden procesar bolsas tamaño 8 al 12 (lógica de coexistencia).

### Tipo de Producto — ESTRICTO
- **Solo Bolsas de Base Cuadrada.**
- Dimensión siempre: Ancho × Alto × Fuelle (los tres valores son constantes).
- NO se procesan bolsas planas ni especiales.

### Cálculo Automático de Ancho de Bobina
Si el archivo/formulario no trae el ancho de bobina, el backend lo calcula:
```
Ancho_Bobina = (Ancho_bolsa + Fuelle) × 2 + Pega
Pega estándar = 2.5 cm (usar 2 si no se especifica, máximo 3)
```
Este campo debe calcularse y guardarse en `ordenes_fabricacion.ancho_bobina_mm`.

### Jerarquía del Optimizador (orden ESTRICTO)

**PASO 1 — Prioridad Comercial (entre máquinas):**
1. Clasificar por Franquicia: Nivel 1 → 2 → 3 → 4
2. Empate en franquicia → ordenar por `fecha_entrega ASC`

**PASO 2 — Optimización de Tiempos Muertos (dentro de cada máquina):**
Agrupar en este orden exacto para minimizar setup:
1. FORMATO (mismo Ancho/Cilindro) → evita 8h de pérdida
2. ALTURA → cambios de 1.5 a 2h
3. MATERIAL → Kraft (rápido), Liner, Antigrasa (lento/delicado)
4. COLOR → el más barato, 30 min de lavado

### Regla Especial — "Jugada Corta" (Tamaños Contiguos)
Transición entre tamaños contiguos (8→10, 5→6, etc.) varía solo ~0.5 cm
en el ancho del papel. Se trata como **cambio de altura** (1.5-2h),
NO como cambio de formato completo (8h).

```python
TAMAÑOS_CONTIGUOS = [(5,6), (6,8), (8,10), (10,12)]

def es_cambio_contiguo(tamaño_a: int, tamaño_b: int) -> bool:
    par = (min(tamaño_a, tamaño_b), max(tamaño_a, tamaño_b))
    return par in TAMAÑOS_CONTIGUOS
```
Si `es_cambio_contiguo()` → penalización = 105 min (promedio 1.5-2h)
En lugar de 480 min de cambio de formato completo.

### Persistencia del Último Setup por Máquina
Para calcular el setup del PRIMER pedido de la semana, el sistema
necesita saber qué quedó montado la semana anterior.

Tabla requerida:
```sql
CREATE TABLE IF NOT EXISTS sipp.ultimo_estado_maquina (
    id SERIAL PRIMARY KEY,
    maquina_id INT NOT NULL UNIQUE REFERENCES sipp.maquinas(id),
    ultima_of_id INT REFERENCES sipp.ordenes_fabricacion(id),
    ancho_mm NUMERIC(7,2),
    alto_mm NUMERIC(7,2),
    fuelle_mm NUMERIC(7,2),
    cilindro_id INT REFERENCES sipp.cilindros(id),
    material_id INT REFERENCES sipp.materiales(id),
    color_principal VARCHAR(80),
    actualizado_en TIMESTAMPTZ DEFAULT NOW()
);
```
El optimizador lee esta tabla para calcular el costo del primer setup.
Al finalizar la semana, actualiza el registro con la última OF ejecutada.

### Coexistencia M8 / M14
Cuando una OF puede ir en M8 o M14 (tamaños 8-12):
```
score_maquina = (100 - carga_pct) × 0.4 + compatibilidad_ultimo_estado × 0.6
```
Asignar a la máquina con mayor score.

### Paradas / Imprevistos
Endpoint obligatorio: `POST /api/v1/paradas`
Body: `{maquina_id, inicio, fin, tipo, descripcion}`
Efecto: desplaza automáticamente `inicio_estimado` y `fin_estimado`
de TODAS las secuencias pendientes de esa máquina a partir de la parada.

### Reordenamiento Manual
Endpoint: `PUT /api/v1/semanas/{id}/reordenar`
Body: `{"orden": [of_id_1, of_id_2, of_id_3, ...]}`
Efecto: reescribe posiciones + recalcula costo_setup_min entre cada par.

### Tabla de Franquicias (Prioridad Comercial)
```sql
CREATE TABLE IF NOT EXISTS sipp.franquicias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    nivel INT NOT NULL CHECK (nivel BETWEEN 1 AND 4),
    descripcion TEXT
);
```
FK en clientes: `franquicia_id INT REFERENCES sipp.franquicias(id)`
