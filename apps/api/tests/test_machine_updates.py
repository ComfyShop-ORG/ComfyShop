import hashlib
import json
import subprocess
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from fastapi.testclient import TestClient
import pytest

from test_outputs import run_group
from test_worker import claim_body, setup_job


def publish_command(*args):
    script = Path(__file__).resolve().parents[3] / "tooling" / "publish-worker-release.py"
    return subprocess.run([sys.executable, script, *args], capture_output=True, text=True)


@pytest.fixture
def publish(settings, tmp_path):
    key = tmp_path / "worker-signing.pem"
    key.write_bytes(
        Ed25519PrivateKey.generate().private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        )
    )

    def sign(version, directory=settings.data_dir / "worker-releases"):
        package = tmp_path / f"worker-{version}.zip"
        root = f"comfyshop-worker-{version}"
        build = hashlib.sha256(version.encode()).hexdigest()
        with ZipFile(package, "w") as bundle:
            bundle.writestr(f"{root}/requirements.txt", "")
            bundle.writestr(f"{root}/comfyshop_worker/__main__.py", "")
            bundle.writestr(
                f"{root}/comfyshop_worker/worker-build.json",
                json.dumps({"version": version, "build": build}),
            )
        result = publish_command("--package", package, "--key", key, directory)
        assert result.returncode == 0, result.stderr
        manifest = json.loads((directory / "release.json").read_bytes())
        return manifest["release"], package.read_bytes()

    return sign


def heartbeat(worker, version=None, **kwargs):
    headers = (
        {
            "X-ComfyShop-Worker-Runtime": json.dumps(
                {"version": version, "canUpdate": True, **kwargs}
            )
        }
        if version
        else {}
    )
    response = worker.post("/api/v1/worker/heartbeat", json={"protocolVersion": 3}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_update_keeps_lease_and_refetches_after_publish(authenticated, settings, graph, publish):
    client = authenticated
    machine, task, body = setup_job(client, graph)
    queued = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())}).json()
    machine_id = machine["machine"]["id"]
    endpoint = f"/api/v1/machines/{machine_id}/update"
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    original, _ = publish("0.1.2")
    directory = settings.data_dir / "worker-releases"
    assert heartbeat(worker)["runtime"] is None
    assert client.put(endpoint).status_code == 409
    assert heartbeat(worker, "0.1.1")["runtime"]["version"] == "0.1.1"
    assert client.put(endpoint, json={"releaseSha256": "0" * 64}).status_code == 409
    claim = claim_body()
    assert worker.post("/api/v1/worker/claim", json=claim).json()["task"]["id"] == task["id"]
    requested = client.put(endpoint)
    assert requested.status_code == 200, requested.text
    pending = requested.json()["update"]
    assert pending["status"] == "pending" and pending["release"] is None
    assert client.put(endpoint).json()["update"]["id"] == pending["id"]
    begin = f"/api/v1/worker/updates/{pending['id']}"
    original_download = f"/api/v1/worker/releases/{original['sha256']}"
    assert worker.put(begin).status_code == 409
    assert worker.get(original_download).status_code == 404

    next_release, _ = publish("0.1.3")
    assert {file.stem for file in directory.glob("*.zip")} == {next_release["sha256"]}
    assert worker.post("/api/v1/worker/claim", json=claim).json()["task"]["id"] == task["id"]
    run_group(client, worker, task["id"], claim["leaseSecret"], members=1)
    assert worker.post("/api/v1/worker/claim", json=claim_body()).json() is None
    assert worker.put(begin).json() == next_release
    assert worker.put(begin).json() == next_release
    assert worker.get(original_download).status_code == 404

    latest, payload = publish("0.1.4")
    assert {file.stem for file in directory.glob("*.zip")} == {latest["sha256"]}
    superseded = f"/api/v1/worker/releases/{next_release['sha256']}"
    assert worker.get(superseded).status_code == 410
    assert worker.get(superseded).status_code == 404
    assert worker.put(begin).status_code == 409
    retry = heartbeat(worker, "0.1.1", failure={"id": pending["id"], "reason": "下载失败"})[
        "update"
    ]
    assert retry["status"] == "pending" and retry["id"] != pending["id"]
    assert worker.post("/api/v1/worker/claim", json=claim_body()).json() is None
    assert worker.put(f"/api/v1/worker/updates/{retry['id']}").json() == latest
    assert worker.get(f"/api/v1/worker/releases/{latest['sha256']}").content == payload
    checking = heartbeat(worker, latest["version"], build=latest["build"], checking=True)
    assert checking["runtime"]["version"] == "0.1.1"
    assert checking["update"]["status"] == "updating"
    assert worker.post("/api/v1/worker/claim", json=claim_body()).json() is None
    running = heartbeat(worker, latest["version"], build=latest["build"])
    assert running["id"] == machine_id
    assert running["update"]["status"] == "succeeded"
    assert (
        worker.post("/api/v1/worker/claim", json=claim_body()).json()["task"]["id"] == queued["id"]
    )


def test_update_failure_releases_queue_and_can_be_retried(authenticated, settings, graph, publish):
    client = authenticated
    machine, task, _ = setup_job(client, graph)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    endpoint = f"/api/v1/machines/{machine['machine']['id']}/update"
    release, payload = publish("0.1.2")
    manifest = settings.data_dir / "worker-releases" / "release.json"
    public_key = json.loads(manifest.read_bytes())["publicKey"]
    install = client.get("/api/v1/worker/package")
    with ZipFile(BytesIO(install.content)) as bundle:
        assert (
            bundle.read("comfyshop-worker-0.1.2/worker-release.pub").strip() == public_key.encode()
        )
        assert (
            json.loads(bundle.read("comfyshop-worker-0.1.2/worker.json"))["serverUrl"]
            == "http://testserver"
        )
    heartbeat(worker, "0.1.1")
    choice = {"releaseSha256": release["sha256"]}
    update_id = client.put(endpoint, json=choice).json()["update"]["id"]
    assert worker.put(f"/api/v1/worker/updates/{update_id}").status_code == 200
    assert worker.get(f"/api/v1/worker/releases/{release['sha256']}").content == payload
    publish("0.1.3")
    resumed = heartbeat(worker, "0.1.1", failure={"id": update_id, "reason": "新版未能启动"})
    assert resumed["update"]["status"] == "failed"
    assert resumed["runtime"]["version"] == "0.1.1"
    assert worker.post("/api/v1/worker/claim", json=claim_body()).json()["task"]["id"] == task["id"]
    retried = client.put(endpoint).json()["update"]
    assert retried["status"] == "pending" and retried["id"] != update_id
    assert (
        heartbeat(worker, "0.1.1", failure={"id": update_id, "reason": "过期反馈"})["update"]
        == retried
    )


def test_signed_startup_archive_is_stable_across_downloads(authenticated, publish, monkeypatch):
    publish("0.1.2")
    path = "/api/v1/worker/package"
    first = authenticated.get(path).raise_for_status().content
    monkeypatch.setattr(
        zipfile, "time", SimpleNamespace(localtime=time.localtime, time=lambda: time.time() + 60)
    )
    assert authenticated.get(path).raise_for_status().content == first


def test_installing_signed_release_prunes_only_old_release_archives(settings, tmp_path, publish):
    current, _ = publish("0.1.2")
    destination = settings.data_dir / "worker-releases"
    (destination / "notes.zip").write_bytes(b"unrelated")
    staging = tmp_path / "staged-release"
    latest, payload = publish("0.1.3", staging)
    archive = staging / f"{latest['sha256']}.zip"
    archive.write_bytes(payload + b"damage")
    assert publish_command("--install-from", staging, destination).returncode != 0
    assert (destination / f"{current['sha256']}.zip").is_file()
    archive.write_bytes(payload)

    for _ in range(2):
        result = publish_command("--install-from", staging, destination)
        assert result.returncode == 0, result.stderr
        assert {file.name for file in destination.glob("*.zip")} == {archive.name, "notes.zip"}
        assert (destination / "release.json").read_bytes() == (
            staging / "release.json"
        ).read_bytes()
