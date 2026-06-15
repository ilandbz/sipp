# Skill: Prompt Optimizer — Cómo pedirle tareas al agente
# Archivo: .claude/skills/00_prompt_guide.md
# Cuándo usarlo: ANTES de escribir cualquier prompt al agente.
# Este skill define cómo estructurar los pedidos para obtener
# código correcto, completo y alineado al proyecto desde el primer intento.

---

## Principio fundamental

El agente SIEMPRE debe leer `CLAUDE.md` antes de generar código.
Si no lo menciona explícitamente en el prompt, recordárselo:

```
Antes de generar código, lee el CLAUDE.md en la raíz del proyecto.
```

---

## Estructura de un prompt efectivo para este proyecto

```
[CONTEXTO] Qué parte del sistema se va a tocar
[TAREA]    Qué exactamente se necesita hacer
[INPUTS]   Qué archivos/datos/endpoints ya existen y son relevantes
[OUTPUT]   Qué archivos debe crear o modificar
[REGLAS]   Restricciones específicas para esta tarea (opcional)
```

---

## Plantillas de prompt por tipo de tarea

---

### 🏗 ARRANQUE DEL PROYECTO (usar solo una vez al inicio)

```
Lee el CLAUDE.md en la raíz del proyecto.

Contexto:
- BD PostgreSQL lista con schema `sipp` y 12 tablas (ver CLAUDE.md sección 4)
- Proyecto vacío: solo existe la estructura de carpetas y los archivos
  de modelos SQLModel en backend/app/models/
- El .env todavía no tiene los parámetros de conexión

Tarea:
1. Completar el archivo `.env` con los parámetros de conexión a PostgreSQL
   (DATABASE_URL, POSTGRES_SCHEMA, API_HOST, API_PORT, DEBUG, BACKEND_URL)
2. Crear `backend/app/core/config.py` con Settings usando pydantic-settings
3. Crear `backend/app/core/database.py` con el engine async y get_session()
4. Crear `backend/app/main.py` con la app FastAPI base (sin routers aún)
5. Verificar que `python -m uvicorn app.main:app --reload` arranque sin errores

Reglas:
- DATABASE_URL debe usar el driver `postgresql+asyncpg`
- El schema sipp ya existe en Postgres — NO ejecutar CREATE SCHEMA
- Los modelos SQLModel ya están creados, no recrearlos
- Usar NullPool en el engine async
```

---

### 📡 CREAR UN ROUTER/ENDPOINT

```
Lee el CLAUDE.md y el skill `.claude/skills/03_fastapi_router.md`.

Contexto: el backend FastAPI ya tiene core/config.py y core/database.py funcionando.

Tarea: Crear el router `backend/app/api/routers/[nombre].py` con los siguientes endpoints:
- GET /api/v1/[recurso]/          → listar con filtros opcionales: ?[param]=
- GET /api/v1/[recurso]/{id}      → obtener por id
- POST /api/v1/[recurso]/         → crear nuevo
- PATCH /api/v1/[recurso]/{id}    → actualizar campos
- DELETE /api/v1/[recurso]/{id}   → eliminar (soft delete si aplica)

El modelo SQLModel ya existe en `backend/app/models/[modelo].py`.
Crear también el schema Pydantic en `backend/app/schemas/[nombre].py`
con las clases Read, Create y Update.

Registrar el router en `backend/app/main.py` con prefix `/api/v1`.
```

---

### 📋 CREAR EL FORMULARIO DE ÓRDENES DE FABRICACIÓN

```
Lee el CLAUDE.md y el skill `.claude/skills/05_formulario_of.md`.

Contexto:
- El backend tiene los endpoints GET/POST/PATCH en /api/v1/ordenes/
- Los endpoints de maestros también existen:
  GET /api/v1/maquinas/, /api/v1/clientes/, /api/v1/materiales/, /api/v1/cilindros/

Tarea: Crear `frontend/pages/ordenes.py` con:
1. Tab "Lista de OFs" — tabla filtrable por máquina, estado y búsqueda de texto
2. Tab "Nueva OF" — formulario completo con los 7 bloques definidos en el skill
3. Al hacer clic en una fila de la lista → modo edición del mismo formulario

Agregar en `frontend/utils/api_client.py` las funciones:
get_ordenes(), get_clientes(), get_materiales(), get_cilindros(),
crear_orden(), actualizar_orden()

Reglas:
- fecha_entrega es obligatorio — mostrar st.error si está vacío
- estado siempre inicia en "PENDIENTE" al crear
- Después de guardar exitosamente → st.rerun()
- Todos los selectbox cargan datos del backend, no listas hardcodeadas
```

---

### ⚙ CREAR EL OPTIMIZADOR

```
Lee el CLAUDE.md y el skill `.claude/skills/02_optimizer.md`.

Contexto:
- Las tablas sipp.setup_penalizaciones, sipp.secuencias_produccion,
  sipp.icc_cache y sipp.log_optimizaciones ya existen en PostgreSQL
- Los modelos SQLModel correspondientes ya están en backend/app/models/

Tarea:
1. Crear `backend/app/services/optimizer.py` con la función
   `async def optimizar_semana(db, semana_id: int) -> dict`
2. Crear `backend/app/services/icc.py` con `calcular_icc(setup_min) -> float`
3. Crear el endpoint POST /api/v1/optimizador/ejecutar en
   `backend/app/api/routers/optimizador.py`

Reglas:
- Las penalizaciones NUNCA se hardcodean — leerlas de sipp.setup_penalizaciones
- Al finalizar, guardar cada par de OFs en sipp.icc_cache
- Registrar la corrida en sipp.log_optimizaciones con setup antes/después
- El ICC se calcula como: max(0, min(100, 100 - (setup_min / 480 * 100)))
```

---

### 🖥 CREAR EL DASHBOARD PRINCIPAL (Anexo 20)

```
Lee el CLAUDE.md y el skill `.claude/skills/04_streamlit_ui.md`.

Contexto:
- El backend tiene funcionando:
  GET /api/v1/kpi/semanal
  GET /api/v1/maquinas/{id}/cola
  GET /api/v1/maquinas/
  POST /api/v1/optimizador/ejecutar

Tarea: Crear `frontend/app.py` con el dashboard principal replicando el Anexo 20:
- Sidebar con navegación y selector de semana
- Fila de 4 KPIs (st.metric): total OFs, setup total en horas,
  utilización promedio, máquinas activas
- Columna izquierda: colas de máquinas con st.tabs([M8, M10, M14, ...])
- Columna derecha: matriz ICC coloreada (verde/amarillo/rojo) + botón optimizador

Reglas:
- st.set_page_config(layout="wide") obligatorio
- @st.cache_data(ttl=30) en todas las llamadas al backend
- Si backend no responde → st.error(...) y st.stop()
- NUNCA conectar directo a PostgreSQL desde el frontend
```

---

### 🌱 CREAR EL SEED INICIAL

```
Lee el CLAUDE.md y el skill `.claude/skills/01_csv_seed.md`.

Contexto:
- El archivo CSV está en `data/PROGRAMACIÓN_ABRIL.csv`
- Las tablas maestras en sipp están vacías
- Este script se ejecuta UNA sola vez para poblar datos iniciales

Tarea: Crear `backend/app/management/seed_inicial.py` que:
1. Lea el CSV con encoding='utf-8-sig', sep=';'
2. Pueble sipp.maquinas con los MAQ únicos
3. Pueble sipp.materiales con los MATERIAL+GRAMAJE únicos
4. Pueble sipp.clientes con RAZON SOCIAL únicos
5. Pueble sipp.cilindros con los CILINDRO únicos
6. Inserte las OFs del CSV en sipp.ordenes_fabricacion

Todas las inserciones con ON CONFLICT DO NOTHING (idempotente).
NO crear endpoint en la API para esto.
```

---

### 🐛 DEBUGGEAR UN ERROR

```
Lee el CLAUDE.md.

Estoy recibiendo este error:
[PEGAR EL TRACEBACK COMPLETO]

Archivo afectado: [ruta del archivo]
Contexto: [qué acción lo dispara — ej: "al hacer POST /api/v1/ordenes/"]

Analiza el error considerando:
- El schema de BD es `sipp` (siempre con prefijo en las tablas)
- El engine es async con asyncpg
- Los modelos SQLModel tienen __table_args__ = {"schema": "sipp"}

No cambies la estructura del proyecto ni el stack. Solo corrige el error.
```

---

### ✅ VERIFICACIÓN ANTES DE HACER COMMIT

```
Lee el CLAUDE.md.

Revisa el archivo [ruta] que acabo de crear/modificar y verifica:

1. ¿Todas las funciones de BD son async def con await?
2. ¿Los modelos SQLModel tienen schema="sipp" en __table_args__?
3. ¿El frontend no importa nada de backend/?
4. ¿Las penalizaciones SMED se leen de BD, no hardcodeadas?
5. ¿Las llamadas al backend en Streamlit tienen @st.cache_data(ttl=30)?
6. ¿Los endpoints tienen prefix, tags, y response_model declarados?
7. ¿Hay manejo de errores si el backend no responde?

Si encuentras alguna violación, corrígela y explica qué cambió.
```

---

## Errores comunes que el prompt debe prevenir

| Error | Cómo prevenirlo en el prompt |
|---|---|
| El agente conecta el frontend a Postgres | Añadir: "NUNCA conectar directo a PostgreSQL desde frontend" |
| Hardcodea las penalizaciones SMED | Añadir: "leer penalizaciones de sipp.setup_penalizaciones" |
| Olvida el schema `sipp` | Añadir: "todas las tablas llevan prefijo sipp. en SQL" |
| Mezcla sync/async | Añadir: "todo el backend es async, usar await session.execute" |
| Crea endpoint para el seed | Añadir: "el seed es un script de management, no un endpoint" |
| Inventa el layout del dashboard | Añadir: "replicar exactamente el Anexo 20 definido en el skill" |
