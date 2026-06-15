from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Crear motor asíncrono con NullPool
engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=settings.DEBUG
)

async def get_session() -> AsyncSession:
    """
    Dependency generator that yields an async SQLModel session.
    """
    async with AsyncSession(engine) as session:
        yield session
