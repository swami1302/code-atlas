"""uuid primary keys

Switch repositories / repo_snapshots ids from bigint to UUIDv7.
The tables only hold test data, so they are dropped and recreated.
Also adds the current_snapshot_id foreign key, which the previous
migration never created (autogenerate put the use_alter FK inside
create_table, where it is silently skipped).

Revision ID: 57cce8452494
Revises: 8a9df620263a
Create Date: 2026-11-01 06:11:16.172766

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "57cce8452494"
down_revision: str | Sequence[str] | None = "8a9df620263a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_tables(use_uuid: bool) -> None:
    id_type = postgresql.UUID(as_uuid=True) if use_uuid else sa.BigInteger()

    def id_column() -> sa.Column:
        if use_uuid:
            return sa.Column(
                "id", id_type, server_default=sa.text("uuidv7()"), nullable=False
            )
        return sa.Column("id", id_type, sa.Identity(always=False), nullable=False)

    def created_at() -> sa.Column:
        return sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        )

    op.create_table(
        "repositories",
        id_column(),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("default_branch", sa.String(), nullable=False),
        sa.Column("current_snapshot_id", id_type, nullable=True),
        created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repositories")),
        sa.UniqueConstraint("owner", "name", name=op.f("uq_repositories_owner_name")),
    )
    op.create_table(
        "repo_snapshots",
        id_column(),
        sa.Column("repository_id", id_type, nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_repo_snapshots_repository_id_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repo_snapshots")),
        sa.UniqueConstraint(
            "repository_id",
            "commit_sha",
            name=op.f("uq_repo_snapshots_repository_id_commit_sha"),
        ),
    )
    # Added after both tables exist, because the two tables reference each other
    op.create_foreign_key(
        op.f("fk_repositories_current_snapshot_id_repo_snapshots"),
        "repositories",
        "repo_snapshots",
        ["current_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )


def _drop_tables() -> None:
    # CASCADE also removes the circular current_snapshot_id foreign key
    op.execute("DROP TABLE IF EXISTS repo_snapshots, repositories CASCADE")


def upgrade() -> None:
    _drop_tables()
    _create_tables(use_uuid=True)


def downgrade() -> None:
    _drop_tables()
    _create_tables(use_uuid=False)
