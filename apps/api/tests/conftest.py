import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from helpers import sync_machine
from loguru import logger
from official_test_support import OWNER, TOKEN, register
from playwright.sync_api import sync_playwright
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from comfyshop_api.core.config import Settings
from comfyshop_api.db import make_engine
from comfyshop_api.main import create_app


@pytest.fixture
def web_engine():
    name = os.environ.get("COMFYSHOP_TEST_WEB_ENGINE", "chromium")
    if name not in {"chromium", "webkit", "firefox"}:
        pytest.fail("COMFYSHOP_TEST_WEB_ENGINE must be chromium, webkit, or firefox")
    with sync_playwright() as playwright:
        yield getattr(playwright, name)


@pytest.fixture
def pg_url():
    url = os.environ.get("COMFYSHOP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("需要 PostgreSQL 测试连接")
    schema = "test_comfyshop_" + uuid4().hex
    admin = make_engine(url)
    with admin.begin() as conn:
        conn.exec_driver_sql(f"CREATE SCHEMA {schema}")
    try:
        yield (
            make_url(url)
            .update_query_dict({"options": "-csearch_path=" + schema})
            .render_as_string(hide_password=False)
        )
    finally:
        with admin.begin() as conn:
            conn.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
        admin.dispose()


@pytest.fixture
def settings(tmp_path, request):
    database_url = f"sqlite:///{tmp_path / 'data.db'}"
    if getattr(request, "param", None) == "postgresql":
        database_url = request.getfixturevalue("pg_url")
    settings = Settings(
        database_url=database_url,
        data_dir=tmp_path,
        static_dir=None,
        public_url="http://testserver",
    )
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.attributes["database_url"] = settings.database_dsn
    command.upgrade(config, "head")
    return settings


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), headers={"Origin": "http://testserver"}) as client:
        yield client


@pytest.fixture
def authenticated(client):
    response = client.post(
        "/api/v1/auth/register", json={"username": "owner", "password": "correct-horse-battery"}
    )
    assert response.status_code == 201, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrfToken"]
    machine = client.post("/api/v1/machines", json={"name": "工作机"})
    assert machine.status_code == 201
    sync_machine(client, machine.json())
    return client


@pytest.fixture
def graph():
    return {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "自然光人像"}},
        "2": {"class_type": "KSampler", "inputs": {"positive": ["1", 0], "seed": 42, "steps": 28}},
    }


@pytest.fixture
def official(client, settings):
    settings.worker_service_tokens["official"] = SecretStr(TOKEN)
    settings.official_owner = OWNER
    register(client, OWNER)
    return client


@pytest.fixture
def worker_logs():
    messages = []
    sink = logger.add(messages.append, level="DEBUG", format="{level} | {message} | {extra}")
    try:
        yield messages
    finally:
        logger.remove(sink)


@pytest.fixture
def small_mp4(tmp_path, settings):
    if not shutil.which(settings.ffmpeg) or not shutil.which(settings.ffprobe):
        pytest.skip("ffmpeg and ffprobe are required")
    path = tmp_path / "sample.mp4"
    subprocess.run(
        [
            settings.ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x48:d=0.2",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            str(path),
        ],
        check=True,
    )
    return path.read_bytes()
