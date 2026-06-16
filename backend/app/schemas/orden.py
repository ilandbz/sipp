from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class OrdenFabricacionBase(BaseModel):
    codigo_of: str
    codigo_pt: Optional[str] = None
    descripcion: Optional[str] = None
    referencia: Optional[str] = None
    cliente_id: Optional[int] = None
    maquina_asignada_id: Optional[int] = None
    material_id: Optional[int] = None
    cilindro_id: Optional[int] = None
    clise_id: Optional[int] = None
    medida_texto: Optional[str] = None
    ancho_mm: Optional[float] = None
    alto_mm: Optional[float] = None
    fuelle_mm: Optional[float] = None
    distancia_base_mm: Optional[float] = None
    leva_requerida: Optional[str] = None
    gramaje: Optional[float] = None
    num_colores: Optional[int] = None
    colores_detalle: Optional[str] = None
    tipo_bolsa: Optional[str] = None
    tipo_bolsa_id: Optional[int] = None
    tipo_etiqueta: Optional[str] = None
    ancho_bobina_mm: Optional[float] = None
    pega_cm: Optional[float] = None
    franquicia_nivel: Optional[int] = None
    cantidad_pedido: Optional[float] = None
    saldo_por_atender: Optional[float] = None
    stock_disponible: Optional[float] = None
    unidad_medida: Optional[str] = None
    cantidad_programada: Optional[float] = None
    tp_unidades: Optional[float] = None
    peso_por_millar: Optional[float] = None
    peso_requerido: Optional[float] = None
    cantidad_empaquetado: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_entrega: Optional[date] = None
    fecha_atencion: Optional[date] = None
    inicio_prod: Optional[datetime] = None
    prioridad: Optional[int] = None
    horas_preparacion: Optional[float] = None
    horas_correccion: Optional[float] = None
    horas_produccion: Optional[float] = None
    horas_trabajo_maquina: Optional[float] = None
    dias_semana_programados: Optional[int] = None
    horas_estimadas: Optional[float] = None
    horas_subtotal: Optional[float] = None
    dia_festivo: bool = False
    horas_total_produccion: Optional[float] = None
    fin_ocupacion_calculado: Optional[datetime] = None
    fin_produccion_proyectado: Optional[datetime] = None
    fin_produccion: Optional[datetime] = None
    tipo_produccion: Optional[str] = None
    estado: str = "PENDIENTE"
    observacion: Optional[str] = None

class OrdenFabricacionCreate(OrdenFabricacionBase):
    pass

class OrdenFabricacionUpdate(BaseModel):
    codigo_of: Optional[str] = None
    codigo_pt: Optional[str] = None
    descripcion: Optional[str] = None
    referencia: Optional[str] = None
    cliente_id: Optional[int] = None
    maquina_asignada_id: Optional[int] = None
    material_id: Optional[int] = None
    cilindro_id: Optional[int] = None
    clise_id: Optional[int] = None
    medida_texto: Optional[str] = None
    ancho_mm: Optional[float] = None
    alto_mm: Optional[float] = None
    fuelle_mm: Optional[float] = None
    distancia_base_mm: Optional[float] = None
    leva_requerida: Optional[str] = None
    gramaje: Optional[float] = None
    num_colores: Optional[int] = None
    colores_detalle: Optional[str] = None
    tipo_bolsa: Optional[str] = None
    tipo_etiqueta: Optional[str] = None
    cantidad_pedido: Optional[float] = None
    saldo_por_atender: Optional[float] = None
    stock_disponible: Optional[float] = None
    unidad_medida: Optional[str] = None
    cantidad_programada: Optional[float] = None
    tp_unidades: Optional[float] = None
    peso_por_millar: Optional[float] = None
    peso_requerido: Optional[float] = None
    cantidad_empaquetado: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_entrega: Optional[date] = None
    fecha_atencion: Optional[date] = None
    inicio_prod: Optional[datetime] = None
    prioridad: Optional[int] = None
    horas_preparacion: Optional[float] = None
    horas_correccion: Optional[float] = None
    horas_produccion: Optional[float] = None
    horas_trabajo_maquina: Optional[float] = None
    dias_semana_programados: Optional[int] = None
    horas_estimadas: Optional[float] = None
    horas_subtotal: Optional[float] = None
    dia_festivo: Optional[bool] = None
    horas_total_produccion: Optional[float] = None
    fin_ocupacion_calculado: Optional[datetime] = None
    fin_produccion_proyectado: Optional[datetime] = None
    fin_produccion: Optional[datetime] = None
    tipo_produccion: Optional[str] = None
    estado: Optional[str] = None
    observacion: Optional[str] = None

class OrdenFabricacionRead(BaseModel):
    id: int
    codigo_of: str
    codigo_pt: Optional[str] = None
    descripcion: Optional[str] = None
    referencia: Optional[str] = None
    estado: str = "PENDIENTE"
    maquina_asignada_id: Optional[int] = None
    material_id: Optional[int] = None
    cliente_id: Optional[int] = None
    cilindro_id: Optional[int] = None
    tipo_bolsa_id: Optional[int] = None
    medida_texto: Optional[str] = None
    ancho_mm: Optional[float] = None
    alto_mm: Optional[float] = None
    fuelle_mm: Optional[float] = None
    ancho_bobina_mm: Optional[float] = None
    gramaje: Optional[float] = None
    num_colores: Optional[int] = None
    colores_detalle: Optional[str] = None
    cantidad_pedido: Optional[float] = None
    cantidad_programada: Optional[float] = None
    unidad_medida: Optional[str] = None
    fecha_entrega: Optional[date] = None
    fecha_emision: Optional[date] = None
    fecha_atencion: Optional[date] = None
    prioridad: Optional[int] = None
    franquicia_nivel: Optional[int] = None
    horas_produccion: Optional[float] = None
    observacion: Optional[str] = None
    tipo_produccion: Optional[str] = None
    importado_en: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    maquina_codigo: Optional[str] = None
    material_nombre: Optional[str] = None
    cliente_nombre: Optional[str] = None
    
    model_config = {"from_attributes": True}
