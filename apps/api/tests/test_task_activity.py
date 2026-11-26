from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from helpers import expire_machine_heartbeat, machine_heartbeat
from sqlalchemy import event
from sqlalchemy.orm import Session
from test_outputs import run_group
from test_worker import claim_body, setup_job

from comfyshop_api.models import Machine


def test_offline_machine_rejects_new_tasks_and_keeps_its_queue(authenticated, graph):
    client = authenticated
    machine, original, body = setup_job(client, graph)
    response = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())})
    assert response.status_code == 201
    queued_id = response.json()["id"]
    machine_id = machine["machine"]["id"]
    expire_machine_heartbeat(client, machine_id)
    url = f"/api/v1/tasks/{queued_id}/progress"
    assert client.get(url).json()["waitReason"] == "machine_offline"

    assert client.put(f"/api/v1/machines/{machine_id}/default").status_code == 204
    new_task = {**body, "idempotencyKey": str(uuid4())}
    for requested_id in (machine_id, None):
        blocked = client.post("/api/v1/tasks", json={**new_task, "machineId": requested_id})
        assert blocked.status_code == 409 and "离线" in blocked.json()["detail"]
    repeated = client.post("/api/v1/tasks", json=body)
    assert repeated.status_code == 200
    assert (repeated.json()["id"], repeated.json()["machineId"], repeated.json()["status"]) == (
        original["id"],
        machine_id,
        "queued",
    )
    assert len(client.get("/api/v1/tasks").json()["items"]) == 2

    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    heartbeat = worker.post("/api/v1/worker/heartbeat", json=machine_heartbeat())
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


def test_pausing_a_machine_keeps_its_lease_and_queue(authenticated, graph):
    client = authenticated
    machine, current, body = setup_job(client, graph)
    path = f"/api/v1/machines/{machine['machine']['id']}"
    assert machine["machine"]["paused"] is False
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    assert worker.post("/api/v1/worker/claim", json=claim).json()["task"]["id"] == current["id"]

    first = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())}).json()
    for _ in range(2):
        assert client.put(f"{path}/pause", json={"paused": True}).status_code == 204
    second = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())}).json()
    detail = client.get(path).json()
    assert detail["machine"]["paused"] is True
    assert detail["currentTask"]["id"] == current["id"] and detail["queuedCount"] == 2
    # 工作机丢失领取回执后，仍可用原领取编号恢复正在执行的任务。
    assert worker.post("/api/v1/worker/claim", json=claim).json()["task"]["id"] == current["id"]
    completed, outputs = run_group(client, worker, current["id"], claim["leaseSecret"], members=1)
    assert completed["status"] == "succeeded" and len(outputs) == 1
    assert client.get(f"/api/v1/tasks/{current['id']}").json()["status"] == "succeeded"

    next_claim = claim_body()
    assert worker.post("/api/v1/worker/claim", json=next_claim).json() is None
    for task in (first, second):
        waiting = client.get(f"/api/v1/tasks/{task['id']}/progress").json()
        assert waiting["status"] == "queued" and waiting["waitReason"] == "machine_paused"
    for _ in range(2):
        assert client.put(f"{path}/pause", json={"paused": False}).status_code == 204
    assert client.get(f"/api/v1/tasks/{first['id']}/progress").json()["waitReason"] is None
    assert worker.post("/api/v1/worker/claim", json=next_claim).json()["task"]["id"] == first["id"]


def test_queue_reason_distinguishes_local_work_from_platform_connection(authenticated, graph):
    client = authenticated
    machine, task, _ = setup_job(client, graph)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    progress = f"/api/v1/tasks/{task['id']}/progress"
    for status, reason in [("busy", "comfy_busy"), ("unreachable", "comfy_unreachable")]:
        heartbeat = (
            worker.post(
                "/api/v1/worker/heartbeat",
                json=machine_heartbeat(comfyStatus=status),
            )
            .raise_for_status()
            .json()
        )
        assert heartbeat["online"] and heartbeat["comfyStatus"] == status
        assert heartbeat["catalogSyncedAt"] is not None
        assert client.get(progress).json()["waitReason"] == reason
    with Session(client.app.state.engine) as db:
        db.get(Machine, machine["machine"]["id"]).update_info = {
            "status": "updating",
            "id": str(uuid4()),
        }
        db.commit()
    assert client.get(progress).json()["waitReason"] == "machine_updating"


def test_changing_a_waiting_tasks_machine_preserves_the_snapshot_and_joins_the_tail(
    authenticated, graph
):
    client = authenticated
    source, task, _ = setup_job(client, graph, execution_count=3)
    target, earlier, _ = setup_job(client, graph)
    task_path = f"/api/v1/tasks/{task['id']}"
    target_id = target["machine"]["id"]
    source_worker = TestClient(client.app, headers={"Authorization": "Bearer " + source["apiKey"]})
    target_worker = TestClient(client.app, headers={"Authorization": "Bearer " + target["apiKey"]})
    inputs = client.get(task_path + "/inputs").json()
    assert client.get(task_path + "/progress").json()["queueAhead"] == 0
    assert task["machineName"] == source["machine"]["name"]
    client.patch(f"/api/v1/machines/{target_id}", json={"name": "备用工作机"}).raise_for_status()
    reassigned = (
        client.put(task_path + "/machine", json={"machineId": target_id}).raise_for_status().json()
    )
    assert reassigned["machineId"] == target_id and reassigned["machineName"] == "备用工作机"
    assert client.get(task_path + "/inputs").json() == inputs
    moved = client.get(task_path + "/progress").json()
    assert (moved["machineId"], moved["queueAhead"]) == (target_id, 1)
    assert source_worker.post("/api/v1/worker/claim", json=claim_body()).json() is None
    first = target_worker.post("/api/v1/worker/claim", json=claim_body()).json()
    assert first["task"]["id"] == earlier["id"]
    assert client.get(task_path + "/progress").json()["queueAhead"] == 0
    assert client.post(f"/api/v1/tasks/{earlier['id']}/cancel").status_code == 200
    second = target_worker.post("/api/v1/worker/claim", json=claim_body()).json()
    assert second["task"]["id"] == task["id"]
    assert [binding[0]["value"] for binding in second["executionSeeds"]] == ["42", "43", "44"]


def test_changing_work_machines_and_claiming_the_same_task_are_exclusive(authenticated, graph):
    client = authenticated
    source, task, _ = setup_job(client, graph)
    target, _, _ = setup_job(client, graph)
    target_id = target["machine"]["id"]
    task_path = f"/api/v1/tasks/{task['id']}"
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + source["apiKey"]})
    start = Barrier(2)

    def change():
        start.wait(timeout=5)
        return client.put(task_path + "/machine", json={"machineId": target_id})

    def claim():
        start.wait(timeout=5)
        return worker.post("/api/v1/worker/claim", json=claim_body()).raise_for_status().json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        changing, claiming = pool.submit(change), pool.submit(claim)
        response, job = changing.result(), claiming.result()
    assert response.status_code == (409 if job else 200)
    if job:
        assert job["task"]["id"] == task["id"]
    else:
        assert response.json()["machineId"] == target_id


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
    assert worker.post("/api/v1/worker/heartbeat", json=machine_heartbeat()).status_code == 200
    claim = claim_body()
    claimed = worker.post("/api/v1/worker/claim", json=claim).json()
    assert claimed["task"]["id"] == running["id"]

    stopped = client.post(f"/api/v1/tasks/{running['id']}/cancel")
    assert stopped.status_code == 200 and stopped.json()["status"] == "cancelled"
    heartbeat = worker.post(
        f"/api/v1/worker/tasks/{running['id']}/heartbeat",
        json={"sequence": 1, "progress": 10, "stage": "executing", "executionIndex": 0},
        headers={"X-Task-Lease": claim["leaseSecret"], "Accept-Language": "en"},
    )
    assert heartbeat.status_code == 409 and heartbeat.json()["detail"] == "Task canceled"
    assert heartbeat.headers["X-ComfyShop-Error-Code"] == "task_cancelled"
    # 工作机不再被这次领取占用，可以领取后面的排队任务。
    following = worker.post("/api/v1/worker/claim", json=claim_body()).json()
    assert following["task"]["id"] == queued["id"]
    assert client.post(f"/api/v1/tasks/{running['id']}/cancel").status_code == 200
