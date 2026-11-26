FROM python:3.12-slim-bookworm

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml ./apps/api/pyproject.toml
COPY libs/media/pyproject.toml ./libs/media/pyproject.toml
COPY libs/worker-protocol ./libs/worker-protocol
COPY integrations/comfyui/pyproject.toml ./integrations/comfyui/pyproject.toml
COPY integrations/runninghub-worker/pyproject.toml ./integrations/runninghub-worker/pyproject.toml
COPY integrations/official-worker ./integrations/official-worker
RUN python -m pip install --no-cache-dir uv==0.11.23 \
    && uv sync --locked --package comfyshop-official-worker --no-dev --no-editable

USER 10001:10001
HEALTHCHECK NONE
ENTRYPOINT ["comfyshop-official-worker"]
CMD ["run"]
