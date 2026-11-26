import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from helpers import CATALOG, report_inventory, serve_test_app, task_body
from playwright.sync_api import expect, sync_playwright
from test_inputs import picture
from test_outputs import run_group
from test_worker import claim_body

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


@pytest.fixture
def result_site(settings, graph, request):
    assert (WEB_DIST / "index.html").is_file(), "请用 pnpm test:browser 构建网页并运行此测试"
    kind = getattr(request, "param", None)
    media = None
    catalog = CATALOG
    if kind in {"reference", "comparison"}:
        graph = {
            "1": {"class_type": "LoadImage", "inputs": {"image": "reference.png"}},
            "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
        }
        catalog = {
            "nodes": CATALOG["nodes"] | {"LoadImage": {"inputs": {"image": {"kind": "image"}}}}
        }
        if kind == "comparison":
            graph["3"] = {
                "class_type": "ImagePadForOutpaint",
                "inputs": {"image": ["1", 0], "left": 10, "top": 12, "right": 6, "bottom": 4},
            }
            graph["2"]["inputs"]["images"] = ["3", 0]
            catalog["nodes"]["ImagePadForOutpaint"] = {
                "inputs": {
                    key: {"kind": "integer", "minimum": "0", "maximum": "16384", "step": "1"}
                    for key in ("left", "top", "right", "bottom")
                }
            }
            media = [("png", picture("red", size=(48, 64)), "images")]
    elif kind == "video":
        media = [("mp4", request.getfixturevalue("small_mp4"), "videos")]
    elif kind == "audio":
        sample = settings.data_dir / "sample.flac"
        subprocess.run(
            [
                settings.ffmpeg,
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=6",
                str(sample),
            ],
            check=True,
            capture_output=True,
        )
        media = [("flac", sample.read_bytes(), "audio")]
    credentials = {"username": "browser-test", "password": "browser-test-password"}
    with serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, web):
        session = web.post("/api/v1/auth/register", json=credentials).raise_for_status().json()
        web.headers["X-CSRF-Token"] = session["csrfToken"]
        machine = web.post("/api/v1/machines", json={"name": "工作机"}).raise_for_status().json()
        workflow = (
            web.post("/api/v1/workflows", json={"name": "分页结果", "graph": graph})
            .raise_for_status()
            .json()
        )
        with httpx.Client(
            base_url=address,
            headers={"Authorization": "Bearer " + machine["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker, catalog)
            body = task_body(web, workflow, machine["machine"]["id"])
            # 默认准备两页，用于第二页内的详情切换。全屏用例用六项验证扩列。
            body["executionCount"] = 1 if media else 6 if kind == "reference" else 26
            if kind in {"reference", "comparison"}:
                form = (
                    web.get(
                        f"/api/v1/workflows/{workflow['id']}/inputs",
                        params={"machine_id": body["machineId"], "version_id": body["versionId"]},
                    )
                    .raise_for_status()
                    .json()
                )
                (reference,) = [field for field in form["fields"] if field["kind"] == "image"]
                asset = (
                    web.put(
                        f"/api/v1/assets/{uuid4()}",
                        params={"filename": "reference.png"},
                        content=picture(),
                    )
                    .raise_for_status()
                    .json()
                )
                body["inputValues"][reference["id"]] = {"assetId": asset["id"]}
            task = web.post("/api/v1/tasks", json=body).raise_for_status().json()
            claim = claim_body()
            job = worker.post("/api/v1/worker/claim", json=claim).raise_for_status().json()
            assert job["task"]["id"] == task["id"]
            for index in range(body["executionCount"]):
                members = 2 if index == 1 else 1
                run_group(
                    web,
                    worker,
                    task["id"],
                    claim["leaseSecret"],
                    index=index,
                    members=members,
                    media=media,
                )
            worker.post(
                f"/api/v1/worker/tasks/{task['id']}/complete",
                headers={"X-Task-Lease": claim["leaseSecret"]},
            ).raise_for_status()
        yield address, credentials


@pytest.mark.parametrize("result_site", ["video"], indirect=True)
@pytest.mark.parametrize(("width", "height"), [(1280, 900), (320, 640)], ids=["desktop", "mobile"])
def test_video_player_in_work_and_result_previews(result_site, web_engine, width, height):
    address, credentials = result_site
    with web_engine.launch() as browser:
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": height},
            locale="zh-CN",
            reduced_motion="reduce",
        )
        page.add_init_script(
            f"""(() => {{
                const safari = {str(web_engine.name == "webkit").lower()};
                const actions = {{}};
                Object.defineProperty(navigator, 'mediaSession', {{
                  value: {{
                    metadata: null, playbackState: 'none', actions,
                    setActionHandler: (name, handler) => {{ actions[name] = handler; }},
                    setPositionState: (position) => {{ window.mediaPosition = position; }},
                  }},
                }});
                if (!window.MediaMetadata) window.MediaMetadata = class {{
                  constructor(data) {{ Object.assign(this, data); }}
                }};
                let pip = null;
                Object.defineProperty(document, 'pictureInPictureEnabled', {{value: !safari}});
                Object.defineProperty(document, 'pictureInPictureElement', {{get: () => pip}});
                if (safari) {{
                  Object.defineProperties(HTMLVideoElement.prototype, {{
                    webkitSupportsPresentationMode: {{value: () => true}},
                    webkitPresentationMode: {{get() {{
                      return pip === this ? 'picture-in-picture' : 'inline';
                    }}}},
                    webkitSetPresentationMode: {{value(mode) {{
                      pip = mode === 'picture-in-picture' ? this : null;
                      this.dispatchEvent(new Event('webkitpresentationmodechanged'));
                    }}}},
                  }});
                }} else {{
                  Object.defineProperty(HTMLVideoElement.prototype, 'requestPictureInPicture', {{
                    value() {{
                      pip = this;
                      this.dispatchEvent(new Event('enterpictureinpicture'));
                      return Promise.resolve();
                    }},
                  }});
                  Object.defineProperty(document, 'exitPictureInPicture', {{value() {{
                    const video = pip;
                    pip = null;
                    video.dispatchEvent(new Event('leavepictureinpicture'));
                    return Promise.resolve();
                  }}}});
                }}
            }})()"""
        )
        login = page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        )
        assert login.ok, login.status
        headers = {"Origin": address, "X-CSRF-Token": login.json()["csrfToken"]}
        (execution,) = page.request.get("/api/v1/executions").json()["items"]
        workflow = f"/api/v1/workflows/{execution['workflowId']}"
        assert page.request.post(f"{workflow}/publish", headers=headers).ok
        artifact_id = execution["coverArtifactId"]
        published = page.request.post(
            "/api/v1/works",
            headers=headers,
            data={
                "id": str(uuid4()),
                "executionId": execution["id"],
                "title": "视频作品",
                "artifactIds": [artifact_id],
                "coverArtifactId": artifact_id,
                "shareParameters": True,
            },
        )
        assert published.ok, published.text()

        page.goto("/workspace/artworks")
        card = page.get_by_role("button", name="查看作品 视频作品")
        if width == 1280:
            page.emulate_media(reduced_motion="no-preference")
            clip = card.locator("video")
            expect(clip).not_to_be_attached()
            card.hover()
            expect(clip).to_have_attribute("data-visible", "true")
            assert clip.evaluate("(video) => video.muted")
            assert "/video-preview" in clip.evaluate("(video) => video.currentSrc")
            page.mouse.move(0, 0)
            expect(clip).not_to_be_attached()
            page.emulate_media(reduced_motion="reduce")
        card.click()
        dialog = page.get_by_role("dialog", name="视频作品")
        video = dialog.locator("video")

        def expect_paused(paused):
            # 等待播放控件同步状态，再读取视频元素的原生属性。
            label = "播放" if paused else "暂停"
            expect(dialog.get_by_role("button", name=label, exact=True)).to_be_visible()
            assert video.evaluate("(element) => element.paused") is paused

        expect(dialog.get_by_role("heading", name="视频作品")).to_be_focused()
        expect_paused(True)

        page.keyboard.down("Space")
        expect_paused(False)
        page.keyboard.down("Space")  # 长按时的重复事件。
        page.keyboard.up("Space")
        expect_paused(False)
        dialog.locator(".video-preview").press("Space")
        expect_paused(True)

        dialog.get_by_role("button", name="开启声音").press("Space")
        expect(dialog.get_by_role("button", name="静音")).to_be_visible()
        assert not video.evaluate("(element) => element.muted")
        expect_paused(True)
        slider = dialog.get_by_role("slider", name="播放位置")
        slider.press("Space")
        expect_paused(True)

        dialog.get_by_role("button", name="播放", exact=True).press("Space")
        expect_paused(False)
        assert page.evaluate("navigator.mediaSession.metadata.title") == "output-0-0.mp4"
        page.evaluate("navigator.mediaSession.actions.pause()")
        expect_paused(True)
        page.evaluate("navigator.mediaSession.actions.play()")
        expect_paused(False)
        pip = dialog.get_by_role("button", name="画中画", exact=True)
        pip.click()
        expect(pip).to_have_attribute("aria-pressed", "true")
        pip.click()
        expect(pip).to_have_attribute("aria-pressed", "false")
        dialog.get_by_role("button", name="放大查看").click()
        expect(dialog.get_by_role("button", name="退出放大")).to_be_visible()
        page.keyboard.press("Space")
        expect_paused(True)
        expect(dialog.get_by_role("button", name="退出放大")).to_be_visible()

        page.goto("/workspace/results")
        page.get_by_role("button", name=re.compile("^查看 分页结果")).click()
        result = page.get_by_role("dialog", name="分页结果")
        slider = result.get_by_role("slider", name="播放位置")
        slider.press("ArrowRight")
        expect(slider).to_have_attribute("aria-valuenow", "50")
        with page.expect_response(f"**/executions/{execution['id']}/cover*") as cover:
            result.get_by_role("button", name="用当前画面作组封面").click()
        assert cover.value.ok, cover.value.text()
        assert cover.value.json()["coverFrameMs"] == 50


@pytest.mark.parametrize(("width", "height"), [(1280, 900), (320, 640)], ids=["desktop", "mobile"])
def test_paged_result_restores_scroll_and_keyboard_focus(result_site, web_engine, width, height):
    address, credentials = result_site
    with web_engine.launch() as browser:
        page = browser.new_page(
            base_url=address, viewport={"width": width, "height": height}, locale="zh-CN"
        )
        page.goto("/workspace/results")
        sign_in = page.get_by_role("dialog", name="登录", exact=True)
        sign_in.get_by_label("账号", exact=True).fill(credentials["username"])
        sign_in.get_by_label("密码", exact=True).fill(credentials["password"])
        with page.expect_response("**/api/v1/auth/login") as login:
            sign_in.get_by_role("button", name="登录", exact=True).click()
        assert login.value.ok, login.value.status
        expect(sign_in).not_to_be_visible()
        with page.expect_response(
            lambda response: "/api/v1/executions?" in response.url and "cursor=" in response.url
        ) as next_page:
            expect(
                page.get_by_role("button", name=re.compile("^查看 分页结果")).first
            ).to_be_visible()
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        assert next_page.value.ok
        first, second = next_page.value.json()["items"][:2]
        first_label = f"第 {first['index'] + 1} 次执行"
        second_label = f"第 {second['index'] + 1} 次执行"
        trigger = page.get_by_role("button", name=re.compile(f"的{first_label}$"))
        trigger.scroll_into_view_if_needed()
        trigger.focus()
        expect(trigger).to_be_in_viewport()
        scroll_before = page.evaluate("window.scrollY")
        assert scroll_before > 0

        trigger.press("Enter")
        dialog = page.get_by_role("dialog", name="分页结果")
        expect(dialog.get_by_text(re.compile(f"· {first_label}$"))).to_be_visible()
        page.keyboard.press("ArrowRight")
        expect(dialog.get_by_text(re.compile(f"· {second_label}$"))).to_be_visible()
        page.keyboard.press("Escape")

        expect(dialog).not_to_be_visible()
        expect(trigger).to_be_focused()
        assert abs(page.evaluate("window.scrollY") - scroll_before) <= 1

        trigger.press("Enter")
        expect(page).to_have_url(re.compile(r"\?result="))
        asset = dialog.get_by_role("button", name="查看 output-1-1.png")
        asset.click()
        expect(dialog.get_by_role("button", name="返回成品列表")).to_be_visible()
        expect(page).to_have_url(re.compile(r"&artifact="))

        page.go_back()
        expect(asset).to_be_focused()
        page.go_back()
        expect(dialog).not_to_be_visible()
        expect(trigger).to_be_focused()
        assert abs(page.evaluate("window.scrollY") - scroll_before) <= 1

        page.go_forward()
        expect(asset).to_be_visible()
        page.go_forward()
        expect(dialog.get_by_role("img", name="output-1-1.png")).to_be_visible()
        dialog.get_by_role("button", name="返回成品列表").click()
        expect(asset).to_be_focused()
        page.keyboard.press("Escape")
        expect(trigger).to_be_focused()


@pytest.mark.parametrize("result_site", ["audio"], indirect=True)
@pytest.mark.parametrize(("width", "height"), [(1280, 900), (320, 640)], ids=["desktop", "mobile"])
def test_audio_player_uses_the_shared_playback_controls(result_site, width, height):
    address, credentials = result_site
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        page = browser.new_page(
            base_url=address, viewport={"width": width, "height": height}, locale="zh-CN"
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/workspace/results")
        page.get_by_role("button", name=re.compile("^查看 分页结果")).click()
        player = page.get_by_role("group", name="output-0-0.flac")
        audio = player.locator("audio")
        seek = player.get_by_role("slider", name="播放位置")
        expect(seek).to_be_visible()
        assert not audio.evaluate("element => element.controls")
        player.get_by_role("button", name="播放", exact=True).click()
        player.get_by_role("button", name="暂停", exact=True).click()
        assert audio.evaluate("element => element.paused")
        seek.press("ArrowRight")
        expect(seek).not_to_have_attribute("aria-valuenow", "0")
        player.get_by_role("button", name="静音", exact=True).click()
        assert audio.evaluate("element => element.muted")
        expect(player.get_by_role("button", name="开启声音", exact=True)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_filter_results_and_return_from_source_task(result_site):
    address, credentials = result_site
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        page = browser.new_page(
            base_url=address,
            locale="zh-CN",
            viewport={"width": 320, "height": 640},
            has_touch=True,
            is_mobile=True,
            reduced_motion="reduce",
            timezone_id="America/Sao_Paulo",
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        executions = page.request.get("/api/v1/executions").json()["items"]
        timestamp = executions[0]["created"]
        match = {
            "workflow_name": "分页",
            "created_from": timestamp,
            "created_before": timestamp + 1,
        }
        filtered = page.request.get("/api/v1/executions", params=match).json()["items"]
        assert executions[0] in filtered
        assert all(item["created"] == timestamp for item in filtered)
        assert (
            page.request.get(
                "/api/v1/executions", params={**match, "created_before": timestamp}
            ).json()["items"]
            == []
        )
        assert (
            page.request.get("/api/v1/executions", params={"workflow_name": "%"}).json()["items"]
            == []
        )

        page.goto("/workspace/results")
        name = page.get_by_role("searchbox", name="工作流名称")
        date = page.get_by_role("button", name=re.compile("^生成日期"))
        name.fill("不存在的工作流")
        expect(page.get_by_text("没有符合筛选条件的结果", exact=True)).to_be_visible()
        name.fill("分页")
        day = page.evaluate(
            """time => {
                const date = new Date(time);
                return [date.getFullYear(), date.getMonth() + 1, date.getDate()]
                  .map(Number).map(value => String(value).padStart(2, '0')).join('-');
            }""",
            timestamp,
        )
        date.press("Enter")
        calendar = page.get_by_role("dialog", name="生成日期", exact=True)
        expect(calendar.get_by_role("grid")).to_be_visible()
        selected = calendar.locator(f'[data-day="{day}"] button')
        expect(selected).to_be_focused()
        page.keyboard.press("ArrowRight")
        expect(selected).not_to_be_focused()
        page.keyboard.press("ArrowLeft")
        expect(selected).to_be_focused()
        page.keyboard.press("Enter")
        expect(calendar).not_to_be_visible()
        expect(date).to_be_focused()
        expect(page).to_have_url(re.compile(rf"[?&]date={day}(?:&|$)"))
        result = page.get_by_role("button", name=re.compile("^查看 分页结果")).first
        result.click()
        origin = page.url
        page.get_by_role("dialog", name="分页结果").get_by_role("link", name="查看来源任务").click()
        task = page.get_by_role("dialog", name="任务详情")
        expect(task.get_by_text("分页结果", exact=True)).to_be_visible()
        task.get_by_role("button", name="关闭", exact=True).click()
        expect(page).to_have_url(origin)
        expect(page.get_by_role("dialog", name="分页结果")).to_be_visible()
        page.keyboard.press("Escape")
        expect(date).to_have_accessible_name(re.compile("^生成日期 .+"))
        expect(name).to_have_value("分页")
        date.click()
        expect(calendar.locator(f'[data-day="{day}"]')).to_have_attribute("aria-selected", "true")
        calendar.get_by_role("button", name="清除日期", exact=True).click()
        expect(date).to_have_accessible_name("生成日期")
        expect(name).to_have_value("分页")
        date.click()
        calendar.get_by_role("button", name="今天", exact=True).click()
        expect(page).to_have_url(re.compile(rf"[?&]date={day}(?:&|$)"))
        page.get_by_role("main").get_by_role("button", name="清除搜索", exact=True).press("Enter")
        expect(name).to_have_value("")
        expect(name).to_be_focused()
        expect(page).to_have_url(f"{address}/workspace/results?date={day}")
        name.fill("分页")
        page.get_by_role("button", name="清除筛选", exact=True).click()
        expect(name).to_have_value("")
        expect(date).to_have_accessible_name("生成日期")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_loading_result_parameters_keeps_workflow_back_steps(result_site, web_engine):
    address, credentials = result_site
    with web_engine.launch() as browser:
        page = browser.new_page(
            base_url=address, viewport={"width": 1280, "height": 720}, locale="zh-CN"
        )
        login = page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        )
        assert login.ok, login.status
        page.goto("/workspace/workflows")
        card = page.get_by_role("button", name="分页结果", exact=True)
        card.click()
        workflow = page.locator(".workflow-dialog")
        workflow.get_by_role("tab", name="我的结果").click()
        results = workflow.get_by_role("button", name=re.compile("^查看 分页结果"))
        results.first.click()
        result = page.locator(".result-dialog")
        result.get_by_role("button", name="载入参数").click()
        expect(result).not_to_be_visible()
        expect(page).to_have_url(re.compile(r"\?version="))

        results.first.click()
        result.get_by_role("button", name="关闭", exact=True).click()
        expect(result).not_to_be_visible()
        expect(workflow).to_be_visible()
        expect(page).to_have_url(re.compile(r"\?version=[^&]+$"))

        workflow.locator("#run-count").focus()
        page.keyboard.press("Escape")
        expect(page).to_have_url(re.compile(r"/workspace/workflows$"))
        expect(card).to_be_focused()


@pytest.mark.parametrize(("width", "height"), [(1280, 720), (390, 844)], ids=["desktop", "mobile"])
def test_switching_versions_keeps_the_workflow_dialog_and_picker(
    result_site, graph, web_engine, width, height
):
    address, credentials = result_site
    with web_engine.launch() as browser:
        page = browser.new_page(
            base_url=address, viewport={"width": width, "height": height}, locale="zh-CN"
        )
        login = page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        )
        assert login.ok, login.status
        headers = {"Origin": address, "X-CSRF-Token": login.json()["csrfToken"]}
        (original,) = page.request.get("/api/v1/workflows?scope=mine").json()["items"]
        path = f"/api/v1/workflows/{original['id']}"
        assert page.request.post(f"{path}/publish", headers=headers).ok
        graph["1"]["inputs"]["text"] = "第二版默认提示词"
        middle = page.request.patch(path, data={"graph": graph}, headers=headers)
        assert middle.ok, middle.status
        graph["1"]["inputs"]["text"] = "第三版默认提示词"
        updated = page.request.patch(path, data={"graph": graph}, headers=headers)
        assert updated.ok, updated.status

        page.goto("/workspace/workflows")
        card = page.get_by_role("button", name="分页结果", exact=True)
        card.click()
        dialog = page.locator(".workflow-dialog")
        picker = dialog.get_by_role("combobox", name="工作流版本")
        expect(picker).to_have_text("v3 草稿")
        page.wait_for_function(
            "() => document.querySelector('.workflow-dialog').getAnimations().length === 0"
        )
        tab = dialog.get_by_role("tab", name="我的结果")
        tab.click()
        count = dialog.locator("#run-count")
        count.fill("2")
        elements = [(node, node.element_handle(), node.bounding_box()) for node in (dialog, picker)]

        def expect_stable():
            for locator, original_element, original_box in elements:
                assert locator.evaluate("(node, original) => node === original", original_element)
                assert locator.bounding_box() == pytest.approx(original_box, abs=1)

        historical = re.compile(re.escape(f"{path}?version_id={original['versionId']}") + "$")
        held = []
        page.route(historical, lambda route: held.append(route))

        def choose_old():
            with page.expect_request(historical):
                picker.click()
                page.get_by_role("option", name="v1", exact=True).click()
            expect(picker).to_have_attribute("aria-busy", "true")
            expect(picker).to_have_text("v3 草稿")
            expect(dialog.locator(".workflow-dialog-body")).to_have_attribute("inert", "")
            expect_stable()

        choose_old()
        held.pop().fulfill(status=404, json={"detail": "工作流版本暂不可用"})
        expect(page.get_by_text("工作流版本暂不可用", exact=True)).to_be_visible()
        expect(picker).not_to_have_attribute("aria-busy", "true")
        expect(count).to_have_value("2")
        expect_stable()

        choose_old()
        held.pop().continue_()
        expect(picker).to_have_text("v1")
        expect(tab).to_have_attribute("aria-selected", "true")
        expect(count).to_have_value("1")
        expect(picker).to_be_focused()
        expect_stable()

        picker.press("Enter")
        page.get_by_role("option", name="v3 草稿").press("Enter")
        expect(picker).to_have_text("v3 草稿")
        expect(count).to_have_value("2")
        expect(picker).to_be_focused()
        expect_stable()

        count.press("ArrowDown")
        expect(picker).to_have_text("v3 草稿")
        page.unroute(historical)
        middle_request = re.compile(
            re.escape(f"{path}?version_id={middle.json()['versionId']}") + "$"
        )
        page.route(middle_request, lambda route: held.append(route))
        title = dialog.locator(".workflow-dialog-heading h2")
        title.focus()
        page.keyboard.press("ArrowUp")
        expect(picker).to_have_text("v3 草稿")
        expect(picker).not_to_have_attribute("aria-busy", "true")

        with page.expect_request(middle_request):
            page.keyboard.press("ArrowDown")
        expect(picker).to_have_attribute("aria-busy", "true")
        expect_stable()
        page.keyboard.press("ArrowDown")
        expect(picker).to_have_text("v1")
        expect_stable()
        expect(title).to_be_focused()
        with page.expect_response(middle_request) as response:
            held.pop().continue_()
        assert response.value.ok
        page.unroute(middle_request)
        page.keyboard.press("ArrowDown")
        expect(picker).to_have_text("v1")
        expect(picker).not_to_have_attribute("aria-busy", "true")
        page.keyboard.press("ArrowUp")
        expect(picker).to_have_text("v2 草稿")
        expect_stable()
        expect(title).to_be_focused()

        page.go_back()
        expect(dialog).not_to_be_visible()
        expect(card).to_be_focused()


@pytest.mark.parametrize("result_site", ["reference"], indirect=True)
def test_workflow_fullscreen_keeps_draft_results_and_share_link(result_site, web_engine, tmp_path):
    address, credentials = result_site
    width, height = 1536, 900
    viewport = {"width": width, "height": height}
    mobile_viewport = {"width": 320, "height": 640}
    with web_engine.launch() as browser:
        page = browser.new_page(
            base_url=address, viewport=viewport, locale="zh-CN", reduced_motion="reduce"
        )
        login = page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        )
        assert login.ok, login.text()
        headers = {"Origin": address, "X-CSRF-Token": login.json()["csrfToken"]}
        (workflow,) = page.request.get("/api/v1/workflows?scope=mine").json()["items"]
        path = f"/api/v1/workflows/{workflow['id']}"
        assert page.request.post(f"{path}/publish", headers=headers).ok
        executions = page.request.get("/api/v1/executions").json()["items"]
        for index, execution in enumerate(executions[:2], start=1):
            published = page.request.post(
                "/api/v1/works",
                headers=headers,
                data={
                    "id": str(uuid4()),
                    "executionId": execution["id"],
                    "title": f"全屏作品 {index}",
                    "artifactIds": [execution["coverArtifactId"]],
                    "coverArtifactId": execution["coverArtifactId"],
                },
            )
            assert published.ok, published.text()
        graph = page.request.get(f"{path}/graph").json()["graph"]
        graph["1"]["inputs"]["image"] = "updated.png"
        assert page.request.patch(path, data={"graph": graph}, headers=headers).ok
        assert page.request.post(
            "/api/v1/workflows", data={"name": "相邻工作流", "graph": graph}, headers=headers
        ).ok

        page.add_init_script("""Object.defineProperty(navigator, 'clipboard', {
          value: { writeText: async (text) => { window.copiedWorkflowLink = text; } },
        });""")
        page.goto("/workspace/workflows")
        card = page.get_by_role("button", name=workflow["name"], exact=True)
        card.click()
        dialog = page.get_by_role("dialog", name=workflow["name"], exact=True)
        version = dialog.get_by_role("combobox", name="工作流版本")
        expect(version).to_have_text("v2 草稿")
        version.click()
        page.get_by_role("option", name="v1", exact=True).click()
        expect(version).to_have_text("v1")
        count = dialog.locator("#run-count")
        count.fill("3")
        dialog.locator('form.run-fields input[type="file"]').set_input_files(
            {
                "name": "本次参考图.png",
                "mimeType": "image/png",
                "buffer": picture("blue"),
            }
        )
        asset = dialog.get_by_text("本次参考图.png", exact=True)
        expect(asset).to_be_visible()

        def card_width(columns, *, filled=True):
            feed = dialog.locator(".gallery-panel[data-state='active'] .media-feed")
            return page.wait_for_function(
                """({ feed, columns, filled }) => {
                    const cards = [...feed.querySelectorAll('[data-media-id]')]
                        .map(card => card.getBoundingClientRect());
                    if (new Set(cards.map(card => card.left)).size !== columns) return false;
                    const lastRight = Math.max(...cards.map(card => card.right));
                    const fillsWidth = Math.abs(feed.getBoundingClientRect().right - lastRight)
                        <= columns; // Allow rounding to whole pixels per column.
                    return fillsWidth === filled && cards[0].width;
                }""",
                arg={"feed": feed.element_handle(), "columns": columns, "filled": filled},
            ).json_value()

        works_tab = dialog.get_by_role("tab", name="作品", exact=True)
        works_tab.click()
        normal_work_width = card_width(2)
        tab = dialog.get_by_role("tab", name="我的结果", exact=True)
        tab.click()
        results = dialog.get_by_role("button", name=re.compile(r"^查看 分页结果"))
        expect(results).to_have_count(6)
        result = results.first
        expect(result).to_be_visible()
        normal_result_width = card_width(3)

        elements = [(item, item.element_handle()) for item in (dialog, count, asset)]

        def expect_draft():
            for locator, original in elements:
                assert locator.evaluate("(node, original) => node === original", original)
            expect(count).to_have_value("3")
            expect(asset).to_be_visible()
            expect(tab).to_have_attribute("aria-selected", "true")
            expect(result).to_be_visible()

        def expect_viewport_fill(browser_page, panel):
            size = browser_page.viewport_size
            expect(panel).to_have_css("width", f"{size['width']}px")
            expect(panel).to_have_css("height", f"{size['height']}px")
            browser_page.wait_for_function(
                "panel => panel.getAnimations().length === 0", arg=panel.element_handle()
            )
            assert panel.bounding_box() == pytest.approx({"x": 0, "y": 0, **size}, abs=1)

        enter = dialog.get_by_role("button", name="全屏", exact=True)
        exit_fullscreen = dialog.get_by_role("button", name="退出全屏", exact=True)
        pager = dialog.locator(":scope > .dialog-navigation")
        expect(pager).to_be_visible()
        enter.press("Enter")
        expect(exit_fullscreen).to_be_focused()
        expect(dialog).to_have_attribute("data-fullscreen", "true")
        expect_viewport_fill(page, dialog)
        expect(pager).to_have_css("display", "none")
        expect_draft()
        fullscreen_result_width = card_width(4)
        assert fullscreen_result_width == pytest.approx(normal_result_width, rel=0.15)
        page.set_viewport_size({"width": 1600, "height": height})
        expect_viewport_fill(page, dialog)
        assert card_width(4) > fullscreen_result_width
        page.set_viewport_size(viewport)
        expect_viewport_fill(page, dialog)
        works_tab.click()
        fullscreen_work_width = card_width(2, filled=False)
        assert fullscreen_work_width == pytest.approx(normal_work_width, rel=0.15)
        assert fullscreen_work_width <= normal_work_width
        tab.click()
        expect_draft()
        page.screenshot(path=tmp_path / "workflow-fullscreen.png", animations="disabled")

        dialog.get_by_role("button", name="复制工作流链接", exact=True).click()
        page.wait_for_function("() => Boolean(window.copiedWorkflowLink)")
        copied = page.evaluate("window.copiedWorkflowLink")
        assert parse_qs(urlsplit(copied).query) == {
            "version": [workflow["versionId"]],
            "view": ["fullscreen"],
        }
        guest = browser.new_page(viewport=viewport, locale="zh-CN", reduced_motion="reduce")
        guest.goto(copied)
        direct = guest.get_by_role("dialog", name=workflow["name"], exact=True)
        expect(direct.get_by_role("button", name="退出全屏", exact=True)).to_be_visible()
        expect(direct).to_have_attribute("data-fullscreen", "true")
        expect_viewport_fill(guest, direct)

        phone = browser.new_page(
            viewport=mobile_viewport,
            locale="zh-CN",
            has_touch=True,
            is_mobile=web_engine.name != "firefox",
            reduced_motion="reduce",
        )
        for link in (copied, f"{address}/workflows/{workflow['id']}"):
            phone.goto(link)
            phone_dialog = phone.get_by_role("dialog", name=workflow["name"], exact=True)
            expect(phone_dialog.get_by_role("button", name="关闭", exact=True)).to_be_visible()
            expect(
                phone_dialog.get_by_role("button", name=re.compile("^全屏$|^退出全屏$"))
            ).to_have_count(0)
            expect_viewport_fill(phone, phone_dialog)

        page.set_viewport_size(mobile_viewport)
        expect(exit_fullscreen).not_to_be_visible()
        expect_draft()
        page.screenshot(path=tmp_path / "workflow-mobile.png", animations="disabled")
        page.set_viewport_size(viewport)
        expect(exit_fullscreen).to_be_visible()

        result.click()
        details = page.locator(".result-dialog")
        expect(details).to_be_visible()
        details.get_by_role("button", name="关闭", exact=True).click()
        expect(details).not_to_be_visible()
        expect(dialog).to_have_attribute("data-fullscreen", "true")
        exit_fullscreen.click()
        expect(enter).to_be_visible()
        expect(pager).to_be_visible()
        expect(dialog).not_to_have_attribute("data-fullscreen", "true")
        expect_draft()
        assert parse_qs(urlsplit(page.url).query) == {"version": [workflow["versionId"]]}

        grid = dialog.locator(".gallery-panel[data-state='active'] .media-feed").get_by_role("list")
        page.wait_for_function(
            """({ grid, toggle }) => {
                if (getComputedStyle(grid).pointerEvents === 'none') {
                    toggle.click();
                    return true;
                }
                grid.closest('.viewer-scroll').dispatchEvent(new Event('scroll'));
                return false;
            }""",
            arg={"grid": grid.element_handle(), "toggle": enter.element_handle()},
        )
        expect(dialog).to_have_attribute("data-fullscreen", "true")
        expect(grid).to_have_css("pointer-events", "auto")
        title = dialog.get_by_role("heading", name=workflow["name"], exact=True, level=2)
        title.press("ArrowLeft")
        neighbor = page.get_by_role("dialog", name="相邻工作流", exact=True)
        expect(neighbor).to_have_attribute("data-fullscreen", "true")
        neighbor.get_by_role("heading", name="相邻工作流", exact=True, level=2).press("ArrowRight")
        expect(dialog).to_have_attribute("data-fullscreen", "true")
        exit_fullscreen.click()
        page.set_viewport_size(mobile_viewport)
        expect(pager).to_have_css("display", "none")
        title.press("ArrowLeft")
        expect(neighbor).to_be_visible()
        expect(neighbor.locator(":scope > .dialog-navigation")).to_have_css("display", "none")
        neighbor.get_by_role("button", name="关闭", exact=True).click()
        expect(page).to_have_url(f"{address}/workspace/workflows")
        expect(card).to_be_focused()


@pytest.mark.parametrize("result_site", ["comparison"], indirect=True)
@pytest.mark.parametrize("width", [1440, 320], ids=["desktop", "mobile"])
def test_compare_result_uses_the_frozen_reference_offset(result_site, web_engine, width, tmp_path):
    address, credentials = result_site
    with web_engine.launch() as browser:
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 760},
            locale="zh-CN",
            reduced_motion="reduce",
            has_touch=width == 320,
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        (execution,) = page.request.get("/api/v1/executions").json()["items"]
        metadata = page.request.get("/api/v1/tasks/" + execution["taskId"] + "/inputs").json()
        (source,) = metadata["assets"]
        assert metadata["comparisons"]["2"] == {
            "assetId": source["id"],
            "width": 48,
            "height": 64,
            "x": 10,
            "y": 12,
            "uniformUpscale": False,
        }
        page.goto("/workspace/results?result=" + execution["id"])
        trigger = page.get_by_role("button", name="对比原图", exact=True)
        trigger.click()
        editor = page.get_by_role("dialog", name="对比原图", exact=True)
        slider = editor.get_by_role("slider", name="对比分界线")
        expect(slider).to_be_enabled()
        surface = editor.locator(".comparison-frame")
        image = surface.get_by_role("img", name="原图", exact=True)
        expect(image).to_be_visible()
        frame, original = image.evaluate(
            """img => [img.closest('.comparison-frame'), img]
                .map(el => el.getBoundingClientRect().toJSON())"""
        )
        assert abs(original["x"] - frame["x"] - frame["width"] * 10 / 48) < 1
        assert abs(original["y"] - frame["y"] - frame["height"] * 12 / 64) < 1
        assert abs(original["width"] - frame["width"] * 32 / 48) < 1
        editor.get_by_role("button", name="原图", exact=True).click()
        expect(slider).to_have_attribute("aria-valuenow", "100")
        slider.press("ArrowLeft")
        expect(slider).to_have_attribute("aria-valuenow", "99")
        bounds = surface.bounding_box()
        assert bounds
        quarter = {"x": bounds["width"] / 4, "y": bounds["height"] / 2}
        if width == 320:
            surface.tap(position=quarter)
        else:
            surface.click(position=quarter)
        expect(slider).to_have_attribute("aria-valuenow", "25")
        expect(editor.get_by_text("48 × 64 像素")).to_be_visible()
        assert editor.evaluate("e => e.scrollWidth <= e.clientWidth+1")
        editor.screenshot(path=tmp_path / "comparison.png", animations="disabled")
        editor.get_by_role("button", name="关闭", exact=True).click()
        expect(trigger).to_be_focused()
