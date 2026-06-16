from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, or_
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
from app.core.database import get_session
from app.models.orden_fabricacion import OrdenFabricacion
from app.models.maquina import Maquina
from app.models.material import Material
from app.models.cliente import Cliente
from app.schemas.orden import OrdenFabricacionRead, OrdenFabricacionCreate, OrdenFabricacionUpdate
from app.services.icc import calcular_ancho_bobina

router = APIRouter(prefix="/ordenes", tags=["Órdenes"])

@router.get("/", response_model=List[OrdenFabricacionRead])
async def listar_ordenes(
    maquina: Optional[str] = None,
    estado: Optional[str] = None,
    buscar: Optional[str] = None,
    db: AsyncSession = Depends(get_session)
):
    query = select(
        OrdenFabricacion,
        Maquina.codigo.label("maquina_codigo"),
        Material.tipo.label("material_nombre"),
        Cliente.razon_social.label("cliente_nombre")
    ).join(
        Maquina, Maquina.id == OrdenFabricacion.maquina_asignada_id, isouter=True
    ).join(
        Material, Material.id == OrdenFabricacion.material_id, isouter=True
    ).join(
        Cliente, Cliente.id == OrdenFabricacion.cliente_id, isouter=True
    )
    
    # Aplicar filtros
    if maquina and maquina != "Todas":
        query = query.where(Maquina.codigo == maquina)
    if estado and estado != "Todos":
        query = query.where(OrdenFabricacion.estado == estado)
    if buscar:
        buscar_pattern = f"%{buscar}%"
        query = query.where(
            or_(
                OrdenFabricacion.codigo_of.ilike(buscar_pattern),
                OrdenFabricacion.descripcion.ilike(buscar_pattern),
                OrdenFabricacion.codigo_pt.ilike(buscar_pattern)
            )
        )
        
    result = await db.execute(query)
    rows = result.all()
    
    ordenes_read = []
    for row in rows:
        of = row[0]
        of_data = of.model_dump()
        of_data["maquina_codigo"] = row[1]
        of_data["material_nombre"] = row[2]
        of_data["cliente_nombre"] = row[3]
        ordenes_read.append(OrdenFabricacionRead(**of_data))
        
    return ordenes_read

@router.get("/{id}", response_model=OrdenFabricacionRead)
async def obtener_orden(id: int, db: AsyncSession = Depends(get_session)):
    query = select(
        OrdenFabricacion,
        Maquina.codigo.label("maquina_codigo"),
        Material.tipo.label("material_nombre"),
        Cliente.razon_social.label("cliente_nombre")
    ).join(
        Maquina, Maquina.id == OrdenFabricacion.maquina_asignada_id, isouter=True
    ).join(
        Material, Material.id == OrdenFabricacion.material_id, isouter=True
    ).join(
        Cliente, Cliente.id == OrdenFabricacion.cliente_id, isouter=True
    ).where(OrdenFabricacion.id == id)
    
    result = await db.execute(query)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Orden de fabricación no encontrada")
        
    of = row[0]
    of_data = of.model_dump()
    of_data["maquina_codigo"] = row[1]
    of_data["material_nombre"] = row[2]
    of_data["cliente_nombre"] = row[3]
    return OrdenFabricacionRead(**of_data)

async def generar_codigo_of(db: AsyncSession) -> str:
    """
    Genera código único formato AAММ-NNNN.
    Usa SELECT FOR UPDATE para evitar duplicados concurrentes.
    """
    ahora = datetime.now()
    prefijo = ahora.strftime("%y%m")  # "2606" para junio 2026
    
    # Buscar el último secuencial del mes actual con bloqueo
    result = await db.execute(text("""
        SELECT codigo_of 
        FROM sipp.ordenes_fabricacion
        WHERE codigo_of LIKE :prefijo
        ORDER BY codigo_of DESC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    """), {"prefijo": f"{prefijo}-%"})
    
    ultimo = result.scalar_one_or_none()
    
    if ultimo:
        # Extraer el número y sumar 1
        try:
            ultimo_num = int(ultimo.split("-")[1])
            siguiente = ultimo_num + 1
        except (ValueError, IndexError):
            siguiente = 1
    else:
        siguiente = 1
    
    # Formato: 2606-0001
    codigo_of = f"{prefijo}-{siguiente:04d}"
    print(f"Código generado: {codigo_of}")
    return codigo_of

@router.post("/", response_model=OrdenFabricacionRead, status_code=status.HTTP_201_CREATED)
async def crear_orden(
    body: OrdenFabricacionCreate,
    db: AsyncSession = Depends(get_session)
):
    try:
        # Generar código OF si no viene
        codigo_of = body.codigo_of
        if not codigo_of or not codigo_of.strip():
            codigo_of = await generar_codigo_of(db)
        
        # Calcular ancho de bobina
        ancho_bobina = None
        if body.ancho_mm and body.fuelle_mm:
            pega = body.pega_cm or 2.5
            ancho_bobina = (body.ancho_mm + body.fuelle_mm) * 2 + (pega * 10)
        
        # Crear objeto con datos del body
        datos = body.model_dump(exclude_unset=False)
        datos["codigo_of"] = codigo_of
        datos["ancho_bobina_mm"] = ancho_bobina
        datos["estado"] = "PENDIENTE"
        from datetime import datetime
        datos["importado_en"] = datetime.utcnow()
        datos["created_at"] = datetime.utcnow()
        datos["updated_at"] = datetime.utcnow()
        
        # Insertar usando SQL directo para evitar lazy loading
        from sqlalchemy import text
        
        # Filtrar solo columnas que existen en la tabla
        columnas_validas = [
            "codigo_of", "codigo_pt", "descripcion", "referencia",
            "cliente_id", "maquina_asignada_id", "material_id",
            "cilindro_id", "tipo_bolsa_id", "medida_texto",
            "ancho_mm", "alto_mm", "fuelle_mm", "ancho_bobina_mm",
            "pega_cm", "gramaje", "num_colores", "colores_detalle",
            "cantidad_programada", "unidad_medida", "fecha_entrega",
            "prioridad", "estado", "observacion",
            "importado_en", "created_at", "updated_at"
        ]
        
        insert_datos = {k: v for k, v in datos.items() 
                       if k in columnas_validas and v is not None}
        
        of = OrdenFabricacion(**insert_datos)
        db.add(of)
        await db.flush()  # Obtener el ID sin cerrar la sesión
        of_id = of.id
        await db.commit()
        
        # Retornar solo los datos que ya tenemos (sin lazy load)
        # We need to construct a valid dict matching the updated OrdenFabricacionRead.
        # We merge insert_datos with the required default fields.
        return {
            **insert_datos,
            "id": of_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        )

@router.patch("/{id}", response_model=OrdenFabricacionRead)
async def actualizar_orden(id: int, body: OrdenFabricacionUpdate, db: AsyncSession = Depends(get_session)):
    of = await db.get(OrdenFabricacion, id)
    if not of:
        raise HTTPException(status_code=404, detail="Orden de fabricación no encontrada")
        
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(of, key, value)
        
    # Auto-calcular ancho bobina tras actualizacion
    calc = calcular_ancho_bobina(of)
    if calc > 0:
        of.ancho_bobina_mm = calc
        
    db.add(of)
    await db.flush()
    await db.commit()
    
    # Reload with joined details
    return await obtener_orden(of.id, db)

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_orden(id: int, db: AsyncSession = Depends(get_session)):
    of = await db.get(OrdenFabricacion, id)
    if not of:
        raise HTTPException(status_code=404, detail="Orden de fabricación no encontrada")
    await db.delete(of)
    await db.commit()
    return None

@router.post("/{id}/sugerir-maquina", status_code=status.HTTP_200_OK)
async def post_sugerir_maquina(id: int, db: AsyncSession = Depends(get_session)):
    from app.services.asignador import sugerir_maquina
    ranking = await sugerir_maquina(db, id)
    if not ranking:
        raise HTTPException(status_code=404, detail="Orden de fabricación no encontrada o no se pudo calcular sugerencia")
    return ranking
