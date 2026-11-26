"""普通工作机入口在个人及团队空间中的权限、接入和素材归属。"""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from helpers import machine_heartbeat, report_inventory, serve_test_app, sync_machine
from httpx import Client
from playwright.sync_api import expect, sync_playwright
from sqlalchemy.orm import Session
from test_inputs import picture
from test_inputs import prepared as prepared
from test_team_spaces import API, add_member, open_space_picker
from test_worker import claim_body
from test_workspace_sharing import ORIGIN, PASSWORD, WEB_DIST, register_account

from comfyshop_api.models import Machine, WorkflowVersion
from comfyshop_api.schemas import AssetReference
from comfyshop_api.services.inputs import compile_inputs


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_work_machines_belong_to_one_space_and_managers_control_them(client):
    register_account(client, "machine-owner")
    first, second = [
        client.post(f"{API}/teams", json={"name": name}).raise_for_status().json()["id"]
        for name in ("摄影组", "视频组")
    ]
    team = f"{API}/teams/{first}"
    scope = {"workspace_team": first}
    members = {}
    for role in ("reader", "editor", "manager"):
        member = TestClient(client.app, headers={"Origin": ORIGIN})
        member_id = register_account(member, f"machine-{role}")
        assert add_member(client, team, f"machine-{role}", role).status_code == 204
        members[role] = (member, member_id)
    manager, manager_id = members["manager"]
    personal = client.post(f"{API}/machines", json={"name": "个人工作机"}).raise_for_status()
    created = manager.post(f"{API}/machines", params=scope, json={"name": "团队工作机"})
    assert created.status_code == 201
    key = created.raise_for_status().json()
    machine_id = key["machine"]["id"]
    machine_path = f"{API}/machines/{machine_id}"
    worker = sync_machine(manager, key)
    assert worker.post(f"{API}/worker/claim", json=claim_body()).raise_for_status().json() is None

    for role in ("reader", "editor"):
        member, _ = members[role]
        view = member.get(machine_path, params=scope).raise_for_status().json()
        assert view["machine"]["online"]
        assert view["queuedCount"] == 0
        assert "apiKey" not in view["machine"]
        assert (
            member.post(f"{API}/machines", params=scope, json={"name": "无权添加"}).status_code
            == 403
        )
        assert (
            member.patch(machine_path, params=scope, json={"name": "无权修改"}).status_code == 403
        )
        assert member.post(machine_path + "/rotate", params=scope).status_code == 403

    listing = client.get(f"{API}/machines", params=scope).raise_for_status().json()
    assert [item["id"] for item in listing["items"]] == [machine_id]
    assert listing["defaultMachineId"] == machine_id
    personal_listing = client.get(f"{API}/machines").raise_for_status().json()
    assert listing["connectionTypes"] == personal_listing["connectionTypes"]
    personal_id = personal.json()["machine"]["id"]
    assert personal_listing["defaultMachineId"] == personal_id
    assert client.get(f"{API}/machines/{personal_id}", params=scope).status_code == 404
    assert client.get(machine_path).status_code == 404
    assert client.get(machine_path, params={"workspace_team": second}).status_code == 404
    assert client.put(f"{API}/machines/{personal_id}/default", params=scope).status_code == 404
    assert client.put(machine_path + "/default").status_code == 404

    assert client.delete(f"{team}/members/{manager_id}").status_code == 204
    assert manager.get(machine_path, params=scope).status_code == 404
    assert worker.post(f"{API}/worker/heartbeat", json=machine_heartbeat()).status_code == 200
    assert client.patch(machine_path, params=scope, json={"name": "共享渲染机"}).status_code == 204
    assert (
        client.put(machine_path + "/pause", params=scope, json={"paused": True}).status_code == 204
    )
    view = client.get(machine_path, params=scope).json()["machine"]
    assert (view["name"], view["paused"]) == ("共享渲染机", True)
    rotated = client.post(machine_path + "/rotate", params=scope).raise_for_status().json()
    assert worker.post(f"{API}/worker/heartbeat", json=machine_heartbeat()).status_code == 401
    current_worker = sync_machine(client, rotated)
    assert client.delete(team).status_code == 204
    assert (
        current_worker.post(f"{API}/worker/heartbeat", json=machine_heartbeat()).status_code == 401
    )
    assert client.get(f"{API}/machines").json()["defaultMachineId"] == personal_id


def test_connection_code_targets_the_selected_team_and_preserves_reconnect(client):
    register_account(client, "link-owner")
    owner_machine = client.post(f"{API}/machines", json={"name": "个人机"}).raise_for_status()
    personal_id = owner_machine.json()["machine"]["id"]
    team_id = client.post(f"{API}/teams", json={"name": "连接组"}).raise_for_status().json()["id"]
    scope = {"workspace_team": team_id}
    manager = TestClient(client.app, headers={"Origin": ORIGIN})
    register_account(manager, "link-manager")
    assert (
        add_member(client, f"{API}/teams/{team_id}", "link-manager", "manager").status_code == 204
    )

    def pair(approval):
        request = client.post(f"{API}/worker/links", json={"name": "渲染节点"}).raise_for_status()
        link = request.json()
        path = f"{API}/machines/links/{link['code']}"
        assert manager.get(path, params=scope).json()["status"] == "pending"
        assert (
            manager.post(
                path + "/approve", params=scope, json={"machineId": personal_id}
            ).status_code
            == 404
        )
        assert manager.post(path + "/approve", params=scope, json=approval).status_code == 204
        assert manager.get(path).status_code == 404
        assert manager.get(path, params=scope).json()["status"] == "approved"
        redeemed = client.post(f"{API}/worker/links/token", json={"secret": link["secret"]})
        assert manager.get(path, params=scope).json()["status"] == "linked"
        return redeemed.raise_for_status().json()["apiKey"]

    key = pair({"name": "团队渲染机"})
    listing = client.get(f"{API}/machines", params=scope).raise_for_status().json()
    machine_id = listing["defaultMachineId"]
    assert [item["id"] for item in listing["items"]] == [machine_id]
    assert key != pair({"machineId": machine_id})
    listing = client.get(f"{API}/machines", params=scope).raise_for_status().json()
    assert [item["id"] for item in listing["items"]] == [machine_id]
    assert client.delete(f"{API}/machines/{machine_id}", params=scope).status_code == 200
    assert client.get(f"{API}/machines", params=scope).json()["defaultMachineId"] is None
    for _ in range(2):
        assert client.delete(f"{API}/machines/{machine_id}/record", params=scope).status_code == 204
    assert client.get(f"{API}/machines", params=scope).json()["items"] == []


def test_team_workflow_form_and_materials_are_bound_to_the_machine_space(prepared):
    owner, _, original, _, _, personal_asset, personal_body, catalog = prepared
    team_id = owner.post(f"{API}/teams", json={"name": "素材组"}).raise_for_status().json()["id"]
    team = f"{API}/teams/{team_id}"
    scope = {"workspace_team": team_id}
    editor = TestClient(owner.app, headers={"Origin": ORIGIN})
    register_account(editor, "form-editor")
    assert add_member(owner, team, "form-editor", "editor").status_code == 204
    workflow = owner.post(f"{team}/workflows/{original['id']}/copy").raise_for_status().json()
    created = owner.post(f"{API}/machines", params=scope, json={"name": "团队图像机"})
    native_machine = created.raise_for_status().json()
    team_id_machine = native_machine["machine"]["id"]
    sync_machine(owner, native_machine, catalog)
    asset = (
        editor.put(
            f"{team}/assets/{uuid4()}",
            params={"filename": "团队参考.png"},
            content=picture("blue"),
        )
        .raise_for_status()
        .json()
    )
    form_path = f"{API}/workflows/{workflow['id']}/inputs"
    form = editor.get(form_path, params={**scope, "machine_id": team_id_machine})
    assert form.status_code == 200, form.text
    image = next(field for field in form.json()["fields"] if field["kind"] == "image")
    assert (
        editor.get(
            form_path, params={**scope, "machine_id": personal_body["machineId"]}
        ).status_code
        == 404
    )
    assert (
        owner.get(
            f"{API}/workflows/{original['id']}/inputs", params={"machine_id": team_id_machine}
        ).status_code
        == 404
    )
    assert (
        owner.post(f"{API}/tasks", json={**personal_body, "machineId": team_id_machine}).status_code
        == 409
    )
    assert owner.get(f"{API}/assets/{personal_asset['id']}", params=scope).status_code == 404
    assert editor.get(f"{API}/assets/{asset['id']}", params=scope).status_code == 200

    with Session(owner.app.state.engine) as db:
        version = db.get_one(WorkflowVersion, workflow["versionId"])
        machine = db.get_one(Machine, team_id_machine)
        _, _, _, bindings = compile_inputs(
            db, version, machine, {image["id"]: AssetReference(asset_id=asset["id"])}, None
        )
        assert [binding.asset_id for binding in bindings] == [asset["id"]]
        with pytest.raises(HTTPException) as denied:
            compile_inputs(
                db,
                version,
                machine,
                {image["id"]: AssetReference(asset_id=personal_asset["id"])},
                None,
            )
        assert denied.value.status_code == 404


@pytest.mark.parametrize("width", [1280, 390, 320], ids=["desktop", "mobile", "narrow"])
def test_team_work_machine_pairing_from_existing_page(settings, width, tmp_path):
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, api),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        register_account(api, "pairing-owner")
        team = api.post(f"{API}/teams", json={"name": "数字栩生"}).raise_for_status().json()
        api.post(f"{API}/machines", json={"name": "个人工作机"}).raise_for_status()
        request = (
            api.post(f"{API}/worker/links", json={"name": "团队渲染机"}).raise_for_status().json()
        )
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 844},
            locale="zh-CN",
            has_touch=width < 700,
            is_mobile=width < 700,
            reduced_motion="reduce",
        )
        login = page.request.post(
            f"{API}/auth/login",
            data={"username": "pairing-owner", "password": PASSWORD},
            headers={"Origin": address},
        )
        assert login.ok
        page.goto("/machines")
        add = page.get_by_role("button", name="添加工作机", exact=True)
        expect(add).to_have_css("height", "44px" if width < 700 else "40px")
        add.click()
        page.get_by_role("menuitem", name="输入接入代码", exact=True).click()
        dialog = page.get_by_role("dialog", name="接入工作机", exact=True)
        dialog.get_by_role("textbox", name="接入代码", exact=True).fill(request["code"])
        dialog.get_by_role("button", name="继续", exact=True).click()
        dialog.get_by_role("combobox", name="接入方式", exact=True).click()
        page.get_by_role("option").filter(has_text="个人工作机").click()
        expect(dialog.get_by_role("button", name="重新连接", exact=True)).to_be_enabled()
        dialog.get_by_role("button", name="我的", exact=True).click()
        picker = page.get_by_role("dialog", name="切换空间", exact=True)
        picker.get_by_role("button", name=team["name"], exact=True).click()
        expect(dialog.get_by_role("button", name=team["name"], exact=True)).to_be_visible()
        expect(page).to_have_url(f"{address}/machines/link?code={request['code']}")
        approve = dialog.get_by_role("button", name="确认接入", exact=True)
        expect(approve).to_be_enabled()
        assert dialog.evaluate("(node) => node.scrollWidth <= node.clientWidth + 1")
        dialog.screenshot(path=tmp_path / "team-machine-pairing.png", animations="disabled")
        with page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and f"/links/{request['code']}/approve" in response.url
            )
        ) as approval:
            approve.click()
        assert approval.value.status == 204
        assert f"workspace_team={team['id']}" in approval.value.url
        token = (
            api.post(f"{API}/worker/links/token", json={"secret": request["secret"]})
            .raise_for_status()
            .json()
        )
        with Client(
            base_url=address,
            headers={"Authorization": "Bearer " + token["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker)
        dialog.get_by_role("button", name="完成", exact=True).click()
        expect(page).to_have_url(f"{address}/machines")
        expect(page.get_by_role("button", name="团队渲染机", exact=True)).to_be_visible()
        expect(page.get_by_role("status", name="连接状态")).to_have_text("在线")
        expect(page.get_by_text("默认", exact=True)).to_be_visible()
        expect(page.get_by_text("个人工作机", exact=True)).to_have_count(0)
        assert page.locator("body").evaluate("(node) => node.scrollWidth <= innerWidth")
        page.screenshot(path=tmp_path / "team-machine-list.png", animations="disabled")
        open_space_picker(page).get_by_role("button", name="我的", exact=True).click()
        expect(page.get_by_role("button", name="个人工作机", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="团队渲染机", exact=True)).to_have_count(0)


@pytest.mark.parametrize("team_workspace", [False, True], ids=["personal", "team"])
def test_work_machine_list_updates_after_returning_before_redemption(settings, team_workspace):
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, api),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        register_account(api, "link-refresh-owner")
        scope = {}
        if team_workspace:
            team = api.post(f"{API}/teams", json={"name": "渲染团队"}).raise_for_status().json()
            scope = {"workspace_team": team["id"]}
        api.post(f"{API}/machines", params=scope, json={"name": "已有工作机"}).raise_for_status()
        request = (
            api.post(f"{API}/worker/links", json={"name": "新工作机"}).raise_for_status().json()
        )
        context = browser.new_context(base_url=address, locale="zh-CN")
        approval = context.new_page()
        approval.goto(f"/machines/link?code={request['code']}")
        login = approval.get_by_role("dialog", name="登录", exact=True)
        login.get_by_label("账号", exact=True).fill("link-refresh-owner")
        login.get_by_label("密码", exact=True).fill(PASSWORD)
        login.get_by_role("button", name="登录", exact=True).click()
        dialog = approval.get_by_role("dialog", name="接入工作机", exact=True)
        expect(dialog).to_be_visible()
        if team_workspace:
            dialog.get_by_role("button", name="我的", exact=True).click()
            approval.get_by_role("dialog", name="切换空间", exact=True).get_by_role(
                "button", name="渲染团队", exact=True
            ).click()
        dialog.get_by_role("combobox", name="接入方式", exact=True).click()
        approval.get_by_role("option", name="新增工作机", exact=True).click()

        listing = context.new_page()
        listing.goto("/machines")
        if team_workspace:
            open_space_picker(listing).get_by_role("button", name="渲染团队", exact=True).click()
        expect(listing.get_by_role("button", name="已有工作机", exact=True)).to_be_visible()
        approval.bring_to_front()
        dialog.get_by_role("button", name="确认接入", exact=True).click()
        dialog.get_by_role("button", name="返回工作机列表", exact=True).click()
        expect(approval).to_have_url(f"{address}/machines")
        listing.bring_to_front()

        token = api.post(f"{API}/worker/links/token", json={"secret": request["secret"]})
        with Client(
            base_url=address,
            headers={"Authorization": "Bearer " + token.raise_for_status().json()["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker)
        expect(listing.get_by_role("button", name="新工作机", exact=True)).to_be_visible(
            timeout=4500
        )
        approval.bring_to_front()
        expect(approval.get_by_role("button", name="新工作机", exact=True)).to_be_visible(
            timeout=4500
        )
        new_machine = approval.get_by_role("article").filter(
            has=approval.get_by_role("button", name="新工作机", exact=True)
        )
        expect(new_machine.get_by_role("status", name="连接状态")).to_have_text("在线")
