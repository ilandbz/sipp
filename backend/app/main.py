from fastapi import FastAPI
from app.api.routers import ordenes, maquinas, secuencias, optimizador, kpi, clientes, materiales, cilindros, semanas, tipos_bolsa, usuarios, paradas, franquicias, auth
from app.core.config import settings

app = FastAPI(
    title="SIPP API",
    description="Sistema Inteligente de Programación de Producción - VYGPACK",
    version="1.0.0",
    debug=settings.DEBUG
)

# Registrar routers con prefijo global /api/v1
app.include_router(auth.router, prefix="/api/v1")
app.include_router(ordenes.router, prefix="/api/v1")
app.include_router(maquinas.router, prefix="/api/v1")
app.include_router(secuencias.router, prefix="/api/v1")
app.include_router(optimizador.router, prefix="/api/v1")
app.include_router(kpi.router, prefix="/api/v1")
app.include_router(clientes.router, prefix="/api/v1")
app.include_router(materiales.router, prefix="/api/v1")
app.include_router(cilindros.router, prefix="/api/v1")
app.include_router(semanas.router, prefix="/api/v1")
app.include_router(tipos_bolsa.router, prefix="/api/v1")
app.include_router(usuarios.router, prefix="/api/v1")
app.include_router(paradas.router, prefix="/api/v1")
app.include_router(franquicias.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "SIPP API is running",
        "version": "1.0.0"
    }
