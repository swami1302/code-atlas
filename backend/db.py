from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import settings

# One engine (connection pool) for the whole app.
# pool_pre_ping: Neon suspends idle compute, so test a connection before reusing it.
engine = create_async_engine(settings.database_url, pool_pre_ping=True)

# Opens one session (unit of work) per request.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
