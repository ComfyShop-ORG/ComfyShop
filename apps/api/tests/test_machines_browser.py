from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

import pytest
from helpers import CATALOG, machine_heartbeat, serve_test_app, task_body
from playwright.sync_api import Route, expect, sync_playwright
from test_worker import claim_body

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
MACHINE_NAME = "渲染工作机" * 8
DEVICE = "cuda:0 NVIDIA GeForce RTX 4090 : cudaMallocAsync"


@pytest.fixture
def machines_site(settings, graph):
    assert (WEB_DIST / "index.html").is_file(), (
        "请用 pnpm test:python apps/api/tests/test_machines_browser.py 构建网页并运行此测试"
    )
    credentials = {"username": "machines-browser-test", "password": "browser-test-password"}
    with serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, web):
        session = web.post("/api/v1/auth/register", json=credentials).raise_for_status().json()
        web.headers["X-CSRF-Token"] = session["csrfToken"]
        machines = {}
        for name, system, comfy in [
            (MACHINE_NAME, "windows", "idle"),
            ("图像工作机", "macos", "busy"),
            ("视频工作机", "linux", "unreachable"),
        ]:
            machine = web.post("/api/v1/machines", json={"name": name}).raise_for_status().json()
            machines[name] = machine
            auth = {"Authorization": "Bearer " + machine["apiKey"]}
            web.put("/api/v1/worker/catalog", json=CATALOG, headers=auth).raise_for_status()
            web.post(
                "/api/v1/worker/heartbeat",
                headers=auth,
                json=machine_heartbeat(
                    device=DEVICE,
                    nodes=["KSampler"],
                    operatingSystem=system,
                    comfyStatus=comfy,
                    startupIssue="comfy_connection" if comfy == "unreachable" else None,
                ),
            ).raise_for_status()
        web.post("/api/v1/machines", json={"name": "备用工作机"}).raise_for_status()
        source = machine["machine"]["id"]
        workflow = (
            web.post("/api/v1/workflows", json={"name": "排队测试", "graph": graph})
            .raise_for_status()
            .json()
        )
        for _ in range(2):
            web.post("/api/v1/tasks", json=task_body(web, workflow, source)).raise_for_status()
        workflow = (
            web.post("/api/v1/workflows", json={"name": "补跑测试", "graph": graph})
            .raise_for_status()
            .json()
        )
        first = machines[MACHINE_NAME]
        body = task_body(web, workflow, first["machine"]["id"])
        task = (
            web.post("/api/v1/tasks", json={**body, "executionCount": 3}).raise_for_status().json()
        )
        claim = claim_body()
        work_key = {
            "Authorization": "Bearer " + first["apiKey"],
            "X-Task-Lease": claim["leaseSecret"],
        }
        web.post("/api/v1/worker/claim", json=claim, headers=work_key).raise_for_status()
        base = f"/api/v1/worker/tasks/{task['id']}"
        web.post(
            base + "/executions/0/start", json={"promptId": "waiting-for-history"}, headers=work_key
        ).raise_for_status()
        web.post(
            base + "/fail", json={"error": "工作机连接中断"}, headers=work_key
        ).raise_for_status()
        yield address, credentials


@pytest.mark.parametrize(("width", "height"), [(1280, 900), (320, 640)], ids=["desktop", "mobile"])
def test_task_list_keeps_the_last_work_machine_name(machines_site, width, height):
    address, credentials = machines_site
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        page = browser.new_page(base_url=address, viewport={"width": width, "height": height})
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/workspace/tasks")
        row = page.locator(".task-item").filter(has_text="补跑测试")
        expect(row.locator(".task-open")).to_contain_text(MACHINE_NAME)

        page.get_by_role("link", name="工作机", exact=True).click()
        page.get_by_role("button", name=f"{MACHINE_NAME} 操作", exact=True).click()
        page.get_by_role("menuitem", name="重命名", exact=True).click()
        rename = page.get_by_role("dialog", name="重命名工作机")
        name = "成品渲染工作机"
        rename.get_by_role("textbox").fill(name)
        rename.get_by_role("button", name="保存", exact=True).click()
        actions = page.get_by_role("button", name=f"{name} 操作", exact=True)
        expect(actions).to_be_visible()
        page.go_back()
        expect(row.locator(".task-open")).to_contain_text(name)

        page.get_by_role("link", name="工作机", exact=True).click()
        for operation, confirm in (("撤销工作机", "确认撤销"), ("删除工作机", "确认删除")):
            actions.click()
            page.get_by_role("menuitem", name=operation, exact=True).click()
            confirmation = page.get_by_role("alertdialog", name=operation)
            confirmation.get_by_role("button", name=confirm, exact=True).click()
            expect(confirmation).to_have_count(0)
        expect(actions).to_have_count(0)
        page.go_back()
        page.reload()
        expect(row.locator(".task-open")).to_contain_text(name)
        row.get_by_role("button", name="任务详情", exact=True).click()
        details = page.get_by_role("dialog", name="任务详情")
        expect(details.get_by_text(name, exact=True)).to_be_visible()
        assert page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )


@pytest.mark.parametrize(("width", "height"), [(1280, 900), (320, 640)], ids=["desktop", "mobile"])
def test_machine_list_shows_systems_and_keeps_rows_in_place(machines_site, width, height):
    address, credentials = machines_site
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        page = browser.new_page(base_url=address, viewport={"width": width, "height": height})
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        machine_list_api = "**/api/v1/machines"
        page.route(
            machine_list_api,
            lambda route: route.fulfill(status=503, json={"detail": "读取工作机失败"}),
        )
        page.goto("/machines")
        retry = page.get_by_role("main").get_by_role("alert").get_by_role("button", name="重试")
        expect(retry).to_be_visible()
        expect(page.get_by_role("link", name="下载工作机", exact=True)).to_have_count(0)
        page.unroute(machine_list_api)
        with page.expect_response(
            lambda response: response.url.endswith("/machines") and response.ok
        ):
            retry.click()
        expect(retry).to_have_count(0)

        rows = page.locator(".machine-item")
        name = page.get_by_role("button", name=MACHINE_NAME, exact=True)
        machine = rows.filter(has=name)
        connection = machine.get_by_role("status", name="连接状态")
        intake = machine.get_by_role("status", name="接单状态")
        trigger = machine.get_by_role("button", name=f"{MACHINE_NAME} 操作", exact=True)
        expect(rows).to_have_count(4)
        for label in ("Windows", "macOS", "Linux", "系统未知"):
            expect(rows.get_by_role("img", name=label, exact=True)).to_be_visible()
        expect(connection).to_have_text("在线")
        expect(intake).to_have_text("允许接单")
        expect(rows.get_by_text("等待本机任务", exact=True)).to_be_visible()
        expect(rows.get_by_text("ComfyUI 未响应", exact=True)).to_be_visible()
        expect(machine.get_by_text("默认", exact=True)).to_be_visible()
        expect(machine.get_by_text(DEVICE, exact=True)).to_be_visible(visible=width > 320)
        expect(machine.get_by_text("版本 0.3.0", exact=True)).to_be_visible(visible=width > 320)
        expect(rows.get_by_text("版本未知", exact=True)).to_be_visible(visible=width > 320)
        assert page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )

        measure_rows = """rows => rows.map(row => {
          const { y, height } = row.getBoundingClientRect();
          return [y, height];
        })"""
        original = rows.evaluate_all(measure_rows)
        assert len({height for _, height in original}) == 1
        for action, status in (("暂停接单", "已暂停接单"), ("恢复接单", "允许接单")):
            trigger.click()
            with page.expect_response("**/api/v1/machines/*/pause") as pause:
                page.get_by_role("menuitem", name=action, exact=True).click()
            assert pause.value.ok
            expect(intake).to_have_text(status)
            expect(connection).to_have_text("在线")
            expect(trigger).to_be_focused()
            assert rows.evaluate_all(measure_rows) == original

        name.click()
        details = page.get_by_role("dialog", name=MACHINE_NAME)
        expect(details.get_by_text(DEVICE, exact=True)).to_be_visible()
        expect(details.get_by_text("Windows", exact=True)).to_be_visible()
        expect(details.get_by_text("节点数", exact=True)).to_be_visible()
        expect(details.get_by_text("1 个", exact=True)).to_be_visible()


@pytest.mark.parametrize(
    ("width", "failing_path"),
    [(1280, "/api/v1/tasks"), (320, "/api/v1/tasks/activity")],
    ids=["history-desktop", "activity-mobile"],
)
def test_task_list_retries_the_failed_request_and_keeps_pages(machines_site, width, failing_path):
    address, credentials = machines_site
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 720},
            locale="zh-CN",
            has_touch=width == 320,
            is_mobile=width == 320,
            reduced_motion="reduce",
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        unavailable = True
        fail_next_page = True

        def route_list(route: Route) -> None:
            url = urlsplit(route.request.url)
            params = dict(parse_qsl(url.query))
            if (unavailable and url.path == failing_path) or (
                fail_next_page and "cursor" in params
            ):
                route.fulfill(status=503, json={"detail": "读取任务失败"})
            elif url.path == "/api/v1/tasks":
                # 本地测试服务保留真实游标，每页只返回两条以便验收下一页。
                params["limit"] = "2"
                route.continue_(url=url._replace(query=urlencode(params)).geturl())
            else:
                route.continue_()

        page.route(
            lambda url: urlsplit(url).path in {"/api/v1/tasks", "/api/v1/tasks/activity"},
            route_list,
        )
        page.goto("/workspace/tasks")
        retry = page.get_by_role("main").get_by_role("alert").get_by_role("button", name="重试")
        expect(retry).to_be_visible()
        with page.expect_request(
            lambda request: (
                urlsplit(request.url).path in {"/api/v1/tasks", "/api/v1/tasks/activity"}
            )
        ) as retried:
            unavailable = False
            retry.click()
        assert urlsplit(retried.value.url).path == failing_path
        expect(retry).to_have_count(0)

        rows = page.locator(".task-item")
        expect(rows).to_have_count(2)
        titles = rows.locator("strong[id^='task-workflow-']")
        first_page = titles.evaluate_all("nodes => nodes.map(node => node.id)")
        load_more = page.get_by_role("button", name="加载更多", exact=True)
        load_more.click()
        expect(retry).to_be_visible()
        expect(rows).to_have_count(2)
        with page.expect_request(
            lambda request: urlsplit(request.url).path == "/api/v1/tasks"
        ) as next_page:
            fail_next_page = False
            retry.click()
        assert "cursor" in dict(parse_qsl(urlsplit(next_page.value.url).query))
        expect(rows).to_have_count(3)
        expect(retry).to_have_count(0)
        expect(load_more).to_have_count(0)
        loaded = titles.evaluate_all("nodes => nodes.map(node => node.id)")
        assert loaded[:2] == first_page and len(set(loaded)) == 3


@pytest.mark.parametrize(("width", "height"), [(1280, 900), (320, 640)], ids=["desktop", "mobile"])
def test_task_details_can_open_the_machine_and_move_a_waiting_task(machines_site, width, height):
    address, credentials = machines_site
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        page = browser.new_page(base_url=address, viewport={"width": width, "height": height})
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/workspace/tasks")
        task_button = (
            page.locator(".task-item")
            .filter(has_text="排队测试")
            .get_by_role("button", name="任务详情", exact=True)
            .first
        )
        task_button.click()
        details = page.get_by_role("dialog", name="任务详情")
        expect(details.get_by_text("ComfyUI 未响应 · 前方还有 1 个平台任务")).to_be_visible()
        details.get_by_role("link", name="查看工作机").click()
        machine = page.get_by_role("dialog", name="视频工作机")
        expect(machine.get_by_text("最近启动错误", exact=True)).to_be_visible()
        expect(machine.get_by_text("无法连接 ComfyUI", exact=False)).to_be_visible()
        page.go_back()
        task_button.click()

        details.get_by_role("button", name="换工作机").click()
        move = page.get_by_role("dialog", name="换工作机")
        move.get_by_role("combobox", name="目标工作机").click()
        expect(page.get_by_role("option", name="备用工作机", exact=False)).to_have_count(0)
        page.get_by_role("option", name="图像工作机 · 在线", exact=True).click()
        with page.expect_response("**/api/v1/tasks/*/machine") as changed:
            move.get_by_role("button", name="换工作机").click()
        assert changed.value.ok
        expect(move).to_have_count(0)
        expect(details.get_by_text("图像工作机", exact=True)).to_be_visible()
        expect(details.get_by_text("等待本机任务 · 当前排在队首")).to_be_visible()
        assert page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )


@pytest.mark.parametrize(("width", "height"), [(1280, 900), (320, 640)], ids=["desktop", "mobile"])
def test_retry_lists_only_the_confirmed_remaining_executions(machines_site, width, height):
    address, credentials = machines_site
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        page = browser.new_page(base_url=address, viewport={"width": width, "height": height})
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/workspace/tasks")
        row = page.locator(".task-item").filter(has_text="补跑测试")
        row.get_by_role("button", name="任务详情", exact=True).click()
        details = page.get_by_role("dialog", name="任务详情")
        expect(details.get_by_text("待核对", exact=True)).to_be_visible()
        details.get_by_role("button", name="补跑剩余 2 次").click()
        retry = page.get_by_role("dialog", name="补跑剩余 2 次")
        expect(retry.get_by_role("combobox")).to_have_text(f"{MACHINE_NAME} · 在线")
        with page.expect_response("**/api/v1/tasks/*/retry-executions") as queued:
            retry.get_by_role("button", name="补跑剩余 2 次").click()
        assert queued.value.status == 201
        assert queued.value.json()["executionCount"] == 2
        expect(details.get_by_text("已提交补跑", exact=True)).to_have_count(2)
        expect(details.get_by_text("待核对", exact=True)).to_be_visible()
        assert page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )
