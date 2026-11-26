from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from helpers import task_body
from sqlalchemy.orm import Session
from test_outputs import completed_group, publish_body

from comfyshop_api.models import (
    Artifact,
    Task,
    Work,
    WorkArtifact,
    Workflow,
)
from comfyshop_api.services.artifacts import expire_incomplete_artifacts


def test_soft_delete_hides_work_and_results_but_preserves_files_and_references(
    authenticated, graph, settings
):
    client = authenticated
    task, execution, outputs = completed_group(client, graph)
    first, second, third = [output["id"] for output in outputs]
    workflow = f"/api/v1/workflows/{task['workflowId']}"
    result = f"/api/v1/executions/{execution['id']}"
    artifact = f"/api/v1/artifacts/{first}"
    assert client.post(workflow + "/publish").status_code == 200
    body = publish_body(execution, outputs)
    assert client.post("/api/v1/works", json=body).status_code == 201
    work = f"/api/v1/works/{body['id']}"

    visitor = TestClient(client.app, headers={"Origin": "http://testserver"})
    registration = visitor.post(
        "/api/v1/auth/register", json={"username": "reader", "password": "test-reader-password"}
    )
    visitor.headers["X-CSRF-Token"] = registration.json()["csrfToken"]
    for path in (workflow, result + "/artifacts", artifact, f"/api/v1/tasks/{task['id']}"):
        assert visitor.delete(path).status_code == 404
    assert visitor.post(work + "/delete").status_code == 404
    assert visitor.get(f"/api/v1/artifacts/{second}/file").status_code == 200
    assert client.delete(artifact).status_code == 409
    assert client.delete(result + "/artifacts").status_code == 409
    assert client.get(result).json()["imageCount"] == 3

    assert client.post(work + "/delete").status_code == 204
    assert client.post(work + "/delete").status_code == 204
    assert client.get(work).status_code == 404
    assert client.get("/api/v1/works?scope=mine").json()["items"] == []
    assert visitor.get("/api/v1/works").json()["items"] == []
    assert visitor.get(f"/api/v1/artifacts/{second}/file").status_code == 404
    assert client.get(f"/api/v1/artifacts/{second}/file").status_code == 200
    assert client.post("/api/v1/works", json=body).status_code == 409

    assert visitor.get(artifact + "/thumbnail").status_code == 404
    assert client.get(artifact + "/thumbnail").status_code == 200
    cached = next(settings.thumbnail_dir.glob("*.webp"))
    cache_contents = cached.read_bytes()
    with Session(client.app.state.engine) as db:
        originals = {
            settings.original_dir / db.get(Artifact, asset_id).media.storage_name
            for asset_id in (first, second, third)
        }
    original_contents = {file: file.read_bytes() for file in originals}
    removed = client.delete(artifact)
    assert removed.status_code == 200, removed.text
    assert removed.json()["imageCount"] == 2 and removed.json()["coverArtifactId"] == second
    assert client.delete(artifact).json()["imageCount"] == 2
    assert client.get(artifact + "/file").status_code == 404
    assert visitor.get(artifact + "/thumbnail").status_code == 404
    assert client.get(workflow).json()["media"]["src"].startswith(f"/api/v1/artifacts/{second}/")
    remaining = client.get("/api/v1/artifacts", params={"execution_id": execution["id"]}).json()
    assert [item["id"] for item in remaining["items"]] == [second, third]

    assert client.delete(result + "/artifacts").status_code == 204
    assert client.delete(result + "/artifacts").status_code == 204
    assert client.get("/api/v1/executions").json()["items"] == []
    assert client.get(f"/api/v1/tasks/{task['id']}/progress").json()["status"] == "succeeded"

    with Session(client.app.state.engine) as db:
        expire_incomplete_artifacts(db, settings)
        for asset_id in (first, second, third):
            record = db.get(Artifact, asset_id)
            assert record.deleted_at is not None
        deleted_work = db.get(Work, body["id"])
        assert deleted_work.deleted_at is not None and deleted_work.published
        assert db.get(WorkArtifact, (body["id"], second)) is not None
        db.get(Artifact, first).deleted_at = None
        db.commit()
    assert all(file.read_bytes() == contents for file, contents in original_contents.items())
    assert cached.read_bytes() == cache_contents
    assert client.get(artifact + "/thumbnail").content == cache_contents
    assert client.get(result).json()["coverArtifactId"] == first


def test_delete_task_record_and_archive_workflow_preserve_results(authenticated, graph):
    client = authenticated
    task, execution, outputs = completed_group(client, graph)
    workflow = f"/api/v1/workflows/{task['workflowId']}"
    assert client.post(workflow + "/publish", json={}).status_code == 200
    published = client.post("/api/v1/works", json=publish_body(execution, outputs))
    assert published.status_code == 201
    work = f"/api/v1/works/{published.json()['id']}"
    result = f"/api/v1/executions/{execution['id']}"
    assert client.get(work + "/replay").status_code == 200
    assert client.get(result + "/replay").status_code == 200
    visitor = TestClient(client.app)
    assert visitor.get(workflow).status_code == 200
    body = task_body(client, client.get(workflow).json())
    queued = client.post("/api/v1/tasks", json=body).json()
    pending = f"/api/v1/tasks/{queued['id']}"
    assert client.delete(pending).status_code == 409
    assert client.post(pending + "/cancel").status_code == 200
    assert client.delete(pending).status_code == 204
    assert client.post("/api/v1/tasks", json=body).status_code == 409

    history = f"/api/v1/tasks/{task['id']}"
    without_csrf = TestClient(
        client.app, cookies=client.cookies, headers={"Origin": "http://testserver"}
    )
    assert without_csrf.delete(history).status_code == 403
    assert client.delete(history).status_code == 204
    assert client.delete(history).status_code == 204
    assert client.get(history).status_code == 404
    assert client.get(history + "/progress").status_code == 404
    assert client.get(history + "/inputs").status_code == 200
    assert client.get("/api/v1/tasks").json()["items"] == []
    assert client.delete(workflow).status_code == 204
    assert client.delete(workflow).status_code == 204
    assert client.get("/api/v1/workflows?scope=mine").json()["items"] == []
    assert visitor.get(workflow).status_code == 404
    assert visitor.get(work).status_code == 404
    assert client.get(work).status_code == 200
    assert client.get(work + "/artifacts").json()["items"]
    assert client.get(result).json()["imageCount"] == 3
    assert client.get(f"/api/v1/artifacts/{outputs[0]['id']}/file").status_code == 200
    for source in (work, result):
        replay = client.get(source + "/replay")
        assert replay.status_code == 404
        assert replay.json()["detail"] == "来源工作流或版本不可用，无法载入参数"
    with Session(client.app.state.engine) as db:
        hidden_workflow = db.get(Workflow, task["workflowId"])
        assert hidden_workflow.deleted_at is not None and hidden_workflow.published
        hidden_task = db.get(Task, task["id"])
        assert hidden_task.deleted_at is not None and hidden_task.status == "succeeded"


def test_publish_work_and_delete_artifact_cannot_both_succeed(authenticated, graph):
    client = authenticated
    task, execution, outputs = completed_group(client, graph)
    assert (
        client.post(f"/api/v1/workflows/{task['workflowId']}/publish", json={}).status_code == 200
    )
    body = publish_body(execution, outputs)
    with ThreadPoolExecutor(max_workers=2) as pool:
        publish = pool.submit(client.post, "/api/v1/works", json=body)
        remove = pool.submit(client.delete, f"/api/v1/artifacts/{outputs[0]['id']}")
        assert (publish.result().status_code, remove.result().status_code) in {
            (201, 409),
            (404, 200),
        }


@pytest.mark.parametrize("member", [0, 1], ids=["member", "cover"])
def test_restoring_a_work_requires_all_its_members(authenticated, graph, member):
    client = authenticated
    task, execution, outputs = completed_group(client, graph)
    assert client.post(f"/api/v1/workflows/{task['workflowId']}/publish").status_code == 200
    work = client.post("/api/v1/works", json=publish_body(execution, outputs)).json()
    path = f"/api/v1/works/{work['id']}"
    artifact = f"/api/v1/artifacts/{outputs[member]['id']}"
    assert client.post(path + "/delete").status_code == 204
    assert client.delete(artifact).status_code == 200
    restored = client.post(path + "/restore")
    assert restored.status_code == 409
    assert "请先恢复成品" in restored.json()["detail"]
    visitor = TestClient(client.app)
    assert visitor.get(path).status_code == 404
    assert client.get(path).status_code == 404
    assert client.post(artifact + "/restore").status_code == 200
    assert client.post(path + "/restore").status_code == 204
    assert visitor.get(path).status_code == 200
    for asset in work["coverArtifactId"], outputs[member]["id"]:
        assert visitor.get(f"/api/v1/artifacts/{asset}/file").status_code == 200


def test_restoring_a_work_and_deleting_its_member_cannot_both_succeed(authenticated, graph):
    client = authenticated
    task, execution, outputs = completed_group(client, graph)
    assert client.post(f"/api/v1/workflows/{task['workflowId']}/publish").status_code == 200
    work = client.post("/api/v1/works", json=publish_body(execution, outputs)).json()
    path = f"/api/v1/works/{work['id']}"
    assert client.post(path + "/delete").status_code == 204
    with ThreadPoolExecutor(max_workers=2) as pool:
        restore = pool.submit(client.post, path + "/restore")
        remove = pool.submit(client.delete, f"/api/v1/artifacts/{work['coverArtifactId']}")
        assert (restore.result().status_code, remove.result().status_code) in {
            (204, 409),
            (409, 200),
        }


def test_deleted_records_can_be_restored_by_their_owner(authenticated, graph):
    client = authenticated
    task, execution, outputs = completed_group(client, graph)
    first = outputs[0]["id"]
    workflow = f"/api/v1/workflows/{task['workflowId']}"
    assert client.post(workflow + "/publish").status_code == 200
    body = publish_body(execution, outputs)
    assert client.post("/api/v1/works", json=body).status_code == 201
    work = f"/api/v1/works/{body['id']}"

    def listed(path):
        return {item["id"] for item in client.get(path).json()["items"]}

    assert client.post(work + "/delete").status_code == 204
    assert body["id"] not in listed("/api/v1/works?scope=mine")
    assert client.post(work + "/restore").status_code == 204
    assert body["id"] in listed("/api/v1/works?scope=mine")

    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204
    assert task["id"] not in listed("/api/v1/tasks")
    assert client.post(f"/api/v1/tasks/{task['id']}/restore").status_code == 204
    assert task["id"] in listed("/api/v1/tasks")

    unused = next(output["id"] for output in outputs if output["id"] not in body["artifactIds"])
    assert client.delete(f"/api/v1/artifacts/{unused}").status_code == 200
    restored = client.post(f"/api/v1/artifacts/{unused}/restore").json()
    assert restored["imageCount"] == len(outputs)
    assert first in listed(f"/api/v1/artifacts?execution_id={execution['id']}")

    assert client.delete(workflow).status_code == 204
    assert client.get(workflow).status_code == 404
    assert client.post(workflow + "/restore").json()["published"] is True
    assert client.get(workflow).status_code == 200

    visitor = TestClient(client.app, headers={"Origin": "http://testserver"})
    registration = visitor.post(
        "/api/v1/auth/register", json={"username": "restorer", "password": "test-reader-password"}
    )
    visitor.headers["X-CSRF-Token"] = registration.json()["csrfToken"]
    for path in (workflow, work, f"/api/v1/tasks/{task['id']}", f"/api/v1/artifacts/{first}"):
        assert visitor.post(path + "/restore").status_code == 404


def test_group_delete_and_queue_cancel_can_be_undone(authenticated, graph):
    client = authenticated
    task, execution, outputs = completed_group(client, graph)
    group = f"/api/v1/executions/{execution['id']}/artifacts"
    earlier = outputs[0]["id"]
    assert client.delete(f"/api/v1/artifacts/{earlier}").status_code == 200
    assert client.delete(group).status_code == 204
    restored = client.post(group + "/restore").json()
    # 只恢复这次整组删除的成品，之前单独删除的那份保持删除。
    assert restored["imageCount"] == len(outputs) - 1

    queued = client.post(
        "/api/v1/tasks",
        json=task_body(
            client,
            {
                "id": task["workflowId"],
                "versionId": task["versionId"],
            },
        ),
    ).json()
    url = f"/api/v1/tasks/{queued['id']}"
    cancelled = client.post(url + "/cancel").json()
    assert (cancelled["status"], cancelled["stage"]) == ("cancelled", "cancelled")
    resumed = client.post(url + "/resume").json()
    assert (resumed["status"], resumed["stage"]) == ("queued", "queued")
    progress = client.get(url + "/progress").json()
    assert {item["status"] for item in progress["executions"]} == {"queued"}
    # 工作机领取过的任务取消后不能回到队列。
    assert client.post(f"/api/v1/tasks/{task['id']}/resume").status_code == 409
