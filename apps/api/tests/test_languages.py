import json
from importlib.resources import files
from string import Formatter
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from helpers import sync_machine, task_body
from test_outputs import run_group
from test_worker import claim_body

from comfyshop_api.core.i18n import localize_task_error
from comfyshop_api.core.languages import LANGUAGES


def test_api_language_packs_have_matching_keys_and_placeholders():
    directory = files("comfyshop_api.core").joinpath("locales")
    source = json.loads(directory.joinpath("zh.json").read_text(encoding="utf-8"))
    formatter = Formatter()

    def placeholders(text: str) -> list[str]:
        return sorted(field for _, field, _, _ in formatter.parse(text) if field is not None)

    for language in LANGUAGES:
        translated = json.loads(directory.joinpath(f"{language}.json").read_text(encoding="utf-8"))
        assert translated.keys() == source.keys()
        for key, text in source.items():
            assert placeholders(translated[key]) == placeholders(text), (language, key)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Atlas Cloud 拒绝了生成请求（HTTP 403）",
            "Atlas Cloud rejected the generation request (HTTP 403)",
        ),
        (
            "读取 Atlas Cloud 生成结果失败（HTTP 404）",
            "Failed to retrieve the generation result from Atlas Cloud (HTTP 404)",
        ),
        (
            "Atlas Cloud 成品下载失败（HTTP 410）",
            "Failed to download the output from Atlas Cloud (HTTP 410)",
        ),
        ("reference_{a} 至少需要 2 份素材", "The minimum number of assets for reference_{a} is 2"),
        (
            "素材和生成数量合计最多 15",
            "The total number of input assets and requested outputs cannot exceed 15",
        ),
        ("其他诊断（HTTP 404）", "其他诊断（HTTP 404）"),
    ],
)
def test_official_worker_errors_keep_their_arguments(source, expected):
    assert localize_task_error(source, "en", official=True) == expected
    assert localize_task_error(source, "en", official=False) == source


def publish_work_result(client, worker, workflow, body):
    task = client.post("/api/v1/tasks", json=body).raise_for_status().json()
    assert task["status"] == "queued"
    claim = claim_body()
    job = worker.post("/api/v1/worker/claim", json=claim).raise_for_status().json()
    assert job["task"]["id"] == task["id"]
    execution, outputs = run_group(client, worker, task["id"], claim["leaseSecret"], members=2)
    worker.post(
        f"/api/v1/worker/tasks/{task['id']}/complete",
        headers={"X-Task-Lease": claim["leaseSecret"]},
    ).raise_for_status()
    client.post(f"/api/v1/workflows/{workflow['id']}/publish").raise_for_status()
    work = (
        client.post(
            "/api/v1/works",
            json={
                "id": str(uuid4()),
                "executionId": execution["id"],
                "title": workflow["name"],
                "artifactIds": [outputs[0]["id"]],
                "coverArtifactId": outputs[0]["id"],
                "shareParameters": True,
            },
        )
        .raise_for_status()
        .json()
    )
    return task, execution, work, outputs[1]


def test_languages_share_catalog_history_and_permissions(authenticated, graph):
    owner = authenticated
    machine = owner.post("/api/v1/machines", json={"name": "Render node"}).raise_for_status().json()
    worker = sync_machine(owner, machine)
    machine_id = machine["machine"]["id"]
    workflow = (
        owner.post("/api/v1/workflows", json={"name": "原文标题", "graph": graph})
        .raise_for_status()
        .json()
    )
    private = (
        owner.post("/api/v1/workflows", json={"name": "Private author draft", "graph": graph})
        .raise_for_status()
        .json()
    )
    body = task_body(owner, workflow, machine_id)
    task, execution, work, private_output = publish_work_result(owner, worker, workflow, body)
    workflow_url = f"/api/v1/workflows/{workflow['id']}"
    work_url = f"/api/v1/works/{work['id']}"
    owner.put(f"{workflow_url}/favorite").raise_for_status()
    visitor = TestClient(owner.app)

    for language, prompt in {
        "zh": "提示词",
        "zh-tw": "提示詞",
        "en": "Prompt",
        "ja": "プロンプト",
        "ko": "프롬프트",
    }.items():
        headers = {"Accept-Language": language}
        public = visitor.get("/api/v1/workflows", headers=headers).raise_for_status().json()
        assert [(item["id"], item["name"]) for item in public["items"]] == [
            (workflow["id"], "原文标题")
        ]
        assert visitor.get(f"/api/v1/workflows/{private['id']}", headers=headers).status_code == 404
        assert visitor.get(work_url, headers=headers).raise_for_status().json()["id"] == work["id"]
        assert visitor.get(work["media"]["src"], headers=headers).status_code == 200
        assert visitor.get(private_output["media"]["src"], headers=headers).status_code == 404
        assert owner.get(private_output["media"]["src"], headers=headers).status_code == 200
        assert owner.get("/api/v1/workspace", headers=headers).json()["favoriteIds"] == [
            workflow["id"]
        ]
        for path, item in (("tasks", task), ("executions", execution), ("works?scope=mine", work)):
            listed = (
                owner.get(f"/api/v1/{path}", headers=headers).raise_for_status().json()["items"]
            )
            assert [record["id"] for record in listed] == [item["id"]]
        form = (
            owner.get(f"{workflow_url}/inputs", params={"machine_id": machine_id}, headers=headers)
            .raise_for_status()
            .json()
        )
        assert prompt in {field["label"] for field in form["fields"]}
        assert form["schemaHash"] == body["inputSchemaHash"]
        replay = owner.get(f"{work_url}/replay", headers=headers).raise_for_status().json()
        assert replay["workflow"]["versionId"] == workflow["versionId"]
        assert owner.post("/api/v1/tasks", json=body, headers=headers).json()["id"] == task["id"]
