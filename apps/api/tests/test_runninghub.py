"""Acceptance tests exercise the work-machine protocol with an instrumented RunningHub transport."""

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from comfyshop_runninghub_worker.provider import definition
from comfyshop_worker_protocol import PROTOCOL_VERSION
from comfyshop_worker_protocol.catalog import make_catalog
from comfyshop_worker_protocol.definition import Source, WorkerDefinition
from comfyshop_worker_protocol.platform import Platform
from comfyshop_worker_protocol.service import ServiceRunner
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from helpers import serve_test_app, sync_machine, task_body
from playwright.sync_api import expect, sync_playwright
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_media_restore import migrate
from test_official_workflows import image_bytes, register
from test_team_spaces import add_member, item_ids, open_space_picker
from test_workspace_sharing import ORIGIN, register_account

from comfyshop_api.main import create_app
from comfyshop_api.models import Machine, Task, now_ms
from comfyshop_api.services.worker_types import WORKERS

TOKEN = "runninghub-worker-service-test-token-32"
OFFICIAL = "official-worker-other-test-token-32"
EXTERNAL = "1930000000000000001"
REFERENCE = "https://www.runninghub.cn/workflow/" + EXTERNAL + "?source=workspace"
GRAPH = {
    "10": {
        "class_type": "LoadImage",
        "inputs": {"image": "base.png"},
        "_meta": {"title": "商品图"},
    },
    "11": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "原提示词"},
        "_meta": {"title": "提示词"},
    },
    "12": {"class_type": "SaveImage", "inputs": {"images": ["10", 0]}},
}


PHOTO_GRAPH = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "studio.safetensors"}},
    "10": GRAPH["10"],
    "11": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "原提示词", "clip": ["1", 1]},
        "_meta": {"title": "提示词"},
    },
    "13": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
    "14": {
        "class_type": "ImageScale",
        "inputs": {
            "image": ["10", 0],
            "width": 512,
            "height": 768,
            "upscale_method": "nearest-exact",
            "crop": "disabled",
        },
    },
    "15": {"class_type": "VAEEncode", "inputs": {"pixels": ["14", 0], "vae": ["1", 2]}},
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0],
            "positive": ["11", 0],
            "negative": ["13", 0],
            "latent_image": ["15", 0],
            "steps": 20,
            "cfg": 8,
            "seed": 7,
            "denoise": 0.8,
            "sampler_name": "euler",
            "scheduler": "normal",
        },
    },
    "16": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["1", 2]}},
    "12": {"class_type": "SaveImage", "inputs": {"images": ["16", 0], "filename_prefix": "photo"}},
}

PHOTO_INFO = {
    name: {"input": {"required": fields}, "output_node": name == "SaveImage"}
    for name, fields in {
        "CheckpointLoaderSimple": {
            "ckpt_name": [["studio.safetensors", "unrelated-private.safetensors"]]
        },
        "LoadImage": {"image": [["base.png"], {"image_upload": True}]},
        "CLIPTextEncode": {"text": ["STRING", {"multiline": True}], "clip": ["CLIP"]},
        "ImageScale": {
            "image": ["IMAGE"],
            "width": ["INT", {"min": 0, "max": 16384, "step": 1}],
            "height": ["INT", {"min": 0, "max": 16384, "step": 1}],
            "upscale_method": [["nearest-exact", "bilinear"]],
            "crop": [["disabled", "center"]],
        },
        "KSampler": {
            "steps": ["INT", {"min": 1, "max": 10000}],
            "cfg": ["FLOAT", {"min": 0, "max": 100, "step": 0.1}],
            "seed": ["INT", {"min": 0, "max": 2**64 - 1}],
            "denoise": ["FLOAT", {"min": 0, "max": 1, "step": 0.01}],
            "sampler_name": ["COMBO", {"options": ["euler", "heun"]}],
            "scheduler": [["normal", "karras"]],
        },
        "VAEEncode": {},
        "VAEDecode": {},
        "SaveImage": {"filename_prefix": ["STRING"]},
    }.items()
}


@pytest.fixture
def upstream(settings, monkeypatch):
    settings.worker_service_tokens["runninghub"] = SecretStr(TOKEN)
    settings.connection_encryption_key = SecretStr(Fernet.generate_key().decode())
    png = image_bytes("green")
    submitted = []
    queries = []
    mode = {"fault": "", "graph": PHOTO_GRAPH, "uploads": 0, "info": PHOTO_INFO, "cancelled": []}
    original = httpx.AsyncHTTPTransport.handle_async_request

    def provider(req):
        path = req.url.path
        if req.url.host == "rh-images.xiaoyaoyou.com":
            assert "authorization" not in req.headers
            return httpx.Response(200, content=png, headers={"Content-Type": "image/png"})
        assert req.url.host == "www.runninghub.cn"
        if path.startswith("/proxy/"):
            assert req.method == "GET" and path.endswith("/object_info")
            return httpx.Response(200, json=mode["info"])
        key = req.headers["Authorization"].removeprefix("Bearer ")
        if path == "/api/openapi/getJsonApiFormat":
            assert json.loads(req.content) == {"apiKey": key, "workflowId": EXTERNAL}
            return httpx.Response(
                200, json={"code": 0, "data": {"prompt": json.dumps(mode["graph"])}}
            )
        if path == "/openapi/v2/media/upload/binary":
            assert png in req.content
            mode["uploads"] += 1
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "fileName": "openapi/ref.png",
                        "download_url": "https://rh-images.xiaoyaoyou.com/ref.png",
                    },
                },
            )
        if path == "/task/openapi/create":
            body = json.loads(req.content)
            submitted.append(body)
            assert body["apiKey"] == key and body["workflowId"] == EXTERNAL
            assert "workflow" not in body
            if mode["fault"] == "rejected":
                return httpx.Response(200, json={"code": 421, "msg": "TASK_QUEUE_MAXED"})
            if mode["fault"] == "unknown":
                return httpx.Response(200, json={"code": 500, "msg": "UNKNOWN_ERROR"})
            if mode["fault"] == "ambiguous":
                raise httpx.ReadError("lost submission response", request=req)
            return httpx.Response(200, json={"code": 0, "data": {"taskId": str(len(submitted))}})
        if path == "/task/openapi/cancel":
            mode["cancelled"].append(json.loads(req.content))
            return httpx.Response(
                200, json={"code": 0 if mode["fault"] != "cancel-failed" else 805, "data": None}
            )
        assert path == "/task/openapi/outputs"
        task_id = json.loads(req.content)["taskId"]
        assert submitted[int(task_id) - 1]["apiKey"] == key
        queries.append(task_id)
        if observe := mode.get("observe"):
            observe()
        if mode["fault"] == "disconnect":
            raise httpx.ReadError("interrupted", request=req)
        if queries.count(task_id) == 1:
            return httpx.Response(200, json={"code": 813, "msg": "APIKEY_TASK_IS_QUEUED"})
        if queries.count(task_id) == 2:
            return httpx.Response(200, json={"code": 804, "msg": "APIKEY_TASK_IS_RUNNING"})
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": [
                    {"nodeId": "12", "fileUrl": "https://rh-images.xiaoyaoyou.com/result.png"}
                ],
            },
        )

    async def dispatch(self, request):
        if request.url.host == "www.runninghub.cn":
            await request.aread()
            return provider(request)
        return await original(self, request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", dispatch)
    return provider, submitted, mode, png


def connect(client, name, key, scope="cn", kind="runninghub", *, params=None):
    result = client.post(
        "/api/v1/machines/connections",
        params=params,
        json={"kind": kind, "scope": scope, "name": name, "apiKey": key},
    ).raise_for_status()
    assert key not in result.text
    return result.json()


def add(client, machine, ref=REFERENCE, *, params=None):
    return (
        client.post(
            "/api/v1/workflows/from-connection",
            params=params,
            json={"machineId": machine["id"], "reference": ref, "name": "商品换背景"},
        )
        .raise_for_status()
        .json()
    )


def parameters(client, flow, machine, *, params=None):
    return (
        client.get(
            f"/api/v1/workflows/{flow['id']}/inputs",
            params={**(params or {}), "machine_id": machine["id"], "version_id": flow["versionId"]},
        )
        .raise_for_status()
        .json()
    )


async def run_once(provider, *, app=None, address="http://testserver"):
    platform = Platform(address, TOKEN, transport=httpx.ASGITransport(app=app) if app else None)
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as cloud:
            return await ServiceRunner(platform, definition, cloud, interval=0.01).run_once()
    finally:
        await platform.close()


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_team_runninghub_uses_workspace_connection_and_assets(client, upstream):
    provider, submitted, mode, png = upstream
    register_account(client, "cloud-team-owner")
    manager = TestClient(client.app, headers={"Origin": ORIGIN})
    editor = TestClient(client.app, headers={"Origin": ORIGIN})
    reader = TestClient(client.app, headers={"Origin": ORIGIN})
    manager_id = register_account(manager, "cloud-team-manager")
    editor_id = register_account(editor, "cloud-team-editor")
    register_account(reader, "cloud-team-reader")
    first, other = [
        client.post("/api/v1/teams", json={"name": name}).raise_for_status().json()["id"]
        for name in ("摄影组", "视频组")
    ]
    team = f"/api/v1/teams/{first}"
    scope = {"workspace_team": first}
    other_scope = {"workspace_team": other}
    for role in ("manager", "editor", "reader"):
        assert add_member(client, team, f"cloud-team-{role}", role).status_code == 204

    machines = "/api/v1/machines"
    body = {"kind": "runninghub", "scope": "cn", "name": "摄影组连接", "apiKey": "team-key"}
    assert editor.post(machines + "/connections", params=scope, json=body).status_code == 403
    personal = connect(client, "个人连接", "personal-scope-key")
    connection = connect(manager, "摄影组连接", "team-initial-key", params=scope)
    edit_path = f"{machines}/{connection['id']}/connection"
    assert editor.put(edit_path, params=scope, json=body).status_code == 403
    updated = manager.put(edit_path, params=scope, json=body).raise_for_status()
    assert body["apiKey"] not in updated.text
    assert item_ids(client.get(machines)) == {personal["id"]}
    listed = reader.get(machines, params=scope).raise_for_status()
    assert item_ids(listed) == {connection["id"]} and body["apiKey"] not in listed.text
    assert not item_ids(client.get(machines, params=other_scope))

    import_path = "/api/v1/workflows/from-connection"
    reference = {"machineId": connection["id"], "reference": REFERENCE}
    assert reader.post(import_path, params=scope, json=reference).status_code == 403
    assert client.post(import_path, params=other_scope, json=reference).status_code == 404
    flow = add(editor, connection, params=scope)
    assert flow["teamId"] == first and flow["owner"] == editor_id
    assert add(manager, connection, params=scope)["versionId"] == flow["versionId"]
    assert not item_ids(editor.get("/api/v1/workflows", params={"scope": "mine"}))
    form = parameters(editor, flow, connection, params=scope)
    image = next(field for field in form["fields"] if field["kind"] == "image")
    reference_image = (
        manager.put(f"{team}/assets/{uuid4()}?filename=team.png", content=png)
        .raise_for_status()
        .json()
    )
    request = {
        "workflowId": flow["id"],
        "versionId": flow["versionId"],
        "inputSchemaHash": form["schemaHash"],
        "inputValues": {image["id"]: {"assetId": reference_image["id"]}},
        "idempotencyKey": str(uuid4()),
    }
    tasks = "/api/v1/tasks"
    assert reader.post(tasks, params=scope, json=request).status_code == 403
    foreign = {**request, "machineId": personal["id"]}
    assert client.post(tasks, params=scope, json=foreign).status_code == 409
    task = editor.post(tasks, params=scope, json=request).raise_for_status().json()
    assert task["owner"] == editor_id and task["machineId"] == connection["id"]
    assert not item_ids(editor.get(tasks)) and not item_ids(client.get(tasks, params=other_scope))

    mode["fault"] = "rejected"
    assert asyncio.run(run_once(provider, app=client.app))
    task_path = f"{tasks}/{task['id']}"
    progress = manager.get(task_path + "/progress", params=scope).raise_for_status().json()
    assert progress["executions"][0]["recovery"] == "rerunnable"
    mode["fault"] = ""
    retry = (
        manager.post(
            task_path + "/retry-executions",
            params=scope,
            json={"service": True, "executionIndices": [0], "idempotencyKey": str(uuid4())},
        )
        .raise_for_status()
        .json()
    )
    assert retry["owner"] == manager_id and retry["machineId"] == connection["id"]
    assert asyncio.run(run_once(provider, app=client.app))
    assert [request["apiKey"] for request in submitted] == [body["apiKey"], body["apiKey"]]
    assert mode["uploads"] == 2
    assert reader.get(f"{tasks}/{retry['id']}", params=scope).json()["status"] == "succeeded"
    artifacts = reader.get("/api/v1/artifacts", params={**scope, "task_id": retry["id"]})
    (result,) = artifacts.raise_for_status().json()["items"]
    assert reader.get(result["media"]["src"]).content == png
    assert client.get(f"{tasks}/{retry['id']}", params=other_scope).status_code == 404
    manager.post(f"/api/v1/workflows/{flow['id']}/publish", params=scope).raise_for_status()


def test_named_connections_share_workflow_and_keep_billing_and_results_separate(
    client, settings, upstream
):
    provider, submitted, _, png = upstream
    register(client, "cloud-author")
    personal = connect(client, "个人设计", "author-personal-key")
    unsupported = client.put(
        f"/api/v1/machines/{personal['id']}/pause",
        headers={"Accept-Language": "en"},
        json={"paused": True},
    )
    assert unsupported.status_code == 409
    assert unsupported.json()["detail"] == "This worker does not support pausing job pickup."
    studio = connect(client, "设计部", "author-studio-key")
    foreign_site = connect(client, "国际账号", "site-key", "ai")
    local = client.post("/api/v1/machines", json={"name": "本地 ComfyUI"}).raise_for_status().json()
    sync_machine(client, local, make_catalog(PHOTO_INFO))
    flow = add(client, personal)
    assert add(client, studio, EXTERNAL)["versionId"] == flow["versionId"]
    assert flow["worker"]["scope"] == "cn"
    data = parameters(client, flow, personal)
    assert not data["catalogLimited"]
    assert "unrelated-private" not in json.dumps(data)
    fields = {(f["nodeId"], f["inputName"]): f for f in data["fields"]}
    steps, cfg, sampler = (fields["3", name] for name in ("steps", "cfg", "sampler_name"))
    assert (steps["minimum"], steps["maximum"], cfg["step"]) == ("1", "10000", "0.1")
    assert sampler["choices"] == ["euler", "heun"]
    assert fields["14", "width"]["maximum"] == fields["14", "height"]["maximum"] == "16384"
    native = (
        client.post("/api/v1/workflows", json={"name": "本地图", "graph": PHOTO_GRAPH})
        .raise_for_status()
        .json()
    )
    native_form = parameters(client, native, local["machine"])
    for field in (steps, cfg, sampler):
        assert field in native_form["fields"]
        assert (
            native_form["parameterControls"][field["id"]] == data["parameterControls"][field["id"]]
        )
    layout = [
        {"fieldId": fields["10", "image"]["id"], "section": "default"},
        {"fieldId": fields["11", "text"]["id"], "section": "default"},
        {"fieldId": sampler["id"], "section": "default", "defaultValue": "heun"},
        {
            "fieldId": steps["id"],
            "section": "default",
            "displayName": "采样步数",
            "defaultValue": 26,
        },
        {"fieldId": cfg["id"], "section": "advanced", "defaultValue": 6.5},
    ]
    url = f"/api/v1/workflows/{flow['id']}"
    edit = url + f"/versions/{flow['versionId']}/parameter-layout"
    saved = (
        client.put(edit, json={"machineId": studio["id"], "parameterLayout": layout})
        .raise_for_status()
        .json()
    )
    assert [entry["fieldId"] for entry in saved] == [entry["fieldId"] for entry in layout]
    assert parameters(client, flow, personal)["originalDefaults"][steps["id"]] == 20

    def submit(machine, count):
        asset = (
            client.put(f"/api/v1/assets/{uuid4()}?filename=ref.png", content=png)
            .raise_for_status()
            .json()
        )
        values = {
            fields["10", "image"]["id"]: {"assetId": asset["id"]},
            fields["11", "text"]["id"]: "蓝色背景",
            steps["id"]: count,
            sampler["id"]: "euler",
        }
        return (
            client.post(
                "/api/v1/tasks",
                json=task_body(client, flow, machine["id"]) | {"inputValues": values},
            )
            .raise_for_status()
            .json()
        )

    body = task_body(client, flow, studio["id"])
    assert (
        client.post(
            "/api/v1/tasks", json={k: v for k, v in body.items() if k != "machineId"}
        ).status_code
        == 409
    )
    for bad in (foreign_site, local["machine"]):
        assert client.post("/api/v1/tasks", json=body | {"machineId": bad["id"]}).status_code == 409
    assert (
        client.post(
            "/api/v1/tasks", json=body | {"inputValues": {sampler["id"]: "unknown"}}
        ).status_code
        == 422
    )
    tasks = []
    for number, (machine, key) in enumerate(
        ((studio, "author-studio-key"), (personal, "author-personal-key")), 30
    ):
        task = submit(machine, number)
        tasks.append(task["id"])
        progress = client.get("/api/v1/tasks/" + task["id"] + "/progress").raise_for_status().json()
        assert progress["waitReason"] == "service_waiting" and progress["queueAhead"] is None
        assert (task["machineId"], task["machineName"]) == (machine["id"], machine["name"])
        settings.worker_service_tokens["official"] = SecretStr(OFFICIAL)
        official = {"Authorization": "Bearer " + OFFICIAL}
        claim = {
            "claimId": str(uuid4()),
            "leaseSecret": "s" * 36,
            "protocolVersion": PROTOCOL_VERSION,
            "adapters": ["runninghub"],
        }
        assert (
            client.post(
                "/api/v1/worker/services/runninghub/claim",
                headers={"Authorization": "Bearer " + TOKEN},
                json=claim | {"adapters": ["other"]},
            )
            .raise_for_status()
            .json()
            is None
        )
        assert (
            client.post(
                "/api/v1/worker/services/official/claim", headers=official, json=claim
            ).json()
            is None
        )
        assert (
            client.post(
                "/api/v1/worker/services/runninghub/claim", headers=official, json=claim
            ).status_code
            == 403
        )
        assert (
            client.get(
                f"/api/v1/worker/tasks/{task['id']}/connection", headers=official
            ).status_code
            == 404
        )
        assert asyncio.run(run_once(provider, app=client.app))
        done = client.get("/api/v1/tasks/" + task["id"]).json()
        assert done["status"] == "succeeded" and key not in json.dumps(done)
        assert submitted[-1]["apiKey"] == key
        overrides = {
            (node["nodeId"], node["fieldName"]): node["fieldValue"]
            for node in submitted[-1]["nodeInfoList"]
        }
        assert (
            overrides["10", "image"],
            overrides["11", "text"],
            overrides["3", "steps"],
            overrides["3", "sampler_name"],
            overrides["3", "cfg"],
        ) == ("openapi/ref.png", "蓝色背景", number, "euler", 6.5)
        assert overrides["3", "seed"] == 7
        artifact = client.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"][
            0
        ]
        assert client.get(artifact["media"]["src"]).content == png
    with Session(client.app.state.engine) as db:
        secrets = db.scalars(
            select(Machine.credential).where(Machine.worker_kind == "runninghub")
        ).all()
        assert len(secrets) == 3 and all(s and s.startswith("gAAAA") for s in secrets)
        cipher = Fernet(settings.connection_encryption_key.get_secret_value())
        assert {cipher.decrypt(s.encode()).decode() for s in secrets} == {
            "author-personal-key",
            "author-studio-key",
            "site-key",
        }
    client.post(url + "/publish").raise_for_status()
    register(client, "cloud-reader")
    assert client.get("/api/v1/tasks/" + tasks[0]).status_code == 404
    viewer = connect(client, "读者账号", "viewer-private-key")
    form = parameters(client, flow, viewer)
    assert form["parameterLayout"] == saved and form["originalDefaults"] == {}
    assert (
        client.put(edit, json={"machineId": viewer["id"], "parameterLayout": []}).status_code == 404
    )
    denied = client.post(
        "/api/v1/tasks", json=body | {"machineId": studio["id"], "idempotencyKey": str(uuid4())}
    )
    assert denied.status_code in (404, 409)
    unique = (
        client.post("/api/v1/tasks", json={k: v for k, v in body.items() if k != "machineId"})
        .raise_for_status()
        .json()
    )
    assert unique["machineId"] == viewer["id"]
    assert (
        asyncio.run(run_once(provider, app=client.app))
        and submitted[-1]["apiKey"] == "viewer-private-key"
    )
    assert client.get("/api/v1/artifacts", params={"task_id": tasks[0]}).json()["items"] == []


@pytest.mark.parametrize("fault", ["disconnect", "ambiguous", "unknown", "rotated"])
def test_restart_and_uncertain_submission(client, upstream, fault):
    provider, submitted, mode, _ = upstream
    register(client, "cloud-recovery")
    machine = connect(client, "个人", "original-test-key")
    flow = add(client, machine)
    task = (
        client.post("/api/v1/tasks", json=task_body(client, flow, machine["id"]))
        .raise_for_status()
        .json()
    )
    url = "/api/v1/tasks/" + task["id"]
    mode["fault"] = fault
    if fault == "disconnect":
        with pytest.raises(httpx.ReadError):
            asyncio.run(run_once(provider, app=client.app))
        with Session(client.app.state.engine) as db:
            stored = db.get_one(Task, task["id"])
            assert stored.prompt_id == "1"
            stored.lease_expires_at = now_ms() - 1
            db.commit()
        mode["fault"] = ""
    elif fault == "rotated":
        client.put(
            "/api/v1/machines/" + machine["id"] + "/connection",
            json={
                "kind": "runninghub",
                "name": "新账号",
                "scope": "cn",
                "apiKey": "replacement-key",
            },
        ).raise_for_status()
    assert asyncio.run(run_once(provider, app=client.app))
    done = client.get(url).json()
    assert done["machineName"] == "个人"
    assert done["status"] == ("succeeded" if fault == "disconnect" else "failed")
    assert len(submitted) == (0 if fault == "rotated" else 1)
    if fault in {"ambiguous", "unknown"}:
        assert client.get(url + "/progress").json()["executions"][0]["recovery"] == "unverified"
        assert (
            client.post(
                url + "/retry-executions",
                json={"service": True, "executionIndices": [0], "idempotencyKey": str(uuid4())},
            ).status_code
            == 409
        )
    assert not asyncio.run(run_once(provider, app=client.app))


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("queued", "not_submitted"),
        ("reserved", "unconfirmed"),
        ("acknowledged", "accepted"),
        ("rejected", "unconfirmed"),
        ("rotated", "unconfirmed"),
    ],
)
def test_cancel_records_only_confirmed_cloud_acknowledgements(client, upstream, state, expected):
    provider, _, mode, _ = upstream
    register(client, "rh-cancel")
    machine = connect(client, "个人连接", "cancel-test-key")
    flow = add(client, machine)
    task = (
        client.post("/api/v1/tasks", json=task_body(client, flow, machine["id"]))
        .raise_for_status()
        .json()
    )
    task_url = "/api/v1/tasks/" + task["id"]
    if state == "reserved":
        secret = "s" * 36
        worker = {"Authorization": "Bearer " + TOKEN, "X-Task-Lease": secret}
        client.post(
            "/api/v1/worker/services/runninghub/claim",
            headers=worker,
            json={
                "protocolVersion": PROTOCOL_VERSION,
                "adapters": ["runninghub"],
                "claimId": str(uuid4()),
                "leaseSecret": secret,
            },
        ).raise_for_status()
        assert (
            client.post(f"/api/v1/worker/tasks/{task['id']}/executions/0/reserve", headers=worker)
            .raise_for_status()
            .json()
        )
    elif state != "queued":
        mode["fault"] = "disconnect"
        with pytest.raises(httpx.ReadError):
            asyncio.run(run_once(provider, app=client.app))
        if state == "rotated":
            client.put(
                "/api/v1/machines/" + machine["id"] + "/connection",
                json={
                    "kind": "runninghub",
                    "scope": "cn",
                    "name": "个人连接",
                    "apiKey": "replacement-test-key",
                },
            ).raise_for_status()
        mode["fault"] = "cancel-failed" if state == "rejected" else ""
    for _ in range(2):
        stopped = client.post(task_url + "/cancel").raise_for_status().json()
        assert stopped["status"] == "cancelled" and stopped["cloudCancel"] == expected
    assert client.get(task_url).json()["cloudCancel"] == expected
    assert mode["cancelled"] == (
        [{"apiKey": "cancel-test-key", "taskId": "1"}]
        if state in {"rejected", "acknowledged"}
        else []
    )
    if state == "queued":
        assert client.post(task_url + "/resume").raise_for_status().json()["cloudCancel"] is None
    else:
        assert client.post(task_url + "/resume").status_code == 409


def test_reference_catalog_enrichment_keeps_layout_and_uses_reported_choices(client, upstream):
    _, _, mode, _ = upstream
    register(client, "cloud-catalog")
    machine = connect(client, "私人连接", "catalog-test-key")
    mode["info"] = {}
    flow = add(client, machine)
    form = parameters(client, flow, machine)
    assert form["catalogLimited"]
    fields = {f["inputName"]: f for f in form["fields"] if f["nodeId"] == "3"}
    assert fields["sampler_name"]["kind"] == "string" and fields["steps"]["maximum"] is None
    layout = [{"fieldId": fields["steps"]["id"], "displayName": "步数设置", "section": "default"}]
    client.put(
        f"/api/v1/workflows/{flow['id']}/versions/{flow['versionId']}/parameter-layout",
        json={"machineId": machine["id"], "parameterLayout": layout},
    ).raise_for_status()
    mode["info"] = PHOTO_INFO
    enriched = add(client, machine)
    assert (enriched["id"], enriched["version"]) == (flow["id"], flow["version"] + 1)
    form = parameters(client, enriched, machine)
    assert not form["catalogLimited"] and form["parameterLayout"][0]["displayName"] == "步数设置"
    mode["info"] = {}
    assert add(client, machine)["versionId"] == enriched["versionId"]
    mode["graph"] = {"1": {"class_type": "Custom", "inputs": {"api_key": "embedded-private-value"}}}
    response = client.post(
        "/api/v1/workflows/from-connection",
        json={"machineId": machine["id"], "reference": EXTERNAL},
    )
    assert response.status_code == 422 and "embedded-private-value" not in response.text


def test_definite_rejection_retries_only_on_the_original_named_connection(client, upstream):
    provider, submitted, mode, _ = upstream
    register(client, "cloud-retry")
    machine = connect(client, "个人", "retry-test-key")
    connect(client, "团队", "alternate-test-key")
    flow = add(client, machine)
    task = (
        client.post("/api/v1/tasks", json=task_body(client, flow, machine["id"]))
        .raise_for_status()
        .json()
    )
    mode["fault"] = "rejected"
    assert asyncio.run(run_once(provider, app=client.app))
    url = "/api/v1/tasks/" + task["id"]
    assert client.get(url + "/progress").json()["executions"][0]["recovery"] == "rerunnable"
    mode["fault"] = ""
    retry = (
        client.post(
            url + "/retry-executions",
            json={"service": True, "executionIndices": [0], "idempotencyKey": str(uuid4())},
        )
        .raise_for_status()
        .json()
    )
    assert retry["machineId"] == machine["id"] and asyncio.run(run_once(provider, app=client.app))
    assert [body["apiKey"] for body in submitted] == ["retry-test-key", "retry-test-key"]
    assert client.get("/api/v1/tasks/" + retry["id"]).json()["status"] == "succeeded"


def test_postgres_competing_workers_and_64_bit_seeds(settings, pg_url, upstream):
    provider, submissions, mode, png = upstream
    settings.database_url = pg_url
    migrate(settings)
    with TestClient(create_app(settings), headers={"Origin": "http://testserver"}) as client:
        register(client, "cloud-postgres")
        machine = connect(client, "批量", "postgres-test-key")
        flow = add(client, machine)
        fields = {
            (f["nodeId"], f["inputName"]): f["id"]
            for f in parameters(client, flow, machine)["fields"]
        }
        asset = (
            client.put(f"/api/v1/assets/{uuid4()}?filename=ref.png", content=png)
            .raise_for_status()
            .json()
        )
        values = {
            fields["3", "seed"]: str(2**63 + 1),
            fields["10", "image"]: {"assetId": asset["id"]},
        }
        body = task_body(client, flow, machine["id"]) | {"executionCount": 2, "inputValues": values}
        task = client.post("/api/v1/tasks", json=body).raise_for_status().json()

        async def compete():
            return await asyncio.gather(
                run_once(provider, app=client.app), run_once(provider, app=client.app)
            )

        assert sorted(asyncio.run(compete())) == [False, True]
        assert client.get("/api/v1/tasks/" + task["id"]).json()["status"] == "succeeded"
        assert [
            next(n["fieldValue"] for n in request["nodeInfoList"] if n["fieldName"] == "seed")
            for request in submissions
        ] == [2**63 + 1, 2**63 + 2]
        assert mode["uploads"] == 1


@pytest.mark.parametrize("connection", ["account", "platform"])
def test_register_another_field_worker_without_product_changes(
    client, settings, upstream, monkeypatch, connection
):
    _, _, _, png = upstream
    kind = "test-renderer"
    spec = {
        "fields": [{"name": "prompt", "kind": "string", "label": "说明", "default": "默认"}],
        "execution": {"adapter": kind, "outputKind": "image", "config": {}},
    }

    async def load(scope, key, reference):
        assert (scope, key) == ("default", "reader-key")
        return Source(reference, spec)

    calls = []

    class TestAdapter:
        def __init__(self, http, auth):
            calls.append(auth)

        async def prepare(self, job, assets):
            assert job["task"]["inputValues"] == {"prompt": "测试正文"} and not assets

        async def submit(self, index):
            assert index == 0
            return "accepted"

        async def poll(self, remote_id):
            assert remote_id == "accepted"
            return [{"name": "test.png"}]

        async def download(self, item, path, index):
            path.write_bytes(png)
            return item["name"], "outputs"

    worker = WorkerDefinition(
        kind,
        "测试工作机",
        connection,
        "fields",
        TestAdapter,
        sites={"default": "测试站点"},
        load_reference=load,
        input_kinds=("string",),
        output_kinds=("image",),
        output_node="outputs",
    )
    monkeypatch.setitem(WORKERS, kind, worker)
    token = "extension-test-worker-token-of-at-least-32"
    settings.worker_service_tokens = {kind: SecretStr(token)}
    settings.official_owner = "extension-author"
    register(client, settings.official_owner)
    if connection == "account":
        machine = connect(client, "自带账号", "reader-key", scope="default", kind=kind)
        flow = add(client, machine, ref="demo")
        form = parameters(client, flow, machine)
        machine_data = {"machineId": machine["id"]}
    else:
        manifest = spec | {
            "format": "service",
            "workerKind": kind,
            "key": "demo",
            "name": "测试",
            "category": "image",
        }
        flow = (
            client.post("/api/v1/workflows", json={"name": "测试", "graph": manifest})
            .raise_for_status()
            .json()
        )
        form = (
            client.get(f"/api/v1/workflows/{flow['id']}/service-inputs").raise_for_status().json()
        )
        machine_data = {}
    assert flow["worker"]["kind"] == kind and form["fields"][0]["id"] == "prompt"
    url = f"/api/v1/workflows/{flow['id']}"
    layout = [{"fieldId": "prompt", "section": "default", "defaultValue": "说明文字"}]
    client.put(
        url + f"/versions/{flow['versionId']}/parameter-layout",
        json=machine_data | {"parameterLayout": layout},
    ).raise_for_status()
    form = (
        parameters(client, flow, machine)
        if connection == "account"
        else client.get(url + "/service-inputs").raise_for_status().json()
    )
    task = (
        client.post(
            "/api/v1/tasks",
            json=machine_data
            | {
                "inputSchemaHash": form["schemaHash"],
                "versionId": flow["versionId"],
                "workflowId": flow["id"],
                "inputValues": {"prompt": "测试正文"},
                "idempotencyKey": str(uuid4()),
            },
        )
        .raise_for_status()
        .json()
    )

    async def execute():
        platform = Platform(
            "http://testserver", token, transport=httpx.ASGITransport(app=client.app)
        )
        try:
            async with httpx.AsyncClient() as http:
                assert await ServiceRunner(platform, worker, http).run_once()
        finally:
            await platform.close()

    asyncio.run(execute())
    assert calls == (
        [{"scope": "default", "apiKey": "reader-key"}] if connection == "account" else [{}]
    )
    done = client.get("/api/v1/tasks/" + task["id"]).json()
    assert done["status"] == "succeeded" and done["worker"]["kind"] == kind
    client.post(url + "/publish").raise_for_status()
    artifact = client.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"][0]
    assert client.get(artifact["media"]["src"]).content == png


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "mobile"])
def test_team_runninghub_browser_reuses_machine_and_import_dialogs(
    settings, upstream, width, tmp_path
):
    _, _, _, png = upstream
    settings.static_dir = Path(__file__).resolve().parents[2] / "web/dist"
    with (
        serve_test_app(settings) as (address, client),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        credentials = register(client, "rh-team-browser")
        team = client.post("/api/v1/teams", json={"name": "摄影团队"}).raise_for_status().json()
        scope = {"workspace_team": team["id"]}
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 844},
            locale="zh-CN",
            has_touch=width < 700,
            is_mobile=width < 700,
            reduced_motion="reduce",
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/machines")
        add_machine = page.get_by_role("button", name="添加工作机", exact=True)
        add_connection = page.get_by_role("menuitem", name="添加 RunningHub 连接", exact=True)
        setup = page.get_by_role("dialog", name="添加 RunningHub 连接", exact=True)
        save = setup.get_by_role("button", name="保存", exact=True)
        add_machine.click()
        add_connection.click()
        button_height = save.evaluate("node => getComputedStyle(node).height")
        setup.get_by_role("button", name="关闭", exact=True).click()

        open_space_picker(page).get_by_role("button", name=team["name"], exact=True).click()
        add_machine.click()
        add_connection.click()
        expect(save).to_have_css("height", button_height)
        assert setup.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        setup.screenshot(path=tmp_path / "team-runninghub-connection.png", animations="disabled")
        setup.get_by_label("名称", exact=True).fill("摄影组连接")
        setup.get_by_label("API Key", exact=True).fill("browser-team-test-key")
        save.click()
        expect(setup).to_have_count(0)
        if width > 700:
            page.get_by_role("button", name="从链接或 ID 导入", exact=True).click()
        else:
            page.goto("/workspace/workflows")
            page.get_by_role("button", name="导入工作流", exact=True).click()
            page.get_by_role("radio", name="链接或 ID", exact=True).click()
        importer = page.get_by_role("dialog", name="导入工作流", exact=True)
        importer.get_by_label("RunningHub 工作流链接或 ID").fill(REFERENCE)
        importer.get_by_label("工作流名称（可选）").fill("团队商品换背景")
        importer.get_by_role("button", name="导入工作流", exact=True).click()
        workflow = page.get_by_role("dialog", name="团队商品换背景", exact=True)
        expect(workflow.get_by_role("combobox", name="本次执行工作机")).to_contain_text(
            "摄影组连接"
        )
        assert workflow.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        workflow.screenshot(path=tmp_path / "team-runninghub-workflow.png", animations="disabled")
        workflow.locator('form.run-fields input[type="file"]').first.set_input_files(
            {"name": "ref.png", "mimeType": "image/png", "buffer": png}
        )
        with page.expect_response(
            lambda response: response.request.method == "POST" and "/api/v1/tasks?" in response.url
        ) as result:
            workflow.get_by_role("button", name="生成", exact=True).click()
        assert result.value.status == 201 and f"workspace_team={team['id']}" in result.value.url
        assert item_ids(client.get("/api/v1/tasks", params=scope)) == {result.value.json()["id"]}
        assert not item_ids(client.get("/api/v1/machines"))


@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_browser_link_import_upload_and_generate(settings, upstream, width, height):
    provider, submitted, mode, png = upstream
    mode.update(graph=PHOTO_GRAPH, info=PHOTO_INFO)
    settings.static_dir = Path(__file__).resolve().parents[2] / "web/dist"
    with (
        serve_test_app(settings) as (address, client),
        sync_playwright() as pw,
        pw.chromium.launch() as browser,
    ):
        credentials = register(client, "rh-browser")
        page = browser.new_page(base_url=address, viewport={"width": width, "height": height})
        page.set_default_timeout(8000)
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/machines")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        for name, key in [("个人设计", "browser-key"), ("设计部", "team-key")]:
            page.get_by_role("button", name="添加工作机", exact=True).click()
            page.get_by_role("menuitem", name="添加 RunningHub 连接").click()
            dialog = page.get_by_role("dialog")
            dialog.get_by_label("名称", exact=True).fill(name)
            dialog.get_by_label("API Key", exact=True).fill(key)
            dialog.get_by_role("button", name="保存", exact=True).click()
            expect(dialog).to_have_count(0)
        item = page.locator(".machine-item").filter(has_text="个人设计")
        cloud_menu = item.get_by_role("button", name="个人设计 操作")
        if width > 700:
            local = (
                client.post("/api/v1/machines", json={"name": "本机回归"}).raise_for_status().json()
            )
            page.reload()
            pause_url = f"**/api/v1/machines/{local['machine']['id']}/pause"
            held = []
            page.route(pause_url, lambda route: held.append(route))
            page.get_by_role("button", name="本机回归 操作").click()
            with page.expect_request(pause_url):
                page.get_by_role("menuitem", name="暂停接单").click()
            cloud_menu.click()
            for label in ("重命名", "撤销工作机"):
                expect(page.get_by_role("menuitem", name=label, exact=True)).to_be_disabled()
            held.pop().continue_()
            page.unroute(pause_url)
            expect(page.get_by_role("menuitem", name="重命名", exact=True)).to_be_enabled()
            page.get_by_role("menuitem", name="重命名", exact=True).click()
            rename = page.get_by_role("dialog", name="重命名工作机")
            rename.get_by_role("button", name="关闭").click()
            expect(cloud_menu).to_be_focused()
        item.get_by_role("button", name="个人设计 操作").click()
        page.get_by_role("menuitem", name="连接设置").click()
        settings_dialog = page.get_by_role("dialog", name="连接设置")
        expect(settings_dialog.get_by_text("要让已有任务使用新 Key", exact=False)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        settings_dialog.get_by_role("button", name="关闭").click()
        if width > 700:
            page.goto("/workspace/workflows")
            page.get_by_role("button", name="导入工作流", exact=True).click()
            panel = page.get_by_role("dialog", name="导入工作流")
            panel.get_by_role("radio", name="链接或 ID").click()
            panel.get_by_role("combobox", name="工作机", exact=True).click()
            page.get_by_role("option", name="个人设计", exact=True).click()
            expect(panel.get_by_role("combobox", name="导入分类")).to_have_text("图像")
        else:
            item.get_by_role("button", name="从链接或 ID 导入").click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("RunningHub 工作流链接或 ID").fill(REFERENCE)
        dialog.get_by_label("工作流名称（可选）").fill("商品换背景")
        dialog.get_by_role("button", name="导入工作流").click()
        selector = page.get_by_role("combobox", name="本次执行工作机")
        expect(selector).to_contain_text("个人设计")
        selector.click()
        page.get_by_role("option", name=re.compile("设计部")).click()
        page.get_by_role("button", name="编辑参数").click()
        editor = page.get_by_role("dialog", name="编辑参数")
        for label in ("步数", "采样器"):
            row_button = editor.get_by_role("button", name=re.compile("^" + label))
            row_button.click()
            editor.get_by_role("combobox", name="移动" + label).click()
            page.get_by_role("option", name="默认展示").click()
        editor.get_by_role("button", name=re.compile("^步数")).click()
        editor.get_by_label("默认值", exact=True).fill("26")
        editor.get_by_label("显示名称", exact=True).fill("采样步数")
        editor.get_by_role("button", name="保存", exact=True).click()
        form = page.locator("form.run-fields")
        expect(form.get_by_label("采样步数", exact=True)).to_have_value("26")
        form.get_by_label("采样步数", exact=True).fill("31")
        form.get_by_role("combobox", name="采样器").click()
        page.get_by_role("option", name="heun").click()
        expect(selector).to_contain_text("设计部")
        form.get_by_label("提示词", exact=True).fill("蓝色背景")
        form.locator('input[type="file"]').first.set_input_files(
            {"name": "ref.png", "mimeType": "image/png", "buffer": png}
        )
        generate = page.get_by_role("button", name="生成", exact=True)
        expect(generate).to_be_enabled()
        with page.expect_response(
            lambda res: res.request.method == "POST" and "/api/v1/tasks" in res.url
        ) as result:
            generate.click()
        assert result.value.ok
        task_id = result.value.json()["id"]
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(asyncio.run, run_once(provider, address=address)).result(timeout=10)
        assert [body["apiKey"] for body in submitted] == ["team-key"]
        values = {
            (v["nodeId"], v["fieldName"]): v["fieldValue"] for v in submitted[0]["nodeInfoList"]
        }
        assert (
            values["3", "steps"],
            values["3", "sampler_name"],
            values["11", "text"],
            values["10", "image"],
        ) == (31, "heun", "蓝色背景", "openapi/ref.png")
        assert client.get("/api/v1/tasks/" + task_id).json()["status"] == "succeeded"
        artifact = client.get("/api/v1/artifacts", params={"task_id": task_id}).json()["items"][0]
        assert client.get(artifact["media"]["src"]).raise_for_status().content == png
        results = browser.new_page(base_url=address, viewport={"width": width, "height": height})
        assert results.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        results.goto("/workspace/results")
        results.get_by_role("button", name=re.compile("^查看 商品换背景")).first.click()
        result_dialog = results.get_by_role("dialog", name="商品换背景")
        preview = result_dialog.get_by_role("img", name="result-1.png")
        expect(preview).to_be_visible()
        expect(preview).to_have_js_property("complete", True)
        assert preview.evaluate("image => image.naturalWidth > 0")
        result_dialog.get_by_role("button", name="先发布工作流").click()
        results.get_by_role("button", name="发布工作流并继续").click()
        publish = results.get_by_role("dialog", name="发布作品")
        expect(publish.get_by_role("radio", name=re.compile("公开完整输入"))).to_be_checked()
        publish.get_by_label("名称", exact=True).fill("换背景成品")
        with results.expect_response(
            lambda r: (
                r.request.method == "POST" and r.url.split("?", 1)[0].endswith("/api/v1/works")
            )
        ) as publication:
            publish.get_by_role("button", name="发布作品", exact=True).click()
        assert publication.value.ok
        with httpx.Client(base_url=address, trust_env=False) as guest:
            work_url = "/api/v1/works/" + publication.value.json()["id"]
            work = guest.get(work_url).raise_for_status().json()
            (shared_asset,) = guest.get(work_url + "/inputs").raise_for_status().json()["assets"]
            assert guest.get(shared_asset["media"]["src"]).raise_for_status().content == png
        assert work["published"] and work["title"] == "换背景成品"
        assert (
            work["executionId"] == artifact["executionId"]
            and work["coverArtifactId"] == artifact["id"]
        )
        results.goto("/workspace/results")
