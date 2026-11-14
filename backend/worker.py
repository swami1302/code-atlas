import asyncio
import logging
import signal
from uuid import UUID

from bullmq import Job, UnrecoverableError, Worker
from sqlalchemy import update

from config import settings
from db import SessionLocal
from indexing import index_snapshot
from jobs import INDEX_QUEUE
from log import setup_logging
from models import IndexJob

setup_logging("worker")
logger = logging.getLogger(__name__)


async def set_job(snapshot_id: UUID, **values) -> None:
    """Update this snapshot's index_jobs row."""
    async with SessionLocal() as session:
        await session.execute(
            update(IndexJob).where(IndexJob.snapshot_id == snapshot_id).values(**values)
        )
        await session.commit()


async def process(job: Job, token: str) -> None:
    """Called by BullMQ once per attempt. Raising an error makes BullMQ retry
    (until job.attempts is used up); returning normally completes the job."""
    snapshot_id = UUID(job.data["snapshot_id"])

    # attempts + 1 in SQL: counts every run, also across manual retries
    await set_job(snapshot_id, state="processing", attempts=IndexJob.attempts + 1)

    try:
        await index_snapshot(snapshot_id)
    except Exception as e:
        # attemptsMade = failures before this run, so +1 is this run's number
        attempt = job.attemptsMade + 1
        # UnrecoverableError: BullMQ skips the remaining retries, so it's final too
        last = attempt >= job.attempts or isinstance(e, UnrecoverableError)
        # Only the last failure is final; until then the row stays processing
        await set_job(
            snapshot_id,
            state="failed" if last else "processing",
            error=f"{type(e).__name__}: {e}",
        )
        logger.exception(
            "Snapshot %s failed (attempt %d of %d)", snapshot_id, attempt, job.attempts
        )
        raise

    await set_job(snapshot_id, state="completed", error=None)
    logger.info("Snapshot %s indexed", snapshot_id)


async def main() -> None:
    # Created inside the running event loop: the Worker starts polling right away.
    # One job at a time (BullMQ's default concurrency is 1); scale by adding
    # worker containers.
    worker = Worker(INDEX_QUEUE, process, {"connection": settings.redis_url})

    # docker stop sends SIGTERM, a watchfiles reload sends SIGINT
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    logger.info("Worker listening on queue %r", INDEX_QUEUE)
    await stop.wait()
    logger.info("Shutting down: finishing the current job first")
    await worker.close()  # waits for the running job, then disconnects


if __name__ == "__main__":
    asyncio.run(main())
