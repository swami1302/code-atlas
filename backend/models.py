from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    MetaData,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    owner: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    default_branch: Mapped[str] = mapped_column(String)
    # The live snapshot chat uses; switched in one UPDATE when a re-index completes.
    # use_alter: the two tables reference each other, so this FK is added after both exist.
    current_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("repo_snapshots.id", use_alter=True, ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RepoSnapshot(Base):
    """A repository at one exact commit. Files and chunks will belong to a snapshot."""

    __tablename__ = "repo_snapshots"
    __table_args__ = (UniqueConstraint("repository_id", "commit_sha"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE")
    )
    commit_sha: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
