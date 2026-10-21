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

## Decisions so far

- Single GitHub repo: `frontend/` (Next.js, pnpm) and `backend/` (one uv project, no uv workspace).
- The worker is the same backend code and Docker image as the API, started with a different command. Added in Phase 1, not before.
- Postgres on Neon and Redis on Upstash, for development as well as deployment.
- Redis + BullMQ are kept on purpose, to learn the infrastructure. Postgres `index_jobs` stays the source of truth for job state.
- Docker Compose grows by phase. Phase 0: `backend` + `frontend` services only.
- In dev, compose overrides the containers' command with `sleep infinity`. The user starts the servers manually with `docker compose exec`.
- Dockerfiles are multi-stage, with a `dev` target (used by compose) and a `prod` target (for Phase 6).
- Only install packages when a phase needs them. Currently the backend has only `fastapi[standard]`.
- Schema fixes agreed: `snapshot_id` on `chunks`, a separate `chunk_embeddings` table (untyped `vector`, one partial HNSW index per model), keyword search with the `simple` config and Python-side identifier splitting.
