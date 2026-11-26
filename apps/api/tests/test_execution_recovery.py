from uuid import uuid4

from sqlalchemy.orm import Session
from test_failed_artifacts import claim_job, report_failure, start_execution, upload_output
from test_outputs import run_group
from test_worker import claim_body

from comfyshop_api.models import Task, now_ms


def test_recovers_the_original_group_and_reruns_only_missing_seeds(authenticated, graph):
    client = authenticated
    task, worker, base = claim_job(client, graph, 8)
    task_path = f"/api/v1/tasks/{task['id']}"
    for index in range(3):
        run_group(client, worker, task["id"], worker.headers["X-Task-Lease"], index, members=1)
    start_execution(worker, base, 3)
    first = upload_output(worker, base, 3).raise_for_status().json()
    report_failure(worker, base)
    assert upload_output(worker, base, 3, 1).status_code == 409

    recovery_path = base + "/executions/3/recovery"
    expected = {"promptId": "prompt-3", "outcome": "outputs"}
    assert worker.put(recovery_path, json={**expected, "promptId": "different"}).status_code == 409
    recovered = worker.put(recovery_path, json=expected).raise_for_status().json()
    assert recovered == {"action": "upload", "clientIds": ["r3_0"]}
    rows = client.get(task_path + "/progress").raise_for_status().json()["executions"]
    assert [row["recovery"] for row in rows] == [None] * 3 + ["uploading"] + ["rerunnable"] * 4

    retry_path = task_path + "/retry-executions"
    body = {
        "machineId": task["machineId"],
        "executionIndices": [4, 5, 6, 7],
        "idempotencyKey": str(uuid4()),
    }
    assert client.post(retry_path, json={**body, "executionIndices": [3, 4]}).status_code == 409
    retry = client.post(retry_path, json=body)
    assert retry.status_code == 201, retry.text
    assert retry.json()["executionCount"] == 4
    repeated = client.post(retry_path, json=body)
    assert repeated.status_code == 200 and repeated.json()["id"] == retry.json()["id"]
    assert client.post(retry_path, json={**body, "idempotencyKey": str(uuid4())}).status_code == 409

    worker.headers["X-Task-Recovery"] = "1"
    second = upload_output(worker, base, 3, 1).raise_for_status().json()
    complete = base + "/executions/3/complete"
    manifest = {"clientIds": ["r3_0", "r3_1"]}
    for _ in range(2):
        assert (
            worker.post(complete, json=manifest).raise_for_status().json()["status"] == "succeeded"
        )
    for item in (first, second):
        assert client.get(item["media"]["src"]).status_code == 200
    assert client.get("/api/v1/executions", params={"task_id": task["id"]}).json()["items"]
    rows = client.get(task_path + "/progress").json()["executions"]
    assert [row["status"] for row in rows[:4]] == ["succeeded"] * 4
    assert {row["retryTaskId"] for row in rows[4:]} == {retry.json()["id"]}
    rerun = worker.post("/api/v1/worker/claim", json=claim_body()).raise_for_status().json()
    assert rerun["task"]["id"] == retry.json()["id"]
    assert [binding[0]["value"] for binding in rerun["executionSeeds"]] == ["46", "47", "48", "49"]


def test_failed_prompt_requires_original_machine_confirmation_before_retry(authenticated, graph):
    client = authenticated
    task, worker, base = claim_job(client, graph)
    start_execution(worker, base, 0)
    report_failure(worker, base)
    path = f"/api/v1/tasks/{task['id']}/retry-executions"
    body = {
        "machineId": task["machineId"],
        "executionIndices": [0],
        "idempotencyKey": str(uuid4()),
    }
    assert client.post(path, json=body).status_code == 409
    recovery = worker.put(
        base + "/executions/0/recovery", json={"promptId": "prompt-0", "outcome": "missing"}
    )
    assert recovery.status_code == 200
    assert client.post(path, json=body).status_code == 201
    denied = worker.put(
        base + "/executions/0/recovery", json={"promptId": "prompt-0", "outcome": "outputs"}
    )
    assert denied.status_code == 409


def test_recovery_settles_an_expired_lease_before_opening_uploads(authenticated, graph):
    client = authenticated
    task, worker, base = claim_job(client, graph)
    start_execution(worker, base, 0)
    with Session(client.app.state.engine) as db:
        db.get(Task, task["id"]).lease_expires_at = now_ms() - 1
        db.commit()
    recovery = worker.put(
        base + "/executions/0/recovery", json={"promptId": "prompt-0", "outcome": "outputs"}
    )
    assert recovery.raise_for_status().json()["action"] == "upload"
