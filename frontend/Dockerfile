# ---- base: Node + pnpm + installed dependencies ----
FROM node:24-slim AS base

RUN npm install -g pnpm@10.33.0

WORKDIR /app

# Dependencies first, code later: this layer is cached until the lockfile changes
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

# ---- dev: used by docker-compose, hot reload ----
FROM base AS dev
CMD ["pnpm", "dev"]

# ---- prod: build once, serve the build ----
FROM base AS prod
ENV NODE_ENV=production
RUN pnpm build
CMD ["pnpm", "start"]
