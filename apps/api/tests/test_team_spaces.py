"""团队空间的角色、内容归属和浏览器入口。"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from helpers import report_inventory, serve_test_app, sync_machine
from httpx import Client
from PIL import Image
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_inputs import picture
from test_workspace_sharing import (
    ORIGIN,
    PASSWORD,
    WEB_DIST,
    create_workflow,
    register_account,
    upload_picture,
    workspace_records,
)

from comfyshop_api.models import (
    Asset,
    Team,
    TeamEvent,
    TeamFavorite,
    TeamMember,
    TeamRole,
    Workflow,
)

API = "/api/v1"


def add_member(client, team, username, role):
    return client.put(f"{team}/members/by-name/{username}", json={"role": role})


def item_ids(response):
    return {item["id"] for item in response.raise_for_status().json()["items"]}


def open_space_picker(page):
    page.locator("header .account-button").click()
    page.get_by_role("menuitem", name="切换空间", exact=True).click()
    return page.get_by_role("dialog", name="切换空间", exact=True)


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_public_workflow_favorites_use_team_scope(client, graph):
    register_account(client, "catalog-owner")
    machine = client.post(f"{API}/machines", json={"name": "测试工作机"}).raise_for_status().json()
    public, _, _, _, work, _ = workspace_records(
        client,
        sync_machine(client, machine),
        machine["machine"]["id"],
        graph,
        keep_work_public=True,
    )
    path = f"{API}/workflows/{public['id']}"
    other_graph = {**graph, "2": {**graph["2"], "inputs": {**graph["2"]["inputs"], "seed": 24}}}
    draft = client.patch(path, json={"graph": other_graph}).raise_for_status().json()
    private = create_workflow(client, graph, "个人私有")
    teams = [
        client.post(f"{API}/teams", json={"name": name}).raise_for_status().json()["id"]
        for name in ("摄影组", "视频组")
    ]
    first, second = teams
    scope = {"workspace_team": first}
    team_path = f"{API}/teams/{first}"
    favorite = f"{team_path}/workflows/{public['id']}/favorite"
    assert client.delete(path + "/favorite").status_code == 204

    assert client.put(f"{team_path}/workflows/{private['id']}/favorite").status_code == 404
    assert client.get(path, params=scope).json()["versionId"] == public["versionId"]
    assert client.get(path, params={**scope, "version_id": draft["versionId"]}).status_code == 404
    assert client.get(path + "/versions", params=scope).json()["items"] == [
        {"id": public["versionId"], "number": 1, "published": True}
    ]
    # 所选空间可查看公共作品，也需要按当前已发布状态检查详情。
    work_path = f"{API}/works/{work['id']}"
    assert client.get(work_path, params=scope).status_code == 200
    assert client.get(work_path + "/artifacts", params=scope).status_code == 200
    client.delete(work_path).raise_for_status()
    assert client.get(work_path, params=scope).status_code == 404

    for _ in range(2):
        assert client.put(favorite).status_code == 204
    assert client.get(f"{API}/workspace", params=scope).json()["favoriteIds"] == [public["id"]]
    assert client.get(f"{API}/workspace").json()["favoriteIds"] == []
    assert (
        client.get(f"{API}/workspace", params={"workspace_team": second}).json()["favoriteIds"]
        == []
    )
    response = client.get(f"{API}/workflows", params={**scope, "scope": "favorites"})
    assert item_ids(response) == {public["id"]}
    assert response.json()["items"][0]["versionId"] == public["versionId"]
    assert response.json()["items"][0]["teamId"] is None

    reader = TestClient(client.app, headers={"Origin": ORIGIN})
    reader_id = register_account(reader, "catalog-reader")
    assert add_member(client, team_path, "catalog-reader", "reader").status_code == 204
    assert item_ids(reader.get(f"{API}/workflows", params={**scope, "scope": "favorites"})) == {
        public["id"]
    }
    assert reader.delete(favorite).status_code == 403
    assert client.delete(f"{team_path}/members/{reader_id}").status_code == 204
    assert reader.get(path, params=scope).status_code == 404

    assert client.delete(path).status_code == 204
    assert not item_ids(client.get(f"{API}/workflows", params={**scope, "scope": "favorites"}))
    assert client.get(f"{API}/workspace", params=scope).json()["favoriteIds"] == []


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_private_member_avatar_follows_active_team_membership(client):
    owner_id = register_account(client, "avatar-owner")
    reader = TestClient(client.app, headers={"Origin": ORIGIN})
    reader_id = register_account(reader, "avatar-reader")
    visitor = TestClient(client.app)
    reader.post(f"{API}/teams", json={"name": "读者的团队"}).raise_for_status()
    target = client.post(f"{API}/teams", json={"name": "合作者的团队"}).raise_for_status()
    team = f"{API}/teams/{target.json()['id']}"
    client.put(f"{API}/auth/profile", json={"nickname": "摄影师"}).raise_for_status()
    profile = client.put(f"{API}/auth/profile/avatar", content=picture("blue")).raise_for_status()
    avatar = profile.json()["avatarUrl"]

    assert reader.get(f"{team}/members").status_code == 404
    assert reader.get(avatar).status_code == 404
    assert add_member(client, team, "avatar-reader", "reader").status_code == 204
    roster = reader.get(f"{team}/members").raise_for_status().json()["items"]
    owner = next(member for member in roster if member["id"] == owner_id)
    assert owner == {
        "id": owner_id,
        "username": "avatar-owner",
        "nickname": "摄影师",
        "avatarUrl": avatar,
        "role": "owner",
    }
    response = reader.get(avatar).raise_for_status()
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "private, no-cache"
    cached = {"If-None-Match": response.headers["etag"]}
    assert reader.get(avatar, headers=cached).status_code == 304
    assert visitor.get(avatar).status_code == 404
    assert reader.get(f"{API}/authors/avatar-owner").status_code == 404

    assert client.delete(f"{team}/members/{reader_id}").status_code == 204
    assert reader.get(avatar, headers=cached).status_code == 404
    assert add_member(client, team, "avatar-reader", "reader").status_code == 204
    assert reader.get(avatar).status_code == 200
    assert client.delete(team).status_code == 204
    assert reader.get(avatar, headers=cached).status_code == 404


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_team_profile_follows_team_roles_and_avatar_version(client):
    owner_id = register_account(client, "profile-owner")
    team = client.post(f"{API}/teams", json={"name": "原团队"}).raise_for_status().json()
    path = f"{API}/teams/{team['id']}"
    manager, editor, reader, outsider = [
        TestClient(client.app, headers={"Origin": ORIGIN}) for _ in range(4)
    ]
    manager_id = register_account(manager, "profile-manager")
    register_account(editor, "profile-editor")
    reader_id = register_account(reader, "profile-reader")
    register_account(outsider, "profile-outsider")
    for role in ("manager", "editor", "reader"):
        assert add_member(client, path, "profile-" + role, role).status_code == 204

    assert team["avatarUrl"] is None
    for actor, status in ((reader, 403), (editor, 403), (outsider, 404)):
        assert actor.patch(path, json={"name": "任意队名"}).status_code == status
        assert actor.put(path + "/avatar", content=b"invalid image").status_code == status
        assert actor.delete(path + "/avatar").status_code == status
    for name in ("  ", "长" * 81):
        assert manager.patch(path, json={"name": name}).status_code == 422
    renamed = manager.patch(path, json={"name": "  数字栩生  "}).raise_for_status().json()
    assert (renamed["id"], renamed["name"], renamed["role"]) == (team["id"], "数字栩生", "manager")
    assert reader.get(path).raise_for_status().json()["name"] == "数字栩生"
    assert reader.get(f"{API}/teams").raise_for_status().json()["items"][0]["name"] == "数字栩生"

    avatar = path + "/avatar"
    assert manager.put(avatar, content=b"<svg/>").status_code == 422
    first = manager.put(avatar, content=picture("red")).raise_for_status().json()["avatarUrl"]
    assert reader.get(path).raise_for_status().json()["avatarUrl"] == first
    assert outsider.get(first).status_code == 404
    assert TestClient(client.app).get(first).status_code == 404
    image = reader.get(first).raise_for_status()
    assert image.headers["content-type"] == "image/webp"
    assert image.headers["cache-control"] == "private, no-cache"
    cached = {"If-None-Match": image.headers["etag"]}
    assert reader.get(first, headers=cached).status_code == 304
    with Image.open(BytesIO(image.content)) as thumbnail:
        assert thumbnail.size == (256, 256)
    assert client.delete(f"{path}/members/{reader_id}").status_code == 204
    assert reader.get(first, headers=cached).status_code == 404

    second = client.put(avatar, content=picture("blue")).raise_for_status().json()["avatarUrl"]
    assert first != second and editor.get(first, headers=cached).status_code == 404
    assert (
        client.put(avatar, content=picture("blue")).raise_for_status().json()["avatarUrl"] == second
    )
    assert client.delete(avatar).raise_for_status().json()["avatarUrl"] is None
    assert editor.get(second).status_code == 404
    third = manager.put(avatar, content=picture("green")).raise_for_status().json()["avatarUrl"]
    assert client.delete(path).status_code == 204
    assert manager.get(third).status_code == 404
    assert manager.patch(path, json={"name": "试改归档团队"}).status_code == 404
    assert client.post(path + "/restore").raise_for_status().json()["avatarUrl"] == third
    assert manager.get(third).status_code == 200
    with Session(client.app.state.engine) as db:
        events = db.execute(
            select(TeamEvent.actor_id, TeamEvent.action).where(
                TeamEvent.team_id == team["id"],
                TeamEvent.action.in_(("team.renamed", "team.avatarUpdated", "team.avatarRemoved")),
            )
        ).all()
        assert sorted(events) == sorted(
            [
                (manager_id, "team.renamed"),
                (manager_id, "team.avatarUpdated"),
                (owner_id, "team.avatarUpdated"),
                (owner_id, "team.avatarRemoved"),
                (manager_id, "team.avatarUpdated"),
            ]
        )


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "narrow"])
def test_team_profile_in_browser(settings, width, tmp_path):
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, api),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        register_account(api, "profile-owner")
        team = api.post(f"{API}/teams", json={"name": "数字栩生"}).raise_for_status().json()
        team_path = f"{API}/teams/{team['id']}"
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 844},
            locale="zh-CN",
            has_touch=width < 700,
            is_mobile=width < 700,
            reduced_motion="reduce",
        )
        signup = page.request.post(
            f"{API}/auth/register",
            data={"username": "profile-manager", "password": PASSWORD},
            headers={"Origin": address},
        )
        assert signup.ok, signup.text()
        headers = {"Origin": address, "X-CSRF-Token": signup.json()["csrfToken"]}
        personal = page.request.put(
            f"{API}/auth/profile/avatar", data=picture("indigo"), headers=headers
        )
        assert personal.ok, personal.text()
        assert add_member(api, team_path, "profile-manager", "manager").status_code == 204

        page.goto(f"/workspace/teams/{team['id']}/workflows?from=bookmark#content")
        workspace_url = f"{address}/workspace/workflows?from=bookmark#content"
        expect(page).to_have_url(workspace_url)
        account = page.locator("header .account-button")
        expect(account).to_have_accessible_name("账户 profile-manager · 数字栩生")
        account.click()
        page.get_by_role("menuitem", name="团队资料", exact=True).click()
        settings = page.get_by_role("dialog", name="团队资料", exact=True)
        name = settings.get_by_role("textbox", name="团队名称")
        save = settings.get_by_role("button", name="保存团队名称", exact=True)
        height = "44px" if width < 700 else "40px"
        expect(settings).to_have_css("border-radius", "0px")
        expect(name).to_have_css("height", height)
        expect(save).to_have_css("height", height)
        expect(save).to_be_disabled()

        writes = []
        page.on(
            "request",
            lambda req: (
                writes.append(req.method)
                if req.method in ("PATCH", "PUT", "DELETE") and team_path in req.url
                else None
            ),
        )
        name.fill("数字栩生 · 内容创作团队")
        save.click()
        expect(settings.get_by_role("status")).to_have_text("团队名称已保存")
        expect(account).to_have_attribute(
            "aria-label", "账户 profile-manager · 数字栩生 · 内容创作团队"
        )
        expect(page).to_have_url(workspace_url)

        picker = settings.locator("input[type=file]")
        picker.set_input_files(
            {"name": "team.png", "mimeType": "image/png", "buffer": picture("seagreen")}
        )
        crop = page.get_by_role("dialog", name="裁剪头像", exact=True)
        zoom = crop.get_by_role("slider", name="缩放")
        expect(zoom).to_be_visible()
        zoom.press("ArrowRight")
        page.screenshot(path=tmp_path / "team-avatar-crop.png", animations="disabled")
        crop.get_by_role("button", name="保存头像", exact=True).click()
        expect(crop).to_be_hidden()
        expect(settings.get_by_text("头像已更新", exact=True)).to_be_visible()
        avatar = account.locator(".account-team-avatar img")
        expect(avatar).to_have_attribute("src", re.compile(team_path + "/avatar/"))
        assert avatar.evaluate("(img) => img.decode().then(() => img.naturalWidth)") == 256
        expect(account.locator(".avatar-small img")).to_have_attribute(
            "src", personal.json()["avatarUrl"]
        )
        page.screenshot(path=tmp_path / "team-profile.png", animations="disabled")
        settings.get_by_role("button", name="关闭", exact=True).click()
        expect(account).to_be_focused()
        spaces = open_space_picker(page)
        selected = spaces.get_by_role("button", name="数字栩生 · 内容创作团队", exact=True)
        expect(selected).to_have_attribute("aria-current", "true")
        expect(selected.locator("img")).to_have_attribute("src", avatar.get_attribute("src"))
        spaces.get_by_role("button", name="关闭", exact=True).click()

        account.click()
        page.get_by_role("menuitem", name="团队资料", exact=True).click()
        settings.get_by_role("button", name="移除头像", exact=True).click()
        expect(account.locator(".account-team-avatar")).to_have_text("数")
        expect(settings.get_by_text("头像已移除", exact=True)).to_be_visible()
        assert writes == ["PATCH", "PUT", "DELETE"]
        name.fill("栩" * 80)
        save.click()
        expect(account).to_have_attribute("aria-label", "账户 profile-manager · " + "栩" * 80)
        assert settings.evaluate("(node) => node.scrollWidth <= node.clientWidth")
        assert page.locator("body").evaluate("(node) => node.scrollWidth <= innerWidth")


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_team_membership_controls_private_content(client, graph):
    owner = client
    owner_id = register_account(owner, "team-owner")
    manager, editor, reader = [TestClient(owner.app, headers={"Origin": ORIGIN}) for _ in range(3)]
    manager_id = register_account(manager, "team-manager")
    editor_id = register_account(editor, "team-editor")
    reader_id = register_account(reader, "team-reader")
    groups = [
        owner.post(f"{API}/teams", json={"name": name}).raise_for_status().json()
        for name in ("设计团队", "视频团队")
    ]
    (first, second) = (team["id"] for team in groups)
    team = f"{API}/teams/{first}"
    other_team = f"{API}/teams/{second}"
    scope = {"workspace_team": first}
    other_scope = {"workspace_team": second}
    assert [group["role"] for group in groups] == ["owner", "owner"]
    first_page = owner.get(f"{API}/teams", params={"limit": 1}).raise_for_status().json()
    next_page = owner.get(f"{API}/teams", params={"cursor": first_page["nextCursor"], "limit": 1})
    assert {first_page["items"][0]["id"], *item_ids(next_page)} == {first, second}
    assert reader.get(team).status_code == 404
    assert TestClient(owner.app).get(f"{API}/workflows", params=scope).status_code == 401
    assert add_member(owner, team, "TEAM-MANAGER", "manager").status_code == 204
    assert add_member(manager, team, "team-editor", "manager").status_code == 403
    assert add_member(manager, team, "team-editor", "editor").status_code == 204
    assert add_member(editor, team, "team-reader", "reader").status_code == 403
    assert add_member(manager, team, "team-reader", "reader").status_code == 204
    assert add_member(manager, team, "team-owner", "reader").status_code == 403
    assert add_member(owner, other_team, "team-reader", "editor").status_code == 204
    assert reader.delete(f"{team}/members/{manager_id}").status_code == 403
    assert manager.put(f"{team}/owner/{reader_id}").status_code == 403
    assert owner.delete(f"{team}/members/{owner_id}").status_code == 409
    assert owner.post(f"{API}/auth/account/delete", json={"password": PASSWORD}).status_code == 409
    assert item_ids(reader.get(f"{team}/members")) == {owner_id, manager_id, editor_id, reader_id}

    body = {"name": "团队草稿", "graph": graph}
    assert reader.post(f"{team}/workflows", json=body).status_code == 403
    workflow = editor.post(f"{team}/workflows", json=body).raise_for_status().json()
    workflow_id = workflow["id"]
    path = f"{API}/workflows/{workflow_id}"
    team_workflow = f"{team}/workflows/{workflow_id}"
    assert workflow["owner"] == editor_id
    assert reader.patch(team_workflow, json={"description": "查看者"}).status_code == 403
    changed = manager.patch(team_workflow, json={"description": "团队资料"}).raise_for_status()
    assert changed.json()["description"] == "团队资料"
    assert reader.put(f"{team_workflow}/favorite").status_code == 403
    assert editor.put(f"{team_workflow}/favorite").status_code == 204
    assert reader.get(f"{API}/workspace", params=scope).json()["favoriteIds"] == [workflow_id]
    assert owner.get(f"{API}/workspace").json()["favoriteIds"] == []
    assert item_ids(reader.get(f"{API}/workflows", params={**scope, "scope": "favorites"})) == {
        workflow_id
    }
    assert reader.get(path, params=scope).raise_for_status().json()["popularity"] == 1
    another = editor.post(f"{team}/workflows", json={**body, "name": "未收藏"}).raise_for_status()
    popular = {**scope, "scope": "mine", "sort": "popular", "limit": 1}
    top = reader.get(f"{API}/workflows", params=popular).raise_for_status().json()
    assert [(item["id"], item["popularity"]) for item in top["items"]] == [(workflow_id, 1)]
    next_page = reader.get(f"{API}/workflows", params={**popular, "cursor": top["nextCursor"]})
    assert item_ids(next_page) == {another.json()["id"]}
    assert editor.delete(f"{team_workflow}/favorite").status_code == 204
    assert reader.get(path, params=scope).raise_for_status().json()["popularity"] == 0
    assert editor.put(f"{team_workflow}/favorite").status_code == 204
    assert item_ids(reader.get(f"{API}/workflows", params=other_scope)) == set()
    assert item_ids(editor.get(f"{API}/workflows", params={"scope": "mine"})) == set()
    for endpoint in (path, path + "/versions", path + "/graph"):
        assert reader.get(endpoint, params=scope).status_code == 200
        assert reader.get(endpoint, params=other_scope).status_code == 404
        assert editor.get(endpoint).status_code == 404
    assert editor.patch(path, json={"name": "从个人空间编辑"}).status_code == 404
    assert editor.put(path + "/favorite").status_code == 404
    assert reader.get(path, params={**scope, "workspace_owner": editor_id}).status_code == 422
    for collection in ("tasks", "executions", "artifacts", "works"):
        assert item_ids(reader.get(f"{API}/{collection}", params=scope)) == set()

    assert editor.delete(f"{team}/members/{editor_id}").status_code == 204
    assert editor.get(path, params=scope).status_code == 404
    assert reader.get(path, params=scope).json()["owner"] == editor_id
    assert editor.post(f"{API}/auth/account/delete", json={"password": PASSWORD}).status_code == 204
    assert reader.get(path, params=scope).json()["description"] == "团队资料"
    assert item_ids(reader.get(f"{API}/workflows", params={**scope, "scope": "favorites"})) == {
        workflow_id
    }
    transferred = owner.put(f"{team}/owner/{manager_id}").raise_for_status()
    assert transferred.json()["role"] == "manager"
    assert manager.get(team).json()["role"] == "owner"
    assert owner.delete(f"{team}/members/{owner_id}").status_code == 204
    assert owner.get(path, params=scope).status_code == 404
    assert manager.delete(team).status_code == 204
    assert reader.get(path, params=scope).status_code == 404
    assert item_ids(reader.get(f"{API}/teams")) == {second}
    with Session(owner.app.state.engine) as db:
        assert db.get_one(Team, first).created_by_id == owner_id
        assert db.get_one(TeamFavorite, (first, workflow_id)).added_by_id == editor_id
        persisted = db.get_one(Workflow, workflow_id)
        assert (persisted.team_id, persisted.owner_id, persisted.deleted_at) == (
            first,
            editor_id,
            None,
        )
        changes = dict(
            db.execute(
                select(TeamEvent.action, TeamEvent.actor_id).where(
                    TeamEvent.team_id == first, TeamEvent.record_id == workflow_id
                )
            ).all()
        )
        assert changes == {
            "workflow.created": editor_id,
            "workflow.updated": manager_id,
            "favorite.added": editor_id,
            "favorite.removed": editor_id,
        }


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_team_copies_and_media_use_team_scope(client, settings, graph):
    owner_id = register_account(client, "copy-owner")
    editor = TestClient(client.app, headers={"Origin": ORIGIN})
    register_account(editor, "copy-editor")
    reader = TestClient(client.app, headers={"Origin": ORIGIN})
    reader_id = register_account(reader, "copy-reader")
    groups = [
        client.post(f"{API}/teams", json={"name": name}).raise_for_status().json()["id"]
        for name in ("复制组", "隔离组")
    ]
    first, second = groups
    team = f"{API}/teams/{first}"
    other_team = f"{API}/teams/{second}"
    scope = {"workspace_team": first}
    other_scope = {"workspace_team": second}
    assert add_member(client, team, "copy-editor", "editor").status_code == 204
    assert add_member(client, team, "copy-reader", "reader").status_code == 204
    assert add_member(client, other_team, "copy-reader", "reader").status_code == 204

    original = create_workflow(client, graph, "个人草稿")
    workflow_id = original["id"]
    newer_graph = {**graph, "1": {**graph["1"], "inputs": {"text": "新版本"}}}
    client.patch(f"{API}/workflows/{workflow_id}", json={"graph": newer_graph}).raise_for_status()
    copy_path = f"{team}/workflows/{workflow_id}/copy"
    assert editor.post(copy_path).status_code == 404
    copied = (
        client.post(copy_path, params={"version_id": original["versionId"]})
        .raise_for_status()
        .json()
    )
    assert copied["id"] != workflow_id
    assert copied["version"] == 1 and not copied["published"]
    graph_path = f"{API}/workflows/{copied['id']}/graph"
    assert reader.get(graph_path, params=scope).raise_for_status().json()["graph"] == graph
    assert reader.get(graph_path, params=other_scope).status_code == 404

    personal = upload_picture(client, "个人素材.png", "blue", saved=True)
    asset_path = f"{team}/assets/{personal['id']}/copy"
    assert editor.post(asset_path).status_code == 404
    asset = client.post(asset_path).raise_for_status().json()
    assert asset["id"] != personal["id"]
    assert client.post(asset_path).raise_for_status().json()["id"] == asset["id"]
    image = picture("blue")
    different_image = picture("red")
    settings.asset_quota_bytes = max(len(image), len(different_image))
    request_id = uuid4()
    same_image = f"{team}/assets/{request_id}"
    filename = {"filename": "重复上传.png"}
    assert reader.put(same_image, params=filename, content=image).status_code == 403
    assert editor.put(same_image, params=filename, content=image).json()["id"] == asset["id"]
    assert (
        editor.put(f"{team}/assets/{uuid4()}", params=filename, content=different_image).status_code
        == 413
    )
    other_asset = (
        client.put(f"{other_team}/assets/{uuid4()}", params=filename, content=different_image)
        .raise_for_status()
        .json()
    )
    assert item_ids(reader.get(f"{API}/assets", params=other_scope)) == {other_asset["id"]}
    assert item_ids(reader.get(f"{API}/assets", params=scope)) == {asset["id"]}
    assert item_ids(client.get(f"{API}/assets")) == {personal["id"]}
    details = f"{API}/assets/{asset['id']}"
    assert reader.get(details, params=scope).status_code == 200
    assert reader.get(details, params=other_scope).status_code == 404
    assert client.get(details).status_code == 404
    assert client.delete(details + "/library").status_code == 404

    workflow_cover = f"{team}/workflows/{copied['id']}/cover"
    assert reader.put(workflow_cover, json={"assetId": asset["id"]}).status_code == 403
    assert editor.put(workflow_cover, json={"assetId": personal["id"]}).status_code == 404
    assert editor.put(workflow_cover, json={"assetId": other_asset["id"]}).status_code == 404
    settings.asset_quota_bytes += len(different_image)
    cover_upload = (
        editor.put(
            f"{team}/assets/{uuid4()}",
            params={"filename": "仅用于封面.png", "save_to_library": False},
            content=different_image,
        )
        .raise_for_status()
        .json()
    )
    assert cover_upload["savedAt"] is None
    cover = (
        editor.put(workflow_cover, json={"assetId": cover_upload["id"]})
        .raise_for_status()
        .json()["media"]
    )
    assert item_ids(reader.get(f"{API}/assets", params=scope)) == {asset["id"]}
    media = [asset["media"]["src"], asset["media"]["thumbnail"]["src"], cover["thumbnail"]["src"]]
    assert reader.get(media[0]).raise_for_status().content == image
    for url in media:
        assert reader.get(url).status_code == 200
    assert client.delete(f"{team}/members/{reader_id}").status_code == 204
    for url in media:
        assert reader.get(url).status_code == 404
        assert editor.get(url).status_code == 200
    assert reader.get(details, params=scope).status_code == 404
    assert reader.get(graph_path, params=scope).status_code == 404
    assert reader.get(other_asset["media"]["src"]).status_code == 200
    assert client.delete(f"{API}/assets/{personal['id']}/library").status_code == 204
    assert editor.get(media[0]).raise_for_status().content == image
    with Session(client.app.state.engine) as db:
        persisted = db.get_one(Asset, asset["id"])
        assert (persisted.team_id, persisted.owner_id) == (first, owner_id)


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_team_transfer_and_account_deletion_keep_one_owner(client):
    owner_id = register_account(client, "transfer-owner")
    target = TestClient(client.app, headers={"Origin": ORIGIN})
    target_id = register_account(target, "transfer-editor")
    team_id = client.post(f"{API}/teams", json={"name": "团队"}).raise_for_status().json()["id"]
    team = f"{API}/teams/{team_id}"
    assert add_member(client, team, "transfer-editor", "editor").status_code == 204
    start = Barrier(2, timeout=10)

    def transfer():
        start.wait()
        return client.put(f"{team}/owner/{target_id}").status_code

    def delete():
        start.wait()
        return target.post(f"{API}/auth/account/delete", json={"password": PASSWORD}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        transfer_request = pool.submit(transfer)
        delete_request = pool.submit(delete)
        outcome = (transfer_request.result(timeout=15), delete_request.result(timeout=15))

    assert outcome in {(200, 409), (404, 204)}
    with Session(client.app.state.engine) as db:
        owners = list(
            db.scalars(
                select(TeamMember.user_id).where(
                    TeamMember.team_id == team_id, TeamMember.role == TeamRole.OWNER
                )
            )
        )
        assert owners == [target_id if outcome[0] == 200 else owner_id]


@pytest.mark.parametrize("width", [1280, 390, 320], ids=["desktop", "mobile", "narrow"])
def test_team_spaces_in_browser(settings, graph, width, tmp_path):
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, _),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        pages = [
            browser.new_page(
                base_url=address,
                viewport={"width": width, "height": 844},
                locale="zh-CN",
                has_touch=width < 700,
                is_mobile=width < 700,
                reduced_motion="reduce",
            )
            for _ in range(2)
        ]
        owner, reader = pages
        for page, name in zip(pages, ("browser-owner", "browser-reader"), strict=True):
            response = page.request.post(
                f"{API}/auth/register",
                data={"username": name, "password": PASSWORD},
                headers={"Origin": address},
            )
            assert response.ok, response.text()
            if page is reader:
                headers = {"Origin": address, "X-CSRF-Token": response.json()["csrfToken"]}
                assert page.request.put(
                    f"{API}/auth/profile", data={"nickname": "影像合作者"}, headers=headers
                ).ok
                avatar = page.request.put(
                    f"{API}/auth/profile/avatar",
                    data=picture("blue"),
                    headers={**headers, "Content-Type": "image/png"},
                )
                assert avatar.ok, avatar.text()
            page.goto("/workspace/workflows")

        height = "44px" if width < 700 else "40px"
        account_button = owner.locator("header .account-button")
        expect(account_button).to_have_css("height", height)
        spaces = open_space_picker(owner)
        expect(spaces).to_have_css("width", f"{min(680, width - 32)}px")
        expect(spaces).to_have_css("border-radius", "0px")
        personal = spaces.get_by_role("button", name="我的", exact=True)
        expect(personal).to_have_attribute("aria-current", "true")
        name = spaces.get_by_role("textbox", name="团队名称")
        create = spaces.get_by_role("button", name="创建团队")
        expect(name).to_have_count(0)
        expect(create).to_have_css("height", height)
        create.click()
        expect(name).to_be_focused()
        name.press("Escape")
        expect(name).to_have_count(0)
        expect(create).to_be_focused()
        create.click()
        expect(name).to_have_css("height", height)
        expect(create).to_have_css("height", height)
        name.fill("摄影团队")
        create.click()
        members_button = owner.get_by_role("button", name="团队成员", exact=True)
        expect(members_button).to_have_css("height", height)
        expect(account_button).to_have_css("height", height)
        expect(account_button).to_have_accessible_name("账户 browser-owner · 摄影团队")
        expect(owner).to_have_url(f"{address}/workspace/workflows")
        expect(account_button.locator(".account-team-avatar")).to_have_text("摄")
        members_box, toolbar_box = (
            members_button.bounding_box(),
            owner.locator("main .tabbed-toolbar").bounding_box(),
        )
        assert members_box and toolbar_box
        assert members_box["x"] + members_box["width"] == pytest.approx(
            toolbar_box["x"] + toolbar_box["width"]
        )
        if width >= 1200:
            workflow_tab = owner.get_by_role("tab", name="工作流", exact=True).bounding_box()
            assert workflow_tab and members_box["y"] == pytest.approx(workflow_tab["y"])
        owner.screenshot(path=tmp_path / "team-toolbar.png")
        open_space_picker(owner)
        team_space = spaces.get_by_role("button", name="摄影团队", exact=True)
        expect(team_space).to_have_attribute("aria-current", "true")
        expect(team_space).to_have_accessible_description("所有者")
        expect(team_space).to_have_css("height", height)
        assert spaces.evaluate("(dialog) => dialog.scrollWidth <= dialog.clientWidth + 1")
        owner.screenshot(path=tmp_path / "team-switcher.png", animations="disabled")
        spaces.get_by_role("button", name="关闭", exact=True).click()
        expect(account_button).to_be_focused()
        members_button.click()
        members = owner.get_by_role("dialog", name="「摄影团队」的成员")
        expect(members).to_have_css("width", f"{min(680, width - 32)}px")
        expect(members).to_have_css("border-radius", "0px")
        account = members.get_by_role("textbox", name="成员账号")
        role = members.get_by_role("combobox", name="成员角色", exact=True)
        add = members.get_by_role("button", name="添加成员")
        for control in (account, role, add):
            expect(control).to_have_css("height", height)
        account.fill("browser-reader")
        add.click()
        roster = members.get_by_role("list", name="团队成员")
        expect(roster.get_by_role("listitem").first.get_by_text("你", exact=True)).to_be_visible()
        row = roster.get_by_role("listitem").filter(has_text="影像合作者")
        expect(row.get_by_text("@browser-reader", exact=True)).to_be_visible()
        expect(row.locator("img")).to_have_js_property("naturalWidth", 256)
        menu = row.get_by_role("button", name="browser-reader 的操作")
        member_role = row.get_by_role("combobox", name="browser-reader 的角色")
        for control in (menu, member_role):
            expect(control).to_have_css("height", "44px" if width < 700 else "34px")
        assert members.evaluate("(dialog) => dialog.scrollWidth <= dialog.clientWidth + 1")
        owner.screenshot(path=tmp_path / "team-members.png")

        for label in ("编辑者", "查看者"):
            member_role.click()
            owner.get_by_role("option", name=label, exact=True).click()
            expect(member_role).to_have_text(label)
            expect(member_role).to_be_enabled()
        menu.click()
        owner.get_by_role("menuitem", name="转让所有权").click()
        transfer = owner.get_by_role("alertdialog", name="将所有权转让给 browser-reader")
        transfer.get_by_role("button", name="取消").click()
        expect(transfer).to_be_hidden()
        expect(menu).to_be_focused()
        members.get_by_role("button", name="关闭", exact=True).click()

        owner.get_by_role("button", name="导入工作流", exact=True).click()
        importing = owner.get_by_role("dialog", name="导入工作流")
        expect(importing.get_by_role("radiogroup")).to_have_count(0)
        importing.locator('input[type="file"]').set_input_files(
            {
                "name": "团队测试图.json",
                "mimeType": "application/json",
                "buffer": json.dumps(graph).encode(),
            }
        )
        importing.get_by_role("button", name="导入工作流", exact=True).click()
        workflow = owner.get_by_role("dialog", name="团队测试图", exact=True)
        expect(workflow).to_be_visible()
        workflow.get_by_role("button", name="更多操作").click()
        owner.get_by_role("menuitem", name="编辑工作流").click()
        settings_dialog = owner.get_by_role("dialog", name="编辑工作流")
        settings_dialog.get_by_role("textbox", name="简介").fill("成员可见的团队工作流")
        settings_dialog.get_by_role("button", name="保存", exact=True).click()
        expect(settings_dialog).to_be_hidden()
        workflow.get_by_role("button", name="关闭", exact=True).click()
        bookmark = owner.get_by_role("button", name="收藏 团队测试图", exact=True)
        bookmark.click()
        expect(bookmark).to_have_count(0)
        owner.get_by_role("tab", name="资产库").click()
        owner.get_by_label("上传素材", exact=True).set_input_files(
            {"name": "团队素材.png", "mimeType": "image/png", "buffer": picture("blue")}
        )
        expect(owner.get_by_role("button", name="预览 团队素材.png")).to_be_visible()

        open_space_picker(reader).get_by_role("button", name="摄影团队", exact=True).click()
        expect(reader.get_by_role("tab", name="工作流", exact=True)).to_have_attribute(
            "aria-selected", "true"
        )
        expect(reader.get_by_role("button", name="导入工作流", exact=True)).to_have_count(0)
        reader.get_by_role("button", name="团队成员", exact=True).click()
        read_roster = reader.get_by_role("dialog", name="「摄影团队」的成员")
        expect(read_roster.get_by_text("查看者", exact=True)).to_be_visible()
        expect(read_roster.get_by_role("combobox")).to_have_count(0)
        expect(read_roster.get_by_role("button", name="添加成员")).to_have_count(0)
        expect(read_roster.get_by_role("button", name="browser-owner 的操作")).to_have_count(0)
        read_roster.get_by_role("button", name="关闭", exact=True).click()
        reader.get_by_role("tab", name="收藏").click()
        reader.get_by_role("button", name="团队测试图", exact=True).click()
        readonly = reader.get_by_role("dialog", name="团队测试图", exact=True)
        expect(readonly.get_by_role("button", name="下载 JSON")).to_be_visible()
        expect(readonly.get_by_role("button", name="更多操作")).to_have_count(0)
        expect(readonly.get_by_role("button", name="生成", exact=True)).to_have_count(0)
        readonly.get_by_role("button", name="关闭", exact=True).click()
        tabs = reader.get_by_role("tablist", name="我的内容")
        for label in ("收藏", "工作流", "作品", "结果", "资产库", "任务"):
            expect(tabs.get_by_role("tab", name=label, exact=True)).to_be_visible()
        reader.get_by_role("tab", name="资产库").click()
        expect(reader.get_by_label("上传素材", exact=True)).to_have_count(0)
        reader.get_by_role("button", name="预览 团队素材.png").click()
        asset = reader.get_by_role("dialog", name="团队素材.png")
        expect(asset.get_by_role("link", name="下载原文件")).to_be_visible()
        asset.get_by_role("button", name="关闭", exact=True).click()
        assert reader.locator("body").evaluate("(node) => node.scrollWidth <= innerWidth")
        reader.screenshot(path=tmp_path / "team-reader.png")
        open_space_picker(reader).get_by_role("button", name="我的", exact=True).click()
        expect(reader.get_by_role("button", name="共享空间", exact=True)).to_be_visible()
        expect(reader).to_have_url(f"{address}/workspace/assets")
        expect(reader.get_by_role("button", name="预览 团队素材.png")).to_have_count(0)

        if width == 1280:
            members_button.click()
            menu.click()
            owner.get_by_role("menuitem", name="移除", exact=True).click()
            remove = owner.get_by_role("alertdialog", name="移除成员 browser-reader？")
            remove.get_by_role("button", name="移除", exact=True).click()
            expect(remove).to_be_hidden()
            expect(row).to_have_count(0)
            expect(members.get_by_role("button", name="关闭", exact=True)).to_be_focused()

        if width == 390:
            open_space_picker(owner).get_by_role("button", name="我的", exact=True).click()
            expect(owner.get_by_text("资产库还没有素材", exact=True)).to_be_visible()
            expect(owner).to_have_url(f"{address}/workspace/assets")
            owner.get_by_label("上传素材", exact=True).set_input_files(
                {"name": "个人素材.png", "mimeType": "image/png", "buffer": picture("red")}
            )
            owner.get_by_role("button", name="预览 个人素材.png").click()
            owner.get_by_role("button", name="复制到团队", exact=True).click()
            copy = owner.get_by_role("dialog", name="复制到团队")
            copy.get_by_role("button", name="复制到「摄影团队」").click()
            expect(copy).to_be_hidden()
            open_space_picker(reader).get_by_role("button", name="摄影团队", exact=True).click()
            expect(reader.get_by_role("button", name="预览 个人素材.png")).to_be_visible()


@pytest.mark.parametrize("width", [1280, 390], ids=["desktop", "mobile"])
def test_global_space_picker_and_catalog_favorites_in_browser(settings, graph, width, tmp_path):
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, api),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        register_account(api, "catalog-owner")
        machine = api.post(f"{API}/machines", json={"name": "个人工作机"}).raise_for_status().json()
        with Client(
            base_url=address,
            headers={"Authorization": "Bearer " + machine["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker)
            public, *_ = workspace_records(
                api, worker, machine["machine"]["id"], graph, keep_work_public=True
            )
        personal_favorite = f"{API}/workflows/{public['id']}/favorite"
        api.delete(personal_favorite).raise_for_status()
        first, second = [
            api.post(f"{API}/teams", json={"name": name}).raise_for_status().json()
            for name in ("数字栩生", "影像团队")
        ]
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
            data={"username": "catalog-owner", "password": PASSWORD},
            headers={"Origin": address},
        )
        assert login.ok, login.text()
        page.goto("/")
        account = page.locator("header .account-button")
        navigation = page.get_by_role("navigation", name="主导航")
        workspace_link = navigation.get_by_role("link", name="我的", exact=True)
        machines_link = navigation.get_by_role("link", name="工作机", exact=True)
        favorites_url = f"{address}/workspace/favorites"
        machines_url = f"{address}/machines"

        def check_workspace_urls():
            for label, tab in (
                ("工作流", "workflows"),
                ("作品", "artworks"),
                ("结果", "results"),
                ("资产库", "assets"),
                ("任务", "tasks"),
                ("收藏", "favorites"),
            ):
                page.get_by_role("tab", name=label, exact=True).click()
                expect(page).to_have_url(f"{address}/workspace/{tab}")

        open_space_picker(page).get_by_role("button", name=first["name"], exact=True).click()
        expect(page).to_have_url(f"{address}/")
        expect(account).to_have_accessible_name("账户 catalog-owner · 数字栩生")
        expect(account.locator(".account-team-avatar")).to_be_visible()
        assert page.locator("body").evaluate("(node) => node.scrollWidth <= innerWidth")

        add = page.get_by_role("button", name="收藏 空间里的工作流", exact=True)
        saved = page.get_by_role("button", name="取消收藏 空间里的工作流", exact=True)
        writes = []
        page.on(
            "request",
            lambda request: (
                writes.append((request.method, request.url))
                if request.method in ("PUT", "DELETE") and request.url.endswith("/favorite")
                else None
            ),
        )
        add.click()
        expect(saved).to_have_attribute("aria-pressed", "true")
        expect(page.get_by_text("已收藏到「数字栩生」", exact=True)).to_be_visible()
        assert writes == [
            ("PUT", f"{address}{API}/teams/{first['id']}/workflows/{public['id']}/favorite")
        ]
        account.click()
        expect(page.get_by_text("catalog-owner · 所有者", exact=True)).to_be_visible()
        expect(page.get_by_role("menuitem", name="团队作品", exact=True)).to_have_attribute(
            "href", "/workspace/artworks"
        )
        page.screenshot(path=tmp_path / "global-workspace-menu.png", animations="disabled")
        page.keyboard.press("Escape")
        expect(workspace_link).to_have_attribute("href", "/workspace")
        workspace_link.click()
        expect(page).to_have_url(favorites_url)
        expect(saved).to_be_visible()
        check_workspace_urls()
        page.get_by_role("button", name="空间里的工作流", exact=True).click()
        detail = page.get_by_role("dialog", name="空间里的工作流", exact=True)
        expect(detail.get_by_text("空间里的作品", exact=True)).to_be_visible()
        expect(detail.get_by_role("button", name="更多操作")).to_have_count(0)
        detail.get_by_role("button", name="关闭", exact=True).click()

        machines_link.click()
        expect(page).to_have_url(machines_url)
        expect(account).to_have_accessible_name("账户 catalog-owner · 数字栩生")
        expect(page.get_by_text("团队还没有工作机", exact=True)).to_be_visible()
        expect(page.get_by_text("个人工作机", exact=True)).to_have_count(0)
        open_space_picker(page).get_by_role("button", name=second["name"], exact=True).click()
        expect(page).to_have_url(machines_url)
        expect(account).to_have_accessible_name("账户 catalog-owner · 影像团队")

        workspace_link.click()
        expect(page).to_have_url(favorites_url)
        expect(page.get_by_text("暂无收藏", exact=True)).to_be_visible()
        open_space_picker(page).get_by_role("button", name=first["name"], exact=True).click()
        expect(saved).to_be_visible()
        expect(page).to_have_url(favorites_url)
        page.reload()
        expect(saved).to_be_visible()
        page.go_back()
        expect(page).to_have_url(machines_url)
        expect(account).to_have_accessible_name("账户 catalog-owner · 数字栩生")
        page.go_forward()
        expect(page).to_have_url(favorites_url)
        expect(saved).to_be_visible()

        open_space_picker(page).get_by_role("button", name=second["name"], exact=True).click()
        page.get_by_role("link", name="ComfyShop 首页").click()
        expect(add).to_have_attribute("aria-pressed", "false")

        open_space_picker(page).get_by_role("button", name="我的", exact=True).click()
        expect(account).to_have_accessible_name("账户 catalog-owner")
        expect(add).to_have_attribute("aria-pressed", "false")
        add.click()
        expect(saved).to_be_visible()
        assert writes[-1] == ("PUT", address + personal_favorite)
        open_space_picker(page).get_by_role("button", name=second["name"], exact=True).click()
        expect(add).to_have_attribute("aria-pressed", "false")
        open_space_picker(page).get_by_role("button", name=first["name"], exact=True).click()
        expect(saved).to_have_attribute("aria-pressed", "true")
        saved.click()
        expect(add).to_have_attribute("aria-pressed", "false")
        assert [method for method, _ in writes] == ["PUT", "PUT", "DELETE"]
        assert api.get(f"{API}/workspace").json()["favoriteIds"] == [public["id"]]

        open_space_picker(page).get_by_role("button", name="我的", exact=True).click()
        expect(account).to_have_accessible_name("账户 catalog-owner")
        account.click()
        expect(page.get_by_role("menuitem", name="我的作品", exact=True)).to_have_attribute(
            "href", "/workspace/artworks"
        )
        page.keyboard.press("Escape")
        workspace_link.click()
        expect(page).to_have_url(favorites_url)
        expect(saved).to_be_visible()
        check_workspace_urls()

        unavailable_link = f"{address}/workspace/teams/{uuid4()}/workflows"
        page.goto(unavailable_link)
        back = page.get_by_role("button", name="返回我的", exact=True)
        expect(back).to_be_visible()
        expect(page).to_have_url(unavailable_link)
        back.click()
        expect(page).to_have_url(f"{address}/workspace/workflows")
        expect(page.get_by_role("button", name="共享空间", exact=True)).to_be_visible()
