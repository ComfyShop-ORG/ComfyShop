from copy import deepcopy
from io import BytesIO
from struct import pack
from uuid import uuid4

import pytest
from comfyshop_worker_protocol import PROTOCOL_VERSION
from fastapi.testclient import TestClient
from helpers import execution_id, sync_machine, task_body
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from comfyshop_api.models import Task


def picture(color="black", *, size=(32, 48), format_="PNG"):
    stream = BytesIO()
    Image.new("RGB", size, color).save(stream, format=format_)
    return stream.getvalue()


def test_native_alpha_is_preserved_until_a_matching_mask_is_supplied(authenticated):
    client = authenticated
    machine = client.post("/api/v1/machines", json={"name": "native-alpha"}).json()
    sync_machine(
        client,
        machine,
        {
            "nodes": {
                "LoadImage": {"inputs": {"image": {"kind": "image"}}},
                "LoadImageMask": {"inputs": {"image": {"kind": "image"}}},
                "VAEEncodeForInpaint": {"inputs": {}},
                "MaskToImage": {"inputs": {}},
            }
        },
    )
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
        "2": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {"pixels": ["1", 0], "mask": ["1", 1]},
        },
        "3": {"class_type": "MaskToImage", "inputs": {"mask": ["1", 1]}},
    }
    w = client.post("/api/v1/workflows", json={"name": "alpha", "graph": graph}).json()
    mid = machine["machine"]["id"]
    form = client.get(f"/api/v1/workflows/{w['id']}/inputs", params={"machine_id": mid}).json()
    (source,) = form["parameterPresentation"]
    binding = form["parameterPresentation"][source]["mask"]
    assert binding.keys() == {"fieldId"}
    mask = binding["fieldId"]

    def upload(color, size):
        return client.put(
            f"/api/v1/assets/{uuid4()}?filename=image.png", content=picture(color, size=size)
        ).json()["id"]

    body = task_body(client, w, mid)
    reference = upload("blue", (32, 48))
    body["inputValues"] = {
        source: {"assetId": reference},
        mask: {"assetId": upload("white", (2, 2))},
    }
    assert client.post("/api/v1/tasks", json=body).status_code == 422
    del body["inputValues"][mask]
    assert client.post("/api/v1/tasks", json=body).status_code == 201
    with Session(client.app.state.engine) as db:
        original = db.scalar(select(Task).where(Task.workflow_id == w["id"]))
        assert original is not None and original.input_graph["2"]["inputs"] == graph["2"]["inputs"]
    body["idempotencyKey"] = str(uuid4())
    override = upload("white", (32, 48))
    body["inputValues"][mask] = {"assetId": override}
    sent = client.post("/api/v1/tasks", json=body)
    assert sent.status_code == 201
    with Session(client.app.state.engine) as db:
        task = db.get(Task, sent.json()["id"])
        assert task is not None
        loader, slot = task.input_graph["2"]["inputs"]["mask"]
        assert slot == 0 and task.input_graph["3"]["inputs"]["mask"] == [loader, 0]
        assert task.input_graph[loader]["inputs"] == {
            "channel": "red",
            "image": "__comfyshop_asset__:" + override,
        }
        assert task.input_graph["2"]["inputs"]["pixels"] == ["1", 0]


@pytest.fixture
def prepared(authenticated):
    client = authenticated
    machine = client.post("/api/v1/machines", json={"name": "reference"}).json()
    catalog = {
        "nodes": {
            "LoadImage": {"inputs": {"image": {"kind": "image"}}},
            "CLIPTextEncode": {"inputs": {"text": {"kind": "string", "multiline": True}}},
            "KSampler": {
                "inputs": {
                    "seed": {"kind": "integer", "minimum": "0", "maximum": str(2**64 - 1)},
                    "steps": {"kind": "integer", "minimum": "1", "maximum": "150", "step": "1"},
                    "cfg": {"kind": "number", "minimum": "0", "maximum": "100", "step": "0.5"},
                }
            },
            "SaveImage": {"outputNode": True},
        }
    }
    worker = sync_machine(client, machine, catalog)
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "private-host-file.png"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a bottle"}},
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "positive": ["2", 0],
                "latent_image": ["1", 0],
                "seed": 2**64 - 1,
                "steps": 20,
                "cfg": 4.5,
            },
        },
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}},
    }
    workflow = client.post(
        "/api/v1/workflows", json={"name": "reference workflow", "graph": graph}
    ).json()
    response = client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={"version_id": workflow["versionId"], "machine_id": machine["machine"]["id"]},
    )
    assert response.status_code == 200, response.text
    form = response.json()
    by_name = {field["inputName"]: field for field in form["fields"]}
    asset = client.put(
        f"/api/v1/assets/{uuid4()}", params={"filename": "bottle.png"}, content=picture()
    ).json()
    body = {
        "workflowId": workflow["id"],
        "versionId": workflow["versionId"],
        "machineId": machine["machine"]["id"],
        "executionCount": 1,
        "idempotencyKey": str(uuid4()),
        "inputSchemaHash": form["schemaHash"],
        "inputValues": {by_name["image"]["id"]: {"assetId": asset["id"]}},
    }
    return client, worker, workflow, form, by_name, asset, body, catalog


def test_reference_upload_binding_and_frozen_graph(prepared):
    client, worker, workflow, form, fields, asset, body, catalog = prepared
    assert "private-host-file.png" not in str(form)
    assert fields["seed"]["default"] == str(2**64 - 1)
    response = client.post("/api/v1/tasks", json=body)
    assert response.status_code == 201, response.text
    task = response.json()
    assert client.post("/api/v1/tasks", json=body).json()["id"] == task["id"]
    assert task["inputValues"][fields["image"]["id"]] == {"assetId": asset["id"]}
    replay = client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={
            "version_id": workflow["versionId"],
            "machine_id": body["machineId"],
            "execution_id": execution_id(client, task["id"]),
        },
    ).json()
    assert replay["schemaHash"] == form["schemaHash"]
    assert next(f for f in replay["fields"] if f["kind"] == "image")["default"] == {
        "assetId": asset["id"]
    }
    # Later edits cannot change the submitted graph or its bound asset.
    client.patch(
        f"/api/v1/workflows/{workflow['id']}",
        json={"graph": {"1": {"class_type": "SaveImage", "inputs": {}}}},
    )
    lease = uuid4().hex
    claim = worker.post(
        "/api/v1/worker/claim",
        json={"protocolVersion": PROTOCOL_VERSION, "claimId": str(uuid4()), "leaseSecret": lease},
    )
    assert claim.status_code == 200, claim.text
    job = claim.json()
    assert job["graph"]["3"]["inputs"]["seed"] == 2**64 - 1
    assert job["graph"]["1"]["inputs"]["image"] == "__comfyshop_asset__:" + asset["id"]
    assert job["assets"][0]["id"] == asset["id"]
    assert job["assets"][0]["nodeId"] == "1"
    assert (
        worker.get(
            f"/api/v1/worker/tasks/{task['id']}/assets/{asset['id']}",
            headers={"X-Task-Lease": lease},
        ).content
        == picture()
    )
    extra = client.put(
        f"/api/v1/assets/{uuid4()}", params={"filename": "unused.png"}, content=picture("white")
    ).json()
    catalog["nodes"]["KSampler"]["inputs"]["seed"]["label"] = "新种子标签"
    assert worker.put("/api/v1/worker/catalog", json=catalog).status_code == 200
    recorded = client.get(f"/api/v1/tasks/{task['id']}/inputs")
    assert recorded.status_code == 200
    snapshot = recorded.json()
    assert snapshot["version"] == workflow["version"]
    assert snapshot["assets"] == [asset]
    assert snapshot["fields"] == [
        {key: field[key] for key in ("id", "label", "nodeId", "nodeTitle", "inputName")}
        for field in form["fields"]
    ]
    assert (
        worker.get(
            f"/api/v1/worker/tasks/{task['id']}/assets/{extra['id']}",
            headers={"X-Task-Lease": lease},
        ).status_code
        == 404
    )
    assert (
        worker.get(
            f"/api/v1/worker/tasks/{task['id']}/assets/{asset['id']}",
            headers={"X-Task-Lease": "wrong"},
        ).status_code
        == 409
    )


def test_unconnected_painter_is_not_required_by_the_execution_graph(prepared):
    client, worker, workflow, _, _, asset, body, catalog = prepared
    endpoint = f"/api/v1/workflows/{workflow['id']}"
    graph = client.get(endpoint + "/graph").json()["graph"]
    graph["81"] = {"class_type": "Painter", "inputs": {"mask": "private-mask.png [input]"}}
    saved = client.patch(endpoint, json={"graph": graph})
    assert saved.status_code == 200, saved.text
    params = {"machine_id": body["machineId"], "version_id": saved.json()["versionId"]}
    incomplete = client.get(endpoint + "/inputs", params=params).json()
    assert incomplete["issues"] == ["缺少节点：Painter"]
    submission = task_body(client, saved.json(), body["machineId"])
    rejected = client.post("/api/v1/tasks", json=submission)
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "缺少节点：Painter"

    catalog["nodes"]["Painter"] = {"inputs": {"mask": {"kind": "image"}}}
    assert worker.put("/api/v1/worker/catalog", json=catalog).status_code == 200
    form = client.get(endpoint + "/inputs", params=params).json()
    assert not form["issues"]
    reference = next(field for field in form["fields"] if field["kind"] == "image")
    assert reference["nodeId"] == "1"
    assert all(field["nodeId"] != "81" for field in form["fields"])
    submission = task_body(client, saved.json(), body["machineId"])
    assert client.post("/api/v1/tasks", json=submission).status_code == 422
    submitted = client.post(
        "/api/v1/tasks",
        json={**submission, "inputValues": {reference["id"]: {"assetId": asset["id"]}}},
    )
    assert submitted.status_code == 201, submitted.text
    claim = worker.post(
        "/api/v1/worker/claim",
        json={
            "protocolVersion": PROTOCOL_VERSION,
            "claimId": str(uuid4()),
            "leaseSecret": uuid4().hex,
        },
    )
    assert "81" not in claim.json()["graph"]
    assert "81" in client.get(endpoint + "/graph").json()["graph"]


def test_parameters_and_schema_are_validated_before_queueing(prepared):
    client, worker, _, _, fields, _, body, catalog = prepared
    for name, value in [
        ("steps", 151),
        ("steps", 1.2),
        ("cfg", 100.2),
        ("cfg", "2.5"),
        ("seed", "18446744073709551616"),
        ("seed", "1e5"),
        ("text", 123),
    ]:
        changed = {
            **body,
            "idempotencyKey": str(uuid4()),
            "inputValues": {**body["inputValues"], fields[name]["id"]: value},
        }
        assert client.post("/api/v1/tasks", json=changed).status_code == 422, (name, value)
    assert client.post("/api/v1/tasks", json={**body, "inputValues": {}}).status_code == 422
    assert (
        client.post(
            "/api/v1/tasks",
            json={**body, "inputValues": {**body["inputValues"], "unknown": "value"}},
        ).status_code
        == 422
    )
    incomplete = {
        key: value for key, value in body.items() if key not in {"inputValues", "inputSchemaHash"}
    }
    assert client.post("/api/v1/tasks", json=incomplete).status_code == 422
    catalog["nodes"]["KSampler"]["inputs"]["steps"]["maximum"] = "100"
    worker.put("/api/v1/worker/catalog", json=catalog)
    assert client.post("/api/v1/tasks", json=body).status_code == 409
    assert client.get("/api/v1/tasks").json()["items"] == []


def test_unrelated_catalog_updates_and_uploads_do_not_invalidate_a_form(prepared):
    client, worker, workflow, form, _, _, body, catalog = prepared
    catalog["nodes"]["OtherWorkflowLoader"] = {
        "inputs": {"model": {"kind": "choice", "choices": ["new.safetensors"]}}
    }
    assert worker.put("/api/v1/worker/catalog", json=catalog).status_code == 200
    assert (
        client.put(
            f"/api/v1/assets/{uuid4()}", params={"filename": "extra.png"}, content=picture("white")
        ).status_code
        == 200
    )
    refreshed = client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={"machine_id": body["machineId"], "version_id": body["versionId"]},
    ).json()
    assert refreshed["schemaHash"] == form["schemaHash"]
    original = client.post("/api/v1/tasks", json=body)
    assert original.status_code == 201, original.text
    retry = client.post(
        "/api/v1/tasks", json=body | {"sourceExecutionId": None, "sourceWorkId": None}
    )
    assert retry.status_code == 200 and retry.json()["id"] == original.json()["id"]


def test_long_text_defaults_and_explicit_values_are_preserved(authenticated, graph):
    client = authenticated
    default = ('参考 "光线" 🐈\n' * 5000)[:38_449]
    graph["1"]["inputs"]["text"] = default
    created = client.post("/api/v1/workflows", json={"name": "长文本", "graph": graph})
    assert created.status_code == 201, created.text
    workflow = created.json()
    body = task_body(client, workflow)

    inherited = client.post("/api/v1/tasks", json=body)
    assert inherited.status_code == 201, inherited.text
    text_id = next(
        key for key, value in inherited.json()["inputValues"].items() if value == default
    )
    explicit = "🖼" * 65_536
    submitted = client.post(
        "/api/v1/tasks",
        json={**body, "idempotencyKey": str(uuid4()), "inputValues": {text_id: explicit}},
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["inputValues"][text_id] == explicit

    rejected = client.post(
        "/api/v1/tasks",
        json={**body, "idempotencyKey": str(uuid4()), "inputValues": {text_id: explicit + "。"}},
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "节点 1 的「text」有 65537 个字符，最多允许 65536 个字符"


def test_float_rounding_noise_is_normalized_on_form_read_and_submission(authenticated):
    client = authenticated
    machine = client.post("/api/v1/machines", json={"name": "precision"}).json()
    number = {"kind": "number", "step": "0.01"}
    catalog = {
        "nodes": {
            "ImageScaleBy": {
                "inputs": {"scale_by": {**number, "minimum": "0.01", "maximum": "8.0"}}
            },
            "ResolutionSelector": {
                "inputs": {"megapixels": {**number, "minimum": "0.1", "maximum": "16.0"}}
            },
        }
    }
    worker = sync_machine(client, machine, catalog)
    graph = {
        "1": {"class_type": "ImageScaleBy", "inputs": {"scale_by": 1.0500000000000003}},
        "2": {"class_type": "ResolutionSelector", "inputs": {"megapixels": 2.4000000000000004}},
    }
    response = client.post("/api/v1/workflows", json={"name": "upscale", "graph": graph})
    assert response.status_code == 201, response.text
    workflow = response.json()
    base = f"/api/v1/workflows/{workflow['id']}"
    machine_id = machine["machine"]["id"]
    response = client.get(f"{base}/inputs", params={"machine_id": machine_id})
    assert response.status_code == 200, response.text
    form = response.json()
    fields = {field["inputName"]: field for field in form["fields"]}
    scale = fields["scale_by"]["id"]
    megapixels = fields["megapixels"]["id"]
    body = {
        "workflowId": workflow["id"],
        "versionId": workflow["versionId"],
        "machineId": machine_id,
        "executionCount": 1,
        "inputSchemaHash": form["schemaHash"],
    }
    for inputs, expected in (
        ({}, 1.05),
        ({scale: 1.0500000000000003, megapixels: 2.4000000000000004}, 1.05),
        ({scale: 1.0499999999999998}, 1.05),
        ({scale: 8.000000000000002}, 8.0),
        ({scale: 1.055}, 1.055),
    ):
        queued = client.post(
            "/api/v1/tasks",
            json={**body, "idempotencyKey": str(uuid4()), "inputValues": inputs},
        )
        assert queued.status_code == 201, queued.text
        assert queued.json()["status"] == "queued"
        assert queued.json()["inputValues"] == {scale: expected, megapixels: 2.4}

    assert fields["scale_by"]["default"] == 1.05
    assert fields["megapixels"]["default"] == 2.4
    assert client.get(f"{base}/graph").json()["graph"] == graph
    for invalid in (0.009, 8.010000000000002):
        rejected = client.post(
            "/api/v1/tasks",
            json={**body, "idempotencyKey": str(uuid4()), "inputValues": {scale: invalid}},
        )
        assert rejected.status_code == 422, invalid

    claimed = worker.post(
        "/api/v1/worker/claim",
        json={
            "protocolVersion": PROTOCOL_VERSION,
            "claimId": str(uuid4()),
            "leaseSecret": uuid4().hex,
        },
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["graph"]["1"]["inputs"]["scale_by"] == 1.05
    assert claimed.json()["graph"]["2"]["inputs"]["megapixels"] == 2.4


def test_pixal3d_bias_uses_the_reported_bounds(authenticated):
    client = authenticated
    machine = client.post("/api/v1/machines", json={"name": "Pixal3D"}).json()
    sync_machine(
        client,
        machine,
        {
            "nodes": {
                "BakeAmbientOcclusion": {
                    "inputs": {
                        "bias": {
                            "kind": "number",
                            "minimum": "0.0001",
                            "maximum": "0.2",
                            "step": "0.0005",
                        }
                    }
                }
            }
        },
    )
    graph = {"233": {"class_type": "BakeAmbientOcclusion", "inputs": {"bias": 0.01}}}
    workflow = client.post("/api/v1/workflows", json={"name": "Pixal3D", "graph": graph}).json()
    body = task_body(client, workflow, machine["machine"]["id"])
    inherited = client.post("/api/v1/tasks", json=body)
    assert inherited.status_code == 201, inherited.text
    (field_id,) = inherited.json()["inputValues"]
    assert inherited.json()["inputValues"][field_id] == 0.01
    for value, status in ((0.0001, 201), (0.2, 201), (0, 422), (0.2001, 422)):
        response = client.post(
            "/api/v1/tasks",
            json={**body, "idempotencyKey": str(uuid4()), "inputValues": {field_id: value}},
        )
        assert response.status_code == status, response.text
        if status == 201:
            assert response.json()["inputValues"][field_id] == value


def test_pixal3d_rejects_crops_outside_the_original_image_before_queuing(authenticated):
    client = authenticated
    machine = client.post("/api/v1/machines", json={"name": "four views"}).raise_for_status().json()
    machine_id = machine["machine"]["id"]
    sync_machine(
        client,
        machine,
        {
            "nodes": {
                "LoadImage": {"inputs": {"image": {"kind": "image"}}},
                "ImageCropV2": {},
                "Pixal3DMultiViewConditioning": {"outputNode": True},
            }
        },
    )
    graph = {"sheet": {"class_type": "LoadImage", "inputs": {"image": "sheet.png"}}}
    roles = ("front", "left", "back", "right")
    for index, role in enumerate(roles):
        graph[role] = {
            "class_type": "ImageCropV2",
            "inputs": {
                "image": ["sheet", 0],
                "crop_region": {"x": index * 1584, "y": 0, "width": 1584, "height": 2688},
            },
        }
    graph["pixal"] = {
        "class_type": "Pixal3DMultiViewConditioning",
        "inputs": {role: [role, 0] for role in roles},
    }
    workflow = (
        client.post("/api/v1/workflows", json={"name": "four views", "graph": graph})
        .raise_for_status()
        .json()
    )

    def submit(workflow, size):
        form = (
            client.get(
                f"/api/v1/workflows/{workflow['id']}/inputs",
                params={"machine_id": machine_id, "version_id": workflow["versionId"]},
            )
            .raise_for_status()
            .json()
        )
        (field_id,) = form["imageCrops"]
        asset = (
            client.put(
                f"/api/v1/assets/{uuid4()}",
                params={"filename": "sheet.png"},
                content=picture(size=size),
            )
            .raise_for_status()
            .json()
        )
        return client.post(
            "/api/v1/tasks",
            json={
                **task_body(client, workflow, machine_id),
                "inputValues": {field_id: {"assetId": asset["id"]}},
            },
        )

    rejected = submit(workflow, (1024, 1024))
    assert rejected.status_code == 422
    assert "6336 × 2688" in rejected.json()["detail"]
    assert not client.get("/api/v1/tasks").json()["items"]
    assert submit(workflow, (6336, 2688)).status_code == 201

    graph["right"]["inputs"]["crop_region"]["x"] += 1
    newer = (
        client.patch(f"/api/v1/workflows/{workflow['id']}", json={"graph": graph})
        .raise_for_status()
        .json()
    )
    rejected = submit(newer, (6336, 2688))
    assert rejected.status_code == 422 and "6337 × 2688" in rejected.json()["detail"]
    assert len(client.get("/api/v1/tasks").json()["items"]) == 1


def test_default_asset_formats_reject_tiff_before_queueing(prepared):
    client, _, _, _, fields, _, body, _ = prepared
    field = fields["image"]
    assert field["acceptedContentTypes"] == ["image/png", "image/jpeg", "image/webp", "image/gif"]
    tiff = (
        client.put(
            f"/api/v1/assets/{uuid4()}",
            params={"filename": "photo.tiff"},
            content=picture(format_="TIFF"),
        )
        .raise_for_status()
        .json()
    )
    assert tiff["contentType"] == "image/tiff"
    response = client.post(
        "/api/v1/tasks", json={**body, "inputValues": {field["id"]: {"assetId": tiff["id"]}}}
    )
    assert response.status_code == 422, response.text
    assert client.get("/api/v1/tasks").json()["items"] == []


def test_upload_reports_heif_and_accepts_system_converted_jpeg(authenticated):
    client = authenticated
    response = client.put(
        f"/api/v1/assets/{uuid4()}",
        params={"filename": "photo"},
        content=pack(">I4s4sI4s", 20, b"ftyp", b"heic", 0, b"mif1"),
    )
    assert response.status_code == 422
    assert "当前不支持 HEIC 或 HEIF" in response.json()["detail"]
    converted = (
        client.put(
            f"/api/v1/assets/{uuid4()}",
            params={"filename": "photo.heic"},
            content=picture(format_="JPEG"),
        )
        .raise_for_status()
        .json()
    )
    assert converted["contentType"] == "image/jpeg"


def test_assets_are_private_and_cannot_cross_accounts(prepared):
    client, worker, _, _, fields, asset, body, _ = prepared
    anon = TestClient(client.app)
    assert anon.get(asset["media"]["src"]).status_code == 401
    assert worker.get(asset["media"]["src"]).status_code == 401
    other = TestClient(client.app, headers={"Origin": "http://testserver"})
    registration = other.post(
        "/api/v1/auth/register", json={"username": "asset-owner", "password": "another-password"}
    ).json()
    other.headers["X-CSRF-Token"] = registration["csrfToken"]
    foreign = other.put(
        f"/api/v1/assets/{uuid4()}", params={"filename": "foreign.png"}, content=picture()
    ).json()
    assert other.get(asset["media"]["src"]).status_code == 404
    assert (
        client.post(
            "/api/v1/tasks",
            json={**body, "inputValues": {fields["image"]["id"]: {"assetId": foreign["id"]}}},
        ).status_code
        == 404
    )


def test_upload_retry_integrity_and_size_limit(authenticated, settings):
    client = authenticated
    path = f"/api/v1/assets/{uuid4()}"
    one = client.put(path, params={"filename": "one.png"}, content=picture())
    assert one.status_code == 200
    assert (
        client.put(path, params={"filename": "one.png"}, content=picture()).json()["sha256"]
        == one.json()["sha256"]
    )
    assert (
        client.put(path, params={"filename": "one.png"}, content=picture("white")).status_code
        == 409
    )
    assert len(list(settings.original_dir.iterdir())) == 1
    assert (
        client.put(
            f"/api/v1/assets/{uuid4()}",
            params={"filename": "not-image.png"},
            content=b"not a media file",
        ).status_code
        == 422
    )
    settings.max_asset_bytes = 1024
    assert (
        client.put(
            f"/api/v1/assets/{uuid4()}", params={"filename": "large.png"}, content=b"x" * 1025
        ).status_code
        == 413
    )
    assert len(list(settings.original_dir.iterdir())) == 1


@pytest.mark.parametrize("source_max,target_max", [(2**32 - 1, 2**64 - 1), (2**64 - 1, 2**32 - 1)])
def test_replay_uses_current_integer_encoding_without_changing_saved_input(
    authenticated, graph, source_max, target_max
):
    from helpers import CATALOG, sync_machine, task_body
    from test_outputs import run_group
    from test_worker import claim_body

    client = authenticated
    machine = client.post("/api/v1/machines", json={"name": "integer-inputs"}).json()
    catalog = deepcopy(CATALOG)
    catalog["nodes"]["KSampler"]["inputs"]["seed"]["maximum"] = str(source_max)
    sync_machine(client, machine, catalog)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    workflow = client.post("/api/v1/workflows", json={"name": "seed", "graph": graph}).json()
    body = task_body(client, workflow, machine["machine"]["id"])
    task = client.post("/api/v1/tasks", json=body).json()
    claim = claim_body()
    worker.post("/api/v1/worker/claim", json=claim)
    source, _ = run_group(client, worker, task["id"], claim["leaseSecret"], 0, 1)
    worker.post(
        f"/api/v1/worker/tasks/{task['id']}/complete",
        headers={"X-Task-Lease": claim["leaseSecret"]},
    )
    catalog["nodes"]["KSampler"]["inputs"]["seed"]["maximum"] = str(target_max)
    sync_machine(client, machine, catalog)
    form = client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={"machine_id": machine["machine"]["id"], "execution_id": source["id"]},
    ).json()
    seed = next(field for field in form["fields"] if field["inputName"] == "seed")
    original = source["inputValues"][seed["id"]]
    expected = str(int(original)) if target_max > 2**53 - 1 else int(original)
    assert seed["default"] == expected and type(seed["default"]) is type(expected)
    repeated = client.post(
        "/api/v1/tasks",
        json={
            **body,
            "idempotencyKey": str(uuid4()),
            "inputSchemaHash": form["schemaHash"],
            "inputValues": {field["id"]: field["default"] for field in form["fields"]},
            "sourceExecutionId": source["id"],
        },
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["inputValues"][seed["id"]] == expected
    replay = client.get(f"/api/v1/executions/{source['id']}/replay").json()
    assert replay["sourceExecutionId"] == source["id"]
    saved = client.get("/api/v1/executions", params={"task_id": task["id"]}).json()["items"][0]
    assert saved["inputValues"] == source["inputValues"]


def test_execution_snapshots_and_public_replay_never_share_source_assets(prepared):
    from test_outputs import publish_body, run_group
    from test_worker import claim_body

    client, worker, workflow, _, fields, asset, body, catalog = prepared
    task = client.post("/api/v1/tasks", json={**body, "executionCount": 2}).json()
    claim = claim_body()
    worker.post("/api/v1/worker/claim", json=claim)
    first, _ = run_group(client, worker, task["id"], claim["leaseSecret"], 0, 1)
    second, outputs = run_group(client, worker, task["id"], claim["leaseSecret"], 1)
    worker.post(
        f"/api/v1/worker/tasks/{task['id']}/complete",
        headers={"X-Task-Lease": claim["leaseSecret"]},
    )
    assert first["inputValues"][fields["seed"]["id"]] == str(2**64 - 1)
    assert second["inputValues"][fields["seed"]["id"]] == "0"
    assert second["inputValues"][fields["image"]["id"]] == {"assetId": asset["id"]}
    client.post(f"/api/v1/workflows/{workflow['id']}/publish", json={})
    work = client.post("/api/v1/works", json=publish_body(second, outputs)).json()
    assert client.put("/api/v1/auth/profile", json={"nickname": "创作者"}).status_code == 200
    avatar = client.put("/api/v1/auth/profile/avatar", content=picture()).json()["avatarUrl"]
    anonymous = TestClient(client.app)
    public = anonymous.get(f"/api/v1/works/{work['id']}").json()
    profile = anonymous.get(f"/api/v1/authors/{public['author']}").json()
    assert profile == {"username": public["author"], "nickname": "创作者", "avatarUrl": avatar}
    assert anonymous.get(avatar).headers["content-type"] == "image/webp"
    assert public["authorProfile"] == profile
    assert anonymous.get(f"/api/v1/workflows/{workflow['id']}").json()["authorProfile"] == profile
    assert fields["image"]["id"] not in public["inputValues"]
    assert public["inputValues"][fields["seed"]["id"]] == "0"
    assert public["description"] == ""
    by_author = anonymous.get("/api/v1/works", params={"author": public["author"]}).json()
    assert work["id"] in {item["id"] for item in by_author["items"]}
    assert anonymous.get("/api/v1/works", params={"author": "nobody"}).json()["items"] == []
    shared = anonymous.get(f"/api/v1/works/{work['id']}/inputs").json()
    assert {field["id"] for field in shared["fields"]} == set(public["inputValues"])
    assert shared["assets"] == [] and fields["image"]["id"] not in str(shared)
    assert asset["id"] not in str(public) and "private-host-file" not in str(public)
    assert anonymous.get(asset["media"]["src"]).status_code == 401
    unshared = client.post(
        "/api/v1/works", json={**publish_body(second, outputs), "shareParameters": False}
    ).json()
    assert "parameters" not in unshared and not unshared["inputValues"]
    unshared_inputs = (
        anonymous.get(f"/api/v1/works/{unshared['id']}/inputs").raise_for_status().json()
    )
    assert unshared_inputs["fields"] == unshared_inputs["assets"] == []
    viewer = TestClient(client.app, headers={"Origin": "http://testserver"})
    session = viewer.post(
        "/api/v1/auth/register", json={"username": "replay-viewer", "password": "viewer-password"}
    ).json()
    viewer.headers["X-CSRF-Token"] = session["csrfToken"]
    machine = viewer.post("/api/v1/machines", json={"name": "viewer"}).json()
    viewer_worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    viewer_worker.put("/api/v1/worker/catalog", json=catalog)
    replay_form = viewer.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={
            "machine_id": machine["machine"]["id"],
            "version_id": workflow["versionId"],
            "work_id": work["id"],
        },
    ).json()
    restored = {f["id"]: f["default"] for f in replay_form["fields"]}
    assert restored[fields["seed"]["id"]] == "0"
    assert restored[fields["image"]["id"]] is None
    assert replay_form["sharedAssets"] == []
    assert client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={
            "machine_id": body["machineId"],
            "version_id": workflow["versionId"],
            "execution_id": second["id"],
        },
    ).json()["fields"][0]["default"] == {"assetId": asset["id"]}


def test_full_work_inputs_replay_with_work_scoped_assets(prepared, settings):
    from test_outputs import publish_body, run_group
    from test_worker import claim_body

    author, worker, workflow, _, fields, asset, body, catalog = prepared
    task = author.post("/api/v1/tasks", json=body).json()
    claim = claim_body()
    worker.post("/api/v1/worker/claim", json=claim)
    execution, outputs = run_group(author, worker, task["id"], claim["leaseSecret"])
    assert author.post(f"/api/v1/workflows/{workflow['id']}/publish", json={}).status_code == 200
    publication = {**publish_body(execution, outputs), "shareAssets": True}
    published = author.post("/api/v1/works", json=publication)
    assert published.status_code == 201, published.text
    work = published.json()
    assert author.post("/api/v1/works", json=publication).json() == work
    scalar_body = publish_body(execution, outputs)
    scalar_only = author.post("/api/v1/works", json=scalar_body).json()
    defaults = {"shareAssets": False, "coverAssetId": None, "executionCoverSha256": None}
    repeated = author.post("/api/v1/works", json=scalar_body | defaults)
    assert repeated.status_code == 200 and repeated.json()["id"] == scalar_only["id"]
    assert author.post("/api/v1/works", json=scalar_body | {"shareAssets": True}).status_code == 409
    assert author.post("/api/v1/works", json=scalar_body | {"shareAssets": None}).status_code == 422

    image_id = fields["image"]["id"]
    shared_id = work["inputValues"][image_id]["assetId"]
    assert shared_id != asset["id"]
    assert (
        work["inputValues"][fields["seed"]["id"]] == execution["inputValues"][fields["seed"]["id"]]
    )
    base = f"/api/v1/works/{work['id']}"
    guest = TestClient(author.app)
    language = {"Accept-Language": "en"}
    task_inputs = f"/api/v1/tasks/{task['id']}/inputs"
    assert guest.get(task_inputs).status_code == 401
    snapshot = author.get(task_inputs, headers=language).raise_for_status().json()
    details = guest.get(base + "/inputs", headers=language).raise_for_status().json()
    assert details["fields"] == [
        field for field in snapshot["fields"] if field["id"] in work["inputValues"]
    ]
    (shared,) = details["assets"]
    assert (shared["id"], shared["filename"]) == (shared_id, asset["filename"])
    original = shared["media"]["src"]
    thumbnail = shared["media"]["thumbnail"]["src"]
    assert guest.get(original).content == picture()
    assert guest.get(thumbnail).status_code == 200
    assert guest.get(base + f"/assets/{asset['id']}/file").status_code == 404
    assert (
        guest.get(f"/api/v1/works/{scalar_only['id']}/assets/{shared_id}/file").status_code == 404
    )

    viewer = TestClient(author.app, headers={"Origin": "http://testserver"})
    session = viewer.post(
        "/api/v1/auth/register", json={"username": "full-replay", "password": "viewer-password"}
    ).json()
    viewer.headers["X-CSRF-Token"] = session["csrfToken"]
    machine = viewer.post("/api/v1/machines", json={"name": "viewer"}).json()
    viewer_worker = sync_machine(viewer, machine, catalog)
    machine_id = machine["machine"]["id"]
    assert viewer.get(asset["media"]["src"]).status_code == 404
    assert viewer.get(f"/api/v1/assets/{shared_id}").status_code == 404
    form_path = f"/api/v1/workflows/{workflow['id']}/inputs"
    source = {"machine_id": machine_id, "version_id": workflow["versionId"], "work_id": work["id"]}
    replay = viewer.get(form_path, params=source).json()
    restored = {field["id"]: field["default"] for field in replay["fields"]}
    assert restored[image_id] == {"assetId": shared_id}
    assert replay["sharedAssets"] == [shared]
    submission = {
        **body,
        "machineId": machine_id,
        "inputSchemaHash": replay["schemaHash"],
        "idempotencyKey": str(uuid4()),
        "inputValues": restored,
    }
    assert viewer.post("/api/v1/tasks", json=submission).status_code == 404
    submission["sourceWorkId"] = work["id"]
    settings.asset_quota_bytes = asset["size"] - 1
    assert viewer.post("/api/v1/tasks", json=submission).status_code == 413
    settings.asset_quota_bytes = asset["size"]
    response = viewer.post("/api/v1/tasks", json=submission)
    assert response.status_code == 201, response.text
    queued = response.json()
    private_id = queued["inputValues"][image_id]["assetId"]
    assert private_id not in {asset["id"], shared_id}
    assert viewer.post("/api/v1/tasks", json=submission).json()["id"] == queued["id"]
    repeated = viewer.post("/api/v1/tasks", json={**submission, "idempotencyKey": str(uuid4())})
    assert repeated.status_code == 201
    assert repeated.json()["inputValues"][image_id]["assetId"] == private_id

    assert author.delete(base).status_code == 204
    assert guest.get(original).status_code == guest.get(thumbnail).status_code == 404
    assert viewer.get(form_path, params=source).status_code == 404
    claim = claim_body()
    job = viewer_worker.post("/api/v1/worker/claim", json=claim).json()
    assert job["task"]["sourceWorkId"] == work["id"] and job["assets"][0]["id"] == private_id
    supplied = viewer_worker.get(
        f"/api/v1/worker/tasks/{job['task']['id']}/assets/{private_id}",
        headers={"X-Task-Lease": claim["leaseSecret"]},
    )
    assert supplied.content == picture()


def test_text_primitives_feeding_a_prompt_are_shown_by_default(authenticated):
    client = authenticated
    machine = client.post("/api/v1/machines", json={"name": "prompt sources"}).json()
    sync_machine(
        client,
        machine,
        {
            "nodes": {
                "PrimitiveStringMultiline": {
                    "inputs": {"value": {"kind": "string", "multiline": True}}
                },
                "CLIPTextEncode": {"inputs": {"text": {"kind": "string", "multiline": True}}},
                "KSampler": {"inputs": {"steps": {"kind": "integer", "minimum": "1"}}},
                "SaveImage": {"outputNode": True},
            }
        },
    )
    graph = {
        "1": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "a lighthouse"}},
        "2": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "blurry"}},
        "3": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "lighthouse-output"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": ["1", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": ["2", 0]}},
        "6": {
            "class_type": "KSampler",
            "inputs": {"positive": ["4", 0], "negative": ["5", 0], "steps": 20},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 0], "filename_prefix": ["3", 0]},
        },
    }
    workflow = client.post("/api/v1/workflows", json={"name": "sourced", "graph": graph}).json()
    form = client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={"version_id": workflow["versionId"], "machine_id": machine["machine"]["id"]},
    ).json()
    fields = {field["nodeId"]: field for field in form["fields"] if field["inputName"] == "value"}
    assert (fields["1"]["label"], fields["1"]["primary"]) == ("提示词", True)
    assert (fields["2"]["label"], fields["2"]["primary"]) == ("负向提示词", False)
    assert (fields["3"]["label"], fields["3"]["primary"]) == ("value", False)
    # 没有中文名称的字段标记为未命名，表单默认不显示它。
    assert [fields[key]["named"] for key in ("1", "2", "3")] == [True, True, False]
