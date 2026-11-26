FROM python:3.12-slim-bookworm

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy
WORKDIR /app

RUN python -m pip install --no-cache-dir uv==0.11.23
COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml ./apps/api/pyproject.toml
COPY integrations/official-worker/pyproject.toml ./integrations/official-worker/pyproject.toml
COPY libs/media/pyproject.toml ./libs/media/pyproject.toml
COPY libs/worker-protocol ./libs/worker-protocol
COPY integrations/runninghub-worker/pyproject.toml ./integrations/runninghub-worker/pyproject.toml
COPY integrations/comfyui/pyproject.toml ./integrations/comfyui/pyproject.toml
COPY integrations/comfyui/comfyshop_worker ./integrations/comfyui/comfyshop_worker
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --package comfyshop-worker --no-dev --no-editable

USER 10001:10001
HEALTHCHECK NONE
ENTRYPOINT ["comfyshop-worker"]
