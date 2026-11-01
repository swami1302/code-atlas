from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

# One engine (connection pool) for the whole app.
# pool_pre_ping: Neon suspends idle compute, so test a connection before reusing it.
engine = create_async_engine(settings.database_url, pool_pre_ping=True)

# Opens one session (unit of work) per request.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# FastAPI dependency: one session per request, closed afterwards (even on errors).
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
