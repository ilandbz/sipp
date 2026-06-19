import asyncio
from sqlalchemy import text
from app.core.database import engine

async def update_db():
    async with engine.begin() as conn:
        # TAREA 1
        await conn.execute(text("DELETE FROM sipp.setup_penalizaciones;"))
        
        await conn.execute(text("""
        INSERT INTO sipp.setup_penalizaciones 
            (tipo_cambio, minutos, descripcion, activo) VALUES
        ('CAMBIO_COLOR_LAVADO_ESTACION', 45, 'Lavado de esmeriles por cambio de color', true),
        ('CAMBIO_CILINDRO_IMPRESION', 30, 'Desmontaje y montaje de cilindro', true),
        ('CAMBIO_CLISE', 17.5, 'Cambio de clisé de impresión', true),
        ('CAMBIO_MATERIAL', 25, 'Cambio de tipo o gramaje de papel', true),
        ('CAMBIO_FORMATO_M10_M14', 480, 'Cambio de medida en M10 o M14 (siempre 8h)', true),
        ('CAMBIO_FORMATO_COMPLETO', 480, 'Cambio de medida sin excepción', true);
        """))
        
        await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS sipp.setup_cambio_medida_m8 (
            id SERIAL PRIMARY KEY,
            bolsa_origen INT NOT NULL,
            bolsa_destino INT NOT NULL,
            minutos NUMERIC(7,2) NOT NULL,
            descripcion TEXT,
            UNIQUE(bolsa_origen, bolsa_destino)
        );
        """))
        
        await conn.execute(text("""
        INSERT INTO sipp.setup_cambio_medida_m8 
            (bolsa_origen, bolsa_destino, minutos, descripcion) VALUES
        (5, 6, 30, '0.5h - jugada mínima'),
        (6, 5, 30, '0.5h - jugada mínima'),
        (5, 8, 240, '4h - cambio mediano'),
        (8, 5, 240, '4h - cambio mediano'),
        (5, 10, 420, '7h - cambio grande'),
        (10, 5, 420, '7h - cambio grande'),
        (5, 12, 480, '8h - cambio completo'),
        (12, 5, 480, '8h - cambio completo'),
        (6, 8, 240, '4h - cambio mediano'),
        (8, 6, 240, '4h - cambio mediano'),
        (6, 10, 240, '4h - jugada extendida'),
        (10, 6, 240, '4h - jugada extendida'),
        (6, 12, 480, '8h - cambio completo'),
        (12, 6, 480, '8h - cambio completo'),
        (8, 10, 480, '8h - cambio completo en M8'),
        (10, 8, 480, '8h - cambio completo en M8'),
        (8, 12, 480, '8h - cambio completo'),
        (12, 8, 480, '8h - cambio completo'),
        (10, 12, 300, '5h - cambio grande'),
        (12, 10, 300, '5h - cambio grande')
        ON CONFLICT (bolsa_origen, bolsa_destino) DO UPDATE
        SET minutos = EXCLUDED.minutos;
        """))

        # TAREA 5: merma_pct column
        try:
            await conn.execute(text("""
                ALTER TABLE sipp.ordenes_fabricacion 
                ADD COLUMN IF NOT EXISTS merma_pct NUMERIC(5,2) DEFAULT 2.5;
            """))
        except Exception as e:
            print("Error adding merma_pct:", e)

    print("DB migration completed.")

if __name__ == "__main__":
    asyncio.run(update_db())
