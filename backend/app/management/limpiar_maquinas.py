import asyncio
from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timezone

from app.core.database import engine
from app.models.maquina import Maquina
from app.models.orden_fabricacion import OrdenFabricacion

VALID_CODES = ['M8', 'M10', 'M14', 'FLEXO1', 'FLEXO2']

MAP_CODIGOS = {
    "1": "FLEXO1",
    "2": "FLEXO2",
    "4": "M14",
    "6": "M8",
    "7": "M10",
    "8": "M8",
    "10": "M10",
    "14": "M14",
    "FLEXO 1": "FLEXO1",
    "FLEXO 2": "FLEXO2",
    "FLEXO1": "FLEXO1",
    "FLEXO2": "FLEXO2"
}

CAPACIDADES = {
    "M8": {"velocidad_bpm_max": 80.0, "turno_horas": 8.0, "dias_semana": 5},
    "M10": {"velocidad_bpm_max": 100.0, "turno_horas": 8.0, "dias_semana": 5},
    "M14": {"velocidad_bpm_max": 120.0, "turno_horas": 8.0, "dias_semana": 5},
    "FLEXO1": {"velocidad_bpm_max": 60.0, "turno_horas": 8.0, "dias_semana": 5},
    "FLEXO2": {"velocidad_bpm_max": 60.0, "turno_horas": 8.0, "dias_semana": 5}
}

async def main():
    async with AsyncSession(engine) as db:
        print("Iniciando normalización y limpieza de máquinas...")
        
        # 1. Asegurar que las 5 máquinas válidas existan
        for code, caps in CAPACIDADES.items():
            res = await db.execute(select(Maquina).where(Maquina.codigo == code))
            maq = res.scalars().first()
            if not maq:
                maq = Maquina(codigo=code, nombre=f"Máquina {code}", **caps)
                db.add(maq)
                print(f"Máquina creada: {code}")
            else:
                for k, v in caps.items():
                    setattr(maq, k, v)
                db.add(maq)
                print(f"Máquina actualizada: {code}")
        await db.flush()
        
        # Recargar IDs de las máquinas válidas
        res = await db.execute(select(Maquina).where(Maquina.codigo.in_(VALID_CODES)))
        valid_maquinas = {m.codigo: m.id for m in res.scalars().all()}
        
        # 2. Cargar todas las máquinas para buscar inválidas
        res = await db.execute(select(Maquina))
        all_maqs = res.scalars().all()
        
        invalid_maqs = [m for m in all_maqs if m.codigo not in VALID_CODES]
        
        for inv_maq in invalid_maqs:
            code_clean = inv_maq.codigo.strip()
            target_code = MAP_CODIGOS.get(code_clean)
            if not target_code:
                # Intento de matching fuzzy secundario
                for k, v in MAP_CODIGOS.items():
                    if k in code_clean.upper() or code_clean.upper() in k:
                        target_code = v
                        break
            
            if target_code and target_code in valid_maquinas:
                target_id = valid_maquinas[target_code]
                # Re-asignar OFs asociadas a la máquina inválida
                res_ofs = await db.execute(select(OrdenFabricacion).where(OrdenFabricacion.maquina_asignada_id == inv_maq.id))
                ofs_to_update = res_ofs.scalars().all()
                for of in ofs_to_update:
                    of.maquina_asignada_id = target_id
                    db.add(of)
                print(f"Re-asignadas {len(ofs_to_update)} OFs de máquina '{inv_maq.codigo}' a '{target_code}'")
                
                # Eliminar la máquina inválida
                await db.delete(inv_maq)
                print(f"Máquina inválida eliminada: {inv_maq.codigo}")
            else:
                # Si no hay mapeo, re-asignar a M8 por defecto y borrar
                target_id = valid_maquinas.get("M8")
                res_ofs = await db.execute(select(OrdenFabricacion).where(OrdenFabricacion.maquina_asignada_id == inv_maq.id))
                ofs_to_update = res_ofs.scalars().all()
                for of in ofs_to_update:
                    of.maquina_asignada_id = target_id
                    db.add(of)
                await db.delete(inv_maq)
                print(f"Máquina inválida '{inv_maq.codigo}' eliminada sin mapeo directo (OFs re-asignadas a M8 por defecto)")
                
        await db.flush()
        
        # 3. Crear la tabla de medidas permitidas si no existe
        ddl = """
        CREATE TABLE IF NOT EXISTS sipp.maquina_medidas_permitidas (
            id SERIAL PRIMARY KEY,
            maquina_id INT NOT NULL REFERENCES sipp.maquinas(id) ON DELETE CASCADE,
            ancho_min_mm NUMERIC(7,2),
            ancho_max_mm NUMERIC(7,2),
            alto_min_mm  NUMERIC(7,2),
            alto_max_mm  NUMERIC(7,2),
            fuelle_max_mm NUMERIC(7,2),
            descripcion  TEXT,
            activo BOOLEAN DEFAULT TRUE,
            UNIQUE (maquina_id)
        );
        """
        await db.execute(text(ddl))
        await db.commit()
        print("Tabla 'sipp.maquina_medidas_permitidas' asegurada en PostgreSQL.")
        
        # 4. Calcular rangos de medidas y poblar capacidades de M8, M10, M14
        for code in ['M8', 'M10', 'M14']:
            maq_id = valid_maquinas[code]
            # Consultar min/max de medidas de las OFs asignadas
            q = select(
                text("MIN(ancho_mm)"),
                text("MAX(ancho_mm)"),
                text("MIN(alto_mm)"),
                text("MAX(alto_mm)"),
                text("MAX(fuelle_mm)")
            ).select_from(OrdenFabricacion).where(OrdenFabricacion.maquina_asignada_id == maq_id)
            
            res_medidas = await db.execute(q)
            row = res_medidas.first()
            
            ancho_min = float(row[0]) if row and row[0] is not None else 0.0
            ancho_max = float(row[1]) if row and row[1] is not None else 0.0
            alto_min = float(row[2]) if row and row[2] is not None else 0.0
            alto_max = float(row[3]) if row and row[3] is not None else 0.0
            fuelle_max = float(row[4]) if row and row[4] is not None else 0.0
            
            # Si no hay registros (por ejemplo en flexo), poner algunos defaults razonables
            if ancho_max == 0.0:
                ancho_min, ancho_max = 100.0, 400.0
                alto_min, alto_max = 150.0, 500.0
                fuelle_max = 120.0
                
            # Insertar en maquina_medidas_permitidas
            ins_sql = """
            INSERT INTO sipp.maquina_medidas_permitidas 
            (maquina_id, ancho_min_mm, ancho_max_mm, alto_min_mm, alto_max_mm, fuelle_max_mm, descripcion)
            VALUES (:maquina_id, :ancho_min, :ancho_max, :alto_min, :alto_max, :fuelle_max, :descripcion)
            ON CONFLICT (maquina_id) DO UPDATE SET
                ancho_min_mm = EXCLUDED.ancho_min_mm,
                ancho_max_mm = EXCLUDED.ancho_max_mm,
                alto_min_mm = EXCLUDED.alto_min_mm,
                alto_max_mm = EXCLUDED.alto_max_mm,
                fuelle_max_mm = EXCLUDED.fuelle_max_mm,
                descripcion = EXCLUDED.descripcion;
            """
            await db.execute(text(ins_sql), {
                "maquina_id": maq_id,
                "ancho_min": ancho_min,
                "ancho_max": ancho_max,
                "alto_min": alto_min,
                "alto_max": alto_max,
                "fuelle_max": fuelle_max,
                "descripcion": f"Capacidades calculadas dinámicamente para {code} basadas en OFs cargadas."
            })
            print(f"Capacidades de medidas guardadas para {code}: Ancho [{ancho_min}-{ancho_max}] Alto [{alto_min}-{alto_max}] Fuelle Max [{fuelle_max}]")
            
        await db.commit()
        print("Limpieza y configuracion de medidas finalizada correctamente [OK]")

if __name__ == "__main__":
    asyncio.run(main())
