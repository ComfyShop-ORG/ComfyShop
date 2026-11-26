"""Shared setup for official workflow tests."""

import hashlib
from io import BytesIO
from uuid import uuid4

import httpx
from comfyshop_worker_protocol import PROTOCOL_VERSION
from comfyshop_worker_protocol.platform import Platform
from PIL import Image

from comfyshop_official_worker.atlas_cloud import ADAPTER

TOKEN = "integration-test-official-worker-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
OWNER = "official-maintainer"
SVG_BYTES = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    b'<circle cx="16" cy="16" r="8"/></svg>'
)


def import_official(client, body, language="zh", *, headers=None):
    response = client.post(
        "/api/v1/workflows", json=body, headers={"Accept-Language": language} | (headers or {})
    )
    assert response.status_code == 201, response.text
    return response.json()


def workflow_body(
    key,
    fields,
    *,
    operation="video",
    output_kind=None,
    additional_outputs=(),
    config=None,
    layout=(),
):
    category = operation
    name = f"Official test {key}"
    graph = {
        "format": "service",
        "workerKind": "official",
        "key": key,
        "name": name,
        "category": category,
        "fields": fields,
        "parameterLayout": list(layout),
        "execution": {
            "adapter": ADAPTER,
            "outputKind": output_kind or operation,
            "additionalOutputKinds": list(additional_outputs),
            "config": {
                "model": f"test/{key}",
                "operation": operation,
                "parameters": {},
                **(config or {}),
            },
        },
    }
    return {"name": name, "category": category, "graph": graph}


def register(client, username):
    client.cookies.clear()
    data = {"username": username, "password": "test-password-long"}
    response = client.post("/api/v1/auth/register", json=data).raise_for_status()
    client.headers["X-CSRF-Token"] = response.json()["csrfToken"]
    return data


def submit(client, workflow, values, *, expected_status=201, execution_count=1):
    form = (
        client.get(
            f"/api/v1/workflows/{workflow['id']}/service-inputs",
            params={"version_id": workflow["versionId"]},
        )
        .raise_for_status()
        .json()
    )
    assert "machineId" not in form
    response = client.post(
        "/api/v1/tasks",
        json={
            "workflowId": workflow["id"],
            "versionId": workflow["versionId"],
            "inputSchemaHash": form["schemaHash"],
            "inputValues": values,
            "executionCount": execution_count,
            "idempotencyKey": str(uuid4()),
        },
    )
    assert response.status_code == expected_status, response.text
    task = response.json()
    if expected_status == 201:
        assert (
            task["worker"]["kind"] == "official"
            and task["machineId"] is None
            and task["machineName"] is None
        )
    return task


def worker_client(client):
    return Platform("http://testserver", TOKEN, transport=httpx.ASGITransport(app=client.app))


def complete_official_artifact(client, task, filename, content, *, references=None):
    lease = uuid4().hex
    job = (
        client.post(
            "/api/v1/worker/services/official/claim",
            headers=AUTH,
            json={
                "protocolVersion": PROTOCOL_VERSION,
                "claimId": str(uuid4()),
                "leaseSecret": lease,
                "adapters": [ADAPTER],
            },
        )
        .raise_for_status()
        .json()
    )
    assert job["task"]["id"] == task["id"]
    headers = AUTH | {"X-Task-Lease": lease}
    endpoint = f"/api/v1/worker/tasks/{task['id']}"
    if references:
        assert {asset["id"] for asset in job["assets"]} == references.keys()
        for asset_id, original in references.items():
            asset = client.get(f"{endpoint}/assets/{asset_id}", headers=headers)
            assert asset.raise_for_status().content == original
    execution_url = f"{endpoint}/executions/0"
    assert client.post(f"{execution_url}/reserve", headers=headers).raise_for_status().json()
    client.post(
        f"{execution_url}/start", headers=headers, json={"promptId": "test-prediction"}
    ).raise_for_status()
    artifact = (
        client.put(
            f"{endpoint}/artifacts/test-output",
            headers=headers,
            params={
                "filename": filename,
                "sha256": hashlib.sha256(content).hexdigest(),
                "execution_index": 0,
                "output_node_id": "official",
                "output_slot": "outputs",
                "output_index": 0,
            },
            content=content,
        )
        .raise_for_status()
        .json()
    )
    execution = (
        client.post(
            f"{execution_url}/complete", headers=headers, json={"clientIds": ["test-output"]}
        )
        .raise_for_status()
        .json()
    )
    return execution, artifact


def image_bytes(color, size=(32, 32), *, format="PNG"):
    image = BytesIO()
    Image.new("RGB", size, color).save(image, format=format)
    return image.getvalue()


def asset(client, content, filename="reference.png"):
    return (
        client.put(
            f"/api/v1/assets/{uuid4()}",
            params={"filename": filename},
            content=content,
            headers={"Content-Type": "application/octet-stream"},
        )
        .raise_for_status()
        .json()["id"]
    )
