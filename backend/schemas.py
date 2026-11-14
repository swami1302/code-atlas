from uuid import UUID

from pydantic import BaseModel

# API request/response shapes (JSON). Database tables live in models.py.


class ApiResponse[T](BaseModel):
    """Envelope for every successful response. Errors use the same keys, with
    "errors" instead of "data" (see errors.py)."""

    success: bool = True
    message: str
    data: T | None = None


class AddRepoRequest(BaseModel):
    url: str


class RepoResponse(BaseModel):
    repository_id: UUID
    owner: str
    name: str
    default_branch: str
    snapshot_id: UUID
    commit_sha: str
    job_id: UUID
    state: str
