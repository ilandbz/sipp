import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings

async def run():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        print("Running: ALTER TABLE sipp.semanas_programacion ADD COLUMN es_global")
        await conn.execute(text("ALTER TABLE sipp.semanas_programacion ADD COLUMN IF NOT EXISTS es_global BOOLEAN DEFAULT FALSE;"))
        
        print("Running: ALTER TABLE sipp.semanas_programacion ALTER COLUMN maquina_id DROP NOT NULL")
        await conn.execute(text("ALTER TABLE sipp.semanas_programacion ALTER COLUMN maquina_id DROP NOT NULL;"))
        
        print("Running: CREATE TABLE sipp.maquina_capacidades")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sipp.maquina_capacidades (
                id SERIAL PRIMARY KEY,
                maquina_id INT NOT NULL UNIQUE REFERENCES sipp.maquinas(id),
                ancho_min_mm NUMERIC(7,2),
                ancho_max_mm NUMERIC(7,2),
                alto_min_mm  NUMERIC(7,2),
                alto_max_mm  NUMERIC(7,2),
                fuelle_max_mm NUMERIC(7,2),
                descripcion TEXT
            );
        """))
        
        print("Running: INSERT INTO sipp.maquina_capacidades")
        await conn.execute(text("""
            INSERT INTO sipp.maquina_capacidades
                (maquina_id, ancho_min_mm, ancho_max_mm, alto_min_mm, alto_max_mm, descripcion)
            SELECT m.id,
                CASE m.codigo WHEN 'M8' THEN 80 WHEN 'M10' THEN 100 WHEN 'M14' THEN 120 END,
                CASE m.codigo WHEN 'M8' THEN 200 WHEN 'M10' THEN 250 WHEN 'M14' THEN 350 END,
                CASE m.codigo WHEN 'M8' THEN 100 WHEN 'M10' THEN 120 WHEN 'M14' THEN 150 END,
                CASE m.codigo WHEN 'M8' THEN 400 WHEN 'M10' THEN 450 WHEN 'M14' THEN 500 END,
                CASE m.codigo
                    WHEN 'M8'  THEN 'Bolsas pequeñas y medianas'
                    WHEN 'M10' THEN 'Bolsas medianas'
                    WHEN 'M14' THEN 'Bolsas grandes y medianas'
                END
            FROM sipp.maquinas m WHERE m.codigo IN ('M8','M10','M14')
            ON CONFLICT (maquina_id) DO NOTHING;
        """))
        
        print("Running: INSERT INTO sipp.semanas_programacion global week")
        await conn.execute(text("""
            INSERT INTO sipp.semanas_programacion
              (maquina_id, fecha_inicio, fecha_fin, horas_disponibles, estado, es_global)
            SELECT
              NULL,
              date_trunc('week', CURRENT_DATE)::date,
              (date_trunc('week', CURRENT_DATE) + interval '4 days')::date,
              120.0,
              'EN_EJECUCION',
              TRUE
            WHERE NOT EXISTS (
              SELECT 1 FROM sipp.semanas_programacion WHERE es_global = TRUE AND estado = 'EN_EJECUCION'
            );
        """))
        
    print("All done.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run())
