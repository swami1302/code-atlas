import asyncio
import logging
import tarfile
import tempfile
from pathlib import Path
from uuid import UUID

from bullmq import UnrecoverableError
from sqlalchemy import select

from db import SessionLocal
from github import RepoError, download_tarball
from models import Repository, RepoSnapshot

# The indexing pipeline for one snapshot. worker.py only handles the queue and job
# state; everything about turning a commit into searchable data lives here.

logger = logging.getLogger(__name__)


async def get_snapshot_ref(snapshot_id: UUID) -> tuple[str, str, str]:
    """owner, name and commit_sha of a snapshot. Read from Postgres (the source of
    truth) rather than copied into the BullMQ job, so the two can't disagree."""
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(Repository.owner, Repository.name, RepoSnapshot.commit_sha)
                .join(RepoSnapshot, RepoSnapshot.repository_id == Repository.id)
                .where(RepoSnapshot.id == snapshot_id)
            )
        ).one()
    return row.owner, row.name, row.commit_sha


def unpack(archive: Path, dest: Path) -> list[Path]:
    """Extract the tarball into dest and return every file in it.
    Blocking disk work: called through asyncio.to_thread."""
    with tarfile.open(archive) as tar:
        # filter="data" refuses ../ paths, absolute paths, device files and links that
        # point outside dest, so a malicious archive can't write anywhere else
        tar.extractall(dest, filter="data")
    # GitHub archives hold exactly one top-level folder: <owner>-<name>-<sha7>/
    (root,) = dest.iterdir()
    return [path for path in root.rglob("*") if path.is_file()]


async def index_snapshot(snapshot_id: UUID) -> None:
    owner, name, sha = await get_snapshot_ref(snapshot_id)
    logger.info("Indexing %s/%s at %s", owner, name, sha[:7])

    # Everything on disk lives in this folder and is deleted when the block ends,
    # even if indexing fails. Only the results are kept (in Postgres, next steps).
    with tempfile.TemporaryDirectory(prefix="code-atlas-") as tmp:
        archive = Path(tmp) / "repo.tar.gz"
        try:
            size = await download_tarball(owner, name, sha, archive)
        except RepoError as e:
            # Repo gone/private or too large: a retry can't fix it, so tell BullMQ
            # to skip the remaining attempts
            raise UnrecoverableError(str(e)) from e

        # Unpacking is slow, blocking disk work. Running it in a thread keeps the
        # event loop free, so BullMQ can keep renewing its lock on the job.
        files = await asyncio.to_thread(unpack, archive, Path(tmp) / "src")
        logger.info("Downloaded %.1f MB, extracted %d files", size / 1e6, len(files))
