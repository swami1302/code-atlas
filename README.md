# Code Atlas

A codebase intelligence assistant. Connect a GitHub repository, index its source code, and ask questions about it. Answers cite the exact files and line ranges they are based on, and say so when the repository does not contain enough information.

Example questions:

- Where is authentication implemented?
- Explain this project to a new developer.
- What does this function do, and where is it used?

> **Status:** Phase 0 (foundation) complete. The app does not answer questions yet.

## Tech stack

| Part | Technology |
|---|---|
| Frontend | Next.js, React, Tailwind CSS, pnpm |
| Backend | FastAPI, Python 3.14, uv |
| Database | Postgres + pgvector on Neon, SQLAlchemy (async) + asyncpg, Alembic migrations |
| Queue and cache | Redis on Upstash, BullMQ |
| Code quality | ruff (Python), ESLint + Prettier (frontend), husky + lint-staged pre-commit hook |
| Local development | Docker Compose |

## Project structure

```text
code-atlas/
├── frontend/              # Next.js app
├── backend/               # FastAPI app (uv project)
│   ├── main.py            # API routes
│   ├── config.py          # typed settings, read from .env
│   ├── db.py              # async SQLAlchemy engine + sessions
│   ├── models.py          # SQLAlchemy models (Base)
│   └── migrations/        # Alembic migrations
├── .husky/pre-commit      # runs lint-staged on every commit
├── package.json           # root dev tools only (husky, lint-staged)
└── docker-compose.yml     # runs both apps for local development
```

## Getting started

### Requirements

- Docker Desktop
- [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/) on your machine (the pre-commit hook runs outside Docker)
- A [Neon](https://neon.tech) Postgres database and an [Upstash](https://upstash.com) Redis database (free tiers are enough)

### Setup

```bash
# 1. Secrets: copy the template and fill in real values
cp backend/.env.example backend/.env

# 2. Install the git hook (husky + lint-staged) and local tools
pnpm install
(cd backend && uv sync)
(cd frontend && pnpm install)

# 3. Build and start both apps (servers start automatically)
docker compose up -d --build

# 4. Create the database schema
docker compose exec backend alembic upgrade head
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (API docs at http://localhost:8000/docs)

Notes for `backend/.env`:

- `DATABASE_URL` must use the asyncpg driver and the direct (non-pooler) Neon host: `postgresql+asyncpg://USER:PASSWORD@HOST/DATABASE?ssl=require`
- `REDIS_URL` is the URL only, with `rediss://` for TLS, not the `redis-cli` command Upstash shows.

### Check that everything is connected

```bash
curl http://localhost:8000/health
# {"status":"ok","database":"ok","redis":"ok"}
```

## Development workflow

Code changes reload automatically: the source folders are mounted into the containers.

```bash
docker compose logs -f backend      # follow server output (or: frontend)
docker compose down                 # stop everything
```

| What changed | Command |
|---|---|
| `.py` / frontend code | nothing, hot reload |
| `backend/.env` | `docker compose restart backend` |
| `docker-compose.yml` | `docker compose up -d` |
| `Dockerfile` or dependencies | `docker compose up -d --build -V <service>` |

Adding packages (updates the lockfile and the running container):

```bash
docker compose exec backend uv add <package>
docker compose exec frontend pnpm add <package>
```

Database migrations:

```bash
docker compose exec backend alembic revision -m "describe change"
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
```

### Pre-commit hook

On every `git commit`, lint-staged runs on the staged files only, re-stages any fixes, and blocks the commit if something can't be fixed automatically:

- Python: `ruff check --fix`, `ruff format`
- TypeScript / JavaScript: `eslint --fix`, `prettier --write`
- JSON / CSS / Markdown (frontend): `prettier --write`

## Roadmap

- [x] **Phase 0: Foundation.** Docker setup, Neon and Upstash connections, Alembic migrations, code-quality tooling.
- [ ] **Phase 1: Repository ingestion.** Clone public repositories, parse code with Tree-sitter, chunk and embed it.
- [ ] **Phase 2: First working RAG chat.** Hybrid search (vector + keyword) and answers with file and line citations.
- [ ] **Phase 3: RAG evaluation.** A benchmark dataset and published retrieval and answer quality metrics.
- [ ] **Phase 4: Authentication and private repositories.** GitHub OAuth and repository-level access control.
- [ ] **Phase 5: Advanced code intelligence.** Reference graph and agentic retrieval.
- [ ] **Phase 6: Production-style packaging.** Production images, CI/CD.
- [ ] **Phase 7: AWS deployment.** A public demo.
