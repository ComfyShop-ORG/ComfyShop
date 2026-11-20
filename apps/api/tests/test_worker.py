from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from comfyshop_api.models import Machine, MachineLink, Task, now_ms
from helpers import sync_machine, task_body


def setup_job(client, graph, *, execution_count=1):
    machine = client.post("/api/v1/machines", json={"name": "4090"}).json()
    workflow = client.post("/api/v1/workflows", json={"name": "产品图", "graph": graph}).json()
    sync_machine(client, machine)
    body = task_body(client, workflow, machine["machine"]["id"])
    body["executionCount"] = execution_count
    task = client.post("/api/v1/tasks", json=body)
    assert task.status_code == 201, task.text
    return machine, task.json(), body


def claim_body():
    return {"protocolVersion": 3, "claimId": str(uuid4()), "leaseSecret": uuid4().hex + uuid4().hex}


def image_bytes():
    buffer = BytesIO()
    Image.new("RGB", (24, 32), (45, 70, 80)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_worker_key_isolation_claim_and_completion(authenticated, graph):
    client = authenticated
    machine, task, _ = setup_job(client, graph)
    assert client.post("/api/v1/worker/claim", json=claim_body()).status_code == 401
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    assert worker.get("/api/v1/tasks").status_code == 401
    assert worker.post("/api/v1/worker/heartbeat", json={"device": "4090"}).status_code == 422
    assert worker.post("/api/v1/worker/heartbeat", json={"protocolVersion": 99}).status_code == 422
    unsupported_claim = {**claim_body(), "protocolVersion": 99}
    assert worker.post("/api/v1/worker/claim", json=unsupported_claim).status_code == 422
    claim_without_version = claim_body()
    del claim_without_version["protocolVersion"]
    assert worker.post("/api/v1/worker/claim", json=claim_without_version).status_code == 422
    assert worker.post(
        "/api/v1/worker/heartbeat",
        json={"protocolVersion": 3, "device": "4090", "nodes": ["KSampler"]},
    ).json()["online"]
    claim = claim_body()
    first = worker.post("/api/v1/worker/claim", json=claim)
    assert first.status_code == 200, first.text
    assert first.json()["task"]["id"] == task["id"]
    assert worker.post("/api/v1/worker/claim", json=claim).json()["task"]["id"] == task["id"]
    assert worker.post("/api/v1/worker/claim", json=claim_body()).json() is None
    headers = {"X-Task-Lease": claim["leaseSecret"]}
    base = f"/api/v1/worker/tasks/{task['id']}"
    assert worker.post(base + "/complete", headers=headers).status_code == 409
    assert (
        worker.post(
            base + "/heartbeat",
            json={"sequence": 1, "progress": 1, "stage": "preflight"},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        worker.post(
            base + "/heartbeat",
            json={
                "sequence": 2,
                "progress": 65,
                "stage": "executing",
                "promptId": "actual-prompt",
                "executionIndex": 0,
            },
            headers=headers,
        ).status_code
        == 200
    )
    older = worker.post(
        base + "/heartbeat",
        json={"sequence": 1, "progress": 1, "stage": "preflight", "executionIndex": 0},
        headers=headers,
    ).json()
    assert older["progress"] == 65 and older["stage"] == "executing"
    data = image_bytes()
    assert (
        worker.put(
            base + "/artifacts/r0_unbound",
            params={"filename": "old.png", "sha256": hashlib.sha256(data).hexdigest()},
            content=data,
            headers=headers,
        ).status_code
        == 422
    )
    params = {
        "filename": "product.png",
        "sha256": hashlib.sha256(data).hexdigest(),
        "execution_index": 0,
        "output_node_id": "2",
        "output_slot": "images",
        "output_index": 0,
    }
    uploaded = worker.put(base + "/artifacts/image1", params=params, content=data, headers=headers)
    assert uploaded.status_code == 200, uploaded.text
    asset = uploaded.json()
    assert (asset["media"]["width"], asset["media"]["height"]) == (24, 32)
    assert "published" not in asset
    assert (
        worker.put(base + "/artifacts/image1", params=params, content=data, headers=headers).json()[
            "id"
        ]
        == asset["id"]
    )
    assert client.get(asset["media"]["src"]).status_code == 404
    assert worker.post(base + "/complete", headers=headers).status_code == 409
    assert (
        worker.post(
            base + "/executions/0/start", json={"promptId": "actual-prompt"}, headers=headers
        ).status_code
        == 200
    )
    assert (
        worker.post(
            base + "/executions/0/complete", json={"clientIds": ["image1"]}, headers=headers
        ).status_code
        == 200
    )
    assert worker.post(base + "/complete", headers=headers).json()["status"] == "succeeded"
    assert worker.post(base + "/complete", headers=headers).json()["progress"] == 100
    assert client.get(asset["media"]["src"]).content == data
    assert client.get(asset["media"]["src"], headers={"Range": "bytes=0-9"}).status_code == 206
    anonymous = TestClient(client.app)
    assert anonymous.get(asset["media"]["src"]).status_code == 404
    assert (
        client.post(f"/api/v1/workflows/{task['workflowId']}/publish", json={}).status_code == 200
    )
    assert (
        client.post(
            "/api/v1/works",
            json={
                "id": str(uuid4()),
                "executionId": asset["executionId"],
                "title": "图片",
                "artifactIds": [asset["id"]],
                "coverArtifactId": asset["id"],
            },
        ).status_code
        == 201
    )
    assert anonymous.get(asset["media"]["src"]).status_code == 200
    assert len(client.get("/api/v1/artifacts").json()["items"]) == 1
    with Session(client.app.state.engine) as db:
        assert db.get(Machine, machine["machine"]["id"]).key_hash != machine["apiKey"]


def test_concurrent_claims_are_exclusive_and_expiry_fences_callbacks(authenticated, graph):
    client = authenticated
    machine, task, body = setup_job(client, graph)
    for _ in range(2):
        assert (
            client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())}).status_code
            == 201
        )
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claims = [claim_body() for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(
            pool.map(lambda claim: worker.post("/api/v1/worker/claim", json=claim), claims)
        )
    assert all(r.status_code == 200 for r in responses)
    jobs = [(i, r.json()) for i, r in enumerate(responses) if r.json()]
    assert len(jobs) == 1
    index, job = jobs[0]
    task_id = job["task"]["id"]
    with Session(client.app.state.engine) as db:
        db.get(Task, task_id).lease_expires_at = now_ms() - 1
        db.get(Machine, machine["machine"]["id"]).busy_until = now_ms() - 1
        db.commit()
    stale = worker.post(
        f"/api/v1/worker/tasks/{task_id}/heartbeat",
        json={"sequence": 1, "progress": 99, "stage": "uploading", "executionIndex": 0},
        headers={"X-Task-Lease": claims[index]["leaseSecret"]},
    )
    assert stale.status_code == 409
    next_job = worker.post("/api/v1/worker/claim", json=claim_body()).json()
    assert next_job["task"]["id"] != task_id
    assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "failed"


def test_wrong_machine_revocation_and_corrupt_upload(authenticated, graph, settings):
    client = authenticated
    machine, task, _ = setup_job(client, graph)
    second = client.post("/api/v1/machines", json={"name": "second"}).json()
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    other = TestClient(client.app, headers={"Authorization": "Bearer " + second["apiKey"]})
    claim = claim_body()
    worker.post("/api/v1/worker/claim", json=claim)
    base = f"/api/v1/worker/tasks/{task['id']}"
    headers = {"X-Task-Lease": claim["leaseSecret"]}
    assert other.post(base + "/complete", headers=headers).status_code == 404
    assert worker.post(base + "/complete", headers={"X-Task-Lease": "wrong"}).status_code == 409
    assert (
        worker.put(
            base + "/artifacts/bad",
            params={
                "filename": "bad.png",
                "sha256": "0" * 64,
                "execution_index": 0,
                "output_node_id": "2",
                "output_slot": "images",
                "output_index": 0,
            },
            content=image_bytes(),
            headers=headers,
        ).status_code
        == 422
    )
    data = b"<html>not an image</html>"
    assert (
        worker.put(
            base + "/artifacts/html",
            params={
                "filename": "fake.png",
                "sha256": hashlib.sha256(data).hexdigest(),
                "execution_index": 0,
                "output_node_id": "2",
                "output_slot": "images",
                "output_index": 0,
            },
            content=data,
            headers=headers,
        ).status_code
        == 422
    )
    assert not settings.original_dir.exists() or not any(settings.original_dir.iterdir())
    settings.max_artifact_bytes = 1024
    oversized = b"x" * 1025
    assert (
        worker.put(
            base + "/artifacts/large",
            params={
                "filename": "large.png",
                "sha256": hashlib.sha256(oversized).hexdigest(),
                "execution_index": 0,
                "output_node_id": "2",
                "output_slot": "images",
                "output_index": 0,
            },
            content=oversized,
            headers=headers,
        ).status_code
        == 413
    )
    rotated = client.post(f"/api/v1/machines/{machine['machine']['id']}/rotate").json()
    assert rotated["apiKey"] != machine["apiKey"]
    assert worker.post("/api/v1/worker/claim", json=claim_body()).status_code == 401
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["status"] == "failed"
    assert client.get("/api/v1/artifacts").json()["items"] == []
    assert client.delete(f"/api/v1/machines/{machine['machine']['id']}").json()["revoked"]
    assert (
        client.post(
            "/api/v1/worker/heartbeat",
            headers={"Authorization": "Bearer " + rotated["apiKey"]},
            json={},
        ).status_code
        == 401
    )


def test_machine_preferences_and_assignment_cannot_cross_accounts(authenticated, graph):
    client = authenticated
    _, _, body = setup_job(client, graph)
    other = TestClient(client.app, headers={"Origin": "http://testserver"})
    registered = other.post(
        "/api/v1/auth/register",
        json={"username": "other-worker-owner", "password": "different-password"},
    ).json()
    other.headers["X-CSRF-Token"] = registered["csrfToken"]
    foreign = other.post("/api/v1/machines", json={"name": "foreign"}).json()["machine"]
    assert client.put(f"/api/v1/machines/{foreign['id']}/default").status_code == 404
    assert (
        client.post(
            "/api/v1/tasks",
            json={**body, "idempotencyKey": str(uuid4()), "machineId": foreign["id"]},
        ).status_code
        == 409
    )
    assert all(
        m["id"] != foreign["id"] and "apiKey" not in m
        for m in client.get("/api/v1/machines").json()["items"]
    )


def test_first_start_link_is_approved_in_the_browser_and_redeemed_once(client):
    start = client.post("/api/v1/worker/links", json={"name": "studio-pc"})
    assert start.status_code == 201
    link = start.json()
    token = {"secret": link["secret"]}
    assert client.post("/api/v1/worker/links/token", json=token).json() == {
        "status": "pending",
        "apiKey": None,
        "machineName": None,
    }
    # 确认页需要登录。
    assert client.get(f"/api/v1/machines/links/{link['code']}").status_code == 401
    session = client.post(
        "/api/v1/auth/register", json={"username": "owner", "password": "correct-horse-battery"}
    ).json()
    client.headers["X-CSRF-Token"] = session["csrfToken"]
    spaced = f"{link['code'][:4].lower()}-{link['code'][4:]}"
    shown = client.get(f"/api/v1/machines/links/{spaced}").json()
    assert shown["name"] == "studio-pc"
    assert shown["status"] == "pending"
    # 测试客户端的来源不是合法 IP，地址未知时不判断是否同一网络。
    assert shown["requestedAt"] <= shown["expiresAt"]
    assert shown["source"] == "" and not shown["sameNetwork"]
    approved = client.post(f"/api/v1/machines/links/{spaced}/approve", json={"name": "工作室"})
    assert approved.status_code == 204
    # 确认账号可查看进度，工作机兑换密钥前列表仍为空。
    shown = client.get(f"/api/v1/machines/links/{link['code']}").json()
    assert shown["status"] == "approved" and shown["name"] == "工作室"
    assert client.get("/api/v1/machines").json()["items"] == []
    lost = client.post("/api/v1/worker/links/token", json=token).json()
    assert lost["status"] == "approved" and lost["machineName"] == "工作室"
    assert client.get(f"/api/v1/machines/links/{link['code']}").json()["status"] == "linked"
    # 回复丢失后工作机重试：同一台工作机换发密钥，丢失的那份失效，不会多出一台。
    redeemed = client.post("/api/v1/worker/links/token", json=token).json()
    assert redeemed["status"] == "approved" and redeemed["apiKey"] != lost["apiKey"]
    stale = client.post(
        "/api/v1/worker/heartbeat",
        json={"protocolVersion": 3, "device": "cpu"},
        headers={"Authorization": "Bearer " + lost["apiKey"]},
    )
    assert stale.status_code == 401
    machines = client.get("/api/v1/machines").json()
    assert [machine["name"] for machine in machines["items"]] == ["工作室"]
    assert machines["defaultMachineId"] == machines["items"][0]["id"]
    heartbeat = client.post(
        "/api/v1/worker/heartbeat",
        json={"protocolVersion": 3, "device": "cpu"},
        headers={"Authorization": "Bearer " + redeemed["apiKey"]},
    )
    assert heartbeat.status_code == 200, heartbeat.text


def test_reinstalled_worker_reconnects_to_the_same_machine_and_claims_its_queue(
    authenticated, graph
):
    client = authenticated
    original, task, _ = setup_job(client, graph)
    machine_id = original["machine"]["id"]
    assert client.put(f"/api/v1/machines/{machine_id}/default").status_code == 204
    sibling = client.post("/api/v1/machines", json={"name": "4090"}).json()
    heartbeat = {"protocolVersion": 3, "device": "shared-host"}
    for machine in (original, sibling):
        worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
        assert worker.post("/api/v1/worker/heartbeat", json=heartbeat).status_code == 200
    with Session(client.app.state.engine) as db:
        db.get(Machine, machine_id).last_seen = now_ms() - 60_000
        db.commit()

    previous = client.get("/api/v1/machines").json()
    link = client.post("/api/v1/worker/links", json={"name": "shared-host"}).json()
    path = f"/api/v1/machines/links/{link['code']}"
    assert client.post(path + "/approve", json={"machineId": machine_id}).status_code == 204
    approval = client.get(path).json()
    assert (approval["status"], approval["name"]) == ("approved", original["machine"]["name"])
    assert client.get("/api/v1/machines").json() == previous

    token = {"secret": link["secret"]}
    lost_key = client.post("/api/v1/worker/links/token", json=token).json()["apiKey"]
    new_key = client.post("/api/v1/worker/links/token", json=token).json()["apiKey"]
    assert client.get(path).json()["status"] == "linked"
    for stale in (original["apiKey"], lost_key):
        assert (
            client.post(
                "/api/v1/worker/heartbeat",
                json=heartbeat,
                headers={"Authorization": "Bearer " + stale},
            ).status_code
            == 401
        )
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + new_key})
    connected = worker.post("/api/v1/worker/heartbeat", json=heartbeat).json()
    assert connected["id"] == machine_id and connected["online"]
    assert client.post("/api/v1/worker/links/token", json=token).status_code == 410
    current = client.get("/api/v1/machines").json()
    assert current["defaultMachineId"] == machine_id
    assert [machine["id"] for machine in current["items"]] == [
        machine["id"] for machine in previous["items"]
    ]
    assert worker.post("/api/v1/worker/claim", json=claim_body()).json()["task"]["id"] == task["id"]
    sibling_worker = TestClient(
        client.app, headers={"Authorization": "Bearer " + sibling["apiKey"]}
    )
    assert sibling_worker.post("/api/v1/worker/heartbeat", json=heartbeat).status_code == 200


def test_reconnection_checks_ownership_and_availability_before_issuing_a_key(authenticated):
    client = authenticated
    other = TestClient(client.app, headers={"Origin": "http://testserver"})
    session = other.post(
        "/api/v1/auth/register", json={"username": "other-owner", "password": "different-password"}
    ).json()
    other.headers["X-CSRF-Token"] = session["csrfToken"]
    original = client.post("/api/v1/machines", json={"name": "原工作机"}).json()
    machine_id = original["machine"]["id"]
    body = {"machineId": machine_id}
    link = client.post("/api/v1/worker/links", json={}).json()
    path = f"/api/v1/machines/links/{link['code']}"
    assert other.post(path + "/approve", json=body).status_code == 404
    with Session(client.app.state.engine) as db:
        db.get(Machine, machine_id).busy_until = now_ms() + 60_000
        db.commit()
    assert client.post(path + "/approve", json=body).status_code == 409
    with Session(client.app.state.engine) as db:
        db.get(Machine, machine_id).busy_until = 0
        db.commit()
    assert client.post(path + "/approve", json={**body, "name": "另一台"}).status_code == 422
    assert client.post(path + "/approve", json=body).status_code == 204

    worker = TestClient(client.app, headers={"Authorization": "Bearer " + original["apiKey"]})
    assert worker.post("/api/v1/worker/heartbeat", json={"protocolVersion": 3}).status_code == 200
    token = {"secret": link["secret"]}
    assert client.post("/api/v1/worker/links/token", json=token).status_code == 409
    assert client.get(path).status_code == 409
    assert worker.post("/api/v1/worker/heartbeat", json={"protocolVersion": 3}).status_code == 200
    assert client.post(f"/api/v1/machines/{machine_id}/rotate").status_code == 200
    assert client.post("/api/v1/worker/links/token", json=token).status_code == 410


def test_expired_link_cannot_be_approved_or_redeemed(client, monkeypatch):
    from comfyshop_api.services import machine_links

    link = client.post("/api/v1/worker/links", json={}).json()
    monkeypatch.setattr(machine_links, "now_ms", lambda: 10**15)
    session = client.post(
        "/api/v1/auth/register", json={"username": "owner", "password": "correct-horse-battery"}
    ).json()
    client.headers["X-CSRF-Token"] = session["csrfToken"]
    approve = client.post(f"/api/v1/machines/links/{link['code']}/approve", json={"name": "a"})
    assert approve.status_code == 404
    assert (
        client.post("/api/v1/worker/links/token", json={"secret": link["secret"]}).status_code
        == 410
    )


def synchronize_link_reads(monkeypatch):
    """让并发请求都读取到申请后再继续，稳定覆盖先读后写的竞争窗口。"""
    ready = Barrier(2)
    scalar = Session.scalar

    def concurrent_read(db, *args, **kwargs):
        result = scalar(db, *args, **kwargs)
        if isinstance(result, MachineLink) and not db.info.get("link_read"):
            db.info["link_read"] = True
            ready.wait(timeout=10)
        return result

    monkeypatch.setattr(Session, "scalar", concurrent_read)


def test_concurrent_link_redemption_creates_one_machine(authenticated, monkeypatch):
    client = authenticated
    previous = client.get("/api/v1/machines").json()
    link = client.post("/api/v1/worker/links", json={"name": "new-pc"}).json()
    assert (
        client.post(
            f"/api/v1/machines/links/{link['code']}/approve", json={"name": "工作室"}
        ).status_code
        == 204
    )
    with monkeypatch.context() as context:
        synchronize_link_reads(context)
        with ThreadPoolExecutor(max_workers=2) as pool:
            requests = [
                pool.submit(
                    client.post, "/api/v1/worker/links/token", json={"secret": link["secret"]}
                )
                for _ in range(2)
            ]
            responses = [request.result() for request in requests]
    assert [response.status_code for response in responses] == [200, 200]
    current = client.get("/api/v1/machines").json()
    assert len(current["items"]) == len(previous["items"]) + 1
    assert current["defaultMachineId"] == previous["defaultMachineId"]
    # 两次换取对应同一台工作机，只有后提交的那份密钥有效。
    statuses = [
        client.post(
            "/api/v1/worker/heartbeat",
            headers={"Authorization": "Bearer " + response.json()["apiKey"]},
            json={"protocolVersion": 3},
        ).status_code
        for response in responses
    ]
    assert sorted(statuses) == [200, 401]


def test_only_one_of_two_pending_reconnections_can_replace_the_key(authenticated, monkeypatch):
    client = authenticated
    previous = client.get("/api/v1/machines").json()
    machine_id = previous["defaultMachineId"]
    links = [client.post("/api/v1/worker/links", json={}).json() for _ in range(2)]
    for link in links:
        assert (
            client.post(
                f"/api/v1/machines/links/{link['code']}/approve", json={"machineId": machine_id}
            ).status_code
            == 204
        )
    with monkeypatch.context() as context:
        synchronize_link_reads(context)
        with ThreadPoolExecutor(max_workers=2) as pool:
            requests = [
                pool.submit(
                    client.post, "/api/v1/worker/links/token", json={"secret": link["secret"]}
                )
                for link in links
            ]
            responses = [request.result() for request in requests]
    assert sorted(response.status_code for response in responses) == [200, 410]
    key = next(response.json()["apiKey"] for response in responses if response.status_code == 200)
    connected = client.post(
        "/api/v1/worker/heartbeat",
        headers={"Authorization": "Bearer " + key},
        json={"protocolVersion": 3},
    )
    assert connected.status_code == 200 and connected.json()["id"] == machine_id
    assert len(client.get("/api/v1/machines").json()["items"]) == len(previous["items"])


def test_competing_accounts_cannot_both_approve_a_link(authenticated, monkeypatch):
    client = authenticated
    other = TestClient(client.app, headers={"Origin": "http://testserver"})
    session = other.post(
        "/api/v1/auth/register", json={"username": "second-owner", "password": "different-password"}
    ).json()
    other.headers["X-CSRF-Token"] = session["csrfToken"]
    link = client.post("/api/v1/worker/links", json={}).json()
    path = f"/api/v1/machines/links/{link['code']}/approve"
    with monkeypatch.context() as context:
        synchronize_link_reads(context)
        with ThreadPoolExecutor(max_workers=2) as pool:
            requests = [
                pool.submit(account.post, path, json={"name": "接入"})
                for account in (client, other)
            ]
            statuses = [request.result().status_code for request in requests]
    assert sorted(statuses) == [204, 404]
    winner = (client, other)[statuses.index(204)]
    loser = (client, other)[statuses.index(404)]
    read_path = f"/api/v1/machines/links/{link['code']}"
    assert winner.get(read_path).json()["status"] == "approved"
    assert loser.get(read_path).status_code == 404
    redeemed = client.post("/api/v1/worker/links/token", json={"secret": link["secret"]})
    assert redeemed.status_code == 200
    assert (
        sum(machine["name"] == "接入" for machine in winner.get("/api/v1/machines").json()["items"])
        == 1
    )
    assert all(
        machine["name"] != "接入" for machine in loser.get("/api/v1/machines").json()["items"]
    )


def test_resetting_a_key_keeps_queued_tasks_and_revoking_ends_them(authenticated, graph):
    client = authenticated
    machine, running, body = setup_job(client, graph)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    assert (
        worker.post("/api/v1/worker/claim", json=claim_body()).json()["task"]["id"] == running["id"]
    )
    queued = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())}).json()
    machine_id = machine["machine"]["id"]
    rotated = client.post(f"/api/v1/machines/{machine_id}/rotate").json()
    # 旧密钥持有的租约无法再回传，执行中的任务结束；排队任务等这台工作机用新密钥领取。
    assert client.get(f"/api/v1/tasks/{running['id']}").json()["status"] == "failed"
    assert client.get(f"/api/v1/tasks/{queued['id']}").json()["status"] == "queued"
    worker.headers["Authorization"] = "Bearer " + rotated["apiKey"]
    assert (
        worker.post("/api/v1/worker/claim", json=claim_body()).json()["task"]["id"] == queued["id"]
    )
    waiting = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())}).json()
    assert client.delete(f"/api/v1/machines/{machine_id}").status_code == 200
    assert client.get(f"/api/v1/tasks/{waiting['id']}").json()["status"] == "failed"


def test_link_requests_are_limited_per_address(client):
    statuses = [
        client.post("/api/v1/worker/links", json={"name": "pc"}).status_code for _ in range(31)
    ]
    assert statuses[:30] == [201] * 30 and statuses[30] == 429


def test_a_revoked_machine_cannot_be_redeemed_again(authenticated):
    client = authenticated
    link = client.post("/api/v1/worker/links", json={"name": "pc"}).json()
    client.post(f"/api/v1/machines/links/{link['code']}/approve", json={"name": "工作室"})
    token = {"secret": link["secret"]}
    redeemed = client.post("/api/v1/worker/links/token", json=token).json()
    machine_id = next(
        item["id"]
        for item in client.get("/api/v1/machines").json()["items"]
        if item["name"] == "工作室"
    )
    assert client.delete(f"/api/v1/machines/{machine_id}").status_code == 200
    # 撤销后不能凭原申请换回密钥。
    assert client.post("/api/v1/worker/links/token", json=token).status_code == 410
    assert redeemed["apiKey"]


def test_link_source_is_compared_with_the_browser(client):
    worker = TestClient(client.app, client=("198.51.100.7", 50000))
    link = worker.post("/api/v1/worker/links", json={"name": "pc"}).json()
    # 浏览器走 IPv6 而工作机走 IPv4 时无从比较，不下结论，确认页也就不提示。
    for address, same in (("198.51.100.7", True), ("203.0.113.9", False), ("2001:db8::7", None)):
        browser = TestClient(
            client.app, client=(address, 50000), headers={"Origin": "http://testserver"}
        )
        session = browser.post(
            "/api/v1/auth/register",
            json={
                "username": f"owner-{address.replace(':', '.').split('.')[0]}",
                "password": "correct-horse-battery",
            },
        )
        assert session.status_code == 201, session.text
        shown = browser.get(f"/api/v1/machines/links/{link['code']}").json()
        assert (shown["source"], shown["sameNetwork"]) == ("198.51.100.7", same)


def approved_link(client, name="pc"):
    link = client.post("/api/v1/worker/links", json={"name": name}).json()
    approved = client.post(f"/api/v1/machines/links/{link['code']}/approve", json={"name": name})
    assert approved.status_code == 204
    return {"secret": link["secret"]}


def test_changing_the_password_voids_approved_links(authenticated):
    client = authenticated
    token = approved_link(client)
    change = {"currentPassword": "correct-horse-battery", "newPassword": "a-brand-new-password"}
    assert client.post("/api/v1/auth/password", json=change).status_code == 204
    # 盗用者确认过、还没换取的申请不能在改密码后换出工作机。
    assert client.post("/api/v1/worker/links/token", json=token).status_code == 410


def test_a_link_cannot_be_redeemed_again_once_its_key_is_used_or_reset(authenticated):
    client = authenticated
    token = approved_link(client, "first")
    key = client.post("/api/v1/worker/links/token", json=token).json()["apiKey"]
    worker = {"Authorization": "Bearer " + key}
    assert (
        client.post(
            "/api/v1/worker/heartbeat", json={"protocolVersion": 3}, headers=worker
        ).status_code
        == 200
    )
    # 密钥已经用上，迟到的重复换取不能作废它。
    assert client.post("/api/v1/worker/links/token", json=token).status_code == 410
    assert (
        client.post(
            "/api/v1/worker/heartbeat", json={"protocolVersion": 3}, headers=worker
        ).status_code
        == 200
    )

    token = approved_link(client, "second")
    client.post("/api/v1/worker/links/token", json=token)
    machine_id = next(
        item["id"]
        for item in client.get("/api/v1/machines").json()["items"]
        if item["name"] == "second"
    )
    # 用户在网页重置密钥后，申请凭据不能再抢走新密钥。
    reset = client.post(f"/api/v1/machines/{machine_id}/rotate").json()
    assert client.post("/api/v1/worker/links/token", json=token).status_code == 410
    fresh = {"Authorization": "Bearer " + reset["apiKey"]}
    assert (
        client.post(
            "/api/v1/worker/heartbeat", json={"protocolVersion": 3}, headers=fresh
        ).status_code
        == 200
    )


def test_ipv6_addresses_share_their_network_limit(client):
    from comfyshop_api.security import _address_bucket

    assert _address_bucket("2001:db8::1") == _address_bucket("2001:db8::ffff") == "2001:db8::/64"
    assert _address_bucket("198.51.100.7") == "198.51.100.7"
    assert _address_bucket(None) == "unknown"
