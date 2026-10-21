# Code Atlas

A codebase intelligence assistant. Connect a GitHub repository, index its source code, and ask questions about it. Answers cite the exact files and line ranges they are based on, and say so when the repository does not contain enough information.

Example questions:

- Where is authentication implemented?
- Explain this project to a new developer.
- What does this function do, and where is it used?

> **Status:** Phase 0 (foundation) in progress. The app does not answer questions yet.

## Tech stack

| Part | Technology |
|---|---|
| Frontend | Next.js, React, Tailwind CSS, pnpm |
| Backend | FastAPI, Python 3.14, uv |
| Database | Postgres + pgvector on Neon (planned) |
| Queue and cache | Redis on Upstash + BullMQ (planned) |
| Local development | Docker Compose |

## Project structure

```text
code-atlas/
├── frontend/            # Next.js app
├── backend/             # FastAPI app (uv project)
└── docker-compose.yml   # runs both apps for local development
```

## Getting started

Requirements: Docker Desktop.

```bash
# 1. Build the images and start the containers (they stay idle)
docker compose up -d --build

# 2. Start the backend (http://localhost:8000)
docker compose exec backend uvicorn main:app --host 0.0.0.0 --reload

# 3. In a second terminal, start the frontend (http://localhost:3000)
docker compose exec frontend pnpm dev
```

Check the backend:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Stop everything:

```bash
docker compose down
```

The source folders are mounted into the containers, so code changes reload without a rebuild. Rebuild with `docker compose up -d --build -V` after adding a package.

## Roadmap

- [ ] **Phase 0: Foundation.** Docker setup, database and Redis connections, migrations, tooling.
- [ ] **Phase 1: Repository ingestion.** Clone public repositories, parse code with Tree-sitter, chunk and embed it.
- [ ] **Phase 2: First working RAG chat.** Hybrid search (vector + keyword) and answers with file and line citations.
- [ ] **Phase 3: RAG evaluation.** A benchmark dataset and published retrieval and answer quality metrics.
- [ ] **Phase 4: Authentication and private repositories.** GitHub OAuth and repository-level access control.
- [ ] **Phase 5: Advanced code intelligence.** Reference graph and agentic retrieval.
- [ ] **Phase 6: Production-style packaging.** Production images, CI/CD.
- [ ] **Phase 7: AWS deployment.** A public demo.
