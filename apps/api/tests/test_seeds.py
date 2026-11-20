from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from comfyshop_api.models import Execution
from comfyshop_api.schemas import WorkflowInput
from comfyshop_api.services.inputs import plan_execution_seeds
from helpers import CATALOG, sync_machine, task_body
from test_outputs import run_group
from test_worker import claim_body

FIRST_NOISE = 2**64 - 4


def read_form(client, workflow, body, **params):
    response = client.get(
        f"/api/v1/workflows/{workflow['id']}/inputs",
        params={"machine_id": body["machineId"], "version_id": body["versionId"], **params},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def stepped(authenticated, graph):
    client = authenticated
    graph["2"]["inputs"]["seed"] = 8
    graph["3"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": FIRST_NOISE}}
    machine = client.post("/api/v1/machines", json={"name": "stepped"}).json()
    catalog = deepcopy(CATALOG)
    catalog["nodes"]["KSampler"]["inputs"]["seed"].update(minimum="2", maximum="12")
    catalog["nodes"]["RandomNoise"] = {
        "inputs": {
            "noise_seed": {
                "kind": "integer",
                "minimum": "0",
                "maximum": str(2**64 - 1),
            }
        }
    }
    worker = sync_machine(client, machine, catalog)
    workflow = client.post(
        "/api/v1/workflows", json={"name": "stepped seeds", "graph": graph}
    ).json()
    body = task_body(client, workflow, machine["machine"]["id"])
    form = read_form(client, workflow, body)
    seeds = {field["inputName"]: field["id"] for field in form["fields"]}
    return client, worker, workflow, body, seeds, catalog


def create_batch(client, body, count):
    response = client.post("/api/v1/tasks", json={**body, "executionCount": count})
    assert response.status_code == 201, response.text
    return response.json()


def claim_job(worker, claim):
    response = worker.post("/api/v1/worker/claim", json=claim)
    assert response.status_code == 200, response.text
    return response.json()


def record_seed(client, task_id, field_id, value):
    """改写第二次执行已记录的种子，模拟节点范围或步长变化前留下的历史值。"""
    with Session(client.app.state.engine) as db:
        execution = db.scalar(
            select(Execution).where(Execution.task_id == task_id, Execution.index == 1)
        )
        execution.input_values = {**execution.input_values, field_id: value}
        db.commit()


def test_batch_freezes_incrementing_seeds_that_wrap_at_the_field_limit(stepped):
    client, worker, _, body, seeds, catalog = stepped
    invalid = client.post("/api/v1/tasks", json={**body, "inputValues": {seeds["seed"]: 13}})
    assert invalid.status_code == 422
    assert client.get("/api/v1/tasks").json()["items"] == []
    task = create_batch(client, body, 6)

    small = [8, 9, 10, 11, 12, 2]
    large = [str(FIRST_NOISE + offset) for offset in range(4)] + ["0", "1"]
    with Session(client.app.state.engine) as db:
        runs = db.scalars(
            select(Execution).where(Execution.task_id == task["id"]).order_by(Execution.index)
        ).all()
        assert [run.input_values[seeds["seed"]] for run in runs] == small
        assert [run.input_values[seeds["noise_seed"]] for run in runs] == large

    # 提交后工作机的字段范围变化，不影响已冻结的种子。
    catalog["nodes"]["KSampler"]["inputs"]["seed"]["maximum"] = "9"
    assert worker.put("/api/v1/worker/catalog", json=catalog).status_code == 200
    claim = claim_body()
    job = claim_job(worker, claim)
    assert job["task"]["id"] == task["id"]
    assert job["executionSeeds"] == [
        [
            {"nodeId": "2", "inputName": "seed", "value": str(seed)},
            {"nodeId": "3", "inputName": "noise_seed", "value": noise},
        ]
        for seed, noise in zip(small, large, strict=True)
    ]
    assert claim_job(worker, claim)["executionSeeds"] == job["executionSeeds"]


def test_seed_without_an_upper_bound_keeps_incrementing():
    field = WorkflowInput(
        id="seed", node_id="sample", input_name="seed", node_title="Sampler", kind="integer"
    )
    assert plan_execution_seeds([field], {"seed": 5}, 3) == [{"seed": 5}, {"seed": 6}, {"seed": 7}]


def test_historical_execution_replay_freezes_the_selected_groups_actual_seeds(stepped):
    client, worker, workflow, body, seeds, _ = stepped
    task = create_batch(client, body, 2)
    claim = claim_body()
    assert claim_job(worker, claim)["task"]["id"] == task["id"]
    run_group(client, worker, task["id"], claim["leaseSecret"], members=1)
    source, _ = run_group(client, worker, task["id"], claim["leaseSecret"], index=1, members=1)
    replay = client.get(f"/api/v1/executions/{source['id']}/replay").json()
    assert replay["sourceExecutionId"] == source["id"]
    form = read_form(client, workflow, body, execution_id=replay["sourceExecutionId"])
    restored = {field["id"]: field["default"] for field in form["fields"]}
    assert restored == source["inputValues"]
    assert restored[seeds["seed"]] == 9
    assert restored[seeds["noise_seed"]] == str(FIRST_NOISE + 1)

    repeated = create_batch(
        client,
        {
            **body,
            "idempotencyKey": str(uuid4()),
            "inputSchemaHash": form["schemaHash"],
            "inputValues": restored,
            "sourceExecutionId": source["id"],
        },
        1,
    )
    job = claim_job(worker, claim_body())
    assert job["task"]["id"] == repeated["id"]
    assert job["task"]["sourceExecutionId"] == source["id"]
    assert job["executionSeeds"][0] == [
        {"nodeId": "2", "inputName": "seed", "value": "9"},
        {"nodeId": "3", "inputName": "noise_seed", "value": str(FIRST_NOISE + 1)},
    ]


def test_incompatible_historical_seed_is_kept_and_replay_requires_a_valid_value(stepped):
    client, worker, workflow, body, seeds, _ = stepped
    task = create_batch(client, body, 2)
    claim = claim_body()
    assert claim_job(worker, claim)["task"]["id"] == task["id"]
    run_group(client, worker, task["id"], claim["leaseSecret"], members=1)
    source, _ = run_group(client, worker, task["id"], claim["leaseSecret"], index=1, members=1)
    record_seed(client, task["id"], seeds["seed"], 13)

    form = read_form(client, workflow, body, execution_id=source["id"])
    restored = {field["id"]: field["default"] for field in form["fields"]}
    assert restored[seeds["seed"]] == 13
    retry = {
        **body,
        "idempotencyKey": str(uuid4()),
        "inputSchemaHash": form["schemaHash"],
        "sourceExecutionId": source["id"],
        "inputValues": restored,
    }
    rejected = client.post("/api/v1/tasks", json=retry)
    assert rejected.status_code == 422
    corrected = create_batch(client, {**retry, "inputValues": {**restored, seeds["seed"]: 11}}, 1)
    assert corrected["inputValues"][seeds["seed"]] == 11
    historical = client.get(f"/api/v1/executions/{source['id']}").json()
    assert historical["inputValues"][seeds["seed"]] == 13
