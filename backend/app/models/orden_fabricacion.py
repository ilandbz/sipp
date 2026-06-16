from typing import Optional
from datetime import date, datetime, timezone
from sqlmodel import SQLModel, Field

class OrdenFabricacion(SQLModel, table=True):
    __tablename__ = "ordenes_fabricacion"
    __table_args__ = {"schema": "sipp"}

    id: Optional[int] = Field(default=None, primary_key=True)
    codigo_of: str = Field(max_length=30, unique=True, index=True)
    codigo_pt: Optional[str] = Field(default=None, max_length=30)
    descripcion: Optional[str] = Field(default=None)
    referencia: Optional[str] = Field(default=None, max_length=200)

    # Relaciones
    cliente_id: Optional[int] = Field(default=None, foreign_key="sipp.clientes.id", index=True)
    maquina_asignada_id: Optional[int] = Field(default=None, foreign_key="sipp.maquinas.id", index=True)
    material_id: Optional[int] = Field(default=None, foreign_key="sipp.materiales.id", index=True)
    cilindro_id: Optional[int] = Field(default=None, foreign_key="sipp.cilindros.id", index=True)
    clise_id: Optional[int] = Field(default=None, foreign_key="sipp.clises.id")
    tipo_bolsa_id: Optional[int] = Field(default=None, foreign_key="sipp.tipos_bolsa.id", index=True)

    # Dimensiones del producto (medida)
    medida_texto: Optional[str] = Field(default=None, max_length=50)
    ancho_mm: Optional[float] = Field(default=None)
    alto_mm: Optional[float] = Field(default=None)
    fuelle_mm: Optional[float] = Field(default=None)
    distancia_base_mm: Optional[float] = Field(default=None)
    leva_requerida: Optional[str] = Field(default=None, max_length=50)
    ancho_bobina_mm: Optional[float] = Field(default=None)
    pega_cm: Optional[float] = Field(default=2.5)

    # Impresión
    gramaje: Optional[float] = Field(default=None)
    num_colores: Optional[int] = Field(default=None)
    colores_detalle: Optional[str] = Field(default=None)
    tipo_bolsa: Optional[str] = Field(default=None, max_length=80)
    tipo_etiqueta: Optional[str] = Field(default=None, max_length=50)

    # Cantidades
    cantidad_pedido: Optional[float] = Field(default=None)
    saldo_por_atender: Optional[float] = Field(default=None)
    stock_disponible: Optional[float] = Field(default=None)
    unidad_medida: Optional[str] = Field(default=None, max_length=20)
    cantidad_programada: Optional[float] = Field(default=None)
    tp_unidades: Optional[float] = Field(default=None)
    peso_por_millar: Optional[float] = Field(default=None)
    peso_requerido: Optional[float] = Field(default=None)
    cantidad_empaquetado: Optional[str] = Field(default=None, max_length=50)

    # Fechas
    fecha_emision: Optional[date] = Field(default=None)
    fecha_entrega: Optional[date] = Field(default=None, index=True)
    fecha_atencion: Optional[date] = Field(default=None)
    inicio_prod: Optional[datetime] = Field(default=None)
    prioridad: Optional[int] = Field(default=None)
    franquicia_nivel: Optional[int] = Field(default=4)

    # Tiempos calculados
    horas_preparacion: Optional[float] = Field(default=None)
    horas_correccion: Optional[float] = Field(default=None)
    horas_produccion: Optional[float] = Field(default=None)
    horas_trabajo_maquina: Optional[float] = Field(default=None)
    dias_semana_programados: Optional[int] = Field(default=None)
    horas_estimadas: Optional[float] = Field(default=None)
    horas_subtotal: Optional[float] = Field(default=None)
    dia_festivo: bool = Field(default=False)
    horas_total_produccion: Optional[float] = Field(default=None)

    # Fin calculado / proyectado
    fin_ocupacion_calculado: Optional[datetime] = Field(default=None)
    fin_produccion_proyectado: Optional[datetime] = Field(default=None)
    fin_produccion: Optional[datetime] = Field(default=None)

    # Control
    tipo_produccion: Optional[str] = Field(default=None, max_length=50)
    estado: str = Field(default="PENDIENTE", max_length=30, index=True)
    observacion: Optional[str] = Field(default=None)

    # Trazabilidad importación
    importado_en: datetime = Field(default_factory=datetime.utcnow)
    fuente_archivo: Optional[str] = Field(default=None, max_length=200)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
