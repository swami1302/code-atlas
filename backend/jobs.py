from uuid import UUID

from bullmq import Queue

from config import settings

# Queue name; the worker listens on the same one (Worker(INDEX_QUEUE, ...))
INDEX_QUEUE = "indexing"

# One shared queue client, like the Redis client in main.py
queue = Queue(INDEX_QUEUE, {"connection": settings.redis_url})


async def enqueue_index(snapshot_id: UUID) -> None:
    """Hand a snapshot to the worker. Safe to call again for the same snapshot:
    BullMQ ignores a jobId that is already waiting, retrying or running."""
    await queue.add(
        "index",
        {"snapshot_id": str(snapshot_id)},
        {
            "jobId": f"snapshot:{snapshot_id}",
            "attempts": 3,
            # Retries wait 5s, then 10s
            "backoff": {"type": "exponential", "delay": 5000},
            # Postgres index_jobs keeps the state; dropping finished jobs from Redis
            # lets the same jobId be queued again when a failed snapshot is retried
            "removeOnComplete": True,
            "removeOnFail": True,
        },
    )
