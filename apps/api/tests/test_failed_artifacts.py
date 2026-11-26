import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_inputs import picture
from test_outputs import run_group
from test_worker import claim_body, image_bytes, setup_job

from comfyshop_api.models import Artifact, Execution, OriginalDeletion, Task, now_ms
from comfyshop_api.services import artifacts as cleanup
from comfyshop_api.services import originals
from comfyshop_api.services.machines import expire_leases


def claim_job(client, graph, execution_count=1):
    machine, task, _ = setup_job(client, graph, execution_count=execution_count)
    claim = claim_body()
    worker = TestClient(
        client.app,
        headers={
            "Authorization": "Bearer " + machine["apiKey"],
            "X-Task-Lease": claim["leaseSecret"],
        },
    )
    response = worker.post("/api/v1/worker/claim", json=claim)
    assert response.status_code == 200, response.text
    assert response.json()["task"]["id"] == task["id"]
    return task, worker, f"/api/v1/worker/tasks/{task['id']}"


def start_execution(worker, base, index):
    response = worker.post(
        base + f"/executions/{index}/start", json={"promptId": f"prompt-{index}"}
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def upload_output(worker, base, index=0, position=0, *, corrupt=False, data=None):
    data = image_bytes() if data is None else data
    return worker.put(
        base + f"/artifacts/r{index}_{position}",
        content=b"incomplete file" if corrupt else data,
        params={
            "filename": f"output-{index}-{position}.png",
            "sha256": hashlib.sha256(data).hexdigest(),
            "execution_index": index,
            "output_node_id": "2",
            "output_slot": "images",
            "output_index": position,
        },
    )


def report_failure(worker, base):
    response = worker.post(base + "/fail", json={"error": "成品回传失败"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"


@pytest.mark.parametrize("ending", ["reported", "lease-expiry", "cancelled"])
def test_partial_artifact_retention_starts_when_execution_ends(
    authenticated, graph, settings, monkeypatch, ending
):
    client = authenticated
    task, worker, base = claim_job(client, graph, 2)
    succeeded, [complete] = run_group(
        client, worker, task["id"], worker.headers["X-Task-Lease"], members=1
    )
    failed_id = start_execution(worker, base, 1)
    uploaded = upload_output(worker, base, 1)
    assert uploaded.status_code == 200, uploaded.text
    partial_id = uploaded.json()["id"]
    assert upload_output(worker, base, 1, 1, corrupt=True).status_code == 422

    engine = client.app.state.engine
    ttl_ms = settings.failed_artifact_ttl_seconds * 1000
    old_at = now_ms() - ttl_ms - 1000
    with Session(engine) as db:
        partial = db.get(Artifact, partial_id)
        partial.created_at = old_at
        partial_path = settings.original_dir / partial.media.storage_name
        complete_path = settings.original_dir / db.get(Artifact, complete["id"]).media.storage_name
        assert partial_path == complete_path
        db.get(Execution, failed_id).updated_at = old_at
        db.get(Execution, succeeded["id"]).updated_at = old_at
        db.commit()
        cleanup.expire_incomplete_artifacts(db, settings)
        assert partial_path.is_file() and db.get(Artifact, partial_id)

    if ending == "lease-expiry":
        with Session(engine) as db:
            db.get(Task, task["id"]).lease_expires_at = 0
            db.commit()
            expire_leases(db)
    elif ending == "cancelled":
        assert client.post(f"/api/v1/tasks/{task['id']}/cancel").status_code == 200
    else:
        report_failure(worker, base)

    with Session(engine) as db:
        failed = db.get(Execution, failed_id)
        expected_status = "cancelled" if ending == "cancelled" else "failed"
        assert failed.status == expected_status
        failure_at = failed.updated_at
    assert failure_at > old_at
    assert client.get(f"/api/v1/artifacts/{partial_id}/file").status_code == 404

    clock = failure_at + ttl_ms - 1
    monkeypatch.setattr(cleanup, "now_ms", lambda: clock)
    with Session(engine) as db:
        cleanup.expire_incomplete_artifacts(db, settings)
        assert partial_path.is_file() and db.get(Artifact, partial_id)

    clock += 1
    with Session(engine) as db:
        cleanup.expire_incomplete_artifacts(db, settings)
        assert db.get(Artifact, partial_id) is None
        assert db.get(Execution, failed_id).updated_at == failure_at
        assert db.get(Task, task["id"]).status == expected_status
        originals.retire_unreferenced_originals(db)
        originals.delete_pending_originals(db, settings.media_storage)
    assert client.get(f"/api/v1/executions/{succeeded['id']}").json()["status"] == "succeeded"
    assert complete_path.is_file()
    download = client.get(f"/api/v1/artifacts/{complete['id']}/file")
    assert download.status_code == 200 and download.content == image_bytes()


def test_unlink_failure_retries_and_allows_other_expired_files(
    authenticated, graph, settings, monkeypatch
):
    client = authenticated
    _, worker, base = claim_job(client, graph)
    execution_id = start_execution(worker, base, 0)
    assert upload_output(worker, base).status_code == 200
    assert upload_output(worker, base, position=1, data=picture("white")).status_code == 200
    report_failure(worker, base)

    engine = client.app.state.engine
    with Session(engine) as db:
        first, second = db.scalars(select(Artifact).order_by(Artifact.id)).all()
        first_id, second_id = first.id, second.id
        first_path = settings.original_dir / first.media.storage_name
        second_path = settings.original_dir / second.media.storage_name
        clock = (
            db.get(Execution, execution_id).updated_at + settings.failed_artifact_ttl_seconds * 1000
        )

    unlink = Path.unlink
    unavailable = True

    def temporarily_blocked(path, *args, **kwargs):
        if path == first_path and unavailable:
            raise PermissionError("storage unavailable")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", temporarily_blocked)
    monkeypatch.setattr(cleanup, "now_ms", lambda: clock)
    monkeypatch.setattr(originals, "now_ms", lambda: clock)
    monkeypatch.setattr(cleanup, "CLEANUP_BATCH_SIZE", 1)

    with Session(engine) as db:
        cleanup.expire_incomplete_artifacts(db, settings)
        assert db.get(Artifact, first_id) is None
        originals.retire_unreferenced_originals(db)
        originals.delete_pending_originals(db, settings.media_storage)
        retry_at = db.get(OriginalDeletion, first_path.name).retry_at
        assert retry_at == clock + originals.DELETE_RETRY_MS
        assert first_path.is_file() and second_path.is_file()

    unavailable = False
    clock = retry_at - 1
    with Session(engine) as db:
        cleanup.expire_incomplete_artifacts(db, settings)
        originals.retire_unreferenced_originals(db)
        originals.delete_pending_originals(db, settings.media_storage)
        assert not second_path.exists() and db.get(Artifact, second_id) is None
        assert first_path.is_file() and db.get(OriginalDeletion, first_path.name)

    clock = retry_at
    with Session(engine) as db:
        originals.delete_pending_originals(db, settings.media_storage)
        assert not first_path.exists() and db.get(OriginalDeletion, first_path.name) is None


def test_cleanup_recovers_after_commit_failure(authenticated, graph, settings, monkeypatch):
    client = authenticated
    task, worker, base = claim_job(client, graph)
    execution_id = start_execution(worker, base, 0)
    uploaded = upload_output(worker, base)
    assert uploaded.status_code == 200
    report_failure(worker, base)

    engine = client.app.state.engine
    artifact_id = uploaded.json()["id"]
    with Session(engine) as db:
        execution = db.get(Execution, execution_id)
        clock = execution.updated_at + settings.failed_artifact_ttl_seconds * 1000
        path = settings.original_dir / db.get(Artifact, artifact_id).media.storage_name

    def commit_failed():
        raise OperationalError(None, None, RuntimeError("database temporarily unavailable"))

    monkeypatch.setattr(cleanup, "now_ms", lambda: clock)
    with Session(engine) as db:
        monkeypatch.setattr(db, "commit", commit_failed)
        with pytest.raises(OperationalError):
            cleanup.expire_incomplete_artifacts(db, settings)

    assert path.is_file()
    with Session(engine) as db:
        assert db.get(Artifact, artifact_id)
        cleanup.expire_incomplete_artifacts(db, settings)
        assert db.get(Artifact, artifact_id) is None
        originals.retire_unreferenced_originals(db)
        originals.delete_pending_originals(db, settings.media_storage)
        assert not path.exists()
