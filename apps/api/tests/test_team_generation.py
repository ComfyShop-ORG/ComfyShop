"""团队提交、工作机回传以及公开作品沿用个人版的接口。"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from helpers import CATALOG, serve_test_app, sync_machine
from official_test_support import (
    ADAPTER,
    AUTH,
    OWNER,
    TOKEN,
    asset,
    complete_official_artifact,
    import_official,
    register,
    submit,
    workflow_body,
)
from playwright.sync_api import expect, sync_playwright
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_inputs import picture
from test_outputs import run_group
from test_team_spaces import API, add_member, item_ids, open_space_picker
from test_worker import claim_body
from test_workspace_sharing import ORIGIN, WEB_DIST, register_account

from comfyshop_api.models import Team, TeamEvent, now_ms


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_published_official_workflow_uses_shared_queue_and_team_assets(official):
    owner = TestClient(official.app, headers={"Origin": ORIGIN})
    editor = TestClient(official.app, headers={"Origin": ORIGIN})
    reader = TestClient(official.app, headers={"Origin": ORIGIN})
    register_account(owner, "official-team-owner")
    editor_id = register_account(editor, "official-team-editor")
    register_account(reader, "official-team-reader")
    team_id, other_id = [
        owner.post(f"{API}/teams", json={"name": name}).raise_for_status().json()["id"]
        for name in ("摄影组", "视频组")
    ]
    team = f"{API}/teams/{team_id}"
    scope = {"workspace_team": team_id}
    assert add_member(owner, team, "official-team-editor", "editor").status_code == 204
    assert add_member(owner, team, "official-team-reader", "reader").status_code == 204

    workflow = import_official(
        official,
        workflow_body(
            "team-reference",
            [{"name": "reference", "kind": "image", "label": "参考图"}],
            operation="image",
        ),
    )
    workflow_path = f"{API}/workflows/{workflow['id']}"
    form_path = workflow_path + "/service-inputs"
    assert editor.get(form_path, params=scope).status_code == 404
    original = picture("blue")
    output = picture("green")
    personal_values = {"reference": {"assetId": asset(official, original)}}
    personal_task = submit(official, workflow, personal_values)
    complete_official_artifact(official, personal_task, "result.png", output)
    official.post(workflow_path + "/publish").raise_for_status()

    shared = (
        owner.put(
            f"{team}/assets/{uuid4()}", params={"filename": "reference.png"}, content=original
        )
        .raise_for_status()
        .json()
    )
    owner_personal_asset = asset(owner, original)
    form = editor.get(form_path, params=scope).raise_for_status().json()
    assert form["schemaHash"] == official.get(form_path).raise_for_status().json()["schemaHash"]
    assert "machineId" not in form
    body = {
        "workflowId": workflow["id"],
        "versionId": workflow["versionId"],
        "idempotencyKey": str(uuid4()),
        "inputSchemaHash": form["schemaHash"],
        "inputValues": {"reference": {"assetId": shared["id"]}},
    }
    tasks = f"{API}/tasks"
    assert reader.post(tasks, params=scope, json=body).status_code == 403
    assert (
        owner.post(
            tasks,
            params=scope,
            json={**body, "inputValues": {"reference": {"assetId": owner_personal_asset}}},
        ).status_code
        == 404
    )
    assert owner.post(tasks, params={"workspace_team": other_id}, json=body).status_code == 404
    queued = editor.post(tasks, params=scope, json=body)
    assert queued.status_code == 201, queued.text
    task = queued.json()
    assert task["owner"] == editor_id and task["status"] == "queued"
    assert task["worker"]["kind"] == "official" and task["machineId"] is None
    assert owner.delete(team).status_code == 409
    again = editor.post(tasks, params=scope, json=body)
    assert again.status_code == 200 and again.json()["id"] == task["id"]
    assert item_ids(reader.get(tasks, params=scope)) == {task["id"]}
    assert not item_ids(editor.get(tasks))

    behind = submit(official, workflow, personal_values)
    progress = official.get(f"{tasks}/{behind['id']}/progress").raise_for_status().json()
    assert progress["queueAhead"] == 1
    execution, result = complete_official_artifact(
        official, task, "result.png", output, references={shared["id"]: original}
    )
    task_path = f"{tasks}/{task['id']}"
    assert reader.get(task_path, params=scope).json()["status"] == "succeeded"
    assert owner.get(task_path, params={"workspace_team": other_id}).status_code == 404
    assert item_ids(reader.get(f"{API}/executions", params=scope)) == {execution["id"]}
    assert not item_ids(editor.get(f"{API}/executions"))
    assert reader.get(result["media"]["src"]).content == output
    assert official.get(result["media"]["src"]).status_code == 404


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "mobile"])
@pytest.mark.parametrize("role", ["owner", "editor", "reader"])
def test_team_official_generation_from_the_catalog(settings, width, role, tmp_path):
    settings = settings.model_copy(
        update={
            "static_dir": WEB_DIST,
            "worker_service_tokens": {"official": SecretStr(TOKEN)},
            "official_owner": OWNER,
        }
    )
    with (
        serve_test_app(settings) as (address, web),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        register(web, OWNER)
        workflow = import_official(
            web,
            workflow_body(
                "team-catalog",
                [{"name": "prompt", "kind": "string", "label": "提示词", "default": ""}],
                operation="image",
            ),
        )
        draft_task = submit(web, workflow, {"prompt": "海岸"})
        complete_official_artifact(web, draft_task, "coast.png", picture("blue"))
        web.post(f"{API}/workflows/{workflow['id']}/publish").raise_for_status()
        member = register(web, "atlas-team-member")
        owner = register(web, "atlas-team-owner")
        team = web.post(f"{API}/teams", json={"name": "摄影团队"}).raise_for_status().json()
        scope = {"workspace_team": team["id"]}
        add_member(
            web,
            f"{API}/teams/{team['id']}",
            member["username"],
            "reader" if role == "reader" else "editor",
        ).raise_for_status()
        credentials = owner if role == "owner" else member
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 844},
            locale="zh-CN",
            has_touch=width < 700,
            is_mobile=width < 700,
            reduced_motion="reduce",
        )
        assert page.request.post(
            f"{API}/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/")
        card = page.get_by_role("button", name=workflow["name"], exact=True)
        dialog = page.get_by_role("dialog", name=workflow["name"], exact=True)
        prompt = dialog.locator("form.run-fields").get_by_label("提示词", exact=True)
        generate = dialog.get_by_role("button", name="生成", exact=True)
        card.click()
        expect(prompt).to_be_visible()
        expect(dialog.get_by_role("tab", name="我的结果", exact=True)).to_be_visible()
        button_height = generate.evaluate("node => getComputedStyle(node).height")
        dialog.get_by_role("button", name="关闭", exact=True).click()

        open_space_picker(page).get_by_role("button", name=team["name"], exact=True).click()
        card.click()
        expect(dialog.get_by_role("tab", name="团队结果", exact=True)).to_be_visible()
        permission = dialog.get_by_text(
            "你是团队查看者。团队生成需要编辑者及以上权限。", exact=True
        )
        if role == "reader":
            expect(permission).to_be_visible()
            expect(prompt).to_have_count(0)
            expect(generate).to_have_count(0)
            assert dialog.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
            dialog.screenshot(path=tmp_path / "team-reader-generation.png", animations="disabled")
            return
        expect(permission).to_have_count(0)
        prompt.fill("海岸日出")
        expect(generate).to_have_css("height", button_height)
        expect(dialog.get_by_text("本次执行工作机", exact=True)).to_have_count(0)
        assert dialog.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        dialog.screenshot(path=tmp_path / "team-official-generation.png", animations="disabled")
        requests = []

        def track_submission(request):
            if request.method == "POST" and request.url.split("?")[0].endswith(f"{API}/tasks"):
                requests.append(request.url)

        page.on("request", track_submission)
        with page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and response.url.split("?")[0].endswith(f"{API}/tasks")
            )
        ) as submission:
            generate.click()
        assert submission.value.status == 201
        expect(dialog.get_by_role("region", name="生成进度")).to_be_visible()
        assert requests == [f"{address}{API}/tasks?workspace_team={team['id']}"]
        task = submission.value.json()
        assert task["inputValues"]["prompt"] == "海岸日出" and task["machineId"] is None
        assert item_ids(web.get(f"{API}/tasks", params=scope)) == {task["id"]}

        claim = claim_body()
        job = (
            web.post(
                f"{API}/worker/services/official/claim",
                headers=AUTH,
                json={**claim, "adapters": [ADAPTER]},
            )
            .raise_for_status()
            .json()
        )
        assert job["task"]["id"] == task["id"]
        failed = (
            web.post(
                f"{API}/worker/tasks/{task['id']}/fail",
                headers=AUTH | {"X-Task-Lease": claim["leaseSecret"]},
                json={"error": "供应商返回生成失败", "retryableExecutionIndex": 0},
            )
            .raise_for_status()
            .json()
        )
        assert failed["status"] == "failed"
        outcome = dialog.get_by_role("region", name="生成结果", exact=True)
        expect(outcome.get_by_text("供应商返回生成失败", exact=True)).to_be_visible()
        retry = outcome.get_by_role("button", name="补跑剩余 1 次", exact=True)
        dialog.screenshot(path=tmp_path / "team-generation-recovery.png", animations="disabled")
        if role == "editor":
            expect(retry).to_have_count(0)
        else:
            with page.expect_response(f"**/{task['id']}/retry-executions?*") as retried:
                retry.click()
            assert retried.value.status == 201
            retry_path = f"{API}/tasks/{retried.value.json()['id']}"
            assert web.get(retry_path, params=scope).json()["status"] == "queued"
            assert web.get(retry_path).status_code == 404


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_team_generation_and_publication_use_the_same_entry_points(client, settings):
    owner_id = register_account(client, "delivery-owner")
    first, second = [
        client.post(f"{API}/teams", json={"name": name}).raise_for_status().json()["id"]
        for name in ("摄影组", "视频组")
    ]
    team = f"{API}/teams/{first}"
    scope = {"workspace_team": first}
    other_scope = {"workspace_team": second}
    members = {}
    for role in ("reader", "editor", "manager"):
        member = TestClient(client.app, headers={"Origin": ORIGIN})
        user_id = register_account(member, f"delivery-{role}")
        assert add_member(client, team, f"delivery-{role}", role).status_code == 204
        members[role] = (member, user_id)
    reader, _ = members["reader"]
    editor, editor_id = members["editor"]
    manager, manager_id = members["manager"]
    visitor = TestClient(client.app)

    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "reference.png"}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}},
        "3": {"class_type": "ImageScaleBy", "inputs": {"image": ["1", 0], "scale_by": 2.0}},
    }
    catalog = {
        "nodes": CATALOG["nodes"]
        | {
            "LoadImage": {"inputs": {"image": {"kind": "image"}}},
            "ImageScaleBy": {"inputs": {"scale_by": {"kind": "number", "maximum": "8"}}},
        }
    }
    workflow = (
        editor.post(f"{team}/workflows", json={"name": "团队图像", "graph": graph})
        .raise_for_status()
        .json()
    )
    workflow_path = f"{API}/workflows/{workflow['id']}"
    machine = (
        client.post(f"{API}/machines", params=scope, json={"name": "团队工作机"})
        .raise_for_status()
        .json()
    )
    machine_id = machine["machine"]["id"]
    worker = sync_machine(client, machine, catalog)
    personal = client.post(f"{API}/machines", json={"name": "个人工作机"}).raise_for_status().json()
    personal_worker = sync_machine(client, personal, catalog)
    reference = picture("blue", size=(512, 512))
    asset = (
        client.put(
            f"{team}/assets/{uuid4()}",
            params={"filename": "team-reference.png"},
            content=reference,
        )
        .raise_for_status()
        .json()
    )
    personal_asset = (
        client.put(
            f"{API}/assets/{uuid4()}",
            params={"filename": "personal-reference.png"},
            content=reference,
        )
        .raise_for_status()
        .json()
    )
    form = (
        editor.get(workflow_path + "/inputs", params={**scope, "machine_id": machine_id})
        .raise_for_status()
        .json()
    )
    image = next(field for field in form["fields"] if field["kind"] == "image")
    scale = next(field for field in form["fields"] if field["inputName"] == "scale_by")
    body = {
        "workflowId": workflow["id"],
        "versionId": workflow["versionId"],
        "idempotencyKey": str(uuid4()),
        "inputSchemaHash": form["schemaHash"],
        "inputValues": {image["id"]: {"assetId": asset["id"]}, scale["id"]: 3.0},
    }
    tasks = f"{API}/tasks"
    assert manager.post(workflow_path + "/publish", params=scope).status_code == 409
    assert reader.post(tasks, params=scope, json=body).status_code == 403
    assert (
        editor.post(
            tasks,
            params=scope,
            json={**body, "machineId": personal["machine"]["id"]},
        ).status_code
        == 409
    )
    assert (
        editor.post(
            tasks,
            params=scope,
            json={
                **body,
                "inputValues": {image["id"]: {"assetId": personal_asset["id"]}},
            },
        ).status_code
        == 404
    )
    queued = editor.post(tasks, params=scope, json=body)
    assert queued.status_code == 201, queued.text
    task = queued.json()
    assert task["status"] == "queued" and task["owner"] == editor_id
    assert task["machineId"] == machine_id
    assert client.delete(team).status_code == 409
    again = editor.post(tasks, params=scope, json=body)
    assert again.status_code == 200 and again.json()["id"] == task["id"]
    task_path = f"{tasks}/{task['id']}"
    assert not item_ids(editor.get(tasks))
    assert not item_ids(client.get(tasks, params=other_scope))
    assert editor.get(task_path).status_code == 404
    assert client.get(task_path, params=other_scope).status_code == 404
    assert reader.get(task_path + "/progress", params=scope).json()["status"] == "queued"
    assert reader.post(task_path + "/cancel", params=scope).status_code == 403
    assert editor.post(task_path + "/cancel", params=scope).json()["status"] == "cancelled"
    library = f"{API}/assets/{asset['id']}/library"
    assert manager.delete(library, params=scope).status_code == 204
    assert manager.delete(task_path, params=scope).status_code == 204
    settings.team_asset_quota_bytes[UUID(first)] = 1024
    assert manager.post(task_path + "/restore", params=scope).status_code == 413
    settings.team_asset_quota_bytes[UUID(first)] = asset["size"]
    assert manager.post(task_path + "/restore", params=scope).status_code == 204
    manager.put(library, params=scope).raise_for_status()
    assert editor.post(task_path + "/resume", params=scope).json()["status"] == "queued"

    claim = claim_body()
    assert personal_worker.post(f"{API}/worker/claim", json=claim_body()).json() is None
    job = worker.post(f"{API}/worker/claim", json=claim).raise_for_status().json()
    assert job["task"]["id"] == task["id"]
    assert client.delete(team).status_code == 409
    worker_path = f"{API}/worker/tasks/{task['id']}"
    headers = {"X-Task-Lease": claim["leaseSecret"]}
    source = f"{worker_path}/assets/{asset['id']}"
    assert worker.get(source, headers=headers).content == reference
    assert personal_worker.get(source, headers=headers).status_code == 404
    execution, (selected, private) = run_group(
        editor,
        worker,
        task["id"],
        claim["leaseSecret"],
        members=2,
    )
    worker.post(worker_path + "/complete", headers=headers).raise_for_status()
    executions = f"{API}/executions"
    assert item_ids(reader.get(executions, params=scope)) == {execution["id"]}
    assert not item_ids(editor.get(executions))
    assert reader.get(task_path + "/inputs", params=scope).json()["assets"][0]["id"] == asset["id"]
    assert reader.get(private["media"]["src"]).status_code == 200
    assert visitor.get(selected["media"]["src"]).status_code == 404
    assert reader.get(asset["media"]["src"]).status_code == 200
    assert visitor.get(workflow_path).status_code == 404

    works = f"{API}/works"
    work_body = {
        "id": str(uuid4()),
        "executionId": execution["id"],
        "title": "团队成品",
        "artifactIds": [selected["id"]],
        "coverArtifactId": selected["id"],
    }
    assert manager.post(works, params=scope, json=work_body).status_code == 409
    assert editor.post(workflow_path + "/publish", params=scope).status_code == 403
    assert manager.post(workflow_path + "/publish", params=scope).json()["published"]
    assert visitor.get(workflow_path).json()["versionId"] == workflow["versionId"]
    assert editor.post(works, params=scope, json=work_body).status_code == 403
    assert manager.post(works, json=work_body).status_code == 404
    published = manager.post(works, params=scope, json=work_body)
    assert published.status_code == 201, published.text
    work = published.json()
    assert work["teamId"] == first and work["owner"] == manager_id and work["published"]
    assert manager.post(works, params=scope, json=work_body).status_code == 200
    work_path = f"{works}/{work['id']}"
    assert item_ids(visitor.get(work_path + "/artifacts")) == {selected["id"]}
    assert visitor.get(work_path).json()["inputValues"] == {}
    assert item_ids(reader.get(works, params={**scope, "scope": "mine"})) == {work["id"]}
    assert not item_ids(manager.get(works, params={"scope": "mine"}))
    assert visitor.get(selected["media"]["src"]).status_code == 200
    assert visitor.get(private["media"]["src"]).status_code == 404
    assert visitor.get(asset["media"]["src"]).status_code == 401

    scalar_only = (
        manager.post(
            works, params=scope, json={**work_body, "id": str(uuid4()), "shareParameters": True}
        )
        .raise_for_status()
        .json()
    )
    assert scalar_only["inputValues"] == {scale["id"]: 3.0}
    assert visitor.get(f"{works}/{scalar_only['id']}/inputs").json()["assets"] == []

    with_inputs = (
        manager.post(
            works,
            params=scope,
            json={
                **work_body,
                "id": str(uuid4()),
                "shareAssets": True,
            },
        )
        .raise_for_status()
        .json()
    )
    shared_id = with_inputs["inputValues"][image["id"]]["assetId"]
    assert shared_id != asset["id"]
    shared_path = f"{works}/{with_inputs['id']}/assets/{shared_id}/file"
    assert visitor.get(shared_path).content == reference

    other_machine = (
        client.post(f"{API}/machines", params=other_scope, json={"name": "第二团队工作机"})
        .raise_for_status()
        .json()
    )
    sync_machine(client, other_machine, catalog)
    for target, target_machine in (({}, personal), (other_scope, other_machine)):
        target_form = (
            client.get(
                workflow_path + "/inputs",
                params={
                    **target,
                    "machine_id": target_machine["machine"]["id"],
                    "work_id": with_inputs["id"],
                },
            )
            .raise_for_status()
            .json()
        )
        replay_request = {
            **body,
            "sourceWorkId": with_inputs["id"],
            "inputSchemaHash": target_form["schemaHash"],
            "inputValues": {image["id"]: {"assetId": shared_id}},
        }
        if target == other_scope:
            settings.team_asset_quota_bytes[UUID(second)] = 1024
            assert client.post(tasks, params=target, json=replay_request).status_code == 413
            settings.team_asset_quota_bytes[UUID(second)] = asset["size"]
        replay = client.post(tasks, params=target, json=replay_request)
        assert replay.status_code == 201, replay.text
        assert replay.json()["machineId"] == target_machine["machine"]["id"]
        replay_path = f"{tasks}/{replay.json()['id']}"
        replay_assets = client.get(replay_path + "/inputs", params=target).json()["assets"]
        assert len(replay_assets) == 1 and replay_assets[0]["sha256"] == asset["sha256"]
        assert replay_assets[0]["id"] not in {asset["id"], shared_id}
        assert client.get(replay_path, params=scope).status_code == 404

    assert editor.delete(work_path, params=scope).status_code == 403
    assert manager.delete(work_path, params=scope).status_code == 204
    assert visitor.get(work_path).status_code == 404

    assert client.delete(f"{team}/members/{editor_id}").status_code == 204
    assert editor.get(task_path, params=scope).status_code == 404
    assert editor.get(private["media"]["src"]).status_code == 404
    assert reader.get(private["media"]["src"]).status_code == 200
    assert reader.get(task_path, params=scope).json()["owner"] == editor_id
    with Session(client.app.state.engine) as db:
        events = set(
            db.execute(
                select(TeamEvent.action, TeamEvent.actor_id).where(
                    TeamEvent.team_id == first,
                )
            ).tuples()
        )
        assert ("task.submitted", editor_id) in events
        assert ("workflow.published", manager_id) in events
        assert ("work.published", manager_id) in events
    assert client.delete(team).status_code == 204
    assert visitor.get(workflow_path).status_code == 404
    assert visitor.get(selected["media"]["src"]).status_code == 404
    assert visitor.get(shared_path).status_code == 404
    assert reader.get(task_path, params=scope).status_code == 404
    assert reader.get(private["media"]["src"]).status_code == 404
    assert worker.post(f"{API}/worker/claim", json=claim_body()).status_code == 401

    restore = team + "/restore"
    assert manager.post(restore).status_code == 404
    assert client.post(restore).raise_for_status().json()["id"] == first
    assert client.post(restore).status_code == 200
    assert visitor.get(workflow_path).json()["versionId"] == workflow["versionId"]
    assert visitor.get(work_path).status_code == 404
    assert visitor.get(selected["media"]["src"]).status_code == 200
    assert visitor.get(shared_path).content == reference
    assert reader.get(private["media"]["src"]).status_code == 200
    assert reader.get(task_path, params=scope).json()["owner"] == editor_id
    assert editor.get(task_path, params=scope).status_code == 404
    assert client.get(f"{API}/machines", params=scope).json()["defaultMachineId"] == machine_id
    assert worker.post(f"{API}/worker/claim", json=claim_body()).json() is None
    with Session(client.app.state.engine) as db:
        restores = db.scalars(
            select(TeamEvent.actor_id).where(
                TeamEvent.team_id == first, TeamEvent.action == "team.restored"
            )
        ).all()
        assert restores == [owner_id]

    # 旧版本允许队列里还有任务时归档。恢复它时应告知所有者队列还在。
    pending = client.post(tasks, params=scope, json={**body, "idempotencyKey": str(uuid4())})
    assert pending.status_code == 201, pending.text
    with Session(client.app.state.engine) as db:
        db.get_one(Team, first).archived_at = now_ms()
        db.commit()
    (archived,) = client.get(f"{API}/teams/archived").raise_for_status().json()["items"]
    assert archived["id"] == first and archived["hasQueuedTasks"]
    assert worker.post(f"{API}/worker/claim", json=claim_body()).status_code == 401
    assert client.post(restore).status_code == 200
    claimed = worker.post(f"{API}/worker/claim", json=claim_body()).raise_for_status().json()
    assert claimed["task"]["id"] == pending.json()["id"]
