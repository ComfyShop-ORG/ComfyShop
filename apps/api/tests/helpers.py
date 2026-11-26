import socket
from contextlib import contextmanager
from threading import Thread
from time import monotonic, sleep
from uuid import uuid4

import uvicorn
from comfyshop_worker_protocol import PROTOCOL_VERSION
from fastapi.testclient import TestClient
from httpx import Client
from sqlalchemy import select
from sqlalchemy.orm import Session

from comfyshop_api.main import create_app
from comfyshop_api.models import Execution, Machine, now_ms

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


@contextmanager
def serve_test_app(settings):
    """在临时端口提供同源 FastAPI 与静态资源，退出时关闭服务和数据库连接。"""
    server = uvicorn.Server(uvicorn.Config(create_app(settings), log_level="warning", ws="none"))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        address = f"http://127.0.0.1:{listener.getsockname()[1]}"
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 5
            while not server.started and thread.is_alive() and monotonic() < deadline:
                sleep(0.01)
            assert server.started
            with Client(base_url=address, headers={"Origin": address}, trust_env=False) as web:
                yield address, web
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive()


def machine_heartbeat(**fields):
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "runtime": {"version": "0.3.0"},
        "operatingSystem": "linux",
        **fields,
    }


def report_inventory(worker: Client, catalog=CATALOG) -> None:
    assert worker.put("/api/v1/worker/catalog", json=catalog).status_code == 200
    heartbeat = machine_heartbeat(nodes=list(catalog["nodes"]))
    assert worker.post("/api/v1/worker/heartbeat", json=heartbeat).status_code == 200


def sync_machine(client, machine, catalog=CATALOG):
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    report_inventory(worker, catalog)
    return worker


def expire_machine_heartbeat(client: TestClient, machine_id: str) -> None:
    with Session(client.app.state.engine) as db:
        machine = db.get(Machine, machine_id)
        assert machine is not None
        machine.last_seen = now_ms() - 60_000
        db.commit()


def task_body(client, workflow, machine_id=None):
    machine_id = machine_id or client.get("/api/v1/machines").json()["defaultMachineId"]
    response = client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={
            "machine_id": machine_id,
            "version_id": workflow["versionId"],
        },
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
