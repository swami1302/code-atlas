from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import engine, get_session
from github import RepoError, resolve_repo
from models import Repository, RepoSnapshot
from schemas import AddRepoRequest, RepoResponse

app = FastAPI()

# One shared client; it keeps its own connection pool to Upstash.
redis = Redis.from_url(settings.redis_url)

Session = Annotated[AsyncSession, Depends(get_session)]


@app.get("/health")
async def health():
    # Cheapest query: proves pool, network, SSL and login to Neon all work
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
    # PING proves network, TLS and auth to Upstash
    await redis.ping()
    return {"status": "ok", "database": "ok", "redis": "ok"}


@app.post("/repos", status_code=status.HTTP_201_CREATED)
async def add_repo(body: AddRepoRequest, session: Session) -> RepoResponse:
    try:
        ref = await resolve_repo(body.url)
    except RepoError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    # Upserts: the UNIQUE constraints make re-submitting the same repo/commit reuse
    # the existing rows. DO UPDATE (not DO NOTHING) so RETURNING always gives the id.
    repository_id = await session.scalar(
        insert(Repository)
        .values(owner=ref.owner, name=ref.name, default_branch=ref.default_branch)
        .on_conflict_do_update(
            index_elements=[Repository.owner, Repository.name],
            set_={"default_branch": ref.default_branch},
        )
        .returning(Repository.id)
    )
    snapshot_id = await session.scalar(
        insert(RepoSnapshot)
        .values(repository_id=repository_id, commit_sha=ref.commit_sha)
        .on_conflict_do_update(
            index_elements=[RepoSnapshot.repository_id, RepoSnapshot.commit_sha],
            set_={"commit_sha": ref.commit_sha},
        )
        .returning(RepoSnapshot.id)
    )
    await session.commit()

    return RepoResponse(
        repository_id=repository_id,
        owner=ref.owner,
        name=ref.name,
        default_branch=ref.default_branch,
        snapshot_id=snapshot_id,
        commit_sha=ref.commit_sha,
    )
