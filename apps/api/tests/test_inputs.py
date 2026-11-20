from io import BytesIO
from copy import deepcopy
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from helpers import execution_id, sync_machine


def picture(color="black"):
    stream = BytesIO()
    Image.new("RGB", (32, 48), color).save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def prepared(authenticated):
    client = authenticated
    machine = client.post("/api/v1/machines", json={"name": "reference"}).json()
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
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
    assert worker.put("/api/v1/worker/catalog", json=catalog).status_code == 200
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "private-host-file.png"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a bottle"}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"positive": ["2", 0], "seed": 2**64 - 1, "steps": 20, "cfg": 4.5},
        },
        "4": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
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
        json={"protocolVersion": 3, "claimId": str(uuid4()), "leaseSecret": lease},
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


def test_parameters_and_schema_are_validated_before_queueing(prepared):
    client, worker, _, _, fields, _, body, catalog = prepared
    for name, value in [
        ("steps", 151),
        ("steps", 1.2),
        ("cfg", 2.2),
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
    for invalid in (1.055, 0.009, 8.010000000000002):
        rejected = client.post(
            "/api/v1/tasks",
            json={**body, "idempotencyKey": str(uuid4()), "inputValues": {scale: invalid}},
        )
        assert rejected.status_code == 422, invalid

    claimed = worker.post(
        "/api/v1/worker/claim",
        json={"protocolVersion": 3, "claimId": str(uuid4()), "leaseSecret": uuid4().hex},
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["graph"]["1"]["inputs"]["scale_by"] == 1.05
    assert claimed.json()["graph"]["2"]["inputs"]["megapixels"] == 2.4


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
    from test_outputs import run_group, publish_body
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
    anonymous = TestClient(client.app)
    public = anonymous.get(f"/api/v1/works/{work['id']}").json()
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
    assert client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={
            "machine_id": body["machineId"],
            "version_id": workflow["versionId"],
            "execution_id": second["id"],
        },
    ).json()["fields"][0]["default"] == {"assetId": asset["id"]}


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
        "3": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "unused note"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": ["1", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": ["2", 0]}},
        "6": {
            "class_type": "KSampler",
            "inputs": {"positive": ["4", 0], "negative": ["5", 0], "steps": 20},
        },
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}},
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
