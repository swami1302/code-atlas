import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Postgres 18 built-in: time-ordered UUIDs keep primary-key indexes compact.
UUIDV7 = text("uuidv7()")


# Every table class subclasses Base; Alembic reads Base.metadata for autogenerate.
class Base(DeclarativeBase):
    # Predictable constraint names, so Alembic can drop/alter them later
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Repository(Base):
    """A GitHub project (e.g. fastapi/fastapi). One row per repo, shared by all users."""

    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("owner", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=UUIDV7)
    owner: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    default_branch: Mapped[str] = mapped_column(String)
    # The live snapshot chat uses; switched in one UPDATE when a re-index completes.
    # use_alter: the two tables reference each other, so this FK is added after both exist.
    # Autogenerate gets this wrong: migrations must add it with op.create_foreign_key.
    current_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repo_snapshots.id", use_alter=True, ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RepoSnapshot(Base):
    """A repository at one exact commit. Files and chunks will belong to a snapshot."""

    __tablename__ = "repo_snapshots"
    __table_args__ = (UniqueConstraint("repository_id", "commit_sha"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=UUIDV7)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE")
    )
    commit_sha: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Chunk(Base):
    """One searchable piece of a file in one snapshot: a function, method or class,
    a run of loose code, or a few paragraphs of a doc. The unit of search and
    citation; its vector will live in chunk_embeddings."""

    __tablename__ = "chunks"
    # Chunks never overlap, so only one starts on a given line of a file. The index
    # (snapshot_id first) also serves "all chunks of this snapshot": every search
    # and the delete before a retry filter on it.
    __table_args__ = (UniqueConstraint("snapshot_id", "path", "start_line"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=UUIDV7)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repo_snapshots.id", ondelete="CASCADE")
    )
    path: Mapped[str] = mapped_column(Text)  # inside the repo, e.g. backend/worker.py
    language: Mapped[str] = mapped_column(String(20))
    # 1-based, inclusive: the citation backend/worker.py:20-26
    start_line: Mapped[int]
    end_line: Mapped[int]
    # e.g. "set_job" or "Context.__init__"; NULL for loose code and docs
    symbol: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str | None] = mapped_column(String(20))  # function, method, class, ...
    # Only on pieces 2+ of a split function: its def line(s), which those pieces lack
    signature: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)  # the exact lines, shown in citations
    # sha256 hex of the text that gets embedded (path > symbol, signature, content):
    # the same hash in a later commit means the existing vector is reused
    content_hash: Mapped[str] = mapped_column(String(64))


JOB_STATES = ("queued", "processing", "completed", "failed")


class IndexJob(Base):
    """Indexing work for one snapshot. Postgres is the source of truth for job state;
    BullMQ only delivers the job to a worker."""

    __tablename__ = "index_jobs"
    __table_args__ = (
        # One job per snapshot: a retry reuses the row (BullMQ jobId = snapshot:<id>)
        UniqueConstraint("snapshot_id"),
        CheckConstraint(f"state IN {JOB_STATES}", name="state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=UUIDV7)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repo_snapshots.id", ondelete="CASCADE")
    )
    state: Mapped[str] = mapped_column(String(20), server_default="queued")
    attempts: Mapped[int] = mapped_column(server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # onupdate only fires on SQLAlchemy UPDATEs, not on raw SQL
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
