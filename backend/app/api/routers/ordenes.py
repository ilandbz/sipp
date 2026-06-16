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
async def crear_orden(body: OrdenFabricacionCreate, db: AsyncSession = Depends(get_session)):
    try:
        # Si el body NO trae codigo_of o viene vacío, autogenerarlo
        body_data = body.model_dump()
        if not body_data.get("codigo_of") or not body_data["codigo_of"].strip():
            body_data["codigo_of"] = await generar_codigo_of(db)
        
        # Check if OF already exists
        existing = await db.execute(select(OrdenFabricacion).where(OrdenFabricacion.codigo_of == body_data["codigo_of"]))
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail=f"La Orden de Fabricación {body_data['codigo_of']} ya existe")
            
        of = OrdenFabricacion(**body_data)
        
        # Auto-calcular ancho bobina si es posible
        if not of.ancho_bobina_mm:
            calc = calcular_ancho_bobina(of)
            if calc > 0:
                of.ancho_bobina_mm = calc
                
        db.add(of)
        await db.flush()
        await db.commit()
        
        # Reload with joined details
        return await obtener_orden(of.id, db)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)} | {traceback.format_exc()}"
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
