import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import engine, get_session
from errors import register_error_handlers
from github import RepoError, resolve_repo
from jobs import enqueue_index
from log import setup_logging
from models import IndexJob, Repository, RepoSnapshot
from schemas import AddRepoRequest, ApiResponse, RepoResponse

setup_logging("api")
logger = logging.getLogger(__name__)

app = FastAPI()
register_error_handlers(app)

# One shared client; it keeps its own connection pool to Upstash.
redis = Redis.from_url(settings.redis_url)

Session = Annotated[AsyncSession, Depends(get_session)]


@app.get("/health")
async def health() -> ApiResponse[dict[str, str]]:
    # Cheapest query: proves pool, network, SSL and login to Neon all work
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
    # PING proves network, TLS and auth to Upstash
    await redis.ping()
    return ApiResponse(message="Healthy", data={"database": "ok", "redis": "ok"})


# Message per job state for POST /repos ("failed" is reset to "queued" before this)
REPO_MESSAGES = {
    "queued": "Repository queued for indexing",
    "processing": "Repository is being indexed",
    "completed": "Repository already indexed",
}


# 202 Accepted: the indexing itself happens later, in the worker
@app.post("/repos", status_code=status.HTTP_202_ACCEPTED)
async def add_repo(
    body: AddRepoRequest, session: Session, response: Response
) -> ApiResponse[RepoResponse]:
    try:
        ref = await resolve_repo(body.url)
    except RepoError as e:
        logger.warning("Rejected repo %s: %s", body.url, e)
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
    # One job per snapshot; RETURNING IndexJob gives the whole row as an ORM object
    job = await session.scalar(
        insert(IndexJob)
        .values(snapshot_id=snapshot_id)
        .on_conflict_do_update(
            index_elements=[IndexJob.snapshot_id],
            set_={"snapshot_id": snapshot_id},
        )
        .returning(IndexJob)
    )
    # Re-submitting a failed snapshot is the retry
    if job.state == "failed":
        job.state, job.error = "queued", None
    await session.commit()

    # Only after the commit, so the worker never gets a job whose row isn't saved.
    # A queued job goes to BullMQ every time: if Redis was down on the first try,
    # re-submitting fixes it, and BullMQ ignores the duplicate if it's already there.
    if job.state == "queued":
        await enqueue_index(snapshot_id)
    if job.state == "completed":
        response.status_code = status.HTTP_200_OK

    logger.info(
        "%s/%s at %s: job %s (snapshot %s)",
        ref.owner,
        ref.name,
        ref.commit_sha[:7],
        job.state,
        snapshot_id,
    )
    return ApiResponse(
        message=REPO_MESSAGES[job.state],
        data=RepoResponse(
            repository_id=repository_id,
            owner=ref.owner,
            name=ref.name,
            default_branch=ref.default_branch,
            snapshot_id=snapshot_id,
            commit_sha=ref.commit_sha,
            job_id=job.id,
            state=job.state,
        ),
    )
