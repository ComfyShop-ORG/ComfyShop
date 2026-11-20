FROM node:22-bookworm-slim AS web
WORKDIR /app
RUN npm install --global pnpm@12.21.0

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY patches ./patches
COPY apps/web/package.json ./apps/web/package.json
COPY packages/api-client/package.json ./packages/api-client/package.json
COPY packages/media/package.json ./packages/media/package.json
COPY packages/tokens/package.json ./packages/tokens/package.json
COPY packages/ui/package.json ./packages/ui/package.json
RUN --mount=type=cache,id=comfyshop-pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --store-dir /pnpm/store

COPY apps/web ./apps/web
COPY packages ./packages
COPY turbo.json tsconfig.json ./
RUN pnpm exec turbo run build

FROM python:3.12-slim-bookworm AS api
RUN python -m pip install --no-cache-dir uv==0.11.23
ENV UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_CONCURRENT_DOWNLOADS=4 \
    UV_HTTP_TIMEOUT=120
WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml ./apps/api/pyproject.toml
COPY integrations/comfyui/pyproject.toml ./integrations/comfyui/pyproject.toml
COPY libs ./libs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --package comfyshop-api --no-dev --no-install-workspace
COPY apps/api/src ./apps/api/src
COPY --from=web /app/apps/api/src/comfyshop_api/design_tokens.py ./apps/api/src/comfyshop_api/design_tokens.py
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --package comfyshop-api --no-dev --no-editable
COPY integrations/comfyui ./integrations/comfyui
COPY integrations/skills/comfyshop ./integrations/skills/comfyshop
COPY tooling/build-worker.py tooling/build-skill.py ./tooling/
RUN python tooling/build-worker.py && python tooling/build-skill.py

FROM python:3.12-slim-bookworm AS runtime
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean \
    && sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends ca-certificates ffmpeg \
    && groupadd --gid 10001 comfyshop \
    && useradd --uid 10001 --gid comfyshop --create-home comfyshop \
    && install -d -o comfyshop -g comfyshop -m 0700 /data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COMFYSHOP_DATA_DIR=/data \
    COMFYSHOP_STATIC_DIR=/app/dist
WORKDIR /app
COPY --from=api /app/.venv /app/.venv
COPY --from=web /app/apps/web/dist /app/dist
COPY --from=api /app/dist/downloads /app/dist/downloads
COPY apps/api/alembic.ini ./apps/api/alembic.ini
COPY apps/api/migrations ./apps/api/migrations
COPY --chmod=755 tooling/docker-entrypoint.sh /usr/local/bin/comfyshop-entrypoint

USER comfyshop
VOLUME ["/data"]
EXPOSE 8688
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8688/api/v1/health', timeout=3).close()"]
ENTRYPOINT ["comfyshop-entrypoint"]
CMD ["uvicorn", "comfyshop_api.main:app", "--host", "0.0.0.0", "--port", "8688"]
