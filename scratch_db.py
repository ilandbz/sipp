import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = 'postgresql+asyncpg://postgres:password123%40P@localhost:5432/postgres'

async def main():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        res = await conn.execute(text("""SELECT column_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema='sipp' AND table_name='icc_cache'
ORDER BY ordinal_position;"""))
        print('Columns in sipp.icc_cache:')
        for row in res.fetchall():
            print(row)

asyncio.run(main())
