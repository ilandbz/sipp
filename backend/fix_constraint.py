import asyncio
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text
from app.core.database import engine

async def main():
    async with AsyncSession(engine) as session:
        await session.execute(text("ALTER TABLE sipp.semanas_programacion DROP CONSTRAINT IF EXISTS semanas_programacion_maquina_id_fecha_inicio_key;"))
        await session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_semana_global_unica ON sipp.semanas_programacion(fecha_inicio) WHERE es_global = TRUE AND maquina_id IS NULL;"))
        await session.commit()
        print("Constraint fixed")

if __name__ == "__main__":
    asyncio.run(main())
