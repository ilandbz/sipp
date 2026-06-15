# Skill: FastAPI Routers
# Archivo: .claude/skills/03_fastapi_router.md
# Cuándo usarlo: cada vez que el agente deba crear o modificar
# cualquier archivo en backend/app/api/routers/  o  backend/app/main.py

---

## Propósito
Definir los endpoints REST del SIPP siguiendo las convenciones de FastAPI async
con SQLModel y el schema `sipp` de PostgreSQL.

---

## Patrón base de un router

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.database import get_session

router = APIRouter(prefix="/nombre", tags=["Nombre"])  # tags SIEMPRE declarado

@router.get("/", response_model=list[NombreRead])
async def listar(db: AsyncSession = Depends(get_session)):
    ...

@router.get("/{id}", response_model=NombreRead)
async def obtener(id: int, db: AsyncSession = Depends(get_session)):
    item = await db.get(Nombre, id)
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    return item

@router.post("/", response_model=NombreRead, status_code=status.HTTP_201_CREATED)
async def crear(body: NombreCreate, db: AsyncSession = Depends(get_session)):
    obj = Nombre(**body.model_dump())
    db.add(obj)
    await db.flush()
    return obj
```

---

## Endpoints del SIPP y su router asignado

### `routers/ordenes.py`  — prefix `/api/v1/ordenes`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Listar OFs con filtros: `?maquina=M8&estado=PENDIENTE&semana=2025-04-07` |
| `GET` | `/{id}` | Detalle de una OF |
| `POST` | `/importar` | Subir CSV y disparar `importer.py` |
| `PATCH` | `/{id}/estado` | Cambiar estado de una OF |

```python
# Endpoint importar — recibe multipart/form-data
from fastapi import UploadFile, File
import tempfile, os

@router.post("/importar", response_model=ImportResultSchema)
async def importar_csv(
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
):
    if not archivo.filename.endswith(".csv"):
        raise HTTPException(400, "Solo se aceptan archivos .csv")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(await archivo.read())
        tmp_path = tmp.name
    try:
        from app.services.importer import importar_csv_service
        resultado = await importar_csv_service(tmp_path, archivo.filename, db)
    finally:
        os.unlink(tmp_path)
    return resultado
```

---

### `routers/maquinas.py`  — prefix `/api/v1/maquinas`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Listar máquinas activas |
| `GET` | `/{id}/cola` | Cola de producción (usa `sipp.v_cola_produccion`) |
| `GET` | `/{id}/disponibilidad` | Paros y mantenimientos de la máquina |

```python
# Cola — leer desde la vista materializada
from sqlalchemy import text

@router.get("/{id}/cola", response_model=list[ColaItemSchema])
async def cola_maquina(id: int, semana: str | None = None, db: AsyncSession = Depends(get_session)):
    filtro = "AND s.fecha_inicio = :semana" if semana else ""
    sql = text(f"""
        SELECT * FROM sipp.v_cola_produccion
        WHERE maquina = (SELECT codigo FROM sipp.maquinas WHERE id = :id)
        {filtro}
        ORDER BY posicion
    """)
    params = {"id": id}
    if semana:
        params["semana"] = semana
    result = await db.execute(sql, params)
    return result.mappings().all()
```

---

### `routers/secuencias.py`  — prefix `/api/v1/secuencias`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/semana/{semana_id}` | Todas las secuencias de una semana |
| `PATCH` | `/{id}/posicion` | Reordenar manualmente una OF en la cola |

---

### `routers/optimizador.py`  — prefix `/api/v1/optimizador`

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/ejecutar` | Lanzar el optimizador para una semana |

```python
from app.services.optimizer import optimizar_semana

@router.post("/ejecutar", response_model=OptimizacionResultSchema)
async def ejecutar(body: OptimizarRequest, db: AsyncSession = Depends(get_session)):
    resultado = await optimizar_semana(db, body.semana_id)
    return resultado
```

---

### `routers/kpi.py`  — prefix `/api/v1/kpi`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/semanal` | KPIs de la semana (usa `sipp.v_kpi_semanal`) |

```python
@router.get("/semanal", response_model=list[KpiSemanalSchema])
async def kpi_semanal(semana: str | None = None, db: AsyncSession = Depends(get_session)):
    filtro = "WHERE fecha_inicio = :semana" if semana else ""
    sql = text(f"SELECT * FROM sipp.v_kpi_semanal {filtro} ORDER BY maquina")
    result = await db.execute(sql, {"semana": semana} if semana else {})
    return result.mappings().all()
```

---

## Registro de routers en `main.py`

```python
from fastapi import FastAPI
from app.api.routers import ordenes, maquinas, secuencias, optimizador, kpi

app = FastAPI(
    title="SIPP — VYGPACK",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

PREFIX = "/api/v1"
app.include_router(ordenes.router,     prefix=PREFIX)
app.include_router(maquinas.router,    prefix=PREFIX)
app.include_router(secuencias.router,  prefix=PREFIX)
app.include_router(optimizador.router, prefix=PREFIX)
app.include_router(kpi.router,         prefix=PREFIX)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## Schemas Pydantic v2 — convención de nombres

```python
# schemas/orden.py
from pydantic import BaseModel
from datetime import date
from typing import Optional

class OrdenFabricacionRead(BaseModel):
    id: int
    codigo_of: str
    descripcion: Optional[str]
    medida_texto: Optional[str]
    estado: str
    fecha_entrega: Optional[date]
    model_config = {"from_attributes": True}

class OrdenFabricacionCreate(BaseModel):
    codigo_of: str
    descripcion: Optional[str] = None
    # ... resto de campos

class ImportResultSchema(BaseModel):
    total_filas: int
    insertadas: int
    actualizadas: int
    errores: int
    detalle_errores: list[str]
```

---

## Checklist antes de dar por terminado un router

- [ ] `prefix` y `tags` declarados en `APIRouter(...)`
- [ ] Todas las funciones son `async def`
- [ ] Sesión inyectada con `Depends(get_session)`
- [ ] 404 con `HTTPException(404, ...)` cuando no se encuentra el recurso
- [ ] `response_model` declarado en cada endpoint
- [ ] Router registrado en `main.py` con `app.include_router(..., prefix=PREFIX)`
- [ ] Consultas SQL a vistas usan `text(...)` con parámetros named (nunca f-string con valores de usuario)
