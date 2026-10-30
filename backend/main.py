from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text

from config import settings
from db import engine

app = FastAPI()

# One shared client; it keeps its own connection pool to Upstash.
redis = Redis.from_url(settings.redis_url)


@app.get("/health")
async def health():
    # Cheapest query: proves pool, network, SSL and login to Neon all work
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
    # PING proves network, TLS and auth to Upstash
    await redis.ping()
    return {"status": "ok", "database": "ok", "redis": "ok"}
