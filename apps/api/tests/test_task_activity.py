from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event

from test_outputs import run_group
from test_worker import claim_body, setup_job


def test_queue_wait_reason_tracks_the_assigned_machine(authenticated, graph):
    client = authenticated
    machine, original, body = setup_job(client, graph)
    response = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())})
    assert response.status_code == 201
    queued_id = response.json()["id"]
    url = f"/api/v1/tasks/{queued_id}/progress"
    assert client.get(url).json()["waitReason"] == "machine_offline"

    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    heartbeat = worker.post("/api/v1/worker/heartbeat", json={"protocolVersion": 3})
    assert heartbeat.status_code == 200 and heartbeat.json()["online"]
    assert client.get(url).json()["waitReason"] is None
    claim = worker.post("/api/v1/worker/claim", json=claim_body()).json()
    active_id = claim["task"]["id"]
    assert active_id in {original["id"], queued_id}
    waiting_id = queued_id if active_id == original["id"] else original["id"]
    waiting = client.get(f"/api/v1/tasks/{waiting_id}/progress").json()
    assert waiting["status"] == "queued" and waiting["waitReason"] == "machine_busy"
    assert client.get(f"/api/v1/tasks/{active_id}/progress").json()["waitReason"] is None
    cancelled = client.post(f"/api/v1/tasks/{waiting_id}/cancel")
    assert cancelled.status_code == 200
    assert client.get(f"/api/v1/tasks/{waiting_id}/progress").json()["waitReason"] is None


def test_task_and_machine_reads_succeed_while_sqlite_writer_is_locked(authenticated, graph):
    client = authenticated
    _, task, _ = setup_job(client, graph)
    engine = client.app.state.engine

    def use_short_busy_timeout(connection, _record, _proxy):
        connection.execute("PRAGMA busy_timeout=50").close()

    event.listen(engine, "checkout", use_short_busy_timeout)
    try:
        with engine.connect() as writer:
            writer.exec_driver_sql("BEGIN IMMEDIATE")
            task_path = f"tasks/{task['id']}"
            for path in [
                "tasks",
                task_path,
                f"{task_path}/progress",
                f"{task_path}/inputs",
                "tasks/activity",
                "machines",
            ]:
                response = client.get(f"/api/v1/{path}")
                assert response.status_code == 200, path
            assert client.get("/api/v1/tasks").json()["items"][0]["status"] == "queued"
    finally:
        event.remove(engine, "checkout", use_short_busy_timeout)


def test_activity_tracks_partial_results_and_respects_task_scope(authenticated, graph):
    client = authenticated
    machine, original, body = setup_job(client, graph)
    assert client.post(f"/api/v1/tasks/{original['id']}/cancel").status_code == 200
    response = client.post(
        "/api/v1/tasks", json={**body, "executionCount": 2, "idempotencyKey": str(uuid4())}
    )
    assert response.status_code == 201
    batch = response.json()
    _, unrelated, _ = setup_job(client, graph)
    progress_url = f"/api/v1/tasks/{batch['id']}/progress"
    inputs_url = f"/api/v1/tasks/{batch['id']}/inputs"
    queued = client.get(progress_url).json()
    assert queued["status"] == "queued" and queued["progress"] == 0
    assert queued["machineName"] == machine["machine"]["name"]
    assert [(item["index"], item["status"]) for item in queued["executions"]] == [
        (0, "queued"),
        (1, "queued"),
    ]

    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    assert worker.post("/api/v1/worker/claim", json=claim).json()["task"]["id"] == batch["id"]
    assert client.get(progress_url).json()["stage"] == "preflight"
    run_group(client, worker, batch["id"], claim["leaseSecret"], members=1)
    heartbeat = worker.post(
        f"/api/v1/worker/tasks/{batch['id']}/heartbeat",
        headers={"X-Task-Lease": claim["leaseSecret"]},
        json={"sequence": 3, "stage": "uploading", "executionIndex": 1, "progress": 92},
    )
    assert heartbeat.status_code == 200
    uploading = client.get(progress_url).json()
    assert (uploading["status"], uploading["stage"], uploading["progress"]) == (
        "running",
        "uploading",
        92,
    )
    assert [item["status"] for item in uploading["executions"]] == ["succeeded", "running"]

    url = "/api/v1/tasks/activity"
    activity = client.get(url, params={"workflow_id": batch["workflowId"]}).json()
    assert activity["completedExecutions"] == 1
    assert len(activity["activeTasks"]) == 1
    active = activity["activeTasks"][0]
    assert set(active) == {"id", "status", "progress", "stage", "updated"}
    assert active["id"] == batch["id"] and active["status"] == "running"
    assert client.get(url, params={"task_id": batch["id"]}).json() == activity
    other = client.get(url, params={"workflow_id": unrelated["workflowId"]}).json()
    assert other["completedExecutions"] == 0
    assert [row["id"] for row in other["activeTasks"]] == [unrelated["id"]]

    run_group(client, worker, batch["id"], claim["leaseSecret"], index=1, members=1)
    finished = client.get(progress_url).json()
    assert finished["status"] == "succeeded" and finished["progress"] == 100
    assert [item["status"] for item in finished["executions"]] == ["succeeded", "succeeded"]
    assert client.get(url, params={"task_id": batch["id"]}).json() == {
        "activeTasks": [],
        "completedExecutions": 2,
    }

    visitor = TestClient(client.app, headers={"Origin": "http://testserver"})
    assert visitor.get(url).status_code == 401
    assert visitor.get(progress_url).status_code == 401
    assert visitor.get(inputs_url).status_code == 401
    assert (
        visitor.post(
            "/api/v1/auth/register", json={"username": "other", "password": "other-account"}
        ).status_code
        == 201
    )
    assert visitor.get(progress_url).status_code == 404
    assert visitor.get(inputs_url).status_code == 404
    assert visitor.get(url, params={"task_id": batch["id"]}).json() == {
        "activeTasks": [],
        "completedExecutions": 0,
    }


def test_task_list_filters_by_state(authenticated, graph):
    client = authenticated
    _, waiting, body = setup_job(client, graph)
    cancelled = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())}).json()
    assert client.post(f"/api/v1/tasks/{cancelled['id']}/cancel").status_code == 200

    def listed(state):
        page = client.get("/api/v1/tasks", params={"state": state} if state else {}).json()
        return {task["id"] for task in page["items"]}

    assert listed(None) == {waiting["id"], cancelled["id"]}
    assert listed("active") == {waiting["id"]}
    assert listed("cancelled") == {cancelled["id"]}
    assert listed("succeeded") == set()


def test_stopping_a_running_task_releases_the_machine_and_tells_the_worker(authenticated, graph):
    client = authenticated
    machine, running, body = setup_job(client, graph)
    queued = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())}).json()
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    assert worker.post("/api/v1/worker/heartbeat", json={"protocolVersion": 3}).status_code == 200
    claim = claim_body()
    claimed = worker.post("/api/v1/worker/claim", json=claim).json()
    assert claimed["task"]["id"] == running["id"]

    stopped = client.post(f"/api/v1/tasks/{running['id']}/cancel")
    assert stopped.status_code == 200 and stopped.json()["status"] == "cancelled"
    heartbeat = worker.post(
        f"/api/v1/worker/tasks/{running['id']}/heartbeat",
        json={"sequence": 1, "progress": 10, "stage": "executing", "executionIndex": 0},
        headers={"X-Task-Lease": claim["leaseSecret"]},
    )
    assert heartbeat.status_code == 409 and heartbeat.json()["detail"] == "任务已取消"
    # 工作机不再被这次领取占用，可以领取后面的排队任务。
    following = worker.post("/api/v1/worker/claim", json=claim_body()).json()
    assert following["task"]["id"] == queued["id"]
    assert client.post(f"/api/v1/tasks/{running['id']}/cancel").status_code == 200
