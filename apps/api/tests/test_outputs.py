import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from comfyshop_api.models import Execution, Task, Work, now_ms
from comfyshop_api.services.machines import expire_leases
from test_worker import claim_body, image_bytes, setup_job
from helpers import task_body, sync_machine
import json


def run_group(client, worker, task_id, lease, index=0, members=3):
    base = f"/api/v1/worker/tasks/{task_id}"
    headers = {"X-Task-Lease": lease}
    heartbeat = {
        "sequence": 2 + index * 2,
        "progress": index * 30,
        "stage": "executing",
        "promptId": f"prompt-{index}",
        "executionIndex": index,
    }
    assert worker.post(base + "/heartbeat", json=heartbeat, headers=headers).status_code == 200
    assert (
        worker.post(
            base + "/heartbeat",
            json={**heartbeat, "sequence": 1, "promptId": "stale"},
            headers=headers,
        ).status_code
        == 200
    )
    started = worker.post(
        base + f"/executions/{index}/start", json={"promptId": f"prompt-{index}"}, headers=headers
    )
    assert started.status_code == 200, started.text
    outputs = []
    for position in range(members):
        data = image_bytes()
        params = {
            "filename": f"output-{index}-{position}.png",
            "sha256": hashlib.sha256(data).hexdigest(),
            "execution_index": index,
            "output_node_id": "2",
            "output_slot": "images",
            "output_index": position,
        }
        response = worker.put(
            base + f"/artifacts/r{index}_{position}", content=data, params=params, headers=headers
        )
        assert response.status_code == 200, response.text
        outputs.append(response.json())
    manifest = {"clientIds": [f"r{index}_{position}" for position in range(members)]}
    if members > 1:
        assert (
            worker.post(
                base + f"/executions/{index}/complete",
                json={"clientIds": list(reversed(manifest["clientIds"]))},
                headers=headers,
            ).status_code
            == 409
        )
    assert (
        worker.post(
            base + f"/executions/{index}/complete", json={"clientIds": ["missing"]}, headers=headers
        ).status_code
        == 409
    )
    completed = worker.post(base + f"/executions/{index}/complete", json=manifest, headers=headers)
    assert completed.status_code == 200, completed.text
    assert (
        worker.post(base + f"/executions/{index}/complete", json=manifest, headers=headers).json()[
            "id"
        ]
        == completed.json()["id"]
    )
    return completed.json(), outputs


def completed_group(client, graph):
    machine, task, _ = setup_job(client, graph)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    worker.post("/api/v1/worker/claim", json=claim)
    execution, outputs = run_group(client, worker, task["id"], claim["leaseSecret"])
    done = worker.post(
        f"/api/v1/worker/tasks/{task['id']}/complete",
        headers={"X-Task-Lease": claim["leaseSecret"]},
    )
    assert done.status_code == 200, done.text
    return task, execution, outputs


def publish_body(execution, outputs):
    return {
        "id": str(uuid4()),
        "executionId": execution["id"],
        "title": "精选成品",
        "artifactIds": [outputs[0]["id"], outputs[1]["id"]],
        "coverArtifactId": outputs[1]["id"],
        "shareParameters": True,
    }


def test_batch_and_multi_output_are_distinct_and_manifests_are_complete(authenticated, graph):
    client = authenticated
    machine, _, body = setup_job(client, graph)
    # Cancel setup_job's original single execution so the worker claims this batch.
    original = client.get("/api/v1/tasks").json()["items"][0]
    client.post(f"/api/v1/tasks/{original['id']}/cancel")
    task = client.post(
        "/api/v1/tasks",
        json={
            **body,
            "executionCount": 2,
            "idempotencyKey": str(uuid4()),
        },
    ).json()
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    assert worker.post("/api/v1/worker/claim", json=claim).json()["task"]["id"] == task["id"]
    first, first_outputs = run_group(client, worker, task["id"], claim["leaseSecret"], 0)
    assert (
        worker.post(
            f"/api/v1/worker/tasks/{task['id']}/complete",
            headers={"X-Task-Lease": claim["leaseSecret"]},
        ).status_code
        == 409
    )
    second, _ = run_group(client, worker, task["id"], claim["leaseSecret"], 1, 2)
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["status"] == "succeeded"
    assert (
        worker.post(
            f"/api/v1/worker/tasks/{task['id']}/complete",
            headers={"X-Task-Lease": claim["leaseSecret"]},
        ).status_code
        == 200
    )
    seed_id = hashlib.sha256(json.dumps(["2", "seed"], separators=(",", ":")).encode()).hexdigest()
    assert first["inputValues"][seed_id] + 1 == second["inputValues"][seed_id]
    assert first["imageCount"] == 3 and second["imageCount"] == 2
    page = client.get(f"/api/v1/executions?task_id={task['id']}&limit=1").json()
    assert len(page["items"]) == 1 and page["nextCursor"]
    following = client.get(
        "/api/v1/executions", params={"task_id": task["id"], "cursor": page["nextCursor"]}
    ).json()
    assert len(following["items"]) == 1 and following["items"][0]["id"] != page["items"][0]["id"]
    assets = client.get(
        "/api/v1/artifacts", params={"execution_id": first["id"], "limit": 2}
    ).json()
    assert [a["outputIndex"] for a in assets["items"]] == [0, 1]
    last = client.get(
        "/api/v1/artifacts", params={"execution_id": first["id"], "cursor": assets["nextCursor"]}
    ).json()
    assert [a["id"] for a in last["items"]] == [first_outputs[2]["id"]]
    assert (
        assets["items"][0]["outputNodeId"] == "2"
        and assets["items"][0]["outputNodeTitle"] == "KSampler"
    )
    assert "parameters" not in first


def test_committed_manifest_replays_after_lease_expiry_and_next_claim(authenticated, graph):
    client = authenticated
    machine, task, body = setup_job(client, graph)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    assert worker.post("/api/v1/worker/claim", json=claim).json()["task"]["id"] == task["id"]
    following = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())}).json()
    execution, outputs = run_group(client, worker, task["id"], claim["leaseSecret"], members=1)

    with Session(client.app.state.engine) as db:
        finished = db.get(Task, task["id"])
        assert finished.status == "succeeded" and finished.progress == 100
        finished.lease_expires_at = now_ms() - 1
        db.commit()

    assert (
        worker.post("/api/v1/worker/claim", json=claim_body()).json()["task"]["id"]
        == following["id"]
    )
    base = f"/api/v1/worker/tasks/{task['id']}"
    headers = {"X-Task-Lease": claim["leaseSecret"]}
    event = {"sequence": 99, "progress": 5, "stage": "executing", "executionIndex": 0}
    heartbeat = worker.post(base + "/heartbeat", json=event, headers=headers)
    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "succeeded" and heartbeat.json()["progress"] == 100
    started = worker.post(
        base + "/executions/0/start", json={"promptId": "prompt-0"}, headers=headers
    )
    assert started.status_code == 200 and started.json()["status"] == "succeeded"
    replay = worker.post(
        base + "/executions/0/complete", json={"clientIds": ["r0_0"]}, headers=headers
    )
    assert replay.status_code == 200 and replay.json()["id"] == execution["id"]
    assert (
        worker.post(
            base + "/executions/0/complete", json={"clientIds": ["different"]}, headers=headers
        ).status_code
        == 409
    )
    assert (
        worker.post(base + "/heartbeat", json=event, headers={"X-Task-Lease": "other"}).status_code
        == 409
    )
    assert worker.post(base + "/complete", headers=headers).json()["status"] == "succeeded"
    assert client.get(outputs[0]["media"]["src"]).status_code == 200
    machines = client.get("/api/v1/machines").json()["items"]
    assert next(item for item in machines if item["id"] == machine["machine"]["id"])["busy"]


def test_expiry_finalizes_running_task_with_committed_manifest(authenticated, graph):
    client = authenticated
    task, _, outputs = completed_group(client, graph)
    # Emulate a prior API version that committed the manifest before the task callback.
    with Session(client.app.state.engine) as db:
        pending = db.get(Task, task["id"])
        pending.status = "running"
        pending.stage = "uploading"
        pending.progress = 90
        pending.lease_expires_at = now_ms() - 1
        db.commit()
        expire_leases(db)

    result = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert result["status"] == result["stage"] == "succeeded"
    assert result["progress"] == 100 and result["error"] is None
    assert client.get(outputs[0]["media"]["src"]).status_code == 200


def test_work_subset_cover_grants_and_cross_version_replay_are_independent(authenticated, graph):
    client = authenticated
    task, execution, outputs = completed_group(client, graph)
    workflow_id = task["workflowId"]
    assert client.post(f"/api/v1/workflows/{workflow_id}/publish", json={}).status_code == 200
    anonymous = TestClient(client.app)
    body = publish_body(execution, outputs)
    work_response = client.post("/api/v1/works", json=body)
    assert work_response.status_code == 201, work_response.text
    work = work_response.json()
    assert work["assetCount"] == 2 and work["coverArtifactId"] == outputs[1]["id"]
    assert client.post("/api/v1/works", json=body).status_code == 200
    assert client.post("/api/v1/works", json={**body, "title": "changed"}).status_code == 409
    assert anonymous.get("/api/v1/works").json()["items"][0]["id"] == work["id"]
    assert len(anonymous.get(f"/api/v1/works/{work['id']}/artifacts").json()["items"]) == 2
    for output in outputs[:2]:
        assert anonymous.get(output["media"]["src"]).status_code == 200
    assert anonymous.get(outputs[2]["media"]["src"]).status_code == 404
    assert anonymous.get(f"/api/v1/executions/{execution['id']}").status_code == 401
    assert anonymous.get(f"/api/v1/tasks/{task['id']}").status_code == 401
    # 工作流封面取自作者公开的作品，取消公开后随之消失。
    public = anonymous.get(f"/api/v1/workflows/{workflow_id}").json()
    assert public["media"]["src"] == outputs[1]["media"]["src"]
    assert client.delete(f"/api/v1/works/{work['id']}").status_code == 204
    assert anonymous.get(outputs[0]["media"]["src"]).status_code == 404
    assert anonymous.get(f"/api/v1/workflows/{workflow_id}").json()["media"] is None
    assert client.get(outputs[0]["media"]["src"]).status_code == 200
    # Publish again with a new identity; a new workflow version does not rewrite provenance.
    work = client.post("/api/v1/works", json={**body, "id": str(uuid4())}).json()
    revised = client.patch(
        f"/api/v1/workflows/{workflow_id}",
        json={"graph": {**graph, "3": {"class_type": "SaveImage", "inputs": {}}}},
    ).json()
    assert not revised["published"]
    assert revised["media"]["src"] == outputs[1]["media"]["src"]
    with Session(client.app.state.engine) as db:
        from comfyshop_api.models import Workflow

        db.get(Workflow, workflow_id).published = True
        db.commit()
    viewer = TestClient(client.app, headers={"Origin": "http://testserver"})
    session = viewer.post(
        "/api/v1/auth/register", json={"username": "viewer", "password": "viewer-password"}
    ).json()
    viewer.headers["X-CSRF-Token"] = session["csrfToken"]
    machine_key = viewer.post("/api/v1/machines", json={"name": "viewer machine"}).json()
    sync_machine(viewer, machine_key)
    machine = machine_key["machine"]
    replay = viewer.get(f"/api/v1/works/{work['id']}/replay").json()
    assert (
        replay["workflow"]["versionId"] == task["versionId"] and replay["workflow"]["version"] == 1
    )
    created = viewer.post(
        "/api/v1/tasks",
        json={
            "workflowId": workflow_id,
            "versionId": replay["workflow"]["versionId"],
            **task_body(viewer, replay["workflow"], machine["id"]),
            "sourceWorkId": work["id"],
            "machineId": machine["id"],
            "idempotencyKey": str(uuid4()),
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["sourceWorkId"] == work["id"] and created.json()["status"] == "queued"
    assert viewer.get(f"/api/v1/executions/{execution['id']}").status_code == 404
    assert viewer.post("/api/v1/works", json={**body, "id": str(uuid4())}).status_code == 404


def test_failed_batches_keep_completed_groups(authenticated, graph):
    client = authenticated
    task, execution, outputs = completed_group(client, graph)
    workflow = client.get(f"/api/v1/workflows/{task['workflowId']}").json()
    assert workflow["media"]["src"] == outputs[0]["media"]["src"]
    machine_id = task["machineId"]
    # Read the key only from setup's database hash is impossible; create a separate real key.
    key = client.post(f"/api/v1/machines/{machine_id}/rotate").json()["apiKey"]
    next_task = client.post(
        "/api/v1/tasks",
        json={
            "workflowId": task["workflowId"],
            "versionId": task["versionId"],
            **task_body(client, workflow, machine_id),
            "executionCount": 2,
            "machineId": machine_id,
            "idempotencyKey": str(uuid4()),
        },
    ).json()
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + key})
    claim = claim_body()
    worker.post("/api/v1/worker/claim", json=claim)
    partial, _ = run_group(client, worker, next_task["id"], claim["leaseSecret"], 0, 1)
    assert (
        worker.post(
            f"/api/v1/worker/tasks/{next_task['id']}/fail",
            json={"error": "second execution failed"},
            headers={"X-Task-Lease": claim["leaseSecret"]},
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/executions/{partial['id']}").json()["status"] == "succeeded"
    progress = client.get(f"/api/v1/tasks/{next_task['id']}/progress").json()
    assert progress["status"] == "failed" and progress["error"] == "second execution failed"
    assert [item["status"] for item in progress["executions"]] == ["succeeded", "failed"]
    with Session(client.app.state.engine) as db:
        states = list(
            db.scalars(
                select(Execution.status)
                .where(Execution.task_id == next_task["id"])
                .order_by(Execution.index)
            )
        )
        assert states == ["succeeded", "failed"]
        assert not list(db.scalars(select(Work.id)))


def test_draft_keeps_published_work_and_version_accessible(authenticated, graph, settings):
    from test_covers import add_result

    client = authenticated
    task, execution, outputs = completed_group(client, graph)
    workflow_id = task["workflowId"]
    client.post(f"/api/v1/workflows/{workflow_id}/publish", json={})
    work = client.post("/api/v1/works", json=publish_body(execution, outputs)).json()
    anonymous = TestClient(client.app)
    revised = client.patch(
        f"/api/v1/workflows/{workflow_id}",
        json={"graph": {**graph, "3": {"class_type": "SaveImage", "inputs": {}}}},
    ).json()
    assert not revised["published"]
    assert anonymous.get(f"/api/v1/works/{work['id']}").status_code == 200
    assert anonymous.get(outputs[0]["media"]["src"]).status_code == 200
    public = anonymous.get(f"/api/v1/workflows/{workflow_id}").json()
    assert public["versionId"] == task["versionId"]
    assert (
        anonymous.get(
            f"/api/v1/workflows/{workflow_id}", params={"version_id": revised["versionId"]}
        ).status_code
        == 404
    )
    assert (
        client.get("/api/v1/workflows?scope=public").json()["items"][0]["versionId"]
        == task["versionId"]
    )
    assert (
        client.get("/api/v1/workflows?scope=mine").json()["items"][0]["versionId"]
        == revised["versionId"]
    )
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    draft_asset = add_result(client, settings, revised, owner, 10)
    assert anonymous.get(f"/api/v1/artifacts/{draft_asset}/file").status_code == 404
    assert client.post(f"/api/v1/workflows/{workflow_id}/publish", json={}).status_code == 200
    assert (
        anonymous.get(f"/api/v1/workflows/{workflow_id}").json()["versionId"]
        == revised["versionId"]
    )
    assert anonymous.get(f"/api/v1/works/{work['id']}").status_code == 200
    assert anonymous.get(f"/api/v1/artifacts/{draft_asset}/file").status_code == 404
    client.delete(f"/api/v1/workflows/{workflow_id}")
    assert anonymous.get(f"/api/v1/works/{work['id']}").status_code == 404


def test_owner_chooses_the_group_cover_and_it_falls_back_when_deleted(authenticated, graph):
    client = authenticated
    _, execution, outputs = completed_group(client, graph)
    url = f"/api/v1/executions/{execution['id']}"
    assert client.get(url).json()["coverArtifactId"] == outputs[0]["id"]

    chosen = client.put(f"{url}/cover", json={"artifactId": outputs[2]["id"]})
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["coverArtifactId"] == outputs[2]["id"]
    assert chosen.json()["media"]["src"] == outputs[2]["media"]["src"]
    listed = client.get("/api/v1/executions").json()["items"][0]
    assert listed["coverArtifactId"] == outputs[2]["id"]
    assert client.put(f"{url}/cover", json={"artifactId": str(uuid4())}).status_code == 404
    assert TestClient(client.app).put(f"{url}/cover", json={}).status_code == 401

    removed = client.delete(f"/api/v1/artifacts/{outputs[2]['id']}")
    assert removed.json()["coverArtifactId"] == outputs[0]["id"]
    assert client.put(f"{url}/cover", json={"artifactId": outputs[2]["id"]}).status_code == 404


def test_the_output_limit_applies_to_each_execution(authenticated, graph, settings):
    client = authenticated
    settings.max_execution_artifacts = 3
    machine, task, _ = setup_job(client, graph, execution_count=2)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    worker.post("/api/v1/worker/claim", json=claim)
    # 每次执行各自可以回传上限数量的成品，批次的第二次执行不会因为第一次而超限。
    run_group(client, worker, task["id"], claim["leaseSecret"], index=0, members=3)
    run_group(client, worker, task["id"], claim["leaseSecret"], index=1, members=3)
    done = worker.post(
        f"/api/v1/worker/tasks/{task['id']}/complete",
        headers={"X-Task-Lease": claim["leaseSecret"]},
    )
    assert done.status_code == 200, done.text
    # 按 ID 读取任务时带上代表成品，列表里刚结束的任务不必重新分页就能显示结果。
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["media"] is not None
