import re

import pytest
from fastapi.testclient import TestClient
from helpers import serve_test_app
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import update
from sqlalchemy.orm import Session
from test_team_spaces import API, add_member, open_space_picker
from test_workspace_sharing import ORIGIN, PASSWORD, WEB_DIST, register_account

from comfyshop_api.models import TeamEvent


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_team_events_filter_page_and_keep_history_after_a_member_leaves(client):
    register_account(client, "audit-owner")
    team, other = [
        client.post(f"{API}/teams", json={"name": name}).raise_for_status().json()
        for name in ("摄影组", "视频组")
    ]
    team_path = f"{API}/teams/{team['id']}"
    events_path = team_path + "/events"
    members = {}
    for role in ("reader", "editor", "manager"):
        member = TestClient(client.app, headers={"Origin": ORIGIN})
        member_id = register_account(member, f"audit-{role}")
        assert add_member(client, team_path, f"audit-{role}", role).status_code == 204
        members[role] = (member, member_id)
    manager, manager_id = members["manager"]
    assert members["reader"][0].get(events_path).status_code == 403
    assert members["editor"][0].get(events_path).status_code == 403
    assert TestClient(client.app).get(events_path).status_code == 401
    assert manager.get(f"{API}/teams/{other['id']}/events").status_code == 404

    manager.put(f"{API}/auth/profile", json={"nickname": "设备管理员"}).raise_for_status()
    scope = {"workspace_team": team["id"]}
    machine = (
        manager.post(f"{API}/machines", params=scope, json={"name": "棚内工作机"})
        .raise_for_status()
        .json()["machine"]
    )
    manager.delete(f"{API}/machines/{machine['id']}", params=scope).raise_for_status()
    machine_events = (
        manager.get(events_path, params={"category": "machine", "actor": "设备管理员"})
        .raise_for_status()
        .json()["items"]
    )
    assert [event["action"] for event in machine_events] == ["machine.revoked", "machine.created"]
    for event in machine_events:
        assert (event["target"], event["recordId"], event["actorUsername"]) == (
            "棚内工作机",
            machine["id"],
            "audit-manager",
        )
        assert "apiKey" not in event

    with Session(client.app.state.engine) as db:
        db.execute(update(TeamEvent).where(TeamEvent.team_id == team["id"]).values(created_at=1000))
        db.commit()
    all_events = client.get(events_path, params={"limit": 100}).raise_for_status().json()["items"]
    paged = []
    cursor = None
    while True:
        params = {"limit": 2, "created_from": 1000, "created_before": 1001}
        if cursor:
            params["cursor"] = cursor
        page = client.get(events_path, params=params).raise_for_status().json()
        paged.extend(page["items"])
        cursor = page["nextCursor"]
        if cursor is None:
            break
    assert paged == all_events
    assert not client.get(events_path, params={"created_before": 1000}).json()["items"]
    assert client.get(events_path, params={"category": "invalid"}).status_code == 422

    assert client.delete(f"{team_path}/members/{manager_id}").status_code == 204
    assert manager.get(events_path).status_code == 404
    still_visible = client.get(events_path, params={"actor": "audit-manager"}).json()["items"]
    assert {event["action"] for event in still_visible} == {"machine.created", "machine.revoked"}
    assert (
        manager.post(f"{API}/auth/account/delete", json={"password": PASSWORD}).status_code == 204
    )
    anonymized = client.get(events_path, params={"category": "machine"}).json()["items"]
    assert len(anonymized) == 2 and all(event["actorName"] is None for event in anonymized)


@pytest.mark.parametrize(
    ("width", "expected_rows"),
    [(1280, {1}), (390, {2}), (320, {3, 4})],
    ids=["desktop", "mobile", "narrow"],
)
def test_team_events_from_the_account_menu(settings, width, expected_rows, tmp_path):
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, api),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        register_account(api, "audit-browser")
        team = api.post(f"{API}/teams", json={"name": "摄影团队"}).raise_for_status().json()
        scope = {"workspace_team": team["id"]}
        api.post(f"{API}/machines", params=scope, json={"name": "棚内工作机"}).raise_for_status()
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 844},
            locale="zh-CN",
            has_touch=width < 700,
            is_mobile=width < 700,
            reduced_motion="reduce",
        )
        assert page.request.post(
            f"{API}/auth/login",
            data={"username": "audit-browser", "password": PASSWORD},
            headers={"Origin": address},
        ).ok
        page.goto("/")
        open_space_picker(page).get_by_role("button", name="摄影团队", exact=True).click()
        account = page.locator("header .account-button")
        account.click()
        page.get_by_role("menuitem", name="操作记录", exact=True).click()
        dialog = page.get_by_role("dialog", name="摄影团队 · 操作记录", exact=True)
        expect(dialog.get_by_text("棚内工作机", exact=True)).to_be_visible()
        assert dialog.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        filters = dialog.get_by_role("combobox", name="操作类型")
        filters.click()
        page.get_by_role("option", name="工作机", exact=True).click()
        expect(dialog.locator(".team-event-entry")).to_have_count(1)
        date = dialog.get_by_role("button", name="操作日期", exact=True)
        date.click()
        with page.expect_response(
            lambda response: "/events?" in response.url and "created_from=" in response.url
        ) as filtered:
            page.get_by_role("button", name="今天", exact=True).click()
        assert filtered.value.ok
        search = dialog.get_by_role("searchbox", name="搜索操作者")
        selected_date = dialog.get_by_role("button", name=re.compile(r"^操作日期 .+"))
        clear_filters = dialog.get_by_role("button", name="清除筛选", exact=True)
        toolbar = dialog.locator(".filter-toolbar")
        height = f"{44 if width < 700 else 40}px"
        controls = (search.locator(".."), filters, selected_date, clear_filters)
        for control in controls:
            expect(control).to_have_css("height", height)
        positions = toolbar.evaluate(
            """tool => Array.from(tool.children, control => {
                const { x, y } = control.getBoundingClientRect();
                return [y, x];
            })"""
        )
        assert len(positions) == 4 and positions == sorted(positions)
        assert len({y for y, _ in positions}) in expected_rows
        assert dialog.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        dialog.screenshot(path=tmp_path / "team-events.png", animations="disabled")
        search.fill("不存在的成员")
        expect(dialog.get_by_text("没有符合筛选条件的记录", exact=True)).to_be_visible()
        dialog.get_by_role("button", name="清除搜索", exact=True).click()
        expect(search).to_be_focused()
        expect(filters).to_have_text("工作机")
        expect(selected_date).to_be_visible()
        expect(dialog.locator(".team-event-entry")).to_have_count(1)
        search.fill("audit-browser")
        clear_filters.click()
        expect(search).to_have_value("")
        expect(search).to_be_focused()
        expect(filters).to_have_text("全部操作")
        expect(date).to_be_visible()
        expect(clear_filters).to_have_count(0)
        expect(dialog.locator(".team-event-entry")).to_have_count(2)
        dialog.get_by_role("button", name="关闭", exact=True).click()
        expect(account).to_be_focused()
