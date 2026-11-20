import json

import pytest

from comfyshop_worker.config import Config, Journal


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / "worker.json"
    monkeypatch.setenv("COMFYSHOP_WORKER_CONFIG", str(path))
    for variable in (
        "COMFYSHOP_SERVER_URL",
        "COMFYSHOP_COMFY_URL",
        "COMFYSHOP_API_KEY",
        "COMFYSHOP_WORKER_STATE_DIR",
        "COMFYSHOP_EXECUTION_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(variable, raising=False)
    return path


@pytest.mark.parametrize(
    "invalid",
    [
        [],
        {"serverUrl": None},
        {"comfyUrl": 8188},
        {"apiKey": 123},
        {"executionTimeoutSeconds": True},
    ],
)
def test_config_rejects_invalid_field_types(config_file, invalid):
    value = {"apiKey": "verification-key", "stateDir": str(config_file.parent / "state")}
    config_file.write_text(json.dumps(value | invalid if isinstance(invalid, dict) else invalid))
    with pytest.raises(ValueError):
        Config.load()


def test_config_environment_overrides_file_values(config_file, monkeypatch):
    state_dir = config_file.parent / "state"
    config_file.write_text(json.dumps({"apiKey": "verification-key", "stateDir": str(state_dir)}))
    monkeypatch.setenv("COMFYSHOP_SERVER_URL", "https://service.example/")
    monkeypatch.setenv("COMFYSHOP_EXECUTION_TIMEOUT_SECONDS", "45")
    config = Config.load()
    assert config.server_url == "https://service.example"
    assert config.execution_timeout_seconds == 45
    assert config.state_dir == state_dir


def test_journal_validates_object_and_preserves_mixed_values(tmp_path):
    journal = Journal(tmp_path)
    assert journal.read() is None
    state = {"index": 2, "finishing": True, "job": {"task": {"id": "task"}}}
    journal.save(state)
    assert journal.read() == state
    journal.path.write_text("[]")
    with pytest.raises(ValueError, match="JSON 对象"):
        journal.read()
