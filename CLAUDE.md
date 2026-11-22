# Code Atlas

Codebase Intelligence Assistant: a RAG app that answers questions about a GitHub repo with file and line citations. Full plan: `codebase-intelligence-interactive-plan.md`.

## Goal

This is a resume project. The user must understand every piece well enough to explain it confidently to a recruiter or interviewer. Learning and understanding matter more than speed.

## How to work with the user

- The user stays in control. Do not do several steps in one shot, even when given full access.
- Give suggestions in small chunks: one step or one decision at a time. Wait for the user to confirm the direction before moving on.
- For each step, explain what it does and why, briefly, so the user can explain it later.
- Do not over-complicate. Add a tool, package, or service only in the phase that needs it.
- Do not create files or folders unless the user asks for it in that turn.
- Decide yourself when confident (roughly 80%+) and state the decision in the explanation; plans can be revisited later. Ask only when genuinely unsure (roughly below 60%).
- Use the AskUserQuestion tool only for real design or functionality decisions you are unsure about (below roughly 60%), e.g. while architecting a plan. Never use it for routine questions like "start the next step?", "go ahead?" or "commit first?": end the reply with the proposed next step as plain text and stop. The user often asks several questions about earlier parts before moving on; question popups interrupt that.
- Skills to use without being asked:
  - Planning a feature or step: `/architect`.
  - Reviewing code or a plan: `/ponytail:ponytail-review`.
  - Auditing the repo: `/ponytail:ponytail-audit`.
  - Fixing something that broke or went wrong: `/recover`.
  - After building any UI component: `/imprint`.
- Don't run ruff by hand after edits: the pre-commit hook runs it on commit.
- Never touch Alembic migrations: do not generate (`alembic revision`), edit, format, apply (`alembic upgrade`) or roll back (`alembic downgrade`) them. Change the models only, then give the user the exact commands to run and what to check after each one.
- After every code edit, explain the code: what each part does and why, in words the user can repeat in an interview. This is a resume project; being able to explain it is the end goal.

## Decisions so far

- Single GitHub repo: `frontend/` (Next.js, pnpm) and `backend/` (one uv project, no uv workspace).
- The worker is the same backend code and Docker image as the API, started with a different command. Added in Phase 1, not before.
- Postgres on Neon and Redis on Upstash, for development as well as deployment.
- Redis + BullMQ are kept on purpose, to learn the infrastructure. Postgres `index_jobs` stays the source of truth for job state.
- Docker Compose grows by phase. Phase 0: `backend` + `frontend` services only.
- In dev, both containers auto-start their servers from the Dockerfile `dev` target's `CMD` (uvicorn `--reload`, `pnpm dev`). Logs via `docker compose logs -f <service>`.
- Dockerfiles are multi-stage, with a `dev` target (used by compose) and a `prod` target (for Phase 6).
- Only install packages when a phase needs them. Backend: `fastapi[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `bullmq`; dev: `ruff`. Frontend dev adds `prettier`. No pytest yet (add when real logic arrives in Phase 1).
- Install packages inside the container (`docker compose exec backend uv add ...`) so the lockfile and the container venv stay in sync.
- Config: `backend/config.py` (`Settings`, pydantic-settings) reads `backend/.env`; every new variable goes in `Settings` and `.env.example`. `DATABASE_URL` uses `postgresql+asyncpg://`, the direct Neon host and `?ssl=require`; `REDIS_URL` uses `rediss://`.
- Database: `backend/db.py` holds one async engine (`pool_pre_ping=True`) and `SessionLocal`. Add a `get_session` FastAPI dependency when the first real route needs it.
- Migrations: Alembic in `backend/migrations/` (async template, URL from `settings`). The first migration only enables pgvector; tables are added in the phase that uses them, starting in Phase 1.
- BullMQ (Python, 3.4.6) verified on Upstash: retries, exponential backoff, `job.updateProgress` via `QueueEvents`, graceful `worker.close()`.
- Pre-commit: root `package.json` holds husky + lint-staged only (no Node services planned). The hook runs on the host: ruff for `backend/`, ESLint + Prettier for `frontend/`.
- Neon: a single branch is fine (resume project, no dev/prod branch split).
- Product direction: agentic RAG + MCP. Three tools (`search_code`, `read_file`, `grep`), all reading Postgres chunks; one hand-written agent loop (no framework) where single-shot RAG and the grep-only agent are the same loop with fewer tools; an MCP server (official `mcp` SDK, in FastAPI, public repos only) exposes the same tools. The agent calls tools in-process, not through MCP.
- Embeddings: Google `gemini-embedding-2` at 1536 dims (model key `"gemini-embedding-2:1536"`) via `google-genai`; `GEMINI_API_KEY` in `backend/.env`. Free tier, so public repos only. A local model (jina-embeddings-v2-base-code) comes in a later phase for the evaluation comparison.
- Schema fixes agreed: `snapshot_id` on `chunks`, a separate `chunk_embeddings` table (untyped `vector`, one partial HNSW index per model), keyword search with the `simple` config and Python-side identifier splitting.
