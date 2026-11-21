import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from comfyshop_worker import launcher
from comfyshop_worker.config import Config
from comfyshop_worker.release import Build, Release


def test_signed_release_binds_version_build_and_archive():
    key = Ed25519PrivateKey.generate()
    release = Release(Build("0.1.2", "a" * 64), "b" * 64, 817, "")
    release = replace(release, signature=key.sign(release.signed_data()).hex())
    release.verify(key.public_key(), Build("0.1.1"))
    with pytest.raises(InvalidSignature):
        replace(release, sha256="c" * 64).verify(key.public_key(), Build("0.1.1"))
    with pytest.raises(InvalidSignature):
        release.verify(Ed25519PrivateKey.generate().public_key(), Build("0.1.1"))
    with pytest.raises(ValueError, match="高于当前运行版本"):
        release.verify(key.public_key(), Build("0.1.2"))


def make_child(directory, program):
    module = directory / "comfyshop_worker"
    module.mkdir(parents=True)
    (module / "__init__.py").touch()
    (module / "__main__.py").write_text(program)


@pytest.mark.parametrize("healthy", [True, False])
def test_launcher_promotes_only_a_ready_child(tmp_path, monkeypatch, healthy):
    state = tmp_path / "private"
    state.mkdir()
    config = Config("http://localhost:8688", "http://localhost:8188", "test-key", state)
    bootstrap = tmp_path / "bootstrap"
    key = Ed25519PrivateKey.generate().public_key()
    supervisor = launcher.Launcher(config, bootstrap, key, "uv")
    update_id = str(uuid4())
    child_setup = """
import json
import os
from pathlib import Path
control = Path(os.environ['COMFYSHOP_WORKER_UPDATE_CONTROL'])
state = Path(os.environ['COMFYSHOP_WORKER_STATE_DIR'])
"""
    make_child(
        bootstrap,
        child_setup
        + f"""
if (control.parent / 'failure.json').is_file():
    (state / 'resumed').touch()
else:
    (control / 'request.json').write_text(json.dumps({{'id': '{update_id}'}}))
    raise SystemExit(75)
""",
    )
    candidate = supervisor.versions / ("a" * 64)
    activation = """
import time
(control / 'ready').touch()
pointer = control.parent / 'current.json'
deadline = time.monotonic() + 5
while not pointer.is_file() and time.monotonic() < deadline:
    time.sleep(.01)
assert json.loads(pointer.read_text())['sha256'] == Path.cwd().name
(state / 'activated').touch()
"""
    make_child(candidate, child_setup + (activation if healthy else "raise SystemExit(1)\n"))

    async def prepare(requested, installed):
        assert requested == update_id and installed == bootstrap
        return candidate

    monkeypatch.setattr(supervisor, "prepare", prepare)
    monkeypatch.setattr(launcher, "_python", lambda _source: Path(sys.executable))
    assert asyncio.run(supervisor.run()) == 0
    assert supervisor.current.exists() is healthy
    assert (state / "activated").exists() is healthy
    assert (state / "resumed").exists() is not healthy
    if not healthy:
        failure = json.loads((supervisor.directory / "failure.json").read_text())
        assert failure == {"id": update_id, "reason": "新版未能启动"}
