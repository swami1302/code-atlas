---
author: Project Roadmap
title: Codebase Intelligence Assistant --- Interactive Project Plan
---

# Codebase Intelligence Assistant

> **Goal:** Build a portfolio-ready Full-Stack AI application that helps
> developers understand a GitHub repository through source-grounded
> answers, code citations, and measurable RAG evaluation.

**Project status:** Planning\
**Primary audience:** AI Engineer / Full-Stack AI Engineer recruiters\
**Initial approach:** Build the core RAG workflow locally on public
repositories first. Add authentication, private repositories, and AWS
deployment only after retrieval and evaluation work.

## 1. Project definition

### What it does

Users connect a GitHub repository, index its source code, and ask
questions.

**MVP questions (lookup and explain):**

-   Where is authentication implemented?
-   Explain this project to a new developer.
-   Why might this endpoint return a 401?
-   What does this function/class do and where is it used?

**Advanced questions (need the reference graph or agentic retrieval,
Phase 5):**

-   Trace a request from the frontend to the backend and database.
-   Which files call this function?
-   What could break if this database model changes?

Answers cite the relevant files and line ranges, explain the evidence,
and say when the repository does not contain enough information.

### What makes it stand out

-   [ ] Code-aware indexing (Tree-sitter) rather than naive fixed-size
    text splitting.
-   [ ] Hybrid retrieval: vector similarity + identifier-aware keyword
    search, fused with Reciprocal Rank Fusion (RRF).
-   [ ] Agentic retrieval (LLM tool loop over search/grep/read_file)
    benchmarked against vector-only and hybrid retrieval.
-   [ ] Verified file and line citations that open the exact source
    location.
-   [ ] A repeatable evaluation dataset with published results.
-   [ ] Incremental re-indexing by commit SHA and content hash.
-   [ ] GitHub OAuth and repository-level access control.
-   [ ] Reproducible Docker setup, CI/CD, and a public demo.

## 2. Technology stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Next.js, TypeScript (pnpm) | Application UI |
| Server state | TanStack Query | API requests, caching, loading/error states |
| Client state | URL params + `useState` | UI-only state. Add Zustand only if shared client state appears |
| UI | Tailwind CSS, shadcn/ui | Consistent interface |
| API | Python, FastAPI, Pydantic | REST endpoints and SSE streaming |
| ORM / migrations | SQLAlchemy 2.x, Alembic | Database access and schema changes |
| RAG orchestration | Plain Python (no framework) | Retrieval, fusion, prompting, citations — written by hand to show understanding |
| Python environment | uv (workspace) | Dependencies, lockfile, virtualenv |
| Code parsing | Tree-sitter | Parse code into functions/classes |
| Vector search | PostgreSQL + pgvector (HNSW index) | Store and retrieve embeddings |
| Keyword search | PostgreSQL full-text search with identifier splitting (+ `pg_trgm` if needed) | Exact symbol and identifier search |
| Background jobs | BullMQ (Python package) + Redis | Async indexing in a separate Python worker service |
| Repository storage | Local disk initially; S3 if needed | Repository snapshots (commit tarballs) |
| Answer generation | OpenRouter (OpenAI-compatible API) | Compare LLMs through one API |
| Embeddings | Local code-tuned embedding model | Avoid per-token charges; compare two models in evaluation |
| Authentication | GitHub OAuth (GitHub App) + JWT | Sign-in and repository access |
| Testing | pytest, HTTPX, frontend tests | Unit and integration tests |
| Containers | Docker, Docker Compose | Reproducible local environment |
| CI/CD | GitHub Actions | Test, build, publish images, deploy |
| Image registry | Docker Hub | Versioned images |
| Cloud | AWS | Host the portfolio demo |

**Architecture notes:**

-   OpenRouter is the answer-generation provider, not the whole RAG
    system. Keep all LLM calls in one module (`core/rag/llm.py`) so a
    direct OpenAI or Anthropic client can be swapped in later.
-   The worker is Python, not Node. It runs Tree-sitter and the
    embedding model, which must be the same code the API uses to embed
    queries. One language for the RAG core avoids duplicated logic and
    mismatched vectors.
-   Each service runs in its own container (web, api, worker, postgres,
    redis). This is already a service-oriented architecture; services do
    not need different languages to count as separate services.

## 3. System architecture

``` mermaid
flowchart TD
    U[Developer] --> FE[Next.js frontend]
    FE --> API[FastAPI API]
    API --> AUTH[GitHub OAuth + JWT]
    API --> DB[(PostgreSQL + pgvector)]
    API --> Q[BullMQ queue]
    Q --> R[(Redis)]
    R --> W[Python worker service]
    W --> GH[GitHub commit tarball]
    W --> PARSE[Tree-sitter parsing + chunking]
    PARSE --> EMB[Local embedding model]
    EMB --> DB
    API --> RET[Hybrid / agentic retrieval]
    RET --> DB
    RET --> CTX[Context assembly + chunk-ID citations]
    CTX --> LLM[OpenRouter LLM]
    LLM --> API
    API -->|SSE stream| FE
```

### Request flow

1.  User submits a public repository URL (later: signs in with GitHub
    and picks an authorized repository).
2.  API records the repository and creates an indexing job in BullMQ.
3.  Worker downloads the commit tarball, filters out
    binary/generated/secret files, and parses supported files.
4.  Code is chunked by function/class with a contextual header; chunks
    are embedded and keyword-indexed.
5.  Chunks, embeddings, tsvectors, commit SHA, paths, and line ranges
    are stored in PostgreSQL.
6.  A question triggers hybrid (or agentic) retrieval and context
    assembly within a token budget.
7.  The LLM answers using retrieved evidence and cites chunk IDs; the
    API maps them to file paths and line ranges.
8.  Logs record retrieval configuration, latency, token usage, and user
    feedback.

## 4. Data model

| Table | Key columns |
|---|---|
| `users` | id, github_id, login, created_at |
| `repositories` | id, owner, name, default_branch, is_private |
| `repo_snapshots` | id, repository_id, commit_sha, status, indexed_at (unique repository_id + commit_sha) |
| `files` | id, snapshot_id, path, language, content_hash, size |
| `chunks` | id, file_id, symbol_name, symbol_kind, start_line, end_line, content, content_hash, embedding `vector`, search_tsv `tsvector` |
| `index_jobs` | id, snapshot_id, state (queued/processing/completed/failed), error, attempts |
| `repo_access` | user_id, repository_id (Phase 4) |
| `conversations`, `messages` | chat history, cited chunk IDs per message |
| `eval_runs` | config JSON, metrics JSON, created_at |

Indexes: HNSW on `chunks.embedding`, GIN on `chunks.search_tsv`.
Public repositories are indexed once per commit SHA and shared across
users.

## 5. Build roadmap

Use the checkboxes as a project tracker. Complete the core workflow
before adding advanced features.

### Phase 0 --- Foundation

-   [ ] Create a public GitHub repository and initial README.
-   [ ] Set up the monorepo (see section 8): `apps/web` (pnpm),
    `services/api`, `services/worker`, `packages/core` (uv workspace).
-   [ ] Add Docker Compose for PostgreSQL + pgvector and Redis.
-   [ ] Configure uv, FastAPI, ruff, pytest; Next.js, TypeScript,
    ESLint, Prettier.
-   [ ] Add `.env.example`; ensure real secrets are ignored by Git.
-   [ ] Add Alembic and the initial schema (section 4).
-   [ ] Verify the BullMQ Python package supports what you need:
    retries, backoff, job progress, and graceful worker shutdown.

**Exit criteria:** A new developer can start the stack locally using
documented commands.

### Phase 1 --- Repository ingestion (public repositories)

-   [ ] Accept a public GitHub URL (CLI or API endpoint) and record the
    default branch and commit SHA.
-   [ ] Download the repository as a single commit tarball (avoids
    per-file API calls and rate limits).
-   [ ] Ignore `.git`, dependency folders, build outputs, binaries,
    lockfiles, oversized files, and likely secrets.
-   [ ] Support TypeScript, JavaScript, Python, and PHP code.
-   [ ] Index important non-code files with text chunking: README,
    Markdown docs, Dockerfile, YAML, SQL migrations, package manifests.
-   [ ] Parse code with Tree-sitter; chunk by function/class.
-   [ ] Add fallback chunks for top-level code (routes, config, module
    statements) that is not inside a function or class.
-   [ ] Split oversized functions and merge tiny ones.
-   [ ] Prepend a contextual header to each chunk before embedding: file
    path, language, class name, and function signature/docstring.
-   [ ] Generate embeddings with a local code-tuned embedding model.
-   [ ] Build the keyword index with identifier splitting
    (`getCurrentUser` → `get current user getcurrentuser`,
    `get_current_user` → `get current user get_current_user`).
-   [ ] Store chunks, vectors, and tsvectors in PostgreSQL.
-   [ ] Track job states: queued, processing, completed, failed.
-   [ ] Add retries, idempotency (repository + commit SHA), and
    embedding reuse by content hash.
-   [ ] Add ingestion tests using a small fixture repository.
-   [ ] Start writing benchmark questions (Phase 3) for your chosen
    repository while building this phase.

**Exit criteria:** A public repository is indexed and its files/chunks
can be inspected.

### Phase 2 --- First working RAG chat

-   [ ] Implement vector similarity retrieval.
-   [ ] Implement PostgreSQL full-text search for identifiers and
    symbols.
-   [ ] Fuse results with Reciprocal Rank Fusion (RRF).
-   [ ] Add repository and metadata filters.
-   [ ] Assemble context within a token budget.
-   [ ] Call the LLM through OpenRouter.
-   [ ] Label each context chunk with an ID (`[c1]`, `[c2]`, ...); the
    LLM cites IDs, and the API maps them to repository, path, line
    range, and commit SHA. Reject citations to chunks not in context.
-   [ ] Require evidence-based answers and abstention when evidence is
    insufficient.
-   [ ] Basic prompt-injection defence: wrap repository content as
    untrusted data and state this in the system prompt.
-   [ ] Build a chat UI with SSE streaming and clickable citations
    (GitHub permalink: `blob/<sha>/<path>#L10-L20`, or an in-app code
    viewer).
-   [ ] Persist conversations and messages in PostgreSQL.
-   [ ] Add tests for citation mapping, missing evidence, and retrieval
    boundaries.

**Exit criteria:** A user can ask an MVP question about an indexed
repository and verify the answer against the source.

### Phase 3 --- RAG evaluation

-   [ ] Finalize a benchmark of 30--50 questions for a repository you
    understand.
-   [ ] Record expected files/symbols/evidence for each question.
-   [ ] Include multi-file questions and questions with no answer in
    the repository.
-   [ ] Measure Recall@5 and MRR (add nDCG if ranking comparisons are
    useful).
-   [ ] Measure answer correctness and citation correctness through
    manual review.
-   [ ] Track latency and token usage/cost per query.
-   [ ] Compare retrieval strategies: vector-only vs hybrid (RRF) vs
    agentic retrieval (LLM tool loop with `search_code`, `grep`,
    `read_file`, `list_symbols`).
-   [ ] Compare chunking approaches, top-k values, and two embedding
    models.
-   [ ] Test a second, unfamiliar open-source repository.
-   [ ] Store experiment configuration and results (`eval/results/`)
    for reproducibility.
-   [ ] Publish a results table in the README.

**Do not invent metrics for the README or resume.** Report only results
measured with the documented dataset and method.

> **MVP line:** Phases 0--3 on public repositories are the MVP. Ship and
> document them before starting Phase 4.

### Phase 4 --- Authentication and private repositories

-   [ ] Implement GitHub sign-in using a GitHub App (fine-grained,
    read-only Contents permission, per-repository installation).
-   [ ] Issue short-lived JWT access tokens and an httpOnly refresh
    cookie.
-   [ ] Store users, GitHub identities, repositories, and repository
    access.
-   [ ] Keep GitHub tokens server-side and encrypted at rest; never send
    them to the browser.
-   [ ] Enforce authorization on every repository endpoint and inside
    retrieval queries (only chunks from repositories the user can
    access).
-   [ ] Add tests for unauthenticated access and cross-user access.
-   [ ] Optional, only if needed: email/password (Argon2id) or Google
    sign-in.

**Security note:** Signing in does not automatically grant repository
access. Request the minimum GitHub permissions, validate OAuth state,
and never expose provider tokens to the browser.

### Phase 5 --- Advanced code intelligence

-   [ ] Add reranking only if benchmark results justify it.
-   [ ] Build an import/reference graph for selected languages.
-   [ ] Add symbol and call lookup to support trace and impact
    questions.
-   [ ] Re-index when new commits arrive (GitHub compare API or
    webhook), reusing unchanged chunks by content hash.
-   [ ] Show indexing progress and failures in the UI.
-   [ ] Add thumbs-up/down feedback and an error-reporting workflow.
-   [ ] Red-team prompt injection in repository comments and README
    files.
-   [ ] Optional: evaluation dashboard UI (the README table comes
    first).

### Phase 6 --- Production-style packaging

-   [ ] Create a Dockerfile per service (web, api, worker), built from
    the repository root so it can see `packages/core` and `uv.lock`.
-   [ ] Install Python dependencies with `uv sync --frozen --package
    <service>`.
-   [ ] Keep the API image small; only the worker image includes the
    embedding model and torch.
-   [ ] Add health checks and graceful worker shutdown.
-   [ ] Run tests and lint/type checks in GitHub Actions.
-   [ ] Build images on merge to the main branch.
-   [ ] Publish versioned Docker Hub images and a commit-SHA tag.
-   [ ] Scan dependencies/images where practical.
-   [ ] Add CI secrets through GitHub Actions secrets or OIDC-based
    cloud authentication.
-   [ ] Document local setup, architecture, trade-offs, limitations, and
    screenshots.
-   [ ] Add a short demo video or GIF.

### Phase 7 --- AWS portfolio deployment

-   [ ] Verify current AWS account plan, credit balance, eligible
    services, and pricing.
-   [ ] Configure a billing budget/alert before provisioning resources.
-   [ ] Deploy only after the local application is stable.
-   [ ] Choose a minimal architecture, such as one EC2 instance running
    Docker Compose.
-   [ ] Size memory for the embedding model, or pre-index the demo
    repository locally and ship the vectors so the demo instance only
    embeds queries.
-   [ ] Keep PostgreSQL and Redis private; do not expose their ports
    publicly.
-   [ ] Configure HTTPS, environment secrets, and least-privilege
    access.
-   [ ] Use a demo repository that contains no private or sensitive
    code.
-   [ ] Test the deployed app from a clean browser/session.
-   [ ] Document how to stop/delete resources and verify remaining
    charges.

## 6. Evaluation plan

### Benchmark template

Create a JSON dataset (`eval/datasets/<repo>.json`) with fields like:

``` json
{
  "question": "Where is JWT authentication validated?",
  "expected_files": ["services/api/auth.py"],
  "expected_symbols": ["get_current_user"],
  "expected_evidence": "Token verification and user lookup",
  "answerable": true
}
```

Use actual file paths and symbols from your chosen repository; the
example above is only a template.

### Metrics to report

| Metric | What it tells you |
|---|---|
| Recall@5 | Whether expected evidence appears in the top five retrieved chunks |
| MRR | How highly the first relevant result is ranked |
| nDCG | Whether relevant results are ranked well when graded relevance is available |
| Answer correctness | Whether the response accurately answers the question |
| Citation correctness | Whether citations support the claims and line ranges |
| Abstention quality | Whether the system avoids unsupported answers |
| Latency | How long retrieval and generation take |
| Cost/query | Approximate model cost for a query |

Keep retrieval metrics separate from generation metrics. A good answer
can occasionally mask poor retrieval, and a strong retrieval result can
still be explained incorrectly by the LLM.

### Experiments

| Experiment | Compare |
|---|---|
| Retrieval strategy | Vector-only vs hybrid (RRF) vs agentic |
| Chunking | Function/class + header vs function/class without header vs fixed-size |
| Embedding model | Two code-tuned models |
| Top-k | 5 vs 10 vs 20 |

## 7. Cost strategy

### Development

-   [ ] Run PostgreSQL/pgvector and Redis locally in Docker.
-   [ ] Use local embeddings to avoid embedding API charges.
-   [ ] Use OpenRouter for answer generation with a small prepaid
    budget.
-   [ ] Set usage limits where available and inspect per-model pricing
    before testing.
-   [ ] Reuse embeddings by content hash to avoid re-embedding unchanged
    code.

### AWS

-   [ ] Treat AWS credits as a budget, not as a guarantee of zero cost.
-   [ ] Confirm which services are eligible for the account's current
    plan and credits.
-   [ ] Avoid unnecessary NAT Gateways, oversized instances, and
    always-on managed services.
-   [ ] Stop or delete unused compute resources.
-   [ ] Check storage, snapshots, networking, and other residual
    resources before considering the project shut down.

**Provider decision:** Start with OpenRouter for answer generation
because it simplifies model comparisons. Choose the model based on
benchmark results, answer quality, latency, and cost---not brand alone.

## 8. Repository structure

Python uses one **uv workspace** (one `uv.lock`, one `.venv`). The
frontend is a standalone **pnpm** project; add `pnpm-workspace.yaml`
only if a shared TypeScript package is needed later.

``` text
code-atlas/
├── apps/
│   └── web/                    # Next.js (pnpm)
│       ├── package.json
│       ├── pnpm-lock.yaml
│       └── src/
├── services/
│   ├── api/                    # FastAPI
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── src/api/
│   │   │   ├── main.py
│   │   │   ├── routes/         # repos, chat, auth
│   │   │   └── deps.py         # auth, db session
│   │   └── tests/
│   └── worker/                 # BullMQ worker (Python)
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── src/worker/
│       │   ├── main.py
│       │   └── jobs/           # index_repo.py
│       └── tests/
├── packages/
│   └── core/                   # shared by api + worker
│       ├── pyproject.toml
│       ├── src/core/
│       │   ├── config.py       # settings from .env
│       │   ├── db/             # SQLAlchemy models, session
│       │   └── rag/
│       │       ├── fetch.py    # download commit tarball
│       │       ├── parse.py    # Tree-sitter
│       │       ├── chunk.py
│       │       ├── embed.py
│       │       ├── retrieve.py # vector + keyword + RRF
│       │       └── llm.py      # OpenRouter
│       └── tests/
├── migrations/                 # Alembic
├── eval/
│   ├── datasets/               # benchmark questions
│   ├── results/                # experiment configs + metrics
│   └── run_eval.py
├── alembic.ini
├── pyproject.toml              # uv workspace root
├── uv.lock                     # single lockfile for all Python code
├── docker-compose.yml
├── .env.example
└── README.md
```

### `pyproject.toml` files

`pyproject.toml` is Python's equivalent of `package.json`.
`requirements.txt` is not used: `pyproject.toml` lists dependencies and
`uv.lock` pins exact versions.

| pnpm | uv |
|---|---|
| `package.json` | `pyproject.toml` |
| `pnpm-lock.yaml` | `uv.lock` |
| `node_modules/` | `.venv/` |
| `pnpm-workspace.yaml` | `[tool.uv.workspace]` in root `pyproject.toml` |
| `pnpm add x` | `uv add x` |
| `pnpm install` | `uv sync` |

Root `pyproject.toml` (declares the workspace):

``` toml
[project]
name = "code-atlas"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["services/*", "packages/*"]
```

Service `pyproject.toml` (example: `services/api`):

``` toml
[project]
name = "api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["core", "fastapi", "uvicorn", "bullmq"]

[tool.uv.sources]
core = { workspace = true }   # use local packages/core, not PyPI
```

Each service has its own `pyproject.toml` so each Docker image installs
only what it needs (only the worker installs the embedding model and
torch).

### Setup commands

``` bash
uv init --lib packages/core
uv init --package services/api
uv init --package services/worker
uv add --package api core
uv add --package worker core
pnpm create next-app apps/web
```

If a tool ever requires `requirements.txt`, generate it instead of
maintaining it by hand:

``` bash
uv export --format requirements-txt > requirements.txt
```

### Frontend state rules

| State | Where |
|---|---|
| Server data (repos, messages, index status, eval results) | TanStack Query |
| Selected repo, chat ID, open file | URL (`/repo/123/chat/456`) |
| Sidebar, input text, modals | `useState` |
| Theme | `next-themes` / `localStorage` |
| UI state shared across distant components (e.g. highlighted citation in chat + code viewer) | Zustand, added only when this appears |

## 9. Resume-ready project description

Use this only after implementing and validating the corresponding
features.

**Codebase Intelligence Assistant --- Full-Stack RAG Application**\
*Next.js, TypeScript, FastAPI, Python, SQLAlchemy, PostgreSQL, pgvector,
Tree-sitter, Redis, BullMQ, Docker, GitHub Actions, AWS*

-   Built a repository-aware RAG assistant that indexes source code and
    answers developer questions with verified file- and line-level
    citations.
-   Implemented AST-aware code chunking and hybrid retrieval (vector
    similarity + identifier-aware full-text search fused with RRF), and
    benchmarked it against vector-only and agentic retrieval.
-   Designed an asynchronous ingestion pipeline: FastAPI API and a
    separate Python worker service over Redis/BullMQ, independently
    scalable.
-   Created a reproducible RAG evaluation pipeline measuring retrieval
    quality, answer correctness, citation accuracy, latency, and cost.
-   Implemented GitHub App authentication with repository-level access
    control enforced in retrieval.
-   Containerized the frontend, API, and worker and automated testing
    and image publishing with GitHub Actions.

**Add real measurements only after evaluation**, such as Recall@5
improvement over a vector-only baseline, citation correctness, or median
response latency.

## 10. Definition of done

### MVP (Phases 0--3)

-   [ ] A recruiter can open the GitHub repository and follow the setup
    guide.
-   [ ] A reviewer can launch the application locally with Docker
    Compose.
-   [ ] A public repository can be indexed and queried with verifiable
    citations.
-   [ ] The README shows real benchmark results comparing retrieval
    strategies.

### Full project

-   [ ] A user can sign in with GitHub and connect an authorized
    private repository.
-   [ ] Docker Hub contains versioned images that can be pulled.
-   [ ] GitHub Actions runs tests and builds successfully.
-   [ ] The AWS demo works without exposing database, Redis, or provider
    secrets.
-   [ ] The README explains design choices, measured limitations, and
    next steps.

------------------------------------------------------------------------

**Build principle:** Ship a small, testable end-to-end RAG workflow
first. Add complexity only when you can demonstrate that it improves
retrieval, answer quality, security, or developer experience.
