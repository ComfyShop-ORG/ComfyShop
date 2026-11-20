import json
import os
from pathlib import Path
import runpy
import socket
import sys
from threading import Thread
from time import monotonic, sleep
from uuid import uuid4

import httpx
import pytest
import uvicorn

from comfyshop_api.main import create_app
from helpers import CATALOG
from test_outputs import run_group
from test_worker import claim_body, image_bytes

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def skill_server(settings, tmp_path, monkeypatch):
    static = tmp_path / "web"
    builder = runpy.run_path(str(ROOT / "tooling/build-skill.py"))
    builder["build_skill"](static / "downloads")
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    app = create_app(settings.model_copy(update={"static_dir": static}))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", ws="none"))
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
            with httpx.Client(
                base_url=address, headers={"Origin": address}, trust_env=False
            ) as web:
                yield address, home, web
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive()


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
    paths = json.loads((ROOT / "packages/api-client/openapi.json").read_text())["paths"]
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
        assert operation.payload == ("requestBody" in endpoint)
        covered.add((operation.method, operation.path))
    relevant = {
        (verb.upper(), path.removeprefix("/api/v1"))
        for path, methods in paths.items()
        if path.startswith("/api/v1/") and not path.startswith("/api/v1/worker/")
        for verb in methods
    }
    assert covered | dedicated == relevant


def test_skill_download_installs_into_both_client_directories(skill_server, tmp_path):
    address, home, web = skill_server
    for client_name in ("codex", "claude-code"):
        skill = installed_skill(web, address, home, tmp_path, client_name)
        account = skill["parser"]().parse_args(["account"])
        assert skill["run"](account) == ({"server": address, "user": None}, 0)


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
        assert worker.put("/api/v1/worker/catalog", json=CATALOG).status_code == 200
        form, status = run("form", workflow_id, machine_id, "--version", version_id)
        assert status == 0 and not form["issues"]
        text_id = next(field["id"] for field in form["fields"] if field["inputName"] == "text")

        image = tmp_path / "参考图.png"
        image.write_bytes(image_bytes())
        upload_id = str(uuid4())
        assert run("upload", str(image), "--asset-id", upload_id)[0]["id"] == upload_id
        assert run("upload", str(image), "--asset-id", upload_id)[0]["id"] == upload_id

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

    run("logout")
    assert not client.session_file.exists()
    assert client.session()["user"] is None
    assert web.get("/api/v1/auth/session").json()["user"] == registered.json()["user"]
    with pytest.raises(skill["ClientError"], match="请先登录"):
        run("progress", task_id)


def test_installed_skill_manages_workflows_tasks_and_works(
    skill_server, tmp_path, graph, monkeypatch
):
    address, home, web = skill_server
    skill = installed_skill(web, address, home, tmp_path, "codex")

    def run(*args):
        result, status = skill["run"](skill["parser"]().parse_args(args))
        assert status == 0
        return result

    def call_with_body(operation, *ids, body):
        payload = tmp_path / "payload.json"
        payload.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return run("call", operation, *ids, "--body", str(payload))

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
    workflow_id = workflow["id"]
    version_id = workflow["versionId"]
    assert (
        call_with_body("workflow.update", workflow_id, body={"name": "测试片"})["name"] == "测试片"
    )
    assert run("workflow-link", workflow_id) == {
        "url": f"{address}/workflows/{workflow_id}",
        "published": False,
    }
    run("call", "workflow.favorite", workflow_id)
    assert run("call", "workspace.favorites")["favoriteIds"] == [workflow_id]
    assert (
        run("workflows", "--scope", "favorites", "--category", "image", "--sort", "popular")[
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
        assert worker.put("/api/v1/worker/catalog", json=CATALOG).status_code == 200
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
