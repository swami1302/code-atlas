from fastapi import FastAPI
from sqlalchemy import text

from db import engine

app = FastAPI()


@app.get("/health")
async def health():
    # Cheapest query: proves pool, network, SSL and login to Neon all work
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
    return {"status": "ok", "database": "ok"}
