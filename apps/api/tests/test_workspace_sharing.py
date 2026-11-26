"""验证整个「我的」的账户级授权，包括真实的分页、详情和媒体读取。"""

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from helpers import report_inventory, serve_test_app, sync_machine, task_body
from httpx import Client
from playwright.sync_api import expect, sync_playwright
from test_inputs import picture
from test_inputs import prepared as prepared
from test_outputs import run_group
from test_worker import claim_body

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
PASSWORD = "workspace-test-password"
ORIGIN = "http://testserver"


def register_account(client, username):
    session = (
        client.post("/api/v1/auth/register", json={"username": username, "password": PASSWORD})
        .raise_for_status()
        .json()
    )
    client.headers["X-CSRF-Token"] = session["csrfToken"]
    return session["user"]["id"]


def create_workflow(client, graph, name):
    return (
        client.post("/api/v1/workflows", json={"name": name, "graph": graph})
        .raise_for_status()
        .json()
    )


def upload_picture(client, filename, color, *, saved=False):
    return (
        client.put(
            f"/api/v1/assets/{uuid4()}",
            params={"filename": filename, "save_to_library": saved},
            content=picture(color),
        )
        .raise_for_status()
        .json()
    )


def workspace_records(client, worker, machine_id, graph, *, keep_work_public=False):
    workflow = create_workflow(client, graph, "空间里的工作流")
    workflow_path = f"/api/v1/workflows/{workflow['id']}"
    client.put(workflow_path + "/favorite").raise_for_status()
    task = (
        client.post("/api/v1/tasks", json=task_body(client, workflow, machine_id))
        .raise_for_status()
        .json()
    )
    claim = claim_body()
    worker.post("/api/v1/worker/claim", json=claim).raise_for_status()
    execution, (artifact,) = run_group(client, worker, task["id"], claim["leaseSecret"], members=1)
    client.post(workflow_path + "/publish").raise_for_status()
    asset = upload_picture(client, "素材.png", "blue", saved=True)
    execution = (
        client.put(f"/api/v1/executions/{execution['id']}/cover", json={"assetId": asset["id"]})
        .raise_for_status()
        .json()
    )
    work = (
        client.post(
            "/api/v1/works",
            json={
                "id": str(uuid4()),
                "executionId": execution["id"],
                "title": "空间里的作品",
                "artifactIds": [artifact["id"]],
                "executionCoverSha256": execution["coverImage"]["sha256"],
            },
        )
        .raise_for_status()
        .json()
    )
    if not keep_work_public:
        client.delete(f"/api/v1/works/{work['id']}").raise_for_status()
    return workflow, task, execution, artifact, work, asset


def test_workspace_grant_controls_lists_details_and_media(authenticated, graph):
    owner = authenticated
    owner_id = owner.get("/api/v1/auth/session").json()["user"]["id"]
    machine = (
        owner.post("/api/v1/machines", json={"name": "共享测试工作机"}).raise_for_status().json()
    )
    worker = sync_machine(owner, machine)
    workflow, task, execution, artifact, work, asset = workspace_records(
        owner, worker, machine["machine"]["id"], graph
    )
    unsubmitted = upload_picture(owner, "未提交.png", "red")
    viewer = TestClient(owner.app, headers={"Origin": ORIGIN})
    viewer_id = register_account(viewer, "viewer")
    stranger = TestClient(owner.app, headers={"Origin": ORIGIN})
    register_account(stranger, "stranger")
    guest = TestClient(owner.app)
    scope = {"workspace_owner": owner_id}
    url = f"/api/v1/workspace/shared/{owner_id}"
    assert viewer.get(url).status_code == 404
    assert guest.get(url).status_code == 401
    assert viewer.get(artifact["media"]["src"]).status_code == 404

    for name in ("VIEWER", "viewer"):
        assert owner.put(f"/api/v1/workspace/shares/by-name/{name}").status_code == 204
    assert owner.get("/api/v1/workspace/shares", params={"direction": "sent"}).json()["items"] == [
        {"id": viewer_id, "username": "viewer"}
    ]
    assert viewer.get("/api/v1/workspace/shares", params={"direction": "received"}).json()[
        "items"
    ] == [{"id": owner_id, "username": "owner"}]
    assert viewer.get(url).json() == {"id": owner_id, "username": "owner"}

    draft = create_workflow(owner, graph, "授权后新增的草稿")
    published_path = f"/api/v1/workflows/{workflow['id']}"
    update = {**graph, "1": {**graph["1"], "inputs": {"text": "新版本"}}}
    new_version = owner.patch(published_path, json={"graph": update}).raise_for_status().json()
    assert viewer.get(published_path).json()["versionId"] == workflow["versionId"]
    assert viewer.get(published_path, params=scope).json()["versionId"] == new_version["versionId"]
    collections = [
        ("/api/v1/workflows", {"scope": "favorites"}, {workflow["id"]}),
        ("/api/v1/workflows", {"scope": "mine"}, {workflow["id"], draft["id"]}),
        ("/api/v1/works", {"scope": "mine"}, {work["id"]}),
        ("/api/v1/executions", {}, {execution["id"]}),
        ("/api/v1/assets", {}, {asset["id"]}),
        ("/api/v1/tasks", {}, {task["id"]}),
    ]
    for path, params, expected in collections:
        query = {**scope, **params}
        assert stranger.get(path, params=query).status_code == 404
        assert guest.get(path, params=query).status_code == 401
        items = viewer.get(path, params=query).raise_for_status().json()["items"]
        assert {item["id"] for item in items} == expected
        assert viewer.get(path, params=params).raise_for_status().json()["items"] == []

    workflow_path = f"/api/v1/workflows/{draft['id']}"
    work_path = f"/api/v1/works/{work['id']}"
    task_path = f"/api/v1/tasks/{task['id']}"
    execution_path = f"/api/v1/executions/{execution['id']}"
    asset_path = f"/api/v1/assets/{asset['id']}"
    details = [
        workflow_path,
        workflow_path + "/versions",
        workflow_path + "/graph",
        work_path,
        work_path + "/artifacts",
        work_path + "/inputs",
        task_path,
        task_path + "/progress",
        task_path + "/inputs",
        execution_path,
        asset_path,
    ]
    for path in details:
        assert viewer.get(path, params=scope).status_code == 200, path
        assert stranger.get(path, params=scope).status_code == 404, path
    assert viewer.get(workflow_path).status_code == 404
    assert (
        viewer.get("/api/v1/artifacts", params={**scope, "execution_id": execution["id"]}).json()[
            "items"
        ][0]["id"]
        == artifact["id"]
    )

    media = [
        asset["media"]["src"],
        asset["media"]["thumbnail"]["src"],
        artifact["media"]["src"],
        artifact["media"]["thumbnail"]["src"],
        execution["coverImage"]["src"],
        work["coverImage"]["src"],
    ]
    for path in media:
        assert viewer.get(path).status_code == 200, path
        assert stranger.get(path).status_code == 404, path
    cached = viewer.get(asset["media"]["thumbnail"]["src"])
    assert viewer.get(unsubmitted["media"]["src"]).status_code == 404
    assert viewer.delete(workflow_path, params=scope).status_code == 404
    assert viewer.delete(work_path, params=scope).status_code == 404
    assert viewer.post(task_path + "/cancel", params=scope).status_code == 404
    assert viewer.delete(asset_path + "/library", params=scope).status_code == 404
    assert viewer.delete(execution_path + "/artifacts", params=scope).status_code == 404
    assert (
        viewer.get("/api/v1/workspace/shares", params={"direction": "sent"}).json()["items"] == []
    )

    assert owner.delete(f"/api/v1/workspace/shares/{viewer_id}").status_code == 204
    assert viewer.get(url).status_code == 404
    for path, params, _ in collections:
        assert viewer.get(path, params={**scope, **params}).status_code == 404
    for path in media:
        assert viewer.get(path).status_code == 404, path
    assert (
        viewer.get(
            asset["media"]["thumbnail"]["src"], headers={"If-None-Match": cached.headers["etag"]}
        ).status_code
        == 404
    )
    assert owner.get(artifact["media"]["src"]).status_code == 200


def test_shared_task_inputs_require_a_visible_record(prepared):
    owner, _, _, _, _, asset, body, _ = prepared
    owner_id = owner.get("/api/v1/auth/session").json()["user"]["id"]
    viewer = TestClient(owner.app, headers={"Origin": ORIGIN})
    register_account(viewer, "task-reader")
    owner.put("/api/v1/workspace/shares/by-name/task-reader").raise_for_status()
    file = asset["media"]["src"]
    scope = {"workspace_owner": owner_id}
    assert viewer.get(file).status_code == 404

    task = owner.post("/api/v1/tasks", json=body).raise_for_status().json()
    path = f"/api/v1/tasks/{task['id']}"
    assert viewer.get(path + "/inputs", params=scope).json()["assets"][0]["id"] == asset["id"]
    assert viewer.get(file).status_code == 200

    owner.post(path + "/cancel").raise_for_status()
    owner.delete(path).raise_for_status()
    assert viewer.get(path + "/inputs", params=scope).status_code == 404
    assert viewer.get(file).status_code == 404


@pytest.mark.parametrize("width", [1280, 390, 320], ids=["desktop", "mobile", "narrow"])
def test_workspace_sharing_in_browser(settings, graph, width, tmp_path):
    assert (WEB_DIST / "index.html").is_file(), "请先构建网页"
    with serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, owner):
        owner_id = register_account(owner, "space-owner")
        with Client(base_url=address, headers={"Origin": address}, trust_env=False) as viewer:
            register_account(viewer, "space-reader")
            viewer.put("/api/v1/workspace/shares/by-name/space-owner").raise_for_status()
        machine = owner.post("/api/v1/machines", json={"name": "工作机"}).raise_for_status().json()
        with Client(
            base_url=address,
            headers={"Authorization": "Bearer " + machine["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker)
            *_, asset = workspace_records(owner, worker, machine["machine"]["id"], graph)
        draft = create_workflow(owner, graph, "私有草稿")
        owner.patch(
            f"/api/v1/workflows/{draft['id']}", json={"description": "空间所有者填写的简介"}
        ).raise_for_status()
        with sync_playwright() as playwright, playwright.chromium.launch() as browser:
            context = {
                "base_url": address,
                "viewport": {"width": width, "height": 844},
                "locale": "zh-CN",
                "has_touch": width < 700,
                "is_mobile": width < 700,
                "reduced_motion": "reduce",
            }
            sender = browser.new_page(**context)
            sender.add_init_script(
                """Object.defineProperty(navigator, 'clipboard', {
                    value: { writeText: async (url) => { window.copiedWorkspaceUrl = url; } },
                });"""
            )
            recipient = browser.new_page(**context)
            height = "44px" if width <= 700 else "40px"
            for page, username in [(sender, "space-owner"), (recipient, "space-reader")]:
                response = page.request.post(
                    "/api/v1/auth/login",
                    headers={"Origin": address},
                    data={"username": username, "password": PASSWORD},
                )
                assert response.ok, response.text()
                page.goto("/workspace")
                sharing = page.get_by_role("button", name="共享空间", exact=True)
                tab = page.get_by_role("tab", name="收藏", exact=True)
                expect(tab).to_have_css("height", height)
                expect(sharing).to_have_css("height", height)
                expect(sharing).to_have_css("border-radius", "0px")
                tab_box, sharing_box, toolbar_box = (
                    tab.bounding_box(),
                    sharing.bounding_box(),
                    page.locator("main .tabbed-toolbar").bounding_box(),
                )
                assert tab_box and sharing_box and toolbar_box
                assert sharing_box["x"] + sharing_box["width"] == pytest.approx(
                    toolbar_box["x"] + toolbar_box["width"]
                )
                if width >= 1200:
                    assert sharing_box["y"] == pytest.approx(tab_box["y"])
                else:
                    assert sharing_box["y"] > tab_box["y"]
                sharing.click()
            dialog = sender.get_by_role("dialog", name="共享空间")
            sent = dialog.get_by_role("region", name="已授权账号")
            received = dialog.get_by_role("region", name="与我共享")
            account = sent.get_by_role("textbox", name="账号")
            grant = sent.get_by_role("button", name="授权查看")
            copy_link = sent.get_by_role("button", name="复制共享链接")
            space_link = received.get_by_role("link", name="space-reader", exact=True)
            expect(space_link).to_have_accessible_description("只读")
            expect(space_link).to_have_css("height", height)
            expect(copy_link).to_have_count(0)
            expect(dialog).to_have_css("border-radius", "0px")
            expect(dialog).to_have_css("width", f"{min(680, width - 32)}px")
            for control in (account, grant, dialog.get_by_role("button", name="关闭")):
                expect(control).to_have_css("height", height)
            account_box, grant_box = account.bounding_box(), grant.bounding_box()
            assert account_box and grant_box and account_box["y"] == pytest.approx(grant_box["y"])
            account.fill("space-reader")
            grant.click()
            revoke = sent.get_by_role("button", name="撤销 space-reader 的访问权限")
            expect(revoke).to_be_visible()
            expect(revoke).to_have_css("height", "44px" if width <= 700 else "34px")
            expect(copy_link).to_have_css("height", height)
            assert dialog.evaluate("(node) => node.scrollWidth <= node.clientWidth + 1")
            sent_list = sent.get_by_role("list").bounding_box()
            received_list = received.get_by_role("list").bounding_box()
            assert sent_list and received_list
            assert sent_list["x"] == pytest.approx(received_list["x"])
            assert sent_list["width"] == pytest.approx(received_list["width"])
            dialog.screenshot(path=tmp_path / "workspace-sharing.png")
            share_path = f"/workspace/shared/{owner_id}/favorites"
            sender.bring_to_front()
            copy_link.click()
            expect(sender.get_by_text("已复制共享空间", exact=True)).to_be_visible()
            assert sender.evaluate("window.copiedWorkspaceUrl") == address + share_path
            sender.evaluate(
                "() => { navigator.clipboard.writeText = async () => { throw new Error(); }; }"
            )
            copy_link.click()
            manual_link = sender.get_by_role("textbox", name="共享空间", exact=True)
            expect(manual_link).to_have_value(address + share_path)
            expect(manual_link).to_be_focused()
            sender.keyboard.press("Escape")
            expect(manual_link).to_have_count(0)
            expect(copy_link).to_be_focused()

            recipient.get_by_role("dialog", name="共享空间").get_by_role(
                "button", name="关闭", exact=True
            ).click()
            recipient.get_by_role("button", name="共享空间", exact=True).click()
            open_shared = recipient.get_by_role("link", name="space-owner", exact=True)
            expect(open_shared).to_have_attribute("href", share_path)
            open_shared.click()
            expect(recipient.get_by_role("dialog", name="共享空间")).to_have_count(0)
            expect(
                recipient.get_by_role("heading", name="space-owner 的空间（只读）")
            ).to_be_visible()
            expect(recipient.get_by_role("button", name="空间里的工作流")).to_be_visible()
            tabs = recipient.get_by_role("tablist", name="我的内容")
            for label in ("收藏", "工作流", "作品", "结果", "资产库", "任务"):
                expect(tabs.get_by_role("tab", name=label, exact=True)).to_be_visible()
            tabs.get_by_role("tab", name="工作流", exact=True).click()
            recipient.get_by_role("button", name="私有草稿", exact=True).click()
            detail = recipient.get_by_role("dialog", name="私有草稿")
            expect(detail).to_be_visible()
            expect(detail.get_by_role("button", name="生成", exact=True)).to_have_count(0)
            expect(detail.get_by_role("button", name="下载 JSON", exact=True)).to_be_visible()
            if width < 700:
                detail.get_by_role("button", name="工作流信息").click()
            expect(detail.get_by_text("空间所有者填写的简介")).to_be_visible()
            detail.get_by_role("button", name="关闭", exact=True).click()
            assert draft["published"] is False

            tabs.get_by_role("tab", name="作品", exact=True).click()
            expect(recipient.get_by_text("空间里的作品", exact=True)).to_be_visible()
            tabs.get_by_role("tab", name="结果", exact=True).click()
            recipient.get_by_role("button", name="查看 空间里的工作流", exact=False).click()
            result = recipient.get_by_role("dialog", name="空间里的工作流")
            expect(result.get_by_role("link", name="下载原文件")).to_be_visible()
            expect(result.get_by_role("button", name="发布作品", exact=True)).to_have_count(0)
            result.get_by_role("link", name="查看来源任务").click()
            source = recipient.get_by_role("dialog", name="任务详情")
            expect(source).to_be_visible()
            source.get_by_role("button", name="关闭", exact=True).click()
            expect(result).to_be_visible()
            result.get_by_role("button", name="关闭", exact=True).click()
            assets_tab = tabs.get_by_role("tab", name="资产库", exact=True)
            assets_tab.click()
            search = recipient.get_by_role("searchbox", name="搜索文件名")
            kind = recipient.get_by_role("combobox", name="素材类型")
            expect(search).to_have_css("height", height)
            expect(kind).to_have_css("height", height)
            search_box, kind_box, tab_box = (
                search.bounding_box(),
                kind.bounding_box(),
                assets_tab.bounding_box(),
            )
            assert search_box and kind_box and tab_box
            assert search_box["y"] == pytest.approx(kind_box["y"])
            assert search_box["x"] + search_box["width"] < kind_box["x"]
            if width >= 1200:
                assert search_box["y"] == pytest.approx(tab_box["y"])
            else:
                assert search_box["y"] >= tab_box["y"] + tab_box["height"]
            expect(recipient.get_by_label("上传素材")).to_have_count(0)
            search.fill("无匹配的文件名")
            expect(recipient.get_by_text("没有符合条件的素材", exact=True)).to_be_visible()
            expect(kind).to_be_visible()
            search.clear()
            recipient.get_by_role("button", name="预览 素材.png").click()
            preview = recipient.get_by_role("dialog", name="素材.png")
            expect(preview.get_by_role("img", name="素材.png")).to_have_js_property(
                "naturalWidth", 32
            )
            expect(preview.get_by_role("button", name="移出资产库")).to_have_count(0)
            preview.get_by_role("button", name="关闭", exact=True).click()
            tabs.get_by_role("tab", name="任务", exact=True).click()
            recipient.get_by_role("button", name="任务详情", exact=True).click()
            task = recipient.get_by_role("dialog", name="任务详情")
            expect(task.get_by_role("tab", name="提交参数")).to_be_visible()
            expect(task.get_by_role("button", name="删除任务记录")).to_have_count(0)
            task.get_by_role("button", name="关闭", exact=True).click()
            assert recipient.locator("body").evaluate("(node) => node.scrollWidth <= innerWidth")
            recipient.screenshot(path=tmp_path / "workspace-read-only.png")

            owner.delete(f"/api/v1/assets/{asset['id']}/library").raise_for_status()
            recipient.goto(f"/workspace/shared/{owner_id}/assets")
            expect(recipient.get_by_text("资产库还没有素材", exact=True)).to_be_visible()
            expect(search).to_have_count(0)
            expect(kind).to_have_count(0)
            expect(recipient.get_by_label("上传素材")).to_have_count(0)

            revoke.click()
            expect(revoke).to_have_count(0)
            expect(copy_link).to_have_count(0)
            recipient.goto(f"/workspace/shared/{owner_id}/assets")
            expect(recipient.get_by_role("alert")).to_contain_text("此共享空间不可访问")
            expect(recipient.get_by_role("button", name="预览 素材.png")).to_have_count(0)
