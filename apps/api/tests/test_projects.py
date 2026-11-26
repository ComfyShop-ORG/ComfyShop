from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from helpers import CATALOG, serve_test_app, sync_machine
from official_test_support import (
    OWNER,
    TOKEN,
    complete_official_artifact,
    import_official,
    register,
    submit,
    workflow_body,
)
from playwright.sync_api import expect, sync_playwright
from pydantic import SecretStr
from test_inputs import picture
from test_outputs import run_group
from test_team_spaces import API, add_member, item_ids, open_space_picker
from test_worker import claim_body
from test_workspace_sharing import ORIGIN, WEB_DIST, register_account


def create_project(client, name, scope=None):
    created = client.post(f"{API}/projects", params=scope, json={"name": name})
    assert created.status_code == 201, created.text
    return created.json()


def saved_asset(client, base=API, filename="reference.png"):
    return (
        client.put(
            f"{base}/assets/{uuid4()}",
            params={"filename": filename, "save_to_library": True},
            content=picture("blue"),
        )
        .raise_for_status()
        .json()
    )


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_project_scopes_references_and_batch_assignment(client):
    owner_id = register_account(client, "project-owner")
    accounts = {}
    team_id = client.post(f"{API}/teams", json={"name": "制作组"}).raise_for_status().json()["id"]
    team = f"{API}/teams/{team_id}"
    scope = {"workspace_team": team_id}
    for role, username in (
        ("reader", "project-reader"),
        ("editor", "project-editor"),
        ("editor", "project-colleague"),
        ("manager", "project-manager"),
    ):
        member = TestClient(client.app, headers={"Origin": ORIGIN})
        register_account(member, username)
        assert add_member(client, team, username, role).status_code == 204
        accounts[username] = member
    reader, editor, colleague, manager = accounts.values()
    visitor = TestClient(client.app)
    personal = create_project(client, "个人项目")
    first = create_project(editor, "新品主图", scope)
    second = create_project(client, "备选方案", scope)
    assert client.get(f"{API}/projects/{first['id']}").status_code == 404
    assert reader.get(f"{API}/projects/{personal['id']}").status_code == 404
    assert reader.post(f"{API}/projects", params=scope, json={"name": "只读"}).status_code == 403
    assert item_ids(reader.get(f"{API}/projects", params=scope)) == {first["id"], second["id"]}
    assert item_ids(client.get(f"{API}/projects")) == {personal["id"]}
    assert client.put(f"{API}/workspace/shares/by-name/project-reader").status_code == 204
    shared = {"workspace_owner": owner_id}
    assert item_ids(reader.get(f"{API}/projects", params=shared)) == {personal["id"]}
    assert visitor.get(f"{API}/projects/{personal['id']}").status_code == 401

    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "reference.png"}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }
    workflow = (
        editor.post(f"{team}/workflows", json={"name": "商品摄影", "graph": graph})
        .raise_for_status()
        .json()
    )
    workflow_path = f"{API}/workflows/{workflow['id']}"
    asset, private_asset = saved_asset(editor, team), saved_asset(client)
    project = f"{API}/projects/{first['id']}"
    workflow_ref = f"{project}/workflows/{workflow['id']}"
    asset_ref = f"{project}/assets/{asset['id']}"
    assert reader.put(workflow_ref, params=scope).status_code == 403
    assert editor.put(workflow_ref, params=scope).status_code == 204
    assert editor.put(asset_ref, params=scope).status_code == 204
    assert editor.put(asset_ref, params=scope).status_code == 204
    assert editor.put(f"{project}/assets/{private_asset['id']}", params=scope).status_code == 404
    assert (
        editor.put(f"{API}/projects/{personal['id']}/workflows/{workflow['id']}").status_code == 404
    )
    of_first = {**scope, "project_id": first["id"]}
    of_second = {**scope, "project_id": second["id"]}
    assert item_ids(reader.get(f"{API}/assets", params=of_first)) == {asset["id"]}
    assert item_ids(reader.get(f"{API}/workflows", params={**of_first, "scope": "mine"})) == {
        workflow["id"]
    }
    assert not item_ids(reader.get(f"{API}/assets", params=of_second))
    previews = {
        project["id"]: project["cover"]
        for project in reader.get(f"{API}/projects", params=scope)
        .raise_for_status()
        .json()["items"]
    }
    assert previews == {first["id"]: asset["media"], second["id"]: None}
    assert reader.get(previews[first["id"]]["thumbnail"]["src"]).status_code == 200

    machine = (
        client.post(f"{API}/machines", params=scope, json={"name": "团队工作机"})
        .raise_for_status()
        .json()
    )
    machine_id = machine["machine"]["id"]
    worker = sync_machine(
        client,
        machine,
        {"nodes": CATALOG["nodes"] | {"LoadImage": {"inputs": {"image": {"kind": "image"}}}}},
    )
    form = (
        editor.get(workflow_path + "/inputs", params={**scope, "machine_id": machine_id})
        .raise_for_status()
        .json()
    )
    image_field = next(field for field in form["fields"] if field["kind"] == "image")
    body = {
        "workflowId": workflow["id"],
        "versionId": workflow["versionId"],
        "idempotencyKey": str(uuid4()),
        "inputSchemaHash": form["schemaHash"],
        "inputValues": {image_field["id"]: {"assetId": asset["id"]}},
        "executionCount": 2,
        "projectId": first["id"],
    }
    queued = f"{API}/tasks"
    assert (
        editor.post(queued, params=scope, json={**body, "projectId": personal["id"]}).status_code
        == 404
    )
    task = editor.post(queued, params=scope, json=body).raise_for_status().json()
    assert task["projectId"] == first["id"]
    assert editor.post(queued, params=scope, json=body).status_code == 200
    assert (
        editor.post(queued, params=scope, json={**body, "projectId": second["id"]}).status_code
        == 409
    )
    move = f"{queued}/{task['id']}/project"
    assert colleague.put(move, params=scope, json={"projectId": second["id"]}).status_code == 403
    assert reader.put(move, params=scope, json={"projectId": second["id"]}).status_code == 403
    assert editor.put(move, params=scope, json={"projectId": personal["id"]}).status_code == 404
    assert item_ids(reader.get(queued, params=of_first)) == {task["id"]}
    assert not reader.get(queued + "/activity", params=of_second).json()["activeTasks"]
    claim = claim_body()
    assert worker.post(f"{API}/worker/claim", json=claim).json()["task"]["id"] == task["id"]
    groups = [
        run_group(editor, worker, task["id"], claim["leaseSecret"], index=i, members=1)
        for i in range(2)
    ]
    assert item_ids(reader.get(f"{API}/executions", params=of_first)) == {
        group[0]["id"] for group in groups
    }
    assert editor.put(move, params=scope, json={"projectId": second["id"]}).status_code == 204
    assert not item_ids(reader.get(f"{API}/executions", params=of_first))
    previews = {
        project["id"]: project["cover"]
        for project in reader.get(f"{API}/projects", params=scope)
        .raise_for_status()
        .json()["items"]
    }
    latest_result = groups[1][1][0]["media"]
    assert previews == {first["id"]: asset["media"], second["id"]: latest_result}
    assert reader.get(latest_result["thumbnail"]["src"]).status_code == 200
    assert visitor.get(latest_result["thumbnail"]["src"]).status_code == 404

    manager.post(workflow_path + "/publish", params=scope).raise_for_status()
    execution, (selected,) = groups[0]
    work = (
        manager.post(
            f"{API}/works",
            params=scope,
            json={
                "id": str(uuid4()),
                "executionId": execution["id"],
                "title": "主图第一版",
                "artifactIds": [selected["id"]],
                "coverArtifactId": selected["id"],
            },
        )
        .raise_for_status()
        .json()
    )
    assert item_ids(reader.get(f"{API}/works", params={**of_second, "scope": "mine"})) == {
        work["id"]
    }
    work_path = f"{API}/works/{work['id']}"
    assert visitor.get(work_path).json().get("projectId") is None
    assert visitor.get(f"{API}/works", params={"project_id": second["id"]}).status_code == 422
    assert editor.get(work_path + "/replay", params=scope).json()["projectId"] == second["id"]
    assert editor.get(work_path + "/replay").json()["projectId"] is None
    assert manager.delete(f"{queued}/{task['id']}", params=scope).status_code == 204
    assert manager.put(move, params=scope, json={"projectId": first["id"]}).status_code == 204
    assert item_ids(reader.get(f"{API}/works", params={**of_first, "scope": "mine"})) == {
        work["id"]
    }
    assert (
        reader.get(f"{API}/executions/{execution['id']}/replay", params=scope).json()["projectId"]
        == first["id"]
    )

    details = {"name": "新品交付", "description": "交付用主图"}
    assert reader.put(project, params=scope, json=details).status_code == 403
    assert reader.put(f"{API}/projects/{personal['id']}", json=details).status_code == 404
    renamed = editor.put(project, params=scope, json=details).raise_for_status().json()
    assert renamed == {**first, **details}

    archive = f"{project}/archive"
    restore = f"{project}/restore"
    assert editor.put(archive, params=scope, json={"archived": True}).status_code == 403
    assert editor.delete(project, params=scope).status_code == 403
    assert editor.post(restore, params=scope).status_code == 403
    pending_body = {**body, "idempotencyKey": str(uuid4())}
    pending = editor.post(queued, params=scope, json=pending_body).raise_for_status().json()
    archived = manager.put(archive, params=scope, json={"archived": True}).raise_for_status()
    assert archived.json()["archivedAt"] is not None
    assert manager.put(archive, params=scope, json={"archived": True}).json() == archived.json()
    assert first["id"] not in item_ids(reader.get(f"{API}/projects", params=scope))
    archive_filter = {**scope, "archived": True}
    assert item_ids(reader.get(f"{API}/projects", params=archive_filter)) == {first["id"]}
    assert reader.get(project, params=scope).json() == archived.json()
    assert item_ids(reader.get(f"{API}/assets", params=of_first)) == {asset["id"]}
    assert reader.get(f"{queued}/{pending['id']}", params=scope).json()["status"] == "queued"
    assert editor.post(queued, params=scope, json=pending_body).status_code == 200
    assert (
        editor.post(
            queued, params=scope, json={**pending_body, "idempotencyKey": str(uuid4())}
        ).status_code
        == 409
    )
    assert editor.put(move, params=scope, json={"projectId": first["id"]}).status_code == 409
    assert editor.put(project, params=scope, json=details).status_code == 409
    assert editor.delete(asset_ref, params=scope).status_code == 409
    assert editor.get(work_path + "/replay", params=scope).json()["projectId"] is None

    assert manager.delete(project, params=scope).status_code == 204
    assert manager.delete(project, params=scope).status_code == 204
    assert reader.get(project, params=scope).status_code == 404
    assert not item_ids(reader.get(f"{API}/projects", params=archive_filter))
    assert reader.get(f"{API}/executions", params=of_first).status_code == 404
    assert execution["id"] in item_ids(reader.get(f"{API}/executions", params=scope))
    assert asset["id"] in item_ids(reader.get(f"{API}/assets", params=scope))
    assert visitor.get(work_path).status_code == 200
    claim = claim_body()
    assert worker.post(f"{API}/worker/claim", json=claim).json()["task"]["id"] == pending["id"]

    assert manager.post(restore, params=scope).json() == archived.json()
    assert manager.post(restore, params=scope).json() == archived.json()
    assert item_ids(reader.get(f"{API}/projects", params=archive_filter)) == {first["id"]}
    assert manager.put(archive, params=scope, json={"archived": False}).json() == renamed
    assert item_ids(reader.get(f"{API}/assets", params=of_first)) == {asset["id"]}
    assert editor.get(work_path + "/replay", params=scope).json()["projectId"] == first["id"]

    assert editor.delete(f"{API}/assets/{asset['id']}/library", params=scope).status_code == 204
    assert not item_ids(reader.get(f"{API}/assets", params=of_first))
    events = (
        manager.get(f"{team}/events", params={"category": "project"})
        .raise_for_status()
        .json()["items"]
    )
    assert {
        (event["action"], event["actorUsername"])
        for event in events
        if event["target"] == details["name"]
    } >= {
        ("project.created", "project-editor"),
        ("project.materialsChanged", "project-editor"),
        ("project.updated", "project-editor"),
        ("project.archived", "project-manager"),
        ("project.deleted", "project-manager"),
        ("project.restored", "project-manager"),
        ("project.unarchived", "project-manager"),
    }
    for action in ("archived", "deleted", "restored"):
        assert sum(event["action"] == f"project.{action}" for event in events) == 1


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "narrow"])
def test_projects_from_navigation_through_generation_and_publication(settings, width, tmp_path):
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
                "project-image",
                [{"name": "prompt", "kind": "string", "label": "提示词", "default": ""}],
                operation="image",
            ),
        )
        seed = submit(web, workflow, {"prompt": "样张"})
        complete_official_artifact(web, seed, "sample.png", picture("blue"))
        web.post(f"{API}/workflows/{workflow['id']}/publish").raise_for_status()
        credentials = register(web, "project-artist")
        team = web.post(f"{API}/teams", json={"name": "项目团队"}).raise_for_status().json()
        saved_asset(web)
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 844},
            locale="zh-CN",
            is_mobile=width < 700,
            has_touch=width < 700,
            reduced_motion="reduce",
        )
        assert page.request.post(
            f"{API}/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/")
        nav = page.get_by_role("navigation", name="主导航")
        expect(nav.get_by_role("link")).to_have_text(["工作流", "项目", "我的", "工作机"])
        nav.get_by_role("link", name="项目", exact=True).click()
        expect(page).to_have_url(f"{address}/projects")
        expect(nav.get_by_role("link", name="项目")).to_have_attribute("aria-current", "page")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        project_search = page.get_by_role("searchbox", name="搜索项目名称")
        expect(project_search).to_have_attribute("placeholder", "搜索项目名称")
        new_project = page.get_by_role("button", name="新建项目", exact=True)
        control_height = 44 if width == 320 else 40
        search_position = project_search.locator("..").bounding_box()
        status = page.get_by_role("combobox", name="项目状态")
        status_position = status.bounding_box()
        new_position = new_project.bounding_box()
        assert search_position["x"] == page.locator(".project-index-toolbar").bounding_box()["x"]
        assert (
            search_position["height"]
            == status_position["height"]
            == new_position["height"]
            == control_height
        )
        assert search_position["y"] == status_position["y"]
        if width == 320:
            assert new_position["y"] >= search_position["y"]
            assert nav.bounding_box()["y"] > page.locator(".brand").bounding_box()["y"]
        else:
            assert new_position["y"] == search_position["y"]

        def create(name):
            dialog = page.get_by_role("dialog", name="新建项目", exact=True)
            dialog.get_by_role("textbox", name="项目名称").fill(name)
            dialog.get_by_role("textbox", name="简介（选填）").fill("用于新品交付")
            with page.expect_response(
                lambda response: (
                    urlsplit(response.url).path == f"{API}/projects"
                    and response.request.method == "POST"
                )
            ) as response:
                dialog.get_by_role("button", name="新建项目", exact=True).click()
            assert response.value.status == 201
            expect(dialog).to_have_count(0)
            return response.value.json()["id"]

        new_project.click()
        first = create("夏季新品主图")
        project_url = f"{address}/projects/{first}"
        expect(page).to_have_url(project_url)
        nav.get_by_role("link", name="项目", exact=True).click()
        project_card = page.get_by_role("link", name="夏季新品主图", exact=True)
        expect(project_card.locator(".media-placeholder")).to_be_visible()
        project_card.click()
        expect(page).to_have_url(project_url)
        heading = page.get_by_role("heading", name="夏季新品主图")
        expect(heading).to_be_visible()
        expect(page.get_by_role("main").get_by_role("link", name="项目", exact=True)).to_have_count(
            0
        )
        switch_project = page.get_by_role("button", name="切换项目", exact=True)
        expect(switch_project).to_have_text("")
        switch_position, title = switch_project.bounding_box(), heading.bounding_box()
        generate = page.get_by_role("button", name="选工作流生成", exact=True).bounding_box()
        results_tab = page.get_by_role("tab", name="结果", exact=True).bounding_box()
        search = page.get_by_role("searchbox", name="工作流名称").bounding_box()
        date = page.get_by_role("button", name="生成日期", exact=True).bounding_box()
        assert all(
            box["height"] == control_height
            for box in (switch_position, generate, results_tab, search, date)
        )
        assert switch_position["x"] == results_tab["x"]
        assert switch_position["x"] + switch_position["width"] <= title["x"]
        assert switch_position["y"] <= title["y"] < switch_position["y"] + control_height
        assert search["y"] == date["y"]
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        if width == 320:
            assert search["y"] > results_tab["y"]
            project_tabs = page.get_by_role("tablist", name="项目内容").get_by_role("tab")
            assert all(tab.bounding_box()["y"] == results_tab["y"] for tab in project_tabs.all())
        else:
            intro = page.get_by_text("用于新品交付").bounding_box()
            assert switch_position["y"] <= intro["y"] < switch_position["y"] + control_height
            assert title["x"] < intro["x"] < generate["x"]
            assert results_tab["y"] == search["y"] == generate["y"]
        page.screenshot(path=tmp_path / "project-detail.png", animations="disabled")
        workflows_tab = page.get_by_role("tab", name="工作流", exact=True)
        assets_tab = page.get_by_role("tab", name="参考素材", exact=True)
        workflows_tab.click()
        workflow_panel = page.get_by_role("tabpanel", name="工作流", exact=True)
        toolbar = page.locator(".project-toolbar")
        link_workflow = toolbar.get_by_role("button", name="关联工作流", exact=True)
        link_asset = toolbar.get_by_role("button", name="关联参考素材", exact=True)
        generate_button = toolbar.get_by_role("button", name="选工作流生成", exact=True)
        assert link_workflow.bounding_box()["height"] == control_height
        if width == 1280:
            page.set_viewport_size({"width": 1024, "height": 844})
            assert link_workflow.bounding_box()["y"] == workflows_tab.bounding_box()["y"]
            assert generate_button.bounding_box()["y"] == workflows_tab.bounding_box()["y"]
            page.set_viewport_size({"width": width, "height": 844})

        link_workflow.click()
        page.get_by_role("dialog", name="关联工作流").get_by_role(
            "button", name=workflow["name"], exact=True
        ).click()
        linked_workflow = workflow_panel.locator(".media-feed .workflow-card").filter(
            has=page.get_by_role("button", name=workflow["name"], exact=True)
        )
        expect(linked_workflow).to_be_visible()
        page.screenshot(path=tmp_path / "project-workflows.png", animations="disabled")

        assets_tab.click()
        asset_panel = page.get_by_role("tabpanel", name="参考素材", exact=True)
        link_asset.click()
        asset_picker = page.get_by_role("dialog", name="关联参考素材")
        asset_search = asset_picker.get_by_role("searchbox", name="搜索文件名")
        expect(asset_picker.get_by_role("heading")).to_be_focused()
        asset_search.fill("不存在的素材")
        expect(asset_picker.get_by_text("没有符合条件的素材", exact=True)).to_be_visible()
        asset_picker.get_by_role("button", name="关闭", exact=True).click()
        expect(link_asset).to_be_focused()
        link_asset.click()
        expect(asset_search).to_have_value("")
        asset_picker.get_by_role("button", name="使用 reference.png").click()
        expect(
            asset_panel.locator(".media-feed").get_by_role("button", name="预览 reference.png")
        ).to_be_visible()
        asset_controls = (
            link_asset,
            toolbar.get_by_role("searchbox", name="搜索文件名"),
            toolbar.get_by_role("combobox", name="素材类型"),
        )
        assert all(control.bounding_box()["height"] == control_height for control in asset_controls)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        if width == 1280:
            assert all(
                control.bounding_box()["y"] == assets_tab.bounding_box()["y"]
                for control in (*asset_controls, generate_button)
            )
        page.screenshot(path=tmp_path / "project-assets.png", animations="disabled")

        page.goto(f"{project_url}?tab=materials")
        expect(workflows_tab).to_have_attribute("aria-selected", "true")
        linked_workflow.get_by_role("button", name=workflow["name"], exact=True).click()
        linked_detail = page.get_by_role("dialog", name=workflow["name"], exact=True)
        expect(linked_detail.get_by_role("button", name="项目", exact=True)).to_have_text(
            "夏季新品主图"
        )
        linked_detail.get_by_role("button", name="关闭", exact=True).click()
        linked_workflow.get_by_role("button", name="移出项目", exact=True).click()
        unlink = page.get_by_role("alertdialog", name="移出项目")
        unlink.get_by_role("button", name="确认删除", exact=True).click()
        expect(linked_workflow).to_have_count(0)
        expect(workflow_panel.locator(":focus")).to_have_count(1)

        generate_button.click()
        picker = page.get_by_role("dialog", name="选工作流生成")
        source = picker.get_by_role("combobox", name="工作流来源")
        workflow_search = picker.get_by_role("searchbox", name="搜索工作流")
        expect(picker.get_by_role("heading", name="选工作流生成")).to_be_focused()
        source.click()
        page.get_by_role("option", name="当前空间的工作流", exact=True).click()
        workflow_search.fill("上次搜索")
        picker.get_by_role("button", name="关闭", exact=True).click()
        expect(generate_button).to_be_focused()
        generate_button.click()
        expect(workflow_search).to_have_value("")
        expect(source).to_have_text("公共工作流")
        for label in ("当前空间的工作流", "公共工作流"):
            source.click()
            page.get_by_role("option", name=label, exact=True).click()
            expect(source).to_have_text(label)
            source_box, search_box = source.bounding_box(), workflow_search.bounding_box()
            dialog_box = picker.bounding_box()
            assert source_box["y"] == search_box["y"]
            assert source_box["height"] == search_box["height"] == control_height
            assert source_box["x"] + source_box["width"] < search_box["x"]
            assert search_box["x"] + search_box["width"] <= dialog_box["x"] + dialog_box["width"]
        workflow_search.fill(workflow["name"])
        candidate = picker.get_by_role("button", name=workflow["name"], exact=True)
        expect(candidate).to_be_visible()
        page.screenshot(path=tmp_path / "project-workflow-picker.png", animations="disabled")
        picker.get_by_role("button", name="清除搜索", exact=True).click()
        expect(workflow_search).to_have_value("")
        expect(workflow_search).to_be_focused()
        candidate.click()
        detail = page.get_by_role("dialog", name=workflow["name"], exact=True)
        select_project = detail.get_by_role("button", name="项目", exact=True)
        expect(select_project).to_have_text("夏季新品主图")
        prompt = detail.get_by_label("提示词", exact=True)
        prompt.fill("新品主图")
        with page.expect_response(
            lambda response: (
                urlsplit(response.url).path == f"{API}/tasks" and response.request.method == "POST"
            )
        ) as submitted:
            detail.get_by_role("button", name="生成", exact=True).click()
        assert submitted.value.status == 201, submitted.value.text()
        task = submitted.value.json()
        assert task["projectId"] == first
        complete_official_artifact(web, task, "project-output.png", picture("green"))
        detail.get_by_role("button", name="关闭", exact=True).click()
        page.get_by_role("tab", name="结果", exact=True).click()
        result_card = page.get_by_role("button", name=f"查看 {workflow['name']}", exact=False)
        result_card.click()
        result = page.get_by_role("dialog", name=workflow["name"], exact=True)
        result.get_by_role("button", name="发布作品", exact=True).click()
        publish = page.get_by_role("dialog", name="发布作品", exact=True)
        publish.get_by_role("textbox", name="名称", exact=True).fill("交付主图")
        publish.get_by_role("button", name="发布作品", exact=True).click()
        expect(publish).to_have_count(0)
        result.get_by_role("button", name="关闭", exact=True).click()
        page.get_by_role("tab", name="作品", exact=True).click()
        expect(page.get_by_role("button", name="查看作品 交付主图")).to_be_visible()

        nav.get_by_role("link", name="工作流", exact=True).click()
        page.get_by_role("button", name=workflow["name"], exact=True).click()
        expect(select_project).to_have_text("无项目")
        expect(select_project).to_have_accessible_description("无项目")
        prompt.fill("保留这段提示词")
        select_project.click()
        select_menu = page.get_by_role("menu", name="项目", exact=True)
        expect(select_menu.get_by_role("menuitemradio", name="无项目")).to_have_attribute(
            "aria-checked", "true"
        )
        page.screenshot(path=tmp_path / "project-select-menu.png", animations="disabled")
        select_menu.get_by_role("menuitem", name="新建项目", exact=True).click()
        second = create("补充素材")
        expect(select_project).to_have_text("补充素材")
        expect(select_project).to_be_focused()
        expect(prompt).to_have_value("保留这段提示词")
        detail.get_by_role("button", name="关闭", exact=True).click()
        page.goto(project_url)
        result_card.click()
        result.get_by_role("button", name="归入项目", exact=True).click()
        assignment = page.get_by_role("dialog", name="归入项目")
        assignment.get_by_role("button", name="项目", exact=True).click()
        select_menu.get_by_role("menuitemradio", name="补充素材", exact=True).click()
        assignment.get_by_role("button", name="保存", exact=True).click()
        expect(result).to_have_count(0)
        expect(page.get_by_text("暂无结果", exact=True)).to_be_visible()
        page.get_by_role("tab", name="作品", exact=True).click()
        switch_project.click()
        menu = page.get_by_role("menu", name="切换项目")
        menu_projects = menu.get_by_role("menuitemradio")
        expect(menu_projects).to_have_text(["夏季新品主图", "补充素材"])
        expect(menu_projects.first).to_have_attribute("aria-checked", "true")
        page.screenshot(path=tmp_path / "project-menu.png", animations="disabled")
        menu_projects.nth(1).click()
        expect(page).to_have_url(f"{address}/projects/{second}?tab=works")
        expect(page.get_by_role("button", name="查看作品 交付主图")).to_be_visible()
        nav.get_by_role("link", name="项目", exact=True).click()
        other_card = page.get_by_role("link", name="补充素材", exact=True)
        expect(project_card.locator('img[data-loaded="true"]')).to_be_visible()
        expect(other_card.locator('img[data-loaded="true"]')).to_be_visible()
        page.screenshot(path=tmp_path / "project-index.png", animations="disabled")
        project_search.fill("补充")
        expect(project_card).to_have_count(0)
        expect(other_card).to_be_visible()
        page.get_by_role("main").get_by_role("button", name="清除搜索", exact=True).click()
        expect(project_search).to_be_focused()
        expect(project_card).to_be_visible()
        open_space_picker(page).get_by_role("button", name=team["name"], exact=True).click()
        expect(page).to_have_url(f"{address}/projects")
        expect(page.get_by_text("还没有项目", exact=True)).to_be_visible()
        page.get_by_role("button", name="新建项目", exact=True).click()
        team_project = create("团队交付")
        expect(page).to_have_url(f"{address}/projects/{team_project}")
        assert item_ids(web.get(f"{API}/projects", params={"workspace_team": team["id"]})) == {
            team_project
        }
        if width == 1280:
            for index in range(1, 26):
                create_project(web, f"团队项目 {index}", {"workspace_team": team["id"]})
            generate_button.click()
            picker.get_by_role("button", name=workflow["name"], exact=True).click()
            expect(select_project).to_have_text("团队交付")
            select_project.click()
            choices = select_menu.get_by_role("menuitemradio")
            expect(choices.first).to_have_text("无项目")
            expect(select_menu.get_by_role("menuitemradio", name="团队交付")).to_have_attribute(
                "aria-checked", "true"
            )
            expect(select_menu.get_by_role("menuitem", name="加载更多")).to_be_enabled()

            def project_page(url: str) -> bool:
                link = urlsplit(url)
                return link.path == f"{API}/projects" and "cursor=" in link.query

            page.route(
                project_page,
                lambda route: route.fulfill(status=503, json={"detail": "未能加载下一页"}),
            )
            select_menu.evaluate("element => { element.scrollTop = element.scrollHeight; }")
            retry = select_menu.get_by_role("menuitem", name="重试", exact=True)
            expect(retry).to_be_visible()
            page.unroute(project_page)
            with page.expect_request(lambda request: project_page(request.url)):
                retry.press("Enter")
            expect(choices).to_have_count(27)
            select_menu.get_by_role("menuitemradio", name="团队项目 1", exact=True).click()
            expect(select_project).to_have_text("团队项目 1")
            detail.get_by_role("button", name="关闭", exact=True).click()

            switch_project.click()
            expect(menu_projects.first).to_have_text("团队交付")
            expect(menu_projects.first).to_have_attribute("aria-checked", "true")
            expect(
                menu.get_by_role("menuitemradio", name="团队项目 25", exact=True)
            ).to_be_visible()
            expect(menu_projects).to_have_count(26)


@pytest.mark.parametrize(
    ("width", "team_space"), [(1280, True), (320, False)], ids=["desktop-team", "narrow-personal"]
)
def test_project_management_in_browser(settings, width, team_space, tmp_path):
    settings.static_dir = WEB_DIST
    with (
        serve_test_app(settings) as (address, web),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        credentials = register(web, "project-management")
        team = None
        scope = {}
        if team_space:
            team = web.post(f"{API}/teams", json={"name": "交付团队"}).raise_for_status().json()
            scope = {"workspace_team": team["id"]}
        project = create_project(web, "海报制作", scope)
        project_path = f"{API}/projects/{project['id']}"
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 844},
            locale="zh-CN",
            is_mobile=width < 700,
            has_touch=width < 700,
            reduced_motion="reduce",
        )
        assert page.request.post(
            f"{API}/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/")
        if team is not None:
            open_space_picker(page).get_by_role("button", name=team["name"], exact=True).click()
        projects = page.get_by_role("navigation", name="主导航").get_by_role(
            "link", name="项目", exact=True
        )
        projects.click()
        page.get_by_role("link", name="海报制作", exact=True).click()
        heading = page.get_by_role("heading", level=1)
        actions = page.get_by_role("button", name="项目操作")
        expect(heading).to_have_text("海报制作")
        assert actions.bounding_box()["height"] == (44 if width == 320 else 40)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

        writes = []

        def track_project_write(request):
            path = urlsplit(request.url).path
            if path.startswith(project_path) and request.method in {"PUT", "DELETE", "POST"}:
                writes.append((request.method, path))

        page.on("request", track_project_write)

        def choose(label):
            actions.click()
            page.get_by_role("menuitem", name=label, exact=True).click()

        choose("编辑项目")
        editor = page.get_by_role("dialog", name="编辑项目")
        name = editor.get_by_role("textbox", name="项目名称")
        description = editor.get_by_role("textbox", name="简介（选填）")
        save = editor.get_by_role("button", name="保存", exact=True)
        expect(name).to_have_value("海报制作")
        expect(save).to_be_disabled()
        name.fill("交付海报")
        description.fill("一组已交付的活动海报")
        page.screenshot(path=tmp_path / "project-edit.png", animations="disabled")
        save.click()
        expect(heading).to_have_text("交付海报")
        expect(page.get_by_text("一组已交付的活动海报", exact=True)).to_be_visible()
        expect(actions).to_be_focused()

        choose("归档项目")
        archive = page.get_by_role("alertdialog", name="归档「交付海报」？")
        archive.get_by_role("button", name="归档项目", exact=True).click()
        expect(archive).to_have_count(0)
        expect(actions).to_be_focused()
        expect(page.get_by_text("已归档", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="选工作流生成")).to_have_count(0)
        page.get_by_role("tab", name="工作流", exact=True).click()
        expect(page.get_by_role("button", name="关联工作流", exact=True)).to_have_count(0)
        projects.click()
        card = page.get_by_role("link", name="交付海报", exact=True)
        expect(page.get_by_text("还没有项目", exact=True)).to_be_visible()
        expect(card).to_have_count(0)
        status = page.get_by_role("combobox", name="项目状态")
        status.click()
        page.get_by_role("option", name="已归档", exact=True).click()
        expect(card).to_be_visible()
        expect(status).to_have_text("已归档")
        page.screenshot(path=tmp_path / "project-archive-list.png", animations="disabled")
        card.click()

        choose("恢复项目")
        restore = page.get_by_role("alertdialog", name="恢复「交付海报」？")
        restore.get_by_role("button", name="恢复项目", exact=True).click()
        expect(page.get_by_role("button", name="选工作流生成")).to_be_visible()
        expect(restore).to_have_count(0)

        choose("删除项目")
        deletion = page.get_by_role("alertdialog", name="删除项目")
        deletion.get_by_role("button", name="取消", exact=True).click()
        expect(actions).to_be_focused()
        expect(heading).to_have_text("交付海报")
        choose("删除项目")
        expect(deletion).to_be_visible()
        page.screenshot(path=tmp_path / "project-delete.png", animations="disabled")
        deletion.get_by_role("button", name="确认删除").click()
        expect(page).to_have_url(f"{address}/projects")
        expect(page.get_by_text("还没有项目", exact=True)).to_be_visible()
        assert page.request.get(project_path, params=scope).status == 404
        page.get_by_role("button", name="撤销", exact=True).click()
        expect(card).to_be_visible()
        card.click()
        expect(heading).to_have_text("交付海报")
        assert writes == [
            ("PUT", project_path),
            ("PUT", f"{project_path}/archive"),
            ("PUT", f"{project_path}/archive"),
            ("DELETE", project_path),
            ("POST", f"{project_path}/restore"),
        ]
