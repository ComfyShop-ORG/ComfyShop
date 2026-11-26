"""公开团队资料、目录归属与复用的主页入口。"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from helpers import serve_test_app, sync_machine
from playwright.sync_api import expect, sync_playwright
from test_inputs import picture
from test_outputs import run_group
from test_team_spaces import API, add_member, item_ids
from test_worker import claim_body
from test_workspace_sharing import ORIGIN, PASSWORD, WEB_DIST, register_account


def run_team_workflow(client, team_id, workflow, machine, worker):
    scope = {"workspace_team": team_id}
    machine_id = machine["machine"]["id"]
    form = (
        client.get(
            f"{API}/workflows/{workflow['id']}/inputs", params={**scope, "machine_id": machine_id}
        )
        .raise_for_status()
        .json()
    )
    task = (
        client.post(
            f"{API}/tasks",
            params=scope,
            json={
                "workflowId": workflow["id"],
                "versionId": workflow["versionId"],
                "inputSchemaHash": form["schemaHash"],
                "inputValues": {},
                "idempotencyKey": str(uuid4()),
            },
        )
        .raise_for_status()
        .json()
    )
    claim = claim_body()
    assert (
        worker.post(f"{API}/worker/claim", json=claim).raise_for_status().json()["task"]["id"]
        == task["id"]
    )
    execution, (artifact,) = run_group(client, worker, task["id"], claim["leaseSecret"], members=1)
    worker.post(
        f"{API}/worker/tasks/{task['id']}/complete", headers={"X-Task-Lease": claim["leaseSecret"]}
    ).raise_for_status()
    return execution, artifact


@pytest.fixture
def team_catalog(client, graph):
    register_account(client, "profile-publisher")
    first, second = [
        client.post(f"{API}/teams", json={"name": "影像工作室"}).raise_for_status().json()["id"]
        for _ in range(2)
    ]
    workflow, _draft = [
        client.post(f"{API}/teams/{first}/workflows", json={"name": name, "graph": graph})
        .raise_for_status()
        .json()
        for name in ("公开图像工作流", "私有团队草稿")
    ]
    works = []
    for team_id, title in ((first, "工作室公开成品"), (second, "另一队公开成品")):
        scope = {"workspace_team": team_id}
        machine = (
            client.post(f"{API}/machines", params=scope, json={"name": "团队工作机"})
            .raise_for_status()
            .json()
        )
        worker = sync_machine(client, machine)
        execution, artifact = run_team_workflow(client, team_id, workflow, machine, worker)
        if team_id == first:
            client.post(
                f"{API}/workflows/{workflow['id']}/publish", params=scope
            ).raise_for_status()
        work = (
            client.post(
                f"{API}/works",
                params=scope,
                json={
                    "id": str(uuid4()),
                    "executionId": execution["id"],
                    "artifactIds": [artifact["id"]],
                    "coverArtifactId": artifact["id"],
                    "title": title,
                },
            )
            .raise_for_status()
            .json()
        )
        works.append(work)
    avatar = (
        client.put(f"{API}/teams/{first}/avatar", content=picture("seagreen"))
        .raise_for_status()
        .json()["avatarUrl"]
    )
    return first, second, workflow, works, avatar


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_public_team_profile_follows_consent_and_public_content(client, team_catalog):
    first, second, workflow, (first_work, second_work), avatar = team_catalog
    visitor = TestClient(client.app)
    team, other = (f"{API}/teams/{team_id}" for team_id in (first, second))
    profile = team + "/public"
    visibility = team + "/profile-visibility"
    workflows, works = f"{API}/workflows", f"{API}/works"
    filters = {"public_team_id": first}
    assert client.get(team).json()["profilePublic"] is False
    assert visitor.get(profile).status_code == 404
    assert visitor.get(avatar).status_code == 404
    assert not item_ids(visitor.get(workflows, params=filters))
    assert first_work["id"] in item_ids(visitor.get(works))
    flow_link = f"{workflows}/{workflow['id']}"
    first_work_link = f"{works}/{first_work['id']}"
    other_work_link = f"{works}/{second_work['id']}"
    assert visitor.get(flow_link).raise_for_status().json()["publicTeam"] is None
    assert visitor.get(first_work_link).raise_for_status().json()["publicTeam"] is None
    assert item_ids(visitor.get(works, params={"author": "profile-publisher"})) == {
        first_work["id"],
        second_work["id"],
    }
    editor = TestClient(client.app, headers={"Origin": ORIGIN})
    register_account(editor, "profile-editor")
    assert add_member(client, team, "profile-editor", "editor").status_code == 204
    assert editor.put(visibility, json={"public": True}).status_code == 403
    assert add_member(client, team, "profile-editor", "manager").status_code == 204
    assert editor.put(visibility, json={"public": True}).raise_for_status().json()["profilePublic"]
    assert visitor.get(profile).json() == {
        "id": first,
        "name": "影像工作室",
        "avatarUrl": avatar,
        "hasWorkflows": True,
    }
    assert visitor.get(team + "/members").status_code == 401
    assert item_ids(visitor.get(workflows, params=filters)) == {workflow["id"]}
    assert item_ids(visitor.get(works, params=filters)) == {first_work["id"]}
    credit = {"id": first, "name": "影像工作室", "avatarUrl": avatar}
    (listed,) = visitor.get(workflows, params=filters).raise_for_status().json()["items"]
    assert listed["publicTeam"] == credit
    assert visitor.get(flow_link).raise_for_status().json()["publicTeam"] == credit
    assert visitor.get(first_work_link).raise_for_status().json()["publicTeam"] == credit
    assert visitor.get(other_work_link).raise_for_status().json()["publicTeam"] is None
    members_list = client.get(workflows, params={"workspace_team": first}).raise_for_status()
    (draft,) = [item for item in members_list.json()["items"] if not item["published"]]
    assert draft["publicTeam"] is None
    assert client.get(workflows, params={**filters, "workspace_team": first}).status_code == 422
    assert client.get(works, params={**filters, "scope": "mine"}).status_code == 422
    image = visitor.get(avatar).raise_for_status()
    cached = {"If-None-Match": image.headers["etag"]}
    assert visitor.get(avatar, headers=cached).status_code == 304

    client.put(other + "/profile-visibility", json={"public": True}).raise_for_status()
    assert visitor.get(other + "/public").json()["hasWorkflows"] is False
    assert item_ids(visitor.get(works, params={"public_team_id": second})) == {second_work["id"]}
    assert visitor.get(other_work_link).raise_for_status().json()["publicTeam"] == {
        "id": second,
        "name": "影像工作室",
        "avatarUrl": None,
    }
    client.delete(
        f"{works}/{second_work['id']}", params={"workspace_team": second}
    ).raise_for_status()
    assert visitor.get(other + "/public").status_code == 404

    client.patch(team, json={"name": "新的工作室名称"}).raise_for_status()
    assert visitor.get(profile).json()["name"] == "新的工作室名称"
    assert (
        visitor.get(first_work_link).raise_for_status().json()["publicTeam"]["name"]
        == "新的工作室名称"
    )
    client.put(visibility, json={"public": False}).raise_for_status()
    assert visitor.get(profile).status_code == 404
    assert visitor.get(avatar, headers=cached).status_code == 404
    assert editor.get(avatar).status_code == 200
    assert not item_ids(visitor.get(works, params=filters))
    assert visitor.get(f"{works}/{first_work['id']}").status_code == 200
    assert visitor.get(first_work_link).raise_for_status().json()["publicTeam"] is None
    client.put(visibility, json={"public": True}).raise_for_status()
    client.delete(team).raise_for_status()
    assert visitor.get(profile).status_code == 404
    assert visitor.get(avatar, headers=cached).status_code == 404
    client.post(team + "/restore").raise_for_status()
    assert visitor.get(profile).status_code == 200
    assert visitor.get(avatar).status_code == 200
    client.delete(
        f"{workflows}/{workflow['id']}", params={"workspace_team": first}
    ).raise_for_status()
    assert visitor.get(profile).status_code == 404
    assert visitor.get(avatar, headers=cached).status_code == 404


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "narrow"])
def test_public_team_homepage_in_browser(settings, team_catalog, width, tmp_path):
    first, _, workflow, (work, _), avatar = team_catalog
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, _),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        options = {
            "base_url": address,
            "viewport": {"width": width, "height": 844},
            "locale": "zh-CN",
            "has_touch": width < 700,
            "is_mobile": width < 700,
            "reduced_motion": "reduce",
        }
        owner, visitor = (browser.new_page(**options) for _ in range(2))
        for page in (owner, visitor):
            page.set_default_timeout(12_000)
        path = f"/teams/{first}"
        visitor.goto(path)
        expect(visitor.get_by_role("alert")).to_contain_text("此团队主页不可访问")
        login = owner.request.post(
            f"{API}/auth/login",
            data={"username": "profile-publisher", "password": PASSWORD},
            headers={"Origin": address},
        )
        assert login.ok, login.text()
        owner.goto(f"/workspace/teams/{first}/workflows")
        account = owner.locator("header .account-button")
        expect(account).to_have_accessible_name("账户 profile-publisher · 影像工作室")
        account.click()
        owner.get_by_role("menuitem", name="团队资料", exact=True).click()
        settings_dialog = owner.get_by_role("dialog", name="团队资料", exact=True)
        visibility = settings_dialog.get_by_role("switch", name="公开团队主页")
        expect(visibility).not_to_be_checked()
        save = settings_dialog.get_by_role("button", name="保存公开设置", exact=True)
        expect(save).to_be_disabled()
        visibility.click()
        frame_height = "44px" if width < 700 else "40px"
        expect(save).to_have_css("height", frame_height)
        with owner.expect_response(
            lambda response: response.url.endswith("/profile-visibility")
        ) as saved:
            save.click()
        assert saved.value.ok, saved.value.text()
        link = settings_dialog.get_by_role("link", name="查看公开主页", exact=True)
        expect(link).to_have_attribute("href", path)
        assert settings_dialog.evaluate("(dialog) => dialog.scrollWidth <= dialog.clientWidth")
        owner.screenshot(path=tmp_path / "team-profile-visibility.png", animations="disabled")
        link.click()
        expect(owner).to_have_url(f"{address}{path}")
        expect(settings_dialog).to_be_hidden()
        expect(account).to_have_accessible_name("账户 profile-publisher · 影像工作室")

        visitor.reload()
        expect(visitor.get_by_role("heading", name="影像工作室", exact=True)).to_be_visible()
        expect(visitor.locator(".author-avatar img")).to_have_attribute("src", avatar)
        workflow_tab = visitor.get_by_role("tab", name="工作流", exact=True)
        expect(workflow_tab).to_have_attribute("aria-selected", "true")
        expect(visitor.get_by_role("button", name=workflow["name"], exact=True)).to_be_visible()
        visitor.screenshot(path=tmp_path / "team-public-workflows.png", animations="disabled")
        works_tab = visitor.get_by_role("tab", name="作品", exact=True)
        works_tab.click()
        expect(works_tab).to_have_css("height", frame_height)
        expect(visitor).to_have_url(f"{address}{path}?tab=works")
        expect(
            visitor.get_by_role("button", name=f"查看作品 {work['title']}", exact=True)
        ).to_be_visible()
        assert visitor.locator("body").evaluate("(body) => body.scrollWidth <= innerWidth")
        visitor.screenshot(path=tmp_path / "team-public-works.png", animations="disabled")


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "narrow"])
def test_public_team_attribution_links_in_browser(settings, client, team_catalog, width, tmp_path):
    first, second, workflow, (_, work), avatar = team_catalog
    second_name = "后期工作室 · Image Production"
    for team_id in (first, second):
        client.put(
            f"{API}/teams/{team_id}/profile-visibility", json={"public": True}
        ).raise_for_status()
    client.patch(f"{API}/teams/{second}", json={"name": second_name}).raise_for_status()
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, _),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 844},
            locale="zh-CN",
            has_touch=width < 700,
            is_mobile=width < 700,
            reduced_motion="reduce",
        )
        page.set_default_timeout(12_000)
        card = page.get_by_role("button", name=workflow["name"], exact=True)
        team_link = page.get_by_role("link", name="查看公开主页 影像工作室", exact=True)
        page.goto("/")
        expect(card.locator(".profile-name")).to_have_text("影像工作室")
        expect(card.locator(".profile-avatar img")).to_have_attribute("src", avatar)
        card.click()
        if width < 700:
            page.get_by_role("button", name="工作流信息", exact=True).click()
        expect(team_link).to_have_attribute("href", f"/teams/{first}")
        expect(page.get_by_role("link", name="查看 profile-publisher 的工作流")).to_have_attribute(
            "href", "/authors/profile-publisher"
        )
        page.screenshot(path=tmp_path / "public-workflow-attribution.png", animations="disabled")
        team_link.click()
        expect(page).to_have_url(f"{address}/teams/{first}")
        expect(card.locator(".profile-name")).to_have_text("profile-publisher")

        card.click()
        work_card = page.get_by_role("button", name=f"查看作品 {work['title']}", exact=True)
        expect(work_card.locator(".profile-name")).to_have_text(second_name)
        expect(work_card.locator(".media-card-dimensions")).to_have_css("white-space", "nowrap")
        work_card.click()
        detail = page.get_by_role("dialog", name=work["title"], exact=True)
        other_team = detail.get_by_role("link", name=f"查看公开主页 {second_name}", exact=True)
        expect(other_team).to_have_attribute("href", f"/teams/{second}?tab=works")
        expect(detail.get_by_role("link", name="profile-publisher", exact=True)).to_have_attribute(
            "href", "/authors/profile-publisher"
        )
        assert detail.evaluate("(dialog) => dialog.scrollWidth <= dialog.clientWidth")
        expect(detail.locator(".preview-caption .media-card-dimensions")).to_have_css(
            "white-space", "nowrap"
        )
        page.screenshot(path=tmp_path / "public-work-attribution.png", animations="disabled")
        other_team.click()
        expect(page).to_have_url(f"{address}/teams/{second}?tab=works")
        expect(page.get_by_role("heading", name=second_name, exact=True)).to_be_visible()
        expect(work_card.locator(".profile-name")).to_have_text("profile-publisher")
        expect(page.get_by_role("tab", name="作品", exact=True)).to_have_attribute(
            "aria-selected", "true"
        )
        work_card.click()
        other_team.click()
        expect(detail).to_be_hidden()
        work_card.click()
        detail.get_by_role("link", name="profile-publisher", exact=True).click()
        expect(page).to_have_url(f"{address}/authors/profile-publisher")
        expect(page.get_by_role("heading", name="profile-publisher", exact=True)).to_be_visible()

        if width == 1280:
            login = page.request.post(
                f"{API}/auth/login",
                data={"username": "profile-publisher", "password": PASSWORD},
                headers={"Origin": address},
            )
            assert login.ok, login.text()
            page.goto(f"/workspace/teams/{second}/workflows")
            account = page.locator("header .account-button")
            expect(account).to_have_accessible_name(f"账户 profile-publisher · {second_name}")
            page.goto(f"/teams/{first}")
            expect(account).to_have_accessible_name(f"账户 profile-publisher · {second_name}")
            favorite = page.get_by_role("button", name=f"收藏 {workflow['name']}", exact=True)
            favorite.click()
            expect(
                page.get_by_role("button", name=f"取消收藏 {workflow['name']}", exact=True)
            ).to_have_attribute("aria-pressed", "true")
            assert client.get(f"{API}/workspace", params={"workspace_team": second}).json()[
                "favoriteIds"
            ] == [workflow["id"]]
            assert (
                client.get(f"{API}/workspace", params={"workspace_team": first}).json()[
                    "favoriteIds"
                ]
                == []
            )
