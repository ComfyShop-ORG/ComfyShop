from uuid import uuid4

from fastapi.testclient import TestClient

from helpers import execution_id, sync_machine
from test_covers import add_result
from test_inputs import prepared as prepared
from test_persistence import create_workflow


def test_parameter_layout_applies_to_its_published_version(authenticated, settings, graph):
    client = authenticated
    workflow = create_workflow(client, graph)
    base = f"/api/v1/workflows/{workflow['id']}"
    version = workflow["versionId"]
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    add_result(client, settings, workflow, owner, 1)
    assert client.post(f"{base}/publish", json={}).status_code == 200

    machine = client.get("/api/v1/machines").json()["defaultMachineId"]
    params = {"machine_id": machine, "version_id": version}
    original = client.get(f"{base}/inputs", params=params).json()
    assert original["parameterLayout"] == []
    fields = {field["inputName"]: field for field in original["fields"]}
    route = f"{base}/versions/{version}/parameter-layout"
    layout = [
        {
            "fieldId": fields["steps"]["id"],
            "section": "default",
            "displayName": "细节步数",
            "control": "slider",
        },
        {
            "fieldId": fields["text"]["id"],
            "section": "default",
            "help": " 描述想要的画面 ",
            "control": "text",
        },
        {"fieldId": fields["seed"]["id"], "section": "hidden"},
    ]
    saved = client.put(route, json={"machineId": machine, "parameterLayout": layout})
    assert saved.status_code == 200, saved.text
    assert saved.json()[1]["help"] == "描述想要的画面"
    assert saved.json()[0]["displayName"] == "细节步数"
    assert [entry["control"] for entry in saved.json()] == ["slider", "text", None]
    after = client.get(f"{base}/inputs", params=params).json()
    assert after == {**original, "parameterLayout": saved.json()}

    with TestClient(client.app, headers={"Origin": "http://testserver"}) as reader:
        registered = reader.post(
            "/api/v1/auth/register", json={"username": "viewer", "password": "correct-battery"}
        )
        reader.headers["X-CSRF-Token"] = registered.json()["csrfToken"]
        reader_machine = reader.post("/api/v1/machines", json={"name": "reader"}).json()
        sync_machine(reader, reader_machine)
        reader_params = {**params, "machine_id": reader_machine["machine"]["id"]}
        assert reader.get(f"{base}/inputs", params=reader_params).json()["parameterLayout"] == (
            saved.json()
        )
        denied = reader.put(
            route, json={"machineId": reader_params["machine_id"], "parameterLayout": []}
        )
        assert denied.status_code == 404

    updated = client.patch(base, json={"graph": graph}).json()
    assert updated["versionId"] != version
    assert (
        client.get(f"{base}/inputs", params={"machine_id": machine}).json()["parameterLayout"] == []
    )
    assert client.get(f"{base}/inputs", params=params).json()["parameterLayout"] == saved.json()


def test_version_defaults_apply_to_new_tasks_and_preserve_replay_inputs(prepared):
    client, _, workflow, original, fields, _, body, _ = prepared
    base = f"/api/v1/workflows/{workflow['id']}"
    route = f"{base}/versions/{workflow['versionId']}/parameter-layout"
    steps = fields["steps"]["id"]
    cfg, text, seed = (fields[name]["id"] for name in ("cfg", "text", "seed"))
    hidden = {"fieldId": steps, "section": "hidden", "defaultValue": 40}
    original_graph = client.get(f"{base}/graph").json()["graph"]
    response = client.post(
        "/api/v1/tasks", json={**body, "inputValues": {**body["inputValues"], steps: 36}}
    )
    assert response.status_code == 201, response.text
    prior_execution = execution_id(client, response.json()["id"])
    for invalid in (
        [{"fieldId": fields["image"]["id"], "section": "hidden"}],
        [{"fieldId": fields["image"]["id"], "section": "default", "defaultValue": "image.png"}],
        [{"fieldId": fields["seed"]["id"], "section": "default", "control": "slider"}],
        [{"fieldId": fields["image"]["id"], "section": "default", "control": "textarea"}],
        [{"fieldId": cfg, "section": "advanced", "defaultValue": 6.6}],
        [hidden, hidden],
        [{"fieldId": "0" * 64, "section": "default"}],
    ):
        assert (
            client.put(
                route, json={"machineId": body["machineId"], "parameterLayout": invalid}
            ).status_code
            == 422
        )
    updates = [
        hidden,
        {"fieldId": cfg, "section": "advanced", "defaultValue": 6.500000000000001},
        {"fieldId": text, "section": "default", "defaultValue": ""},
        {"fieldId": seed, "section": "advanced", "defaultValue": str(2**64 - 2)},
    ]
    saved = client.put(route, json={"machineId": body["machineId"], "parameterLayout": updates})
    assert saved.status_code == 200, saved.text
    assert saved.json()[1]["defaultValue"] == 6.5
    params = {"machine_id": body["machineId"]}
    current = client.get(f"{base}/inputs", params=params).json()
    assert current["schemaHash"] != original["schemaHash"]
    assert current["originalDefaults"][steps] == fields["steps"]["default"]
    assert fields["image"]["id"] not in current["originalDefaults"]
    assert client.get(f"{base}/graph").json()["graph"] == original_graph

    submission = {**body, "idempotencyKey": str(uuid4())}
    assert client.post("/api/v1/tasks", json=submission).status_code == 409
    queued = client.post(
        "/api/v1/tasks", json={**submission, "inputSchemaHash": current["schemaHash"]}
    )
    assert queued.status_code == 201, queued.text
    assert queued.json()["inputValues"] == {
        **body["inputValues"],
        steps: 40,
        cfg: 6.5,
        text: "",
        seed: str(2**64 - 2),
    }
    replay = client.get(
        f"{base}/inputs",
        params={**params, "execution_id": prior_execution},
    ).json()
    assert replay["schemaHash"] == current["schemaHash"]
    assert replay["parameterLayout"] == saved.json()
    assert next(field["default"] for field in replay["fields"] if field["id"] == steps) == 36
    assert replay["originalDefaults"] == current["originalDefaults"]

    restored = client.put(
        route,
        json={
            "machineId": body["machineId"],
            "parameterLayout": [{**hidden, "defaultValue": None}, *saved.json()[1:]],
        },
    )
    assert restored.status_code == 200, restored.text
    reset = client.get(f"{base}/inputs", params=params).json()
    assert (
        next(field["default"] for field in reset["fields"] if field["id"] == steps)
        == (fields["steps"]["default"])
    )


def test_default_types_and_work_machine_compatibility(authenticated):
    client = authenticated
    catalog = {
        "nodes": {
            "Parameters": {
                "inputs": {
                    "enabled": {"kind": "boolean"},
                    "quality": {"kind": "choice", "choices": ["soft", "sharp"]},
                }
            }
        }
    }
    machine = client.post("/api/v1/machines", json={"name": "完整目录"}).json()
    sync_machine(client, machine, catalog)
    machine_id = machine["machine"]["id"]
    workflow = create_workflow(
        client,
        {"1": {"class_type": "Parameters", "inputs": {"enabled": True, "quality": "soft"}}},
    )
    base = f"/api/v1/workflows/{workflow['id']}"
    route = f"{base}/versions/{workflow['versionId']}/parameter-layout"
    original = client.get(f"{base}/inputs", params={"machine_id": machine_id}).json()
    fields = {field["inputName"]: field["id"] for field in original["fields"]}
    enabled = {"fieldId": fields["enabled"], "section": "advanced", "defaultValue": False}
    quality = {"fieldId": fields["quality"], "section": "advanced", "defaultValue": "sharp"}
    saved = client.put(route, json={"machineId": machine_id, "parameterLayout": [enabled, quality]})
    assert saved.status_code == 200, saved.text
    assert saved.json()[0]["defaultValue"] is False
    for invalid in ({**enabled, "defaultValue": 0}, {**quality, "defaultValue": "unknown"}):
        assert (
            client.put(
                route, json={"machineId": machine_id, "parameterLayout": [invalid]}
            ).status_code
            == 422
        )

    catalog["nodes"]["Parameters"]["inputs"]["quality"]["choices"] = ["soft"]
    alternate = client.post("/api/v1/machines", json={"name": "精简目录"}).json()
    sync_machine(client, alternate, catalog)
    alternate_id = alternate["machine"]["id"]
    other = client.get(f"{base}/inputs", params={"machine_id": alternate_id}).json()
    assert {field["inputName"]: field["default"] for field in other["fields"]} == {
        "enabled": False,
        "quality": "soft",
    }
    plain = [{"fieldId": entry["fieldId"], "section": "default"} for entry in saved.json()]
    renamed = client.put(route, json={"machineId": alternate_id, "parameterLayout": plain})
    assert renamed.status_code == 200, renamed.text
    assert [entry["defaultValue"] for entry in renamed.json()] == [False, "sharp"]


def test_slider_ranges_and_layout_follow_work_machine_definitions(prepared):
    client, worker, workflow, _, fields, _, body, catalog = prepared
    base = f"/api/v1/workflows/{workflow['id']}"
    route = f"{base}/versions/{workflow['versionId']}/parameter-layout"
    cfg = fields["cfg"]["id"]
    number = catalog["nodes"]["KSampler"]["inputs"]["cfg"]
    number.update(minimum="0.05", maximum="10.68", step="0.1")
    assert worker.put("/api/v1/worker/catalog", json=catalog).status_code == 200
    original = client.get(f"{base}/inputs", params={"machine_id": body["machineId"]}).json()
    assert original["parameterControls"][cfg] == {
        "options": ["slider"],
        "slider": {"minimum": 5, "maximum": 1065, "step": 10, "scale": 100},
    }
    assert fields["seed"]["id"] not in original["parameterControls"]
    slider = {"fieldId": cfg, "section": "default", "control": "slider"}
    saved = client.put(route, json={"machineId": body["machineId"], "parameterLayout": [slider]})
    assert saved.status_code == 200, saved.text
    queued = client.post(
        "/api/v1/tasks",
        json={
            **body,
            "inputSchemaHash": original["schemaHash"],
            "inputValues": {**body["inputValues"], cfg: 10.65},
        },
    )
    assert queued.status_code == 201, queued.text
    assert queued.json()["inputValues"][cfg] == 10.65

    number.pop("step")
    other = client.post("/api/v1/machines", json={"name": "无步长"}).json()
    sync_machine(client, other, catalog)
    other_id = other["machine"]["id"]
    other_form = client.get(f"{base}/inputs", params={"machine_id": other_id}).json()
    assert cfg not in other_form["parameterControls"]
    assert other_form["parameterLayout"] == saved.json()
    changed = client.put(
        route, json={"machineId": other_id, "parameterLayout": [{**slider, "help": "引导强度"}]}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()[0]["control"] == "slider"
    reset = client.put(
        route, json={"machineId": other_id, "parameterLayout": [{**slider, "control": None}]}
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()[0]["control"] is None
