import os
import re
import argparse
import asyncio
import pandas as pd
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, date, timezone

from app.core.database import engine
from app.models.maquina import Maquina
from app.models.material import Material
from app.models.cliente import Cliente
from app.models.cilindro import Cilindro
from app.models.orden_fabricacion import OrdenFabricacion

def parsear_medida(texto: str | None) -> dict:
    """
    "18X32X10.5"   → ancho=18,  alto=32,  fuelle=10.5
    "35X36"        → ancho=35,  alto=36,  fuelle=None
    "27.3 X 25.20" → ancho=27.3, alto=25.2, fuelle=None
    """
    if not texto or str(texto).strip() in ("0", ""):
        return {"ancho_mm": None, "alto_mm": None, "fuelle_mm": None}
    partes = re.split(r"[xX\s]+", str(texto).strip())
    partes = [p for p in partes if p]
    try:
        return {
            "ancho_mm":  float(partes[0]) if len(partes) > 0 else None,
            "alto_mm":   float(partes[1]) if len(partes) > 1 else None,
            "fuelle_mm": float(partes[2]) if len(partes) > 2 else None,
        }
    except (ValueError, IndexError):
        return {"ancho_mm": None, "alto_mm": None, "fuelle_mm": None}

def format_gramage(val):
    if pd.isna(val) or str(val).strip() in ("", "None"):
        return ""
    try:
        f_val = float(val)
        if f_val.is_integer():
            return str(int(f_val))
        return str(f_val)
    except ValueError:
        return str(val).strip()

def parse_float(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s in ("", "None", "#N/D", "#¡VALOR!", "#VALUE!", "No aplica"):
        return None
    try:
        s = s.replace(",", "")
        return float(s)
    except ValueError:
        return None

def parse_int(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s in ("", "None", "#N/D", "#¡VALOR!", "#VALUE!", "No aplica"):
        return None
    try:
        s = s.replace(",", "")
        return int(float(s))
    except ValueError:
        return None

def parse_date(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s in ("", "None", "0/1/1900", "0/01/1900", "0/1/1900 0:00:00", "#N/D", "#¡VALOR!", "#VALUE!"):
        return None
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors='coerce')
        if pd.isna(dt):
            return None
        return dt.date()
    except Exception:
        return None

def parse_datetime(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s in ("", "None", "0/1/1900", "0/01/1900", "0/1/1900 0:00:00", "#N/D", "#¡VALOR!", "#VALUE!"):
        return None
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors='coerce')
        if pd.isna(dt):
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def map_estado(val):
    if pd.isna(val) or not str(val).strip():
        return "PENDIENTE"
    v = str(val).strip().lower()
    if v in ("en producción", "en produccion", "en_proceso", "en cola"):
        return "PENDIENTE" # default target for queueing is PENDIENTE per instruction
    elif v in ("completada", "completado", "terminada", "terminado"):
        return "COMPLETADA"
    elif v in ("cancelada", "cancelado"):
        return "CANCELADA"
    elif v in ("programada", "programado"):
        return "PROGRAMADA"
    return "PENDIENTE"

def strip_tz(obj):
    fields = getattr(obj, "model_fields", getattr(obj, "__fields__", {}))
    for field_name in fields.keys():
        val = getattr(obj, field_name)
        if isinstance(val, datetime) and val.tzinfo is not None:
            setattr(obj, field_name, val.replace(tzinfo=None))
    return obj

def truncate_str(val, max_len):
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip()
    return s[:max_len]

def leer_csv(ruta: str) -> pd.DataFrame:
    df = pd.read_csv(ruta, encoding="utf-8-sig", sep=";")
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    df.columns = df.columns.str.strip()
    df.replace(["#N/D", "#¡VALOR!", "#VALUE!", ""], None, inplace=True)
    return df

async def seed_datos(archivo_path: str):
    print(f"Cargando datos desde: {archivo_path}")
    df = leer_csv(archivo_path)
    
    # Filtrar filas vacías (donde no hay Orden de Fabricación)
    df = df[df['Orden de Fabricación'].notna()]
    df = df[df['Orden de Fabricación'].str.strip() != '']
    
    async with AsyncSession(engine) as db:
        # 1. Cargar máquinas existentes
        maquinas_existentes = {}
        res = await db.execute(select(Maquina))
        for m in res.scalars().all():
            maquinas_existentes[m.codigo.strip().upper()] = m.id
            
        # 2. Cargar materiales existentes
        materiales_existentes = {}
        res = await db.execute(select(Material))
        for mat in res.scalars().all():
            materiales_existentes[mat.tipo.strip().upper()] = mat.id
            
        # 3. Cargar clientes existentes
        clientes_existentes = {}
        res = await db.execute(select(Cliente))
        for c in res.scalars().all():
            key = (c.razon_social.strip().upper(), (c.marca or "").strip().upper(), (c.vendedor or "").strip().upper())
            clientes_existentes[key] = c.id
            
        # 4. Cargar cilindros existentes
        cilindros_existentes = {}
        res = await db.execute(select(Cilindro))
        for cil in res.scalars().all():
            cilindros_existentes[cil.codigo.strip().upper()] = cil.id

        # 5. Cargar órdenes existentes
        res = await db.execute(select(OrdenFabricacion.codigo_of))
        ofs_existentes = set(res.scalars().all())

        maquinas_nuevas = 0
        materiales_nuevos = 0
        clientes_nuevos = 0
        cilindros_nuevos = 0
        ofs_nuevas = 0

        for idx, row in df.iterrows():
            # MAQ -> maquinas
            maq_val = row.get('MAQ')
            maquina_id = None
            if pd.notna(maq_val) and str(maq_val).strip():
                maq_code = truncate_str(maq_val, 20)
                maq_key = maq_code.upper()
                if maq_key not in maquinas_existentes:
                    maquina = Maquina(
                        codigo=maq_code,
                        nombre=truncate_str(f"Máquina {maq_code}", 100)
                    )
                    strip_tz(maquina)
                    db.add(maquina)
                    await db.flush()
                    maquinas_existentes[maq_key] = maquina.id
                    maquinas_nuevas += 1
                maquina_id = maquinas_existentes[maq_key]

            # MATERIAL + GRAMAGE -> materiales
            mat_val = row.get('MATERIAL')
            material_id = None
            if pd.notna(mat_val) and str(mat_val).strip():
                material_name = str(mat_val).strip()
                gramage_val = row.get('GRAMAGE')
                gramage_clean = format_gramage(gramage_val)
                
                if gramage_clean and gramage_clean not in material_name:
                    tipo = f"{material_name} {gramage_clean} GR"
                else:
                    tipo = material_name
                
                tipo = truncate_str(tipo, 80)
                mat_key = tipo.upper()
                if mat_key not in materiales_existentes:
                    factor = 1.0
                    if "ANTIGRASA" in mat_key:
                        factor = 0.85
                    elif "KRAFT 50 GR" in mat_key:
                        factor = 0.95
                    
                    material = Material(
                        tipo=tipo,
                        gramaje_min=parse_float(gramage_val),
                        gramaje_max=parse_float(gramage_val),
                        factor_velocidad=factor
                    )
                    strip_tz(material)
                    db.add(material)
                    await db.flush()
                    materiales_existentes[mat_key] = material.id
                    materiales_nuevos += 1
                material_id = materiales_existentes[mat_key]

            # RAZON SOCIAL + MARCA + VENDEDOR -> clientes
            razon_social = row.get('RAZON SOCIAL')
            cliente_id = None
            if pd.notna(razon_social) and str(razon_social).strip():
                razon_social_clean = truncate_str(razon_social, 200)
                marca = row.get('MARCA')
                marca_clean = truncate_str(marca, 100)
                vendedor = row.get('VENDEDOR')
                vendedor_clean = truncate_str(vendedor, 100)
                
                cli_key = (razon_social_clean.upper(), (marca_clean or "").upper(), (vendedor_clean or "").upper())
                if cli_key not in clientes_existentes:
                    cliente = Cliente(razon_social=razon_social_clean, marca=marca_clean, vendedor=vendedor_clean)
                    strip_tz(cliente)
                    db.add(cliente)
                    await db.flush()
                    clientes_existentes[cli_key] = cliente.id
                    clientes_nuevos += 1
                cliente_id = clientes_existentes[cli_key]

            # CILINDRO -> cilindros
            cil_val = row.get('CILINDRO')
            cilindro_id = None
            if pd.notna(cil_val) and str(cil_val).strip():
                cil_code = str(cil_val).strip()
                if cil_code.endswith('.0'):
                    cil_code = cil_code[:-2]
                cil_code = truncate_str(cil_code, 30)
                
                cil_key = cil_code.upper()
                if cil_key not in cilindros_existentes:
                    cilindro_obj = Cilindro(
                        codigo=cil_code,
                        descripcion=truncate_str(f"Cilindro {cil_code}", 200)
                    )
                    strip_tz(cilindro_obj)
                    db.add(cilindro_obj)
                    await db.flush()
                    cilindros_existentes[cil_key] = cilindro_obj.id
                    cilindros_nuevos += 1
                cilindro_id = cilindros_existentes[cil_key]

            # Orden de Fabricación
            codigo_of = truncate_str(row.get('Orden de Fabricación'), 30)
            if codigo_of not in ofs_existentes:
                medida_txt = str(row.get('Medida')).strip() if pd.notna(row.get('Medida')) else None
                medidas = parsear_medida(medida_txt)
                
                colores = row.get('COLORES')
                num_col = None
                if pd.notna(colores) and str(colores).strip():
                    num_col = str(colores).count(',') + 1

                of_obj = OrdenFabricacion(
                    codigo_of=codigo_of,
                    codigo_pt=truncate_str(row.get('Código PT'), 30),
                    descripcion=str(row.get('Descricpción')).strip() if pd.notna(row.get('Descricpción')) else None,
                    referencia=truncate_str(row.get('REFERENCIA'), 200),
                    
                    cliente_id=cliente_id,
                    maquina_asignada_id=maquina_id,
                    material_id=material_id,
                    cilindro_id=cilindro_id,
                    
                    medida_texto=truncate_str(medida_txt, 50),
                    ancho_mm=medidas['ancho_mm'],
                    alto_mm=medidas['alto_mm'],
                    fuelle_mm=medidas['fuelle_mm'],
                    
                    gramaje=parse_float(row.get('GRAMAGE')),
                    num_colores=num_col,
                    colores_detalle=str(colores).strip() if pd.notna(colores) else None,
                    tipo_bolsa=truncate_str(row.get('DETALLE PRODUCTO'), 80),
                    tipo_etiqueta=truncate_str(row.get('TIPO DE ETIQUETA'), 50),
                    
                    cantidad_pedido=parse_float(row.get('CANT. PEDIDO')),
                    saldo_por_atender=parse_float(row.get('SALDO POR ATENDER')),
                    stock_disponible=parse_float(row.get('STOCK')),
                    unidad_medida=truncate_str(row.get('UM'), 20),
                    cantidad_programada=parse_float(row.get('MT')),
                    tp_unidades=parse_float(row.get('TP')),
                    peso_por_millar=parse_float(row.get('PESO POR MILLAR')),
                    peso_requerido=parse_float(row.get('PESO REQUERIDO')),
                    cantidad_empaquetado=truncate_str(row.get('CANTIDAD DE EMPAQUETADO'), 50),
                    
                    fecha_emision=parse_date(row.get('FECHA DE EMISION')),
                    fecha_entrega=parse_date(row.get('FECHA DE ENTREGA')),
                    inicio_prod=parse_datetime(row.get('Inicio Prod ')),
                    
                    horas_preparacion=parse_float(row.get('Horas preparación de máquina')),
                    horas_correccion=parse_float(row.get('Horas corrección')),
                    horas_produccion=parse_float(row.get('Horas de Producción')),
                    horas_trabajo_maquina=parse_float(row.get('Horas de tabajo (maquina)')),
                    dias_semana_programados=parse_int(row.get('Dias de la semana')),
                    horas_estimadas=parse_float(row.get('Horas Estimadas')),
                    horas_subtotal=parse_float(row.get('Horas sub total')),
                    dia_festivo=(str(row.get('Dia festivo')).strip().lower() in ('si', 'sí', 'yes', 'true')),
                    horas_total_produccion=parse_float(row.get('Horas totales de producción')),
                    
                    fin_ocupacion_calculado=parse_datetime(row.get('Fin de ocupación-Calculado')),
                    fin_produccion_proyectado=parse_datetime(row.get('Fin de Producción-Proyectado')),
                    fin_produccion=parse_datetime(row.get('Fin de Producción')),
                    
                    tipo_produccion=truncate_str(row.get('Tipo de Producción'), 50),
                    estado=map_estado(row.get('Estado')),
                    observacion=str(row.get('OBSERVACIÓN')).strip() if pd.notna(row.get('OBSERVACIÓN')) else None,
                    
                    fuente_archivo=os.path.basename(archivo_path)
                )
                strip_tz(of_obj)
                db.add(of_obj)
                ofs_existentes.add(codigo_of)
                ofs_nuevas += 1

        await db.commit()
        
        print("\n=== RESUMEN DE IMPORTACIÓN DE SEMILLA ===")
        print(f"Máquinas insertadas: {maquinas_nuevas}")
        print(f"Materiales insertados: {materiales_nuevos}")
        print(f"Clientes insertados: {clientes_nuevos}")
        print(f"Cilindros insertados: {cilindros_nuevos}")
        print(f"Órdenes de fabricación insertadas: {ofs_nuevas}")
        print("=========================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poblar la base de datos con la semilla del CSV inicial.")
    parser.add_argument(
        "--archivo",
        type=str,
        default=None,
        help="Ruta al archivo CSV de semilla."
    )
    args = parser.parse_args()
    
    archivo = args.archivo
    if not archivo:
        # Buscar en ubicaciones por defecto
        candidatos = [
            "../data/PROGRAMACIÓN ABRIL.csv",
            "../data/PROGRAMACIÓN_ABRIL.csv",
            "data/PROGRAMACIÓN ABRIL.csv",
            "data/PROGRAMACIÓN_ABRIL.csv"
        ]
        for c in candidatos:
            if os.path.exists(c):
                archivo = c
                break
                
    if not archivo or not os.path.exists(archivo):
        print(f"Error: No se encontró el archivo CSV de semilla en ninguna ubicación por defecto.")
        exit(1)
        
    asyncio.run(seed_datos(archivo))
