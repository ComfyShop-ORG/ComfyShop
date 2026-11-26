"""归档列表、团队恢复权限和桌面、窄屏入口。"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from helpers import report_inventory, serve_test_app
from httpx import Client
from playwright.sync_api import expect, sync_playwright
from test_team_spaces import API, add_member, item_ids, open_space_picker
from test_workspace_sharing import ORIGIN, PASSWORD, WEB_DIST, register_account


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_archived_teams_follow_current_owner(client):
    register_account(client, "archive-creator")
    successor = TestClient(client.app, headers={"Origin": ORIGIN})
    successor_id = register_account(successor, "archive-owner")
    teams = f"{API}/teams"
    first = client.post(teams, json={"name": "摄影组"}).raise_for_status().json()
    second = successor.post(teams, json={"name": "影像组"}).raise_for_status().json()
    path = f"{teams}/{first['id']}"
    archives = f"{teams}/archived"
    assert add_member(client, path, "archive-owner", "editor").status_code == 204
    assert client.put(f"{path}/owner/{successor_id}").status_code == 200
    assert client.delete(path).status_code == 403
    assert successor.delete(path).status_code == 204
    assert successor.delete(f"{teams}/{second['id']}").status_code == 204

    assert not item_ids(client.get(archives))
    assert not item_ids(successor.get(teams))
    assert client.post(path + "/restore").status_code == 404
    rows = successor.get(archives, params={"limit": 1}).raise_for_status().json()
    (recent,) = rows["items"]
    assert recent["archivedAt"] > 0 and not recent["hasQueuedTasks"]
    page = successor.get(archives, params={"cursor": rows["nextCursor"], "limit": 1})
    (older,) = page.raise_for_status().json()["items"]
    assert {recent["id"], older["id"]} == {first["id"], second["id"]}
    assert (recent["archivedAt"], recent["id"]) > (older["archivedAt"], older["id"])
    assert page.json()["nextCursor"] is None

    restored = successor.post(path + "/restore").raise_for_status().json()
    assert restored["id"] == first["id"] and restored["role"] == "owner"
    assert client.get(path).raise_for_status().json()["role"] == "manager"
    assert item_ids(successor.get(archives)) == {second["id"]}
    assert successor.delete(path).status_code == 204
    assert (
        successor.post(f"{API}/auth/account/delete", json={"password": PASSWORD}).status_code == 204
    )
    assert register_account(successor, "archive-owner") != successor_id
    assert not item_ids(successor.get(archives))
    assert successor.post(path + "/restore").status_code == 404


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "narrow"])
def test_team_archive_and_restore_in_browser(settings, graph, width, tmp_path):
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, api),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        register_account(api, "archive-owner")
        name = "数字栩生 · 图像创作与影像交付工作室"
        team = api.post(f"{API}/teams", json={"name": name}).raise_for_status().json()
        team_id = team["id"]
        scope = {"workspace_team": team_id}
        path = f"{API}/teams/{team_id}"
        workflow = (
            api.post(f"{path}/workflows", json={"name": "影像创作", "graph": graph})
            .raise_for_status()
            .json()
        )
        machine = (
            api.post(f"{API}/machines", params=scope, json={"name": "渲染工作机"})
            .raise_for_status()
            .json()
        )
        with Client(
            base_url=address,
            headers={"Authorization": "Bearer " + machine["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker)
        form = (
            api.get(
                f"{API}/workflows/{workflow['id']}/inputs",
                params={**scope, "machine_id": machine["machine"]["id"]},
            )
            .raise_for_status()
            .json()
        )
        created = api.post(
            f"{API}/tasks",
            params=scope,
            json={
                "workflowId": workflow["id"],
                "versionId": workflow["versionId"],
                "inputSchemaHash": form["schemaHash"],
                "idempotencyKey": str(uuid4()),
                "inputValues": {},
            },
        )
        assert created.status_code == 201, created.text
        task = f"{API}/tasks/{created.json()['id']}"

        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 844},
            locale="zh-CN",
            has_touch=width < 700,
            is_mobile=width < 700,
            reduced_motion="reduce",
        )
        page.set_default_timeout(10_000)
        login = page.request.post(
            f"{API}/auth/login",
            data={"username": "archive-owner", "password": PASSWORD},
            headers={"Origin": address},
        )
        assert login.ok, login.text()
        page.goto(f"/workspace/teams/{team_id}/workflows")
        expect(page).to_have_url(f"{address}/workspace/workflows")

        def archive_confirmation():
            page.get_by_role("button", name="团队成员", exact=True).click()
            page.get_by_role("button", name="归档团队", exact=True).click()
            dialog = page.get_by_role("alertdialog", name=f"归档「{name}」？")
            dialog.get_by_role("button", name="归档团队", exact=True).click()
            return dialog

        conflict = archive_confirmation()
        expect(conflict.get_by_role("alert")).to_contain_text("还有排队或执行中的任务")
        page.screenshot(path=tmp_path / "team-archive-queued.png", animations="disabled")
        conflict.get_by_role("button", name="查看团队任务", exact=True).click()
        expect(page).to_have_url(f"{address}/workspace/tasks")
        expect(conflict).to_be_hidden()
        page.get_by_role("button", name="取消 影像创作 的排队任务", exact=True).click()
        expect(page.get_by_text("已取消任务", exact=True)).to_be_visible()
        assert api.get(task, params=scope).raise_for_status().json()["status"] == "cancelled"

        expect(archive_confirmation()).to_be_hidden()
        expect(page).to_have_url(f"{address}/workspace/favorites")
        account = page.locator("header .account-button")
        expect(account).to_have_accessible_name("账户 archive-owner")
        spaces = open_space_picker(page)
        expect(spaces.get_by_role("button", name=name, exact=True)).to_have_count(0)
        disclosure = spaces.get_by_role("button", name="已归档团队", exact=True)
        expect(disclosure).to_have_attribute("aria-expanded", "false")
        expect(disclosure).to_have_css("height", "44px" if width < 700 else "40px")
        disclosure.click()
        archived = spaces.get_by_role("list", name="已归档团队", exact=True)
        expect(archived.get_by_text(name, exact=True)).to_be_visible()
        expect(archived.locator("time")).to_contain_text("归档于")
        assert spaces.evaluate("(node) => node.scrollWidth <= node.clientWidth")
        page.screenshot(path=tmp_path / "team-archives.png", animations="disabled")

        restore = archived.get_by_role("button", name="恢复", exact=True)
        restore.click()
        confirmation = page.get_by_role("alertdialog", name=f"恢复「{name}」？")
        expect(confirmation).to_contain_text("归档前已发布的工作流和作品会重新公开")
        page.screenshot(path=tmp_path / "team-restore-confirmation.png", animations="disabled")
        confirmation.get_by_role("button", name="取消", exact=True).click()
        expect(restore).to_be_focused()
        restore.click()
        confirmation.get_by_role("button", name="恢复", exact=True).click()
        expect(confirmation).to_be_hidden()
        expect(disclosure).to_be_focused()
        expect(spaces.get_by_text("暂无已归档团队", exact=True)).to_be_visible()
        spaces.get_by_role("button", name=name, exact=True).click()
        expect(page).to_have_url(f"{address}/workspace/favorites")
        expect(account).to_have_accessible_name(f"账户 archive-owner · {name}")
        assert api.get(task, params=scope).raise_for_status().json()["status"] == "cancelled"
