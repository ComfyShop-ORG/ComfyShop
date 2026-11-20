from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from comfyshop_api.models import Execution

CATALOG = {
    "nodes": {
        "CLIPTextEncode": {"inputs": {"text": {"kind": "string", "multiline": True}}},
        "KSampler": {
            "inputs": {
                "seed": {"kind": "integer", "minimum": "0", "maximum": str(2**32 - 1)},
                "steps": {"kind": "integer", "minimum": "1", "maximum": "150"},
            }
        },
        "SaveImage": {"outputNode": True},
    }
}


def sync_machine(client, machine, catalog=CATALOG):
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    assert worker.put("/api/v1/worker/catalog", json=catalog).status_code == 200
    return worker


def task_body(client, workflow, machine_id=None):
    machine_id = machine_id or client.get("/api/v1/machines").json()["defaultMachineId"]
    response = client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={"machine_id": machine_id, "version_id": workflow["versionId"]},
    )
    assert response.status_code == 200, response.text
    return {
        "workflowId": workflow["id"],
        "versionId": workflow["versionId"],
        "machineId": machine_id,
        "executionCount": 1,
        "inputValues": {},
        "inputSchemaHash": response.json()["schemaHash"],
        "idempotencyKey": str(uuid4()),
    }


def execution_id(client, task_id, index=0):
    with Session(client.app.state.engine) as db:
        return db.scalar(
            select(Execution.id).where(Execution.task_id == task_id, Execution.index == index)
        )
