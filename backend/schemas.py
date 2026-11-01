from uuid import UUID

from pydantic import BaseModel

# API request/response shapes (JSON). Database tables live in models.py.


class AddRepoRequest(BaseModel):
    url: str


class RepoResponse(BaseModel):
    repository_id: UUID
    owner: str
    name: str
    default_branch: str
    snapshot_id: UUID
    commit_sha: str
