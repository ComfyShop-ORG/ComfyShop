FROM python:3.12-slim-bookworm
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml ./apps/api/pyproject.toml
COPY integrations/official-worker/pyproject.toml ./integrations/official-worker/pyproject.toml
COPY libs ./libs
COPY integrations/comfyui/pyproject.toml ./integrations/comfyui/pyproject.toml
COPY integrations/runninghub-worker ./integrations/runninghub-worker
RUN python -m pip install --no-cache-dir uv==0.11.23 \
    && uv sync --locked --package comfyshop-runninghub-worker --no-dev --no-editable
USER 10001:10001
HEALTHCHECK NONE
ENTRYPOINT ["comfyshop-runninghub-worker"]
