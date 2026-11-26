import hashlib
import json
import shutil
import subprocess
from io import BytesIO
from struct import pack
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from helpers import CATALOG, execution_id, machine_heartbeat, sync_machine, task_body
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_worker import claim_body, image_bytes, setup_job

from comfyshop_api.models import Execution, MediaObject, Task, Work, now_ms
from comfyshop_api.services.machines import expire_leases
from comfyshop_api.services.originals import retire_unreferenced_originals


def run_group(
    client, worker, task_id, lease, index=0, members=3, media=None, effective_prompt=None
):
    base = f"/api/v1/worker/tasks/{task_id}"
    headers = {"X-Task-Lease": lease}
    heartbeat = {
        "sequence": 2 + index * 2,
        "progress": min(index * 30, 99),
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
    files = media if media is not None else [("png", image_bytes(), "images")] * members
    for position, (suffix, data, slot) in enumerate(files):
        params = {
            "filename": f"output-{index}-{position}.{suffix}",
            "sha256": hashlib.sha256(data).hexdigest(),
            "execution_index": index,
            "output_node_id": "2",
            "output_slot": slot,
            "output_index": position,
        }
        response = worker.put(
            base + f"/artifacts/r{index}_{position}", content=data, params=params, headers=headers
        )
        assert response.status_code == 200, response.text
        outputs.append(response.json())
    manifest = {"clientIds": [f"r{index}_{position}" for position in range(len(files))]}
    if effective_prompt is not None:
        manifest["effectivePrompt"] = effective_prompt
    if len(files) > 1:
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


def test_qwen_actual_prompt_is_recorded_per_execution(authenticated, graph):
    client = authenticated
    qwen = {
        "original": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "a cup"}},
        "expansion": {"class_type": "TextGenerate", "inputs": {"prompt": ["original", 0]}},
        "switch": {
            "class_type": "ComfySwitchNode",
            "inputs": {"switch": True, "on_true": ["expansion", 0], "on_false": ["original", 0]},
        },
        "preview": {"class_type": "PreviewAny", "inputs": {"source": ["switch", 0]}},
        "encode": {"class_type": "TextEncodeQwenImage21", "inputs": {"prompt": ["preview", 0]}},
    }
    graph["2"]["inputs"]["images"] = ["encode", 0]
    catalog = {"nodes": {**CATALOG["nodes"], **{n["class_type"]: {} for n in qwen.values()}}}
    workflow = (
        client.post("/api/v1/workflows", json={"name": "prompt", "graph": {**graph, **qwen}})
        .raise_for_status()
        .json()
    )
    machine = client.post("/api/v1/machines", json={"name": "prompt"}).raise_for_status().json()
    worker = sync_machine(client, machine, catalog)
    body = task_body(client, workflow, machine["machine"]["id"])
    task = client.post("/api/v1/tasks", json=body).raise_for_status().json()
    claim = claim_body()
    job = worker.post("/api/v1/worker/claim", json=claim).raise_for_status().json()
    assert job["promptPreviewNodeId"] == "preview"
    prompt = "A cobalt cup on a white table"
    execution, _ = run_group(
        client, worker, task["id"], claim["leaseSecret"], members=1, effective_prompt=prompt
    )
    result = client.get(f"/api/v1/executions/{execution['id']}").raise_for_status().json()
    assert result["effectivePrompt"] == prompt
    assert result["promptExpanded"] is True
    assert result["inputValues"] == task["inputValues"]
    assert (
        worker.post(
            f"/api/v1/worker/tasks/{task['id']}/executions/0/complete",
            json={"clientIds": ["r0_0"], "effectivePrompt": "different"},
            headers={"X-Task-Lease": claim["leaseSecret"]},
        ).status_code
        == 409
    )


@pytest.fixture
def flac(settings, tmp_path):
    if not shutil.which(settings.ffmpeg) or not shutil.which(settings.ffprobe):
        pytest.skip("ffmpeg and ffprobe are required for FLAC acceptance")
    file = tmp_path / "sample.flac"
    subprocess.run(
        [
            settings.ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=duration=0.3",
            str(file),
        ],
        check=True,
    )
    return file.read_bytes()


def glb_bytes():
    vertices = pack("<9f", -1, 0, 0, 1, 0, 0, 0, 1, 0)
    descriptor = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "buffers": [{"byteLength": len(vertices)}],
        "bufferViews": [{"buffer": 0, "byteLength": len(vertices)}],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [-1, 0, 0],
                "max": [1, 1, 0],
            }
        ],
    }
    metadata = json.dumps(descriptor).encode()
    metadata += b" " * (-len(metadata) % 4)
    chunks = (
        pack("<I4s", len(metadata), b"JSON")
        + metadata
        + pack("<I4s", len(vertices), b"BIN\x00")
        + vertices
    )
    return pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def test_models_and_image_previews_are_separate_originals(authenticated, graph):
    client = authenticated
    machine, task, _ = setup_job(client, graph)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    assert worker.post("/api/v1/worker/claim", json=claim).status_code == 200
    glb = glb_bytes()
    execution, (model, image) = run_group(
        client,
        worker,
        task["id"],
        claim["leaseSecret"],
        media=[("glb", glb, "3d"), ("png", image_bytes(), "images")],
    )
    assert (execution["modelCount"], execution["imageCount"], execution["artifactCount"]) == (
        1,
        1,
        2,
    )
    assert execution["media"] == image["media"]
    assert model["contentType"] == "model/gltf-binary"
    assert model["media"]["kind"] == "3d" and model["media"]["thumbnail"] is None
    response = client.get(model["media"]["src"], params={"download": "true"})
    assert response.status_code == 200 and response.content == glb
    assert response.headers["content-type"] == "model/gltf-binary"
    invalid = client.put(
        f"/api/v1/assets/{uuid4()}", params={"filename": "truncated.glb"}, content=glb[:-4]
    )
    assert invalid.status_code == 422 and "GLB" in invalid.json()["detail"]
    workflow = f"/api/v1/workflows/{task['workflowId']}"
    assert client.patch(workflow, json={"category": "3d"}).status_code == 200
    assert client.post(workflow + "/publish").status_code == 200
    request = {
        "id": str(uuid4()),
        "executionId": execution["id"],
        "title": "带预览的模型",
        "artifactIds": [model["id"], image["id"]],
        "coverArtifactId": image["id"],
    }
    visitor = TestClient(client.app)
    preview_only = client.post(
        "/api/v1/works", json={**request, "id": str(uuid4()), "artifactIds": [model["id"]]}
    )
    assert preview_only.status_code == 201, preview_only.text
    shared_model = preview_only.json()
    assert shared_model["assetCount"] == 1 and shared_model["media"] == model["media"]
    assert visitor.get(shared_model["coverImage"]["src"]).status_code == 200
    assert visitor.get(image["media"]["src"]).status_code == 404
    published = client.post("/api/v1/works", json=request)
    assert published.status_code == 201, published.text
    assert published.json()["media"] == image["media"]
    assert published.json()["category"] == "3d"
    model_only = client.post(
        "/api/v1/works",
        json={**request, "id": str(uuid4()), "artifactIds": [model["id"]], "coverArtifactId": None},
    )
    assert model_only.status_code == 201, model_only.text
    assert model_only.json()["media"] == model["media"]
    assert TestClient(client.app).get(model["media"]["src"]).content == glb


def test_audio_only_execution_preserves_the_flac(authenticated, graph, flac):
    client = authenticated
    machine, task, _ = setup_job(client, graph)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    assert worker.post("/api/v1/worker/claim", json=claim).status_code == 200
    execution, (artifact,) = run_group(
        client, worker, task["id"], claim["leaseSecret"], media=[("flac", flac, "audio")]
    )
    assert execution["status"] == "succeeded"
    assert (execution["audioCount"], execution["artifactCount"]) == (1, 1)
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["status"] == "succeeded"
    assert artifact["contentType"] == "audio/flac"
    media = artifact["media"]
    assert media["kind"] == "audio" and media["width"] is None and media["height"] is None
    assert media["durationMs"] == 300 and media["filename"] == artifact["filename"]
    assert media["thumbnail"] is None
    assert client.get(media["src"]).content == flac
    assert client.get(media["src"], headers={"Range": "bytes=0-3"}).content == b"fLaC"
    visitor = TestClient(client.app)
    assert visitor.get(media["src"]).status_code == 404
    assert client.post(f"/api/v1/workflows/{task['workflowId']}/publish").status_code == 200
    body = {
        "id": str(uuid4()),
        "executionId": execution["id"],
        "title": "音频作品",
        "artifactIds": [artifact["id"]],
    }
    published = client.post("/api/v1/works", json=body)
    assert published.status_code == 201, published.text
    assert published.json()["media"] == media
    assert client.post("/api/v1/works", json=body).status_code == 200
    assert visitor.get(media["src"]).content == flac


@pytest.mark.parametrize(("suffix", "kind"), [("flac", "audio"), ("glb", "3d")])
def test_independent_covers_preserve_originals_and_publication(
    authenticated, graph, request, suffix, kind
):
    client = authenticated
    visitor = TestClient(client.app)
    content = request.getfixturevalue("flac") if kind == "audio" else glb_bytes()
    machine, task, _ = setup_job(client, graph)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    assert worker.post("/api/v1/worker/claim", json=claim).status_code == 200
    execution, (artifact,) = run_group(
        client, worker, task["id"], claim["leaseSecret"], media=[(suffix, content, kind)]
    )
    execution_url = f"/api/v1/executions/{execution['id']}/cover"
    workflow_url = f"/api/v1/workflows/{task['workflowId']}"
    assert client.post(f"{workflow_url}/publish").status_code == 200
    assert client.put(execution_url, json={"assetId": "missing"}).status_code == 404

    def upload_cover(color):
        image = BytesIO()
        Image.new("RGB", (68, 104), color).save(image, "PNG")
        response = client.put(
            f"/api/v1/assets/{uuid4()}", params={"filename": "cover.png"}, content=image.getvalue()
        )
        assert response.status_code == 200, response.text
        return response.json()

    first = upload_cover("green")
    next_image = upload_cover("blue")
    chosen = client.put(execution_url, json={"assetId": first["id"]})
    assert chosen.status_code == 200, chosen.text
    preview = chosen.json()["coverImage"]
    assert chosen.json()["media"] == artifact["media"]
    assert preview["width"] == 68 and preview["height"] == 104
    assert client.get(preview["src"]).headers["content-type"].startswith("image/")
    assert visitor.get(preview["src"]).status_code == 401

    body = {
        "id": str(uuid4()),
        "executionId": execution["id"],
        "title": "独立封面",
        "artifactIds": [artifact["id"]],
        "executionCoverSha256": preview["sha256"],
    }
    published = client.post("/api/v1/works", json=body)
    assert published.status_code == 201, published.text
    work = published.json()
    work_url = f"/api/v1/works/{work['id']}"
    assert work["media"]["kind"] == kind and work["assetCount"] == 1
    assert work["media"]["filename"].endswith(f".{suffix}")
    assert visitor.get(work["media"]["src"]).content == content
    work_cover = work["coverImage"]["src"]
    assert work_cover != preview["src"]
    assert visitor.get(work_cover).content == client.get(preview["src"]).content
    assert visitor.get(first["media"]["src"]).status_code == 401
    assert visitor.get(workflow_url).json()["media"]["src"] == work_cover
    assert visitor.get(f"{work_url}/inputs").json()["assets"] == []

    replaced = client.put(execution_url, json={"assetId": next_image["id"]})
    assert replaced.json()["coverImage"]["sha256"] == next_image["sha256"]
    assert client.get(preview["src"]).status_code == 404
    assert client.post("/api/v1/works", json=body).status_code == 200
    assert client.post("/api/v1/works", json={**body, "id": str(uuid4())}).status_code == 409
    assert client.delete(f"/api/v1/assets/{first['id']}").status_code == 204
    with Session(client.app.state.engine) as db:
        retire_unreferenced_originals(db)
        assert db.get(MediaObject, first["sha256"]) is not None
    assert visitor.get(work_cover).status_code == 200

    changed = client.put(f"{work_url}/cover", json={"assetId": next_image["id"]})
    assert changed.status_code == 200, changed.text
    assert changed.json()["media"] == artifact["media"]
    new_cover = changed.json()["coverImage"]["src"]
    assert visitor.get(work_cover).status_code == 404
    assert visitor.get(workflow_url).json()["media"]["src"] == new_cover
    assert client.put(execution_url, json={}).json()["coverImage"] is None
    assert visitor.get(new_cover).status_code == 200
    etag = visitor.get(new_cover).headers["etag"]
    assert client.delete(work_url).status_code == 204
    assert visitor.get(new_cover, headers={"If-None-Match": etag}).status_code == 404
    assert client.get(new_cover).status_code == 200
    assert client.put(f"{work_url}/cover", json={}).json()["coverImage"] is None
    with Session(client.app.state.engine) as db:
        retire_unreferenced_originals(db)
        assert db.get(MediaObject, first["sha256"]) is None


@pytest.mark.parametrize(
    ("node_class", "input_name", "kind", "suffix", "content_type"),
    [
        ("LoadAudio", "audio", "audio", "flac", "audio/flac"),
        ("Load3D", "model_file", "3d", "glb", "model/gltf-binary"),
    ],
)
def test_reference_asset_binds_and_handles_old_replays(
    authenticated, request, node_class, input_name, kind, suffix, content_type
):
    client = authenticated
    data = request.getfixturevalue("flac") if kind == "audio" else glb_bytes()
    machine = client.post("/api/v1/machines", json={"name": "素材工作机"}).json()
    machine_id = machine["machine"]["id"]
    filename = f"old.{suffix}"
    spec = {"kind": "choice", "choices": [filename]}
    catalog = {"nodes": {node_class: {"inputs": {input_name: spec}}}}
    worker = sync_machine(client, machine, catalog)
    graph = {"1": {"class_type": node_class, "inputs": {input_name: filename}}}
    workflow = client.post("/api/v1/workflows", json={"name": "参考输入", "graph": graph}).json()
    old = client.post("/api/v1/tasks", json=task_body(client, workflow, machine_id)).json()
    assert client.post(f"/api/v1/tasks/{old['id']}/cancel").status_code == 200
    spec.update(kind=kind, choices=[])
    assert worker.put("/api/v1/worker/catalog", json=catalog).status_code == 200

    replay = client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={"machine_id": machine_id, "execution_id": execution_id(client, old["id"])},
    )
    assert replay.status_code == 200, replay.text
    (field,) = replay.json()["fields"]
    assert field["kind"] == kind and field["default"] is None
    body = task_body(client, workflow, machine_id)
    assert client.post("/api/v1/tasks", json=body).status_code == 422
    asset = client.put(
        f"/api/v1/assets/{uuid4()}", params={"filename": f"reference.{suffix}"}, content=data
    ).json()
    queued = client.post(
        "/api/v1/tasks", json={**body, "inputValues": {field["id"]: {"assetId": asset["id"]}}}
    )
    assert queued.status_code == 201, queued.text
    claim = claim_body()
    job = worker.post("/api/v1/worker/claim", json=claim).json()
    assert job["graph"]["1"]["inputs"][input_name] == "__comfyshop_asset__:" + asset["id"]
    assert job["assets"][0]["contentType"] == content_type
    transferred = worker.get(
        f"/api/v1/worker/tasks/{queued.json()['id']}/assets/{asset['id']}",
        headers={"X-Task-Lease": claim["leaseSecret"]},
    )
    assert transferred.content == data


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


def test_workflow_histories_filter_by_version_before_pagination(authenticated, settings, graph):
    from test_covers import add_result

    client = authenticated
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    first = client.post("/api/v1/workflows", json={"name": "版本结果", "graph": graph}).json()
    workflow_id = first["id"]
    older = add_result(client, settings, first, owner, 1)
    newer = add_result(client, settings, first, owner, 2)
    second = client.patch(
        f"/api/v1/workflows/{workflow_id}",
        json={"graph": {"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "修订版"}}}},
    ).json()
    latest = add_result(client, settings, second, owner, 3)

    path = "/api/v1/executions"
    params = {"workflow_id": workflow_id, "version_id": first["versionId"], "limit": 1}
    page = client.get(path, params=params).json()
    assert [r["coverArtifactId"] for r in page["items"]] == [newer]
    page = client.get(path, params={**params, "cursor": page["nextCursor"]}).json()
    assert [r["coverArtifactId"] for r in page["items"]] == [older]
    assert page["nextCursor"] is None

    current = client.get(path, params={**params, "version_id": second["versionId"]}).json()
    (item,) = current["items"]
    assert item["coverArtifactId"] == latest and item["versionId"] == second["versionId"]
    assert client.get(path, params={**params, "task_id": item["taskId"]}).json()["items"] == []
    assert [r["coverArtifactId"] for r in client.get(path).json()["items"]] == [
        latest,
        newer,
        older,
    ]

    summary = client.get("/api/v1/tasks", params=params).json()
    (newest_in_version,) = summary["items"]
    assert newest_in_version["versionId"] == first["versionId"]
    assert newest_in_version["media"]["src"] == f"/api/v1/artifacts/{newer}/file"
    activity = "/api/v1/tasks/activity"
    for version, completed in ((first, 2), (second, 1)):
        response = client.get(
            activity, params={"workflow_id": workflow_id, "version_id": version["versionId"]}
        )
        assert response.json() == {"activeTasks": [], "completedExecutions": completed}


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
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + key})
    assert worker.post("/api/v1/worker/heartbeat", json=machine_heartbeat()).status_code == 200
    response = client.post(
        "/api/v1/tasks",
        json={
            "workflowId": task["workflowId"],
            "versionId": task["versionId"],
            **task_body(client, workflow, machine_id),
            "executionCount": 2,
            "machineId": machine_id,
            "idempotencyKey": str(uuid4()),
        },
    )
    assert response.status_code == 201, response.text
    next_task = response.json()
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
