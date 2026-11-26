from fastapi.testclient import TestClient
from helpers import execution_id, task_body
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comfyshop_api.db import Base
from comfyshop_api.main import create_app


def test_fresh_database_contains_no_business_data(client):
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/workflows").json()["items"] == []
    with Session(client.app.state.engine) as db:
        counts = {
            name: db.scalar(select(func.count()).select_from(table))
            for name, table in Base.metadata.tables.items()
        }
    assert not any(counts.values()), counts


def create_workflow(client, graph):
    response = client.post(
        "/api/v1/workflows", json={"name": "人像工作流", "category": "image", "graph": graph}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_form_defaults_and_labels_follow_node_inputs(authenticated):
    graph = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "blur"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a product"}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"positive": ["2", 0], "negative": ["1", 0], "seed": 42, "steps": 16},
        },
    }
    workflow = create_workflow(authenticated, graph)
    client = authenticated
    machine = client.get("/api/v1/machines").json()["defaultMachineId"]
    form = client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs", params={"machine_id": machine}
    ).json()
    texts = {field["nodeId"]: field for field in form["fields"] if field["inputName"] == "text"}
    assert texts["1"]["default"] == "blur" and texts["1"]["label"] == "负向提示词"
    assert texts["2"]["default"] == "a product" and texts["2"]["primary"]


def test_graph_version_task_snapshot_and_idempotency(authenticated, graph):
    client = authenticated
    workflow = create_workflow(client, graph)
    assert client.get(f"/api/v1/workflows/{workflow['id']}/graph").json()["graph"] == graph
    anonymous = TestClient(client.app)
    assert anonymous.get(f"/api/v1/workflows/{workflow['id']}/graph").status_code == 401
    body = task_body(client, workflow)
    first = client.post("/api/v1/tasks", json=body)
    assert first.status_code == 201 and first.json()["status"] == "queued"
    repeated = client.post("/api/v1/tasks", json=body)
    assert repeated.status_code == 200 and repeated.json()["id"] == first.json()["id"]
    changed = client.post("/api/v1/tasks", json={**body, "executionCount": 2})
    assert changed.status_code == 409
    graph2 = {**graph, "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "新的提示词"}}}
    updated = client.patch(
        f"/api/v1/workflows/{workflow['id']}", json={"name": "新名称", "graph": graph2}
    )
    assert updated.status_code == 200 and updated.json()["version"] == 2
    prior = client.get(f"/api/v1/tasks/{first.json()['id']}").json()
    assert prior["versionId"] == workflow["versionId"] and prior["workflowName"] == "人像工作流"
    assert client.post(f"/api/v1/workflows/{workflow['id']}/publish", json={}).status_code == 409
    assert client.get("/api/v1/workflows").json()["items"] == []
    assert client.delete(f"/api/v1/workflows/{workflow['id']}").status_code == 204
    assert client.get(f"/api/v1/tasks/{prior['id']}").status_code == 200


def test_ownership_cancellation_and_restart(authenticated, settings, graph):
    client = authenticated
    workflow = create_workflow(client, graph)
    task = client.post("/api/v1/tasks", json=task_body(client, workflow)).json()
    cookies = dict(client.cookies)
    csrf = client.headers["X-CSRF-Token"]
    with TestClient(create_app(settings), headers={"Origin": "http://testserver"}) as other:
        registration = other.post(
            "/api/v1/auth/register", json={"username": "other", "password": "different-password"}
        )
        other.headers["X-CSRF-Token"] = registration.json()["csrfToken"]
        assert other.get(f"/api/v1/workflows/{workflow['id']}").status_code == 404
        assert other.get(f"/api/v1/tasks/{task['id']}").status_code == 404
        assert other.post(f"/api/v1/tasks/{task['id']}/cancel").status_code == 404
        assert (
            other.patch(f"/api/v1/workflows/{workflow['id']}", json={"name": "stolen"}).status_code
            == 404
        )
        assert other.get("/api/v1/workflows?scope=mine").json()["items"] == []
    # A new app and engine use the same on-disk database and session cookie.
    with TestClient(
        create_app(settings),
        cookies=cookies,
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
    ) as restarted:
        assert restarted.get("/api/v1/auth/session").json()["user"]["username"] == "owner"
        assert restarted.get(f"/api/v1/workflows/{workflow['id']}/graph").json()["graph"] == graph
        assert restarted.get(f"/api/v1/tasks/{task['id']}").json()["status"] == "queued"
        assert restarted.post(f"/api/v1/tasks/{task['id']}/cancel").json()["status"] == "cancelled"
        assert restarted.post(f"/api/v1/tasks/{task['id']}/cancel").status_code == 200


def test_pagination_and_invalid_graphs(authenticated, graph):
    client = authenticated
    assert (
        client.post(
            "/api/v1/workflows", json={"name": "bad", "graph": {"arbitrary": "value"}}
        ).status_code
        == 422
    )
    workflow = create_workflow(client, graph)
    for _ in range(5):
        assert client.post("/api/v1/tasks", json=task_body(client, workflow)).status_code == 201
    records = []
    cursor = None
    while True:
        page = client.get(
            "/api/v1/tasks", params={"limit": 2, **({"cursor": cursor} if cursor else {})}
        ).json()
        records.extend(page["items"])
        cursor = page["nextCursor"]
        if cursor is None:
            break
    assert len(records) == 5 and len({task["id"] for task in records}) == 5
    assert client.get("/api/v1/tasks?cursor=invalid").status_code == 422


def test_cursor_remains_stable_when_new_tasks_are_inserted(authenticated, graph):
    client = authenticated
    workflow = create_workflow(client, graph)
    original = {
        client.post("/api/v1/tasks", json=task_body(client, workflow)).json()["id"]
        for _ in range(4)
    }
    first = client.get("/api/v1/tasks", params={"limit": 2}).json()
    added = client.post("/api/v1/tasks", json=task_body(client, workflow)).json()["id"]
    second = client.get("/api/v1/tasks", params={"limit": 2, "cursor": first["nextCursor"]}).json()
    visited = [item["id"] for item in first["items"] + second["items"]]
    assert set(visited) == original and len(visited) == 4 and added not in visited


def test_publication_is_bound_to_successful_version_and_clients_cannot_forge_status(
    authenticated, graph
):
    from sqlalchemy.orm import Session

    from comfyshop_api.models import Execution, Task

    client = authenticated
    workflow = create_workflow(client, graph)
    body = task_body(client, workflow)
    assert client.post("/api/v1/tasks", json={**body, "status": "succeeded"}).status_code == 422
    task_id = client.post("/api/v1/tasks", json=body).json()["id"]
    with Session(client.app.state.engine) as db:
        record = db.get(Task, task_id)
        db.get(Execution, execution_id(client, task_id)).status = "succeeded"
        record.status = "succeeded"
        record.progress = 100
        db.commit()
    assert client.post(f"/api/v1/workflows/{workflow['id']}/publish", json={}).status_code == 200
    assert client.get("/api/v1/workflows").json()["items"][0]["id"] == workflow["id"]
    revised = {**graph, "3": {"class_type": "SaveImage", "inputs": {}}}
    assert (
        client.patch(f"/api/v1/workflows/{workflow['id']}", json={"graph": revised}).json()[
            "version"
        ]
        == 2
    )
    assert client.post(f"/api/v1/workflows/{workflow['id']}/publish", json={}).status_code == 409


def test_task_keeps_original_graph_after_workflow_archived(authenticated, graph):
    client = authenticated
    workflow = create_workflow(client, graph)
    task = client.post("/api/v1/tasks", json=task_body(client, workflow)).json()
    assert client.delete("/api/v1/workflows/" + workflow["id"]).status_code == 204
    frozen = client.get("/api/v1/tasks/" + task["id"] + "/graph")
    assert frozen.status_code == 200
    assert frozen.json() == {"versionId": workflow["versionId"], "graph": graph}
    assert client.get(f"/api/v1/tasks/{task['id']}/inputs").json()["version"] == workflow["version"]
    assert client.get(f"/api/v1/tasks/{task['id']}/progress").json()["status"] == task["status"]


def test_concurrent_retries_create_one_task(authenticated, graph):
    from concurrent.futures import ThreadPoolExecutor

    workflow = create_workflow(authenticated, graph)
    body = task_body(authenticated, workflow)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(
            pool.map(lambda _: authenticated.post("/api/v1/tasks", json=body), range(4))
        )
    assert [response.status_code for response in responses].count(201) == 1
    assert all(response.status_code in {200, 201} for response in responses)
    assert len({response.json()["id"] for response in responses}) == 1
