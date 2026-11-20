from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from comfyshop_api.core.config import Settings
from comfyshop_api.main import create_app
from helpers import sync_machine


@pytest.fixture
def settings(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'data.db'}",
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
