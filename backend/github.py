import re
from dataclasses import dataclass

import httpx

GITHUB_API = "https://api.github.com"

# https://github.com/owner/repo, optionally with www., .git or a trailing slash
GITHUB_URL = re.compile(
    r"^https?://(?:www\.)?github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


class RepoError(Exception):
    """A repository URL we can't index (bad URL, not found, private, rate limited)."""


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str
    default_branch: str
    commit_sha: str


def parse_github_url(url: str) -> tuple[str, str]:
    match = GITHUB_URL.match(url.strip())
    if not match:
        raise RepoError(f"Not a GitHub repository URL: {url!r}")
    return match.group(1), match.group(2)


async def resolve_repo(url: str) -> RepoRef:
    """Turn a public GitHub URL into owner, name, default branch and the latest commit SHA."""
    owner, name = parse_github_url(url)

    async with httpx.AsyncClient(
        base_url=GITHUB_API,
        headers={"Accept": "application/vnd.github+json"},
        timeout=10,
    ) as client:
        repo = await _get(client, f"/repos/{owner}/{name}")
        branch = repo["default_branch"]
        commit = await _get(client, f"/repos/{owner}/{name}/commits/{branch}")

    # Use GitHub's spelling of owner/name (the URL may differ in case)
    return RepoRef(repo["owner"]["login"], repo["name"], branch, commit["sha"])


async def _get(client: httpx.AsyncClient, path: str) -> dict:
    response = await client.get(path)
    # Without a token, private repos look exactly like missing ones
    if response.status_code == 404:
        raise RepoError("Repository not found, or it is private")
    if response.status_code in (403, 429):
        raise RepoError("GitHub API rate limit hit; try again later")
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    import asyncio

    assert parse_github_url("https://github.com/swami1302/code-atlas") == (
        "swami1302",
        "code-atlas",
    )
    assert parse_github_url("https://github.com/a-b/my.repo.git/") == ("a-b", "my.repo")
    for bad in ["https://gitlab.com/a/b", "https://github.com/a", "github.com/a/b"]:
        try:
            parse_github_url(bad)
            raise AssertionError(f"accepted {bad}")
        except RepoError:
            pass
    print("URL parsing: ok")
    print(asyncio.run(resolve_repo("https://github.com/swami1302/code-atlas")))
