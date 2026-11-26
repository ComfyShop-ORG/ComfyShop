import asyncio
import json
import os
import runpy
import sys
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from comfyshop_worker_protocol.platform import Platform
from helpers import CATALOG, report_inventory, serve_test_app
from pydantic import SecretStr
from test_official_workflows import AUTH, OWNER, SEEDREAM, TOKEN, register, upload_body
from test_outputs import run_group
from test_worker import claim_body, image_bytes

from comfyshop_official_worker.atlas_cloud import ATLAS_ROOT, Atlas
from comfyshop_official_worker.runner import Runner

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def skill_server(settings, tmp_path, monkeypatch):
    static = tmp_path / "web"
    builder = runpy.run_path(str(ROOT / "tooling/build-skill.py"))
    builder["build_skill"](static / "downloads")
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    config = settings.model_copy(
        update={
            "static_dir": static,
            "official_owner": OWNER,
            "worker_service_tokens": {"official": SecretStr(TOKEN)},
        }
    )
    with serve_test_app(config) as (address, web):
        yield address, home, web


def installed_skill(web, address, home, tmp_path, client_name):
    script = web.get("/downloads/install-comfyshop-skill.py")
    assert script.status_code == 200
    installer = tmp_path / "install.py"
    installer.write_bytes(script.content)
    bootstrap = runpy.run_path(str(installer))
    install = bootstrap["parser"]().parse_args(["--server", address, "install", client_name])
    assert bootstrap["run"](install) == (None, 0)
    client_folder = ".agents" if client_name == "codex" else ".claude"
    skill = home / client_folder / "skills/comfyshop"
    for name in ("SKILL.md", "references/generation.md", "references/operations.md"):
        assert (skill / name).read_bytes() == (
            ROOT / "integrations/skills/comfyshop" / name
        ).read_bytes()
    assert (skill / "scripts/comfyshop.py").read_bytes() == script.content
    assert json.loads((skill / "platform.json").read_text()) == {"server": address}
    return runpy.run_path(str(skill / "scripts/comfyshop.py"))


def test_skill_covers_user_api_contract():
    skill = runpy.run_path(str(ROOT / "integrations/skills/comfyshop/scripts/comfyshop.py"))
    openapi = json.loads((ROOT / "packages/api-client/openapi.json").read_text())
    paths = openapi["paths"]
    assert (
        list(skill["WORKFLOW_CATEGORIES"])
        == openapi["components"]["schemas"]["WorkflowCategory"]["enum"]
    )
    dedicated = {
        ("GET", "/auth/session"),
        ("POST", "/auth/login"),
        ("POST", "/auth/logout"),
        ("POST", "/auth/register"),
        ("GET", "/workflows"),
        ("GET", "/workflows/{workflow_id}/inputs"),
        ("POST", "/tasks"),
        ("GET", "/tasks/{task_id}/progress"),
        ("GET", "/machines"),
        ("POST", "/machines"),
        ("POST", "/machines/{machine_id}/rotate"),
        ("GET", "/artifacts/{artifact_id}/file"),
        ("PUT", "/assets/{asset_id}"),
    }
    covered = set()
    for operation in skill["OPERATIONS"].values():
        assert (operation.method, operation.path) not in covered | dedicated
        endpoint = paths["/api/v1" + operation.path][operation.method.lower()]
        assert set(operation.filters) == {
            item["name"] for item in endpoint.get("parameters", ()) if item["in"] == "query"
        }
        assert operation.payload == endpoint.get("requestBody", {}).get("required", False)
        if operation.payload:
            content_type = "application/octet-stream" if operation.binary else "application/json"
            assert content_type in endpoint["requestBody"]["content"]
        covered.add((operation.method, operation.path))
    relevant = {
        (verb.upper(), path.removeprefix("/api/v1"))
        for path, methods in paths.items()
        if path.startswith("/api/v1/") and not path.startswith("/api/v1/worker/")
        for verb in methods
    }
    browser_only = {("GET", "/web-push"), ("PUT", "/web-push"), ("DELETE", "/web-push")}
    assert not browser_only & (covered | dedicated)
    assert covered | dedicated | browser_only == relevant


def test_skill_download_installs_into_both_client_directories(skill_server, tmp_path):
    address, home, web = skill_server
    for client_name in ("codex", "claude-code"):
        skill = installed_skill(web, address, home, tmp_path, client_name)
        account = skill["parser"]().parse_args(["account"])
        assert skill["run"](account) == ({"server": address, "user": None}, 0)


@pytest.mark.parametrize("client_name", ["codex", "claude-code"])
def test_installed_skill_generates_and_replays_official_tasks(skill_server, tmp_path, client_name):
    address, home, web = skill_server
    skill = installed_skill(web, address, home, tmp_path, client_name)
    parser = skill["parser"]()

    def run(*args):
        value, status = skill["run"](parser.parse_args(["--language", "en", *args]))
        assert status == 0
        return value

    register(web, OWNER)
    web.post(
        "/api/v1/workflows",
        params={"initialize": True},
        headers=AUTH,
        json=upload_body(SEEDREAM),
    ).raise_for_status()
    client = skill["Client"](address, "en")
    client.login("skill-user", "test-password-long", register=True)
    assert run("machines")["items"] == []
    (workflow,) = run("workflows", "--search", "Seedream")["items"]
    assert workflow["format"] == "service"
    workflow_id, version_id = workflow["id"], workflow["versionId"]
    for args in (["form", workflow_id], ["form", workflow_id, "personal-machine", "--service"]):
        with pytest.raises(SystemExit) as usage:
            parser.parse_args(args)
        assert usage.value.code == 2
    args = ("form", workflow_id, "--service", "--version", version_id)
    form = run(*args)
    assert "machineId" not in form and form == run(
        "call", "workflow.service-inputs", workflow_id, "--query", f"version_id={version_id}"
    )
    image = tmp_path / "reference.png"
    image.write_bytes(image_bytes())
    prompt = "Draw a lighthouse at dusk"
    inputs = {"prompt": prompt, "reference_1": {"assetId": run("upload", str(image))["id"]}}
    plan = tmp_path / "official-task.json"
    submission = {
        "workflowId": workflow_id,
        "versionId": version_id,
        "inputValues": inputs,
        "inputSchemaHash": form["schemaHash"],
        "idempotencyKey": str(uuid4()),
    }
    plan.write_text(json.dumps(submission))
    (task,) = run("submit", str(plan))["tasks"]
    assert task["worker"]["kind"] == "official" and task["machineId"] is None
    assert run("progress", task["id"])["status"] == "queued"

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            return httpx.Response(200, json={"url": "https://cdn.example/reference.png"})
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"id": "test-prediction"}})
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.png"]}},
        )

    async def generate():
        async with (
            Platform(address, TOKEN) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=image.read_bytes(), headers={"Content-Type": "image/png"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(generate())
    assert run("progress", task["id"])["status"] == "succeeded"
    (execution,) = run("results", task["id"])["executions"]
    artifact = execution["artifacts"][0]["id"]
    work = client.request(
        "POST",
        "/works",
        {
            "id": str(uuid4()),
            "executionId": execution["id"],
            "title": "Lighthouse",
            "artifactIds": [artifact],
            "coverArtifactId": artifact,
            "shareAssets": True,
        },
        csrf=client.csrf(),
    )
    for source, field, record, reference in (
        ("--from-execution", "sourceExecutionId", execution, inputs["reference_1"]),
        ("--from-work", "sourceWorkId", work, work["inputValues"]["reference_1"]),
    ):
        replay = run(*args, source, record["id"])
        defaults = {field["id"]: field["default"] for field in replay["fields"]}
        assert defaults["prompt"] == prompt and defaults["reference_1"] == reference
        assert defaults["reference_2"] is None
        plan.write_text(
            json.dumps(
                {
                    **submission,
                    field: record["id"],
                    "inputValues": {"prompt": prompt, "reference_1": reference},
                    "inputSchemaHash": replay["schemaHash"],
                    "idempotencyKey": str(uuid4()),
                }
            )
        )
        (rerun,) = run("submit", str(plan))["tasks"]
        assert (
            rerun[field] == record["id"]
            and rerun["worker"]["kind"] == "official"
            and rerun["status"] == "queued"
        )


def test_installed_skill_updates_profile_and_downloads_avatar(skill_server, tmp_path):
    address, home, web = skill_server
    skill = installed_skill(web, address, home, tmp_path, "codex")

    def run(*args):
        result, status = skill["run"](skill["parser"]().parse_args(args))
        assert status == 0
        return result

    credentials = {"username": "摄影账号", "password": "test-only-password"}
    skill["Client"](address).login(**credentials, register=True)
    nickname = tmp_path / "profile.json"
    nickname.write_text(json.dumps({"nickname": "摄影师"}), encoding="utf-8")
    assert run("call", "account.nickname", "--body", str(nickname))["nickname"] == "摄影师"
    image = tmp_path / "avatar.png"
    image.write_bytes(image_bytes())
    saved = run("call", "account.avatar-upload", "--body", str(image))
    profile = run("call", "author.get", credentials["username"])
    assert profile["avatarUrl"] == saved["avatarUrl"]
    _, user_id, _, version = profile["avatarUrl"].rsplit("/", 3)
    download = tmp_path / "avatar.webp"
    assert run("call", "author.avatar", user_id, version, "--out", str(download)) == {
        "path": str(download.resolve())
    }
    assert download.read_bytes().startswith(b"RIFF")
    assert run("call", "account.avatar-remove")["avatarUrl"] is None


def test_installed_skill_submits_real_tasks_and_reads_private_results(
    skill_server, tmp_path, graph
):
    address, home, web = skill_server
    skill = installed_skill(web, address, home, tmp_path, "codex")

    def run(*args):
        return skill["run"](skill["parser"]().parse_args(args))

    credentials = {"username": "artist", "password": "test-only-password"}
    registered = web.post("/api/v1/auth/register", json=credentials)
    assert registered.status_code == 201
    web.headers["X-CSRF-Token"] = registered.json()["csrfToken"]
    machine = web.post("/api/v1/machines", json={"name": "工作机"}).json()
    machine_id = machine["machine"]["id"]
    workflow = web.post("/api/v1/workflows", json={"name": "原片", "graph": graph}).json()
    workflow_id = workflow["id"]
    version_id = workflow["versionId"]

    assert not run("workflows")[0]["items"]
    client = skill["Client"](address)
    assert client.login(**credentials)["username"] == credentials["username"]
    if os.name == "posix":
        assert client.session_file.stat().st_mode & 0o777 == 0o600
    assert run("account")[0] == {"server": address, "user": registered.json()["user"]}
    assert (
        run("workflows", "--scope", "mine", "--search", "原片")[0]["items"][0]["id"] == workflow_id
    )
    assert run("machines")[0]["items"][0]["id"] == machine_id

    with httpx.Client(
        base_url=address, headers={"Authorization": "Bearer " + machine["apiKey"]}, trust_env=False
    ) as worker:
        report_inventory(worker)
        form, status = run("form", workflow_id, machine_id, "--version", version_id)
        assert status == 0 and not form["issues"]
        text_id = next(field["id"] for field in form["fields"] if field["inputName"] == "text")

        image = tmp_path / "参考图.png"
        image.write_bytes(image_bytes())
        upload_id = str(uuid4())
        assert run("upload", str(image), "--asset-id", upload_id)[0]["id"] == upload_id
        assert run("upload", str(image), "--asset-id", upload_id)[0]["id"] == upload_id
        assert run("call", "asset.list")[0]["items"] == []
        pinned, status = run("upload", str(image), "--asset-id", upload_id, "--save-to-library")
        assert status == 0 and pinned["savedAt"] is not None
        assert run(
            "call",
            "asset.list",
            "--query",
            "content_types=image/png",
            "--query",
            "content_types=audio/flac",
        )[0]["items"] == [pinned]

        tasks = [
            {
                "workflowId": workflow_id,
                "versionId": version_id,
                "machineId": machine_id,
                "executionCount": 1,
                "inputValues": {text_id: prompt},
                "inputSchemaHash": form["schemaHash"],
                "idempotencyKey": str(uuid4()),
            }
            for prompt in ("窗边日光", "暖色夜景", "阴天街景")
        ]
        pending = tmp_path / "tasks.json"
        invalid = {**tasks[1], "inputSchemaHash": "0" * 64}
        pending.write_text(json.dumps([tasks[0], invalid, tasks[2]]))
        partial, status = run("submit", str(pending))
        task_id = partial["tasks"][0]["id"]
        assert status == 1
        assert partial["stoppedAt"]["index"] == 1
        assert partial["stoppedAt"]["httpStatus"] == 409
        assert partial["remaining"] == 1
        assert run("progress", task_id)[0]["status"] == "queued"
        assert run("results", task_id)[0]["executions"] == []

        pending.write_text(json.dumps(tasks))
        accepted, status = run("submit", str(pending))
        assert status == 0 and accepted["tasks"][0]["id"] == task_id
        assert len(web.get("/api/v1/tasks").json()["items"]) == len(tasks)
        assert run("submit", str(pending)) == (accepted, 0)

        claim = claim_body()
        claimed = worker.post("/api/v1/worker/claim", json=claim).json()
        assert claimed["task"]["id"] == task_id
        _, artifacts = run_group(web, worker, task_id, claim["leaseSecret"], members=1)
        assert run("progress", task_id)[0]["status"] == "succeeded"
        result = run("results", task_id)[0]["executions"][0]["artifacts"][0]
        assert result["id"] == artifacts[0]["id"]
        assert httpx.get(result["url"], trust_env=False).status_code == 404
        download = tmp_path / "生成图.png"
        assert run("download", result["id"], str(download))[0]["path"] == str(download.resolve())
        assert download.read_bytes() == image_bytes()
        assert run("call", "artifact.inpaint-targets", result["id"]) == ([], 0)
        assert not run("workflows", "--scope", "mine", "--inpaint-artifact", result["id"])[0][
            "items"
        ]
        assert run("call", "artifact.use-as-input", result["id"])[0]["id"] == upload_id
        team_id = web.post("/api/v1/teams", json={"name": "创作组"}).raise_for_status().json()["id"]
        with pytest.raises(skill["ClientError"]) as wrong_space:
            run("form", workflow_id, machine_id, "--workspace-team", team_id)
        assert wrong_space.value.status == 404
        pending.write_text(json.dumps({**tasks[0], "idempotencyKey": str(uuid4())}))
        rejected, status = run("submit", str(pending), "--workspace-team", team_id)
        assert status == 1 and rejected["stoppedAt"]["httpStatus"] == 404
        assert run("call", "artifact.save-to-library", result["id"]) == (pinned, 0)
        assert run("call", "asset.remove-from-library", upload_id) == ({}, 0)
        assert run("call", "asset.list")[0]["items"] == []

    run("logout")
    assert not client.session_file.exists()
    assert client.session()["user"] is None
    assert web.get("/api/v1/auth/session").json()["user"] == registered.json()["user"]
    with pytest.raises(skill["ClientError"], match="请先登录"):
        run("progress", task_id)


def test_installed_skill_manages_workflows_tasks_and_works(
    skill_server, tmp_path, graph, monkeypatch, capsys
):
    address, home, web = skill_server
    skill = installed_skill(web, address, home, tmp_path, "codex")

    def run(*args):
        result, status = skill["run"](skill["parser"]().parse_args(args))
        assert status == 0
        return result

    def call_with_body(operation, *ids, body, language="zh"):
        payload = tmp_path / "payload.json"
        payload.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return run("--language", language, "call", operation, *ids, "--body", str(payload))

    with monkeypatch.context() as patch:
        patch.setattr(sys.stdin, "isatty", lambda: True)
        patch.setattr("builtins.input", lambda _prompt: "skill-manager")
        patch.setitem(
            skill["interactive_login"].__globals__, "getpass", lambda _prompt: "local-test-password"
        )
        assert run("register")["user"]["username"] == "skill-manager"

    config_path = tmp_path / "worker.json"
    machine = run("machine-create", "工作机", "--out", str(config_path))
    machine_id = machine["machine"]["id"]
    worker_config = json.loads(config_path.read_text(encoding="utf-8"))
    assert "apiKey" not in machine and worker_config["apiKey"] not in json.dumps(machine)
    assert worker_config["serverUrl"] == address
    if os.name == "posix":
        assert config_path.stat().st_mode & 0o777 == 0o600

    workflow = call_with_body(
        "workflow.import", body={"name": "原名", "category": "image", "graph": graph}
    )
    assert workflow["format"] == "api"
    assert not capsys.readouterr().err
    editor = call_with_body(
        "workflow.import", body={"name": "编辑器原图", "graph": {"nodes": [{"type": "SaveImage"}]}}
    )
    assert editor["format"] == "ui"
    assert "从 ComfyUI 导出 API JSON" in capsys.readouterr().err
    run("call", "workflow.delete", editor["id"])
    workflow_id = workflow["id"]
    version_id = workflow["versionId"]
    assert (
        call_with_body("workflow.update", workflow_id, body={"name": "测试片"})["name"] == "测试片"
    )
    assert run("workflow-link", workflow_id) == {
        "url": f"{address}/workflows/{workflow_id}",
        "published": False,
    }
    english = call_with_body(
        "workflow.import",
        body={"name": "Portrait", "category": "image", "graph": graph},
        language="en",
    )
    assert run("call", "workflow.get", english["id"])["name"] == "Portrait"
    assert run("--language", "en", "workflow-link", english["id"]) == {
        "url": f"{address}/workflows/{english['id']}",
        "published": False,
    }
    run("--language", "en", "call", "workflow.delete", english["id"])
    index = tmp_path / "index.json"
    additional_groups = (
        ("Node Basics", "node_basics"),
        ("Product & Ads", "product_ads"),
        ("Character & Fashion", "character_fashion"),
        ("Brand & Design", "brand_design"),
    )
    index.write_text(
        json.dumps(
            [
                {
                    "title": "Vector",
                    "type": "image",
                    "templates": [{"name": "vector-example", "title": "矢量模板"}],
                },
                *[
                    {"title": group, "templates": [{"name": category, "title": group}]}
                    for group, category in additional_groups
                ],
            ]
        ),
        encoding="utf-8",
    )
    official_graph = tmp_path / "official.api.json"
    official_graph.write_text(json.dumps(graph), encoding="utf-8")
    for group, category in additional_groups:
        imported = run("import-template", str(index), category, str(official_graph))
        assert (imported["name"], imported["category"]) == (group, category)
        recategorized = run("classify-template", str(index), category, workflow_id)
        assert (recategorized["versionId"], recategorized["category"]) == (version_id, category)
        run("call", "workflow.delete", imported["id"])
    imported = run("import-template", str(index), "vector-example", str(official_graph))
    assert (imported["name"], imported["category"]) == ("矢量模板", "vector")
    classified = run("classify-template", str(index), "vector-example", workflow_id)
    assert (classified["id"], classified["versionId"], classified["category"]) == (
        workflow_id,
        version_id,
        "vector",
    )
    run("call", "workflow.delete", imported["id"])
    run("call", "workflow.favorite", workflow_id)
    assert run("call", "workspace.favorites")["favoriteIds"] == [workflow_id]
    assert (
        run("workflows", "--scope", "favorites", "--category", "vector", "--sort", "popular")[
            "items"
        ][0]["id"]
        == workflow_id
    )
    run("call", "workflow.unfavorite", workflow_id)
    exported = tmp_path / "workflow.json"
    run("call", "workflow.graph", workflow_id, "--out", str(exported))
    assert json.loads(exported.read_text(encoding="utf-8")) == graph

    with httpx.Client(
        base_url=address,
        headers={"Authorization": "Bearer " + worker_config["apiKey"]},
        trust_env=False,
    ) as worker:
        report_inventory(worker)
        fields = run("form", workflow_id, machine_id, "--version", version_id)["fields"]
        text_id = next(field["id"] for field in fields if field["inputName"] == "text")
        layout = [{"fieldId": text_id, "section": "advanced", "displayName": "画面描述"}]
        saved = call_with_body(
            "workflow.set-layout",
            workflow_id,
            version_id,
            body={"machineId": machine_id, "parameterLayout": layout},
        )
        assert saved[0]["displayName"] == "画面描述"
        current_form = run("form", workflow_id, machine_id, "--version", version_id)
        assert current_form["parameterLayout"][0]["section"] == "advanced"
        job = {
            "workflowId": workflow_id,
            "versionId": version_id,
            "machineId": machine_id,
            "inputSchemaHash": current_form["schemaHash"],
            "inputValues": {text_id: "测试提示词"},
            "idempotencyKey": str(uuid4()),
        }
        plan = tmp_path / "plan.json"
        plan.write_text(json.dumps(job))
        queued = run("submit", str(plan))["tasks"][0]
        assert run("call", "task.cancel", queued["id"])["status"] == "cancelled"
        run("call", "task.delete", queued["id"])
        assert not run("call", "task.list")["items"]

        replay_plan = {**job, "idempotencyKey": str(uuid4())}
        plan.write_text(json.dumps(replay_plan))
        task_id = run("submit", str(plan))["tasks"][0]["id"]
        assert run("call", "task.graph", task_id) == graph
        claim = claim_body()
        assert worker.post("/api/v1/worker/claim", json=claim).json()["task"]["id"] == task_id
        execution, outputs = run_group(web, worker, task_id, claim["leaseSecret"], members=2)
        first, second = (item["id"] for item in outputs)
    assert run("call", "workflow.publish", workflow_id)["published"]
    work_body = {
        "id": str(uuid4()),
        "executionId": execution["id"],
        "title": "测试作品",
        "artifactIds": [first],
        "coverArtifactId": first,
        "shareParameters": True,
    }
    work = call_with_body("work.publish", body=work_body)
    assert work["category"] == "vector"
    assert run("call", "work.list", "--query", "category=vector")["items"][0]["id"] == work["id"]
    assert not run("call", "work.list", "--query", "category=image")["items"]
    assert call_with_body("work.publish", body=work_body)["id"] == work["id"]
    assert run("call", "work.artifacts", work["id"])["items"][0]["id"] == first
    replay = run("call", "work.replay", work["id"])
    replay_form = run(
        "form",
        workflow_id,
        machine_id,
        "--version",
        replay["workflow"]["versionId"],
        "--from-work",
        replay["sourceWorkId"],
    )
    assert (
        next(field["default"] for field in replay_form["fields"] if field["id"] == text_id)
        == "测试提示词"
    )
    assert (
        httpx.get(f"{address}/api/v1/artifacts/{second}/file", trust_env=False).status_code == 404
    )
    run("call", "work.unpublish", work["id"])
    assert not run("call", "work.get", work["id"])["published"]
    run("call", "work.delete", work["id"])
    run("call", "artifact.delete", first)
    assert (
        run("call", "artifact.list", "--query", f"execution_id={execution['id']}")["items"][0]["id"]
        == second
    )
    run("call", "execution.delete-artifacts", execution["id"])
    assert not run("results", task_id)["executions"]
    run("call", "workflow.delete", workflow_id)
    assert not run("workflows", "--scope", "mine")["items"]


def test_official_reference_inputs_are_pinned_and_bound(skill_server, tmp_path, monkeypatch):
    address, home, web = skill_server
    skill = installed_skill(web, address, home, tmp_path, "codex")
    client = skill["Client"](address)
    client.login("template-owner", "local-test-password", register=True)
    machine = client.request("POST", "/machines", {"name": "素材"}, csrf=client.csrf())
    graph = {
        "4": {"class_type": "LoadImage", "inputs": {"image": "reference.png"}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["4", 0]}},
    }
    workflow = client.request(
        "POST", "/workflows", {"name": "示例", "graph": graph}, csrf=client.csrf()
    )
    catalog = {
        "nodes": {
            "LoadImage": {"inputs": {"image": {"kind": "image"}}},
            "SaveImage": {"outputNode": True},
        }
    }
    with httpx.Client(
        base_url=address, headers={"Authorization": "Bearer " + machine["apiKey"]}, trust_env=False
    ) as worker:
        report_inventory(worker, catalog)
    revision = "a" * 40
    source = {
        "file": "reference.png",
        "nodeId": 4,
        "nodeType": "LoadImage",
        "mediaType": "image",
        "sourceRevision": revision,
    }
    index = tmp_path / "index.json"
    index_data = [
        {"title": "Image", "templates": [{"name": "example", "io": {"inputs": [source]}}]}
    ]
    index.write_text(json.dumps(index_data), encoding="utf-8")
    original = skill["open_response"]
    requested = []
    pixels = image_bytes()

    def open_response(opener, request):
        if request.full_url.startswith("https://raw.githubusercontent.com/"):
            requested.append(request.full_url)
            response = BytesIO(pixels)
            response.headers = {"Content-Length": str(len(pixels))}
            return response
        return original(opener, request)

    monkeypatch.setitem(
        skill["prepare_template_materials"].__globals__, "open_response", open_response
    )
    command = ["template-inputs", str(index), "example", workflow["id"], machine["machine"]["id"]]
    fallback_revision = "b" * 40
    args = skill["parser"]().parse_args([*command, "--source-revision", fallback_revision])
    prepared, status = skill["run"](args)
    assert status == 0
    assert requested == [
        f"https://raw.githubusercontent.com/Comfy-Org/workflow_templates/{revision}/input/reference.png"
    ]
    task = client.request(
        "POST", "/tasks", {**prepared, "idempotencyKey": str(uuid4())}, csrf=client.csrf()
    )
    assert task["status"] == "queued" and task["inputValues"] == prepared["inputValues"]
    source.pop("sourceRevision")
    index.write_text(json.dumps(index_data), encoding="utf-8")
    with pytest.raises(skill["ClientError"], match="reference.png.*sourceRevision"):
        skill["run"](skill["parser"]().parse_args(command))
    with pytest.raises(skill["ClientError"], match=r"--source-revision.*40"):
        skill["run"](skill["parser"]().parse_args([*command, "--source-revision", "main"]))
    assert len(requested) == 1
    supplied, status = skill["run"](args)
    assert status == 0 and supplied == prepared  # The same bytes reuse the stored asset.
    assert requested[1] == (
        f"https://raw.githubusercontent.com/Comfy-Org/workflow_templates/"
        f"{fallback_revision}/input/reference.png"
    )


def test_skill_preserves_machine_key_until_new_configuration_can_be_saved(skill_server, tmp_path):
    address, home, web = skill_server
    skill = installed_skill(web, address, home, tmp_path, "codex")

    def run(*args):
        return skill["run"](skill["parser"]().parse_args(args))[0]

    credentials = {"username": "machine-owner", "password": "local-test-password"}
    assert web.post("/api/v1/auth/register", json=credentials).status_code == 201
    skill["Client"](address).login(**credentials)
    first = tmp_path / "worker.json"
    machine = run("machine-create", "工作机", "--out", str(first))["machine"]
    previous_key = json.loads(first.read_text())["apiKey"]
    machine_id = machine["id"]
    with pytest.raises(FileExistsError):
        run("machine-rotate", machine_id, "--out", str(first))
    assert run("machines")["items"][0]["keyPrefix"] == machine["keyPrefix"]

    second = tmp_path / "rotated.json"
    updated = run("machine-rotate", machine_id, "--out", str(second))
    current_key = json.loads(second.read_text())["apiKey"]
    assert previous_key != current_key
    assert current_key not in json.dumps(updated)
    endpoint = f"{address}/api/v1/worker/catalog"
    assert (
        httpx.put(
            endpoint,
            headers={"Authorization": "Bearer " + previous_key},
            json=CATALOG,
            trust_env=False,
        ).status_code
        == 401
    )
    assert (
        httpx.put(
            endpoint,
            headers={"Authorization": "Bearer " + current_key},
            json=CATALOG,
            trust_env=False,
        ).status_code
        == 200
    )
    run("call", "machine.set-default", machine_id)
    assert run("machines")["defaultMachineId"] == machine_id
    assert run("call", "machine.revoke", machine_id)["revoked"]
    assert run("machines")["defaultMachineId"] is None
