import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:vygpack@localhost:5432/sipp")
engine = create_async_engine(db_url)

async def main():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='sipp' AND table_name='icc_cache'"))
        columns = [r[0] for r in res.fetchall()]
        print("COLUMNS:", columns)
        
        if "costo_setup_min" not in columns:
            print("Adding costo_setup_min...")
            await conn.execute(text("ALTER TABLE sipp.icc_cache ADD COLUMN costo_setup_min NUMERIC(10,2)"))
            await conn.commit()
            print("Added.")
        if "calculado_en" not in columns:
            print("Adding calculado_en...")
            await conn.execute(text("ALTER TABLE sipp.icc_cache ADD COLUMN calculado_en TIMESTAMP"))
            await conn.commit()
            print("Added.")

asyncio.run(main())
