# ---- base: Python + uv + locked dependencies ----
FROM python:3.14-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.25 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Dependencies first, code later: this layer is cached until uv.lock changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# ---- dev: used by docker-compose, reloads on code changes ----
FROM base AS dev
RUN uv sync --frozen --no-install-project
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---- prod: no reload, non-root user ----
FROM base AS prod
RUN useradd --create-home appuser
USER appuser
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
