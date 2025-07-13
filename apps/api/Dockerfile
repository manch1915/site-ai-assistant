# Build context: repository root (the widget bundle is baked into the API's static folder).

FROM node:22-alpine AS widget
WORKDIR /src/apps/widget
COPY apps/widget/package.json apps/widget/package-lock.json ./
RUN npm ci
COPY apps/widget ./
RUN npx tsc --noEmit && npx vite build --mode loader && npx vite build --mode app

FROM python:3.12-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=180 \
    HF_HOME=/models \
    UPLOAD_DIR=/srv/storage/uploads
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv
WORKDIR /srv/app

COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --extra local-embeddings --no-install-project

COPY apps/api/alembic.ini ./
COPY apps/api/migrations ./migrations
COPY apps/api/src ./src
COPY apps/api/static ./static
COPY --from=widget /src/apps/widget/dist/ ./static/
RUN uv sync --frozen --no-dev --extra local-embeddings

RUN useradd --create-home --uid 10001 relay \
    && mkdir -p /models /srv/storage/uploads \
    && chown -R relay /models /srv/storage
USER relay

ENV PATH="/srv/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["fastapi", "run", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
