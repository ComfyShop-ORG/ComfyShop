import re
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from helpers import report_inventory, serve_test_app
from playwright.sync_api import expect, sync_playwright
from test_inputs import picture
from test_outputs import run_group
from test_team_spaces import open_space_picker
from test_worker import claim_body

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


@pytest.mark.parametrize(
    ("width", "height"), [(1280, 900), (440, 850), (320, 640)], ids=["desktop", "mobile", "narrow"]
)
def test_asset_library_upload_preview_and_reuse(settings, small_mp4, width, height, tmp_path):
    assert (WEB_DIST / "index.html").is_file(), "请先构建网页"
    settings.max_asset_bytes = 64 * 1024
    settings.asset_quota_bytes = 10 * 1024**3
    credentials = {"username": "asset-browser", "password": "browser-test-password"}
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "reference.png"}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }
    catalog = {
        "nodes": {
            "LoadImage": {"inputs": {"image": {"kind": "image"}}},
            "SaveImage": {"outputNode": True},
        }
    }
    with serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, web):
        session = web.post("/api/v1/auth/register", json=credentials).raise_for_status().json()
        web.headers["X-CSRF-Token"] = session["csrfToken"]
        team = web.post("/api/v1/teams", json={"name": "摄影团队"}).raise_for_status().json()
        settings.team_asset_quota_bytes[UUID(team["id"])] = 8192
        machine = web.post("/api/v1/machines", json={"name": "工作机"}).raise_for_status().json()
        workflow = (
            web.post("/api/v1/workflows", json={"name": "素材复用", "graph": graph})
            .raise_for_status()
            .json()
        )
        web.put(
            f"/api/v1/assets/{uuid4()}",
            params={"filename": "clip.mp4", "save_to_library": True},
            content=small_mp4,
        ).raise_for_status()
        with (
            httpx.Client(
                base_url=address,
                headers={"Authorization": "Bearer " + machine["apiKey"]},
                trust_env=False,
            ) as worker,
            sync_playwright() as playwright,
            playwright.chromium.launch() as browser,
        ):
            report_inventory(worker, catalog)
            page = browser.new_page(
                base_url=address,
                viewport={"width": width, "height": height},
                locale="zh-CN",
                has_touch=width <= 700,
                is_mobile=width <= 700,
                reduced_motion="reduce",
            )
            page.set_default_timeout(10_000)
            login = page.request.post(
                "/api/v1/auth/login", data=credentials, headers={"Origin": address}
            )
            assert login.ok, login.status
            page.goto("/workspace/assets")
            expect(page.get_by_role("tab", name="资产库")).to_have_attribute(
                "aria-selected", "true"
            )

            def open_usage_menu(account_name):
                account = page.get_by_role("button", name=account_name, exact=True)
                account.click()
                menu = page.get_by_role("menu")
                meter = menu.get_by_role("meter", name="空间用量", exact=True)
                expect(meter).to_be_visible()
                expect(meter).to_have_css("height", "8px")
                expect(menu).to_be_in_viewport(ratio=0.99)
                bounds = menu.bounding_box()
                viewport = page.viewport_size
                assert viewport
                assert bounds and 0 <= bounds["x"] <= width - bounds["width"] + 1
                assert 0 <= bounds["y"] <= viewport["height"] - bounds["height"] + 1
                return menu, meter

            expect(page.get_by_text("空间用量", exact=True)).to_have_count(0)
            menu, meter = open_usage_menu("账户 asset-browser")
            expect(meter).to_have_attribute("aria-valuenow", str(len(small_mp4)))
            expect(meter).to_have_attribute("aria-valuemax", str(settings.asset_quota_bytes))
            expect(menu.get_by_text("<1%", exact=True)).to_be_visible()
            expect(meter).to_have_attribute("data-low-usage", "")
            assert meter.evaluate("el => getComputedStyle(el, '::after').width") == "4px"
            page.keyboard.press("Escape")
            upload = page.get_by_label("上传素材")
            height_px = "44px" if width <= 700 else "40px"
            search = page.get_by_role("searchbox", name="搜索文件名")
            kind = page.get_by_role("combobox", name="素材类型")
            controls = (search.locator(".."), kind, upload.locator(".."))
            for control in controls:
                expect(control).to_have_css("height", height_px)
            search_box, kind_box, upload_box = (control.bounding_box() for control in controls)
            assert search_box and kind_box and upload_box
            assert kind_box["y"] == upload_box["y"]
            if width == 320:
                assert kind_box["y"] > search_box["y"]
                assert kind_box["x"] == search_box["x"]
            else:
                assert kind_box["y"] == search_box["y"]
            if width >= 1200:
                tabs = page.get_by_role("tablist", name="我的内容").bounding_box()
                sharing = page.get_by_role("button", name="共享空间", exact=True).bounding_box()
                assert tabs and sharing and search_box["y"] == tabs["y"] == sharing["y"]
                assert upload_box["x"] + upload_box["width"] + 8 == pytest.approx(sharing["x"])

            reference = picture("blue", size=(40, 64))
            upload_url = re.compile(r"/api/v1/assets/[^/?]+\?filename=reference\.png")
            held = []
            page.route(upload_url, lambda route: held.append(route))
            with page.expect_request(upload_url):
                upload.set_input_files(
                    {"name": "reference.png", "mimeType": "image/png", "buffer": reference}
                )
            expect(upload).to_be_disabled()
            expect(upload.locator("..")).to_have_css("cursor", "not-allowed")
            expect(upload.locator("..")).to_have_css("opacity", "0.4")
            held.pop().continue_()
            page.unroute(upload_url)
            card = page.get_by_role("button", name="预览 reference.png")
            expect(card).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.get_by_role("combobox", name="素材类型").click()
            page.get_by_role("option", name="视频").click()
            expect(page.get_by_role("button", name="预览 clip.mp4")).to_be_visible()
            expect(card).to_have_count(0)
            page.get_by_role("combobox", name="素材类型").click()
            page.get_by_role("option", name="全部类型").click()
            video = page.get_by_role("button", name="预览 clip.mp4")
            expect(video).to_be_visible()
            page.get_by_role("searchbox", name="搜索文件名").fill("reference")
            expect(video).to_have_count(0)
            card.click()
            preview = page.get_by_role("dialog", name="reference.png")
            expect(preview.get_by_role("img", name="reference.png")).to_have_js_property(
                "naturalWidth", 40
            )
            with page.expect_download() as downloaded:
                preview.get_by_role("link", name="下载原文件").click()
            assert downloaded.value.path().read_bytes() == reference
            preview.get_by_role("button", name="关闭", exact=True).click()
            expect(card).to_be_focused()
            page.get_by_role("main").get_by_role("button", name="清除搜索", exact=True).click()
            expect(search).to_be_focused()
            expect(video).to_be_visible()
            page.screenshot(path=tmp_path / "asset-search.png", animations="disabled")
            own_usage = str(len(small_mp4) + len(reference))
            personal_menu, personal_meter = open_usage_menu("账户 asset-browser")
            expect(personal_meter).to_have_attribute("aria-valuenow", own_usage)
            personal_menu.screenshot(
                path=tmp_path / "personal-space-usage.png", animations="disabled"
            )
            page.keyboard.press("Escape")
            open_space_picker(page).get_by_role("button", name="摄影团队", exact=True).click()
            expect(page.get_by_text("资产库还没有素材", exact=True)).to_be_visible()
            page.get_by_role("navigation", name="主导航").get_by_role(
                "link", name="工作机", exact=True
            ).click()
            expect(page).to_have_url(f"{address}/machines")
            team_menu, team_meter = open_usage_menu("账户 asset-browser · 摄影团队")
            expect(team_meter).to_have_attribute("aria-valuenow", "0")
            expect(team_meter).to_have_attribute("aria-valuemax", "8192")
            expect(team_menu.get_by_text("0%", exact=True)).to_be_visible()
            expect(team_menu.locator("[data-low-usage]")).to_have_count(0)
            expect(team_menu.locator("dd")).to_have_text(["0 B", "8.0 KiB", "8.0 KiB"])
            team_menu.screenshot(path=tmp_path / "team-space-usage.png", animations="disabled")
            page.keyboard.press("End")
            expect(team_menu.get_by_role("menuitem", name="退出登录", exact=True)).to_be_focused()
            page.keyboard.press("Escape")
            if width == 320:
                web.put(
                    f"/api/v1/teams/{team['id']}/assets/{uuid4()}",
                    params={"filename": "team-clip.mp4", "save_to_library": True},
                    content=small_mp4,
                ).raise_for_status()
                settings.team_asset_quota_bytes[UUID(team["id"])] = len(small_mp4)
                full_menu, full_meter = open_usage_menu("账户 asset-browser · 摄影团队")
                expect(full_menu.get_by_text("100%", exact=True)).to_be_visible()
                expect(full_meter).to_have_attribute("data-state", "complete")
                page.keyboard.press("Escape")
                settings.team_asset_quota_bytes[UUID(team["id"])] = 1024
                page.set_viewport_size({"width": width, "height": 520})
                limited_menu, limited_meter = open_usage_menu("账户 asset-browser · 摄影团队")
                over_quota = f"{len(small_mp4) * 100 // 1024}%"
                expect(limited_menu.get_by_text(over_quota, exact=True)).to_be_visible()
                expect(limited_meter).to_have_attribute("data-state", "complete")
                expect(limited_meter).to_have_attribute("aria-valuemax", "1024")
                expect(limited_menu.locator("dd").nth(1)).to_have_text("0 B")
                expect(limited_menu.locator("dd").first).not_to_have_text("1.0 KiB")
                assert limited_menu.evaluate("menu => menu.scrollHeight > menu.clientHeight")
                page.keyboard.press("End")
                sign_out = limited_menu.get_by_role("menuitem", name="退出登录", exact=True)
                expect(sign_out).to_be_focused()
                expect(sign_out).to_be_in_viewport()
                page.keyboard.press("Escape")
                page.set_viewport_size({"width": width, "height": height})
            open_space_picker(page).get_by_role("button", name="我的", exact=True).click()
            _, personal_meter = open_usage_menu("账户 asset-browser")
            expect(personal_meter).to_have_attribute("aria-valuenow", own_usage)
            page.keyboard.press("Escape")

            workflow_path = f"/workflows/{workflow['id']}"
            if width == 320:
                english = browser.new_page(
                    base_url=address,
                    viewport={"width": width, "height": height},
                    locale="en-US",
                    has_touch=True,
                    is_mobile=True,
                    reduced_motion="reduce",
                    storage_state=page.context.storage_state(),
                )
                english.goto(workflow_path)
                expect(
                    english.get_by_role("button", name="Run parameters Issues (1)")
                ).to_be_visible()
                expect(english.locator(".run-issue-hint")).to_be_visible()
                review = english.get_by_role("button", name="Review inputs", exact=True)
                box = review.bounding_box()
                assert box and box["x"] + box["width"] <= width
                review.click()
                expect(english.locator('.run-fields input[type="file"]')).to_be_focused()
                english.close()

                novice = browser.new_page(
                    base_url=address,
                    viewport={"width": width, "height": height},
                    locale="zh-CN",
                    has_touch=True,
                    is_mobile=True,
                )
                headers = {"Origin": address}
                register = novice.request.post(
                    "/api/v1/auth/register",
                    data={"username": "asset-new-user", "password": "browser-test-password"},
                    headers=headers,
                )
                assert register.ok
                novice.goto("/workspace/assets")
                empty = novice.get_by_text("资产库还没有素材", exact=True)
                expect(empty).to_be_visible()
                expect(novice.get_by_role("searchbox", name="搜索文件名")).to_have_count(0)
                novice.locator(".empty-state").get_by_label("上传素材").set_input_files(
                    {"name": "first.png", "mimeType": "image/png", "buffer": reference}
                )
                expect(novice.get_by_role("button", name="预览 first.png")).to_be_visible()
                expect(novice.get_by_role("searchbox", name="搜索文件名")).to_be_visible()
                draft = novice.request.post(
                    "/api/v1/workflows",
                    data={"name": "首次生成", "graph": graph},
                    headers={**headers, "X-CSRF-Token": register.json()["csrfToken"]},
                )
                assert draft.ok
                novice.goto(f"/workflows/{draft.json()['id']}")
                expect(novice.get_by_text("暂无作品", exact=True)).to_be_visible()
                expect(novice.get_by_role("button", name="从我的结果发布作品")).to_have_count(0)
                novice.get_by_role("link", name="接入工作机", exact=True).click()
                expect(novice.get_by_role("link", name="下载工作机", exact=True)).to_be_visible()
                novice.close()

            page.goto(workflow_path)
            oversized = b"0" * (settings.max_asset_bytes + 1)
            page.locator('.run-fields input[type="file"]').set_input_files(
                {"name": "oversized.png", "mimeType": "image/png", "buffer": oversized}
            )
            expect(
                page.get_by_role("alert").filter(has_text="素材不能超过 64.0 KiB。")
            ).to_be_visible()
            assert (
                web.put(
                    f"/api/v1/assets/{uuid4()}",
                    params={"filename": "oversized.png", "save_to_library": True},
                    content=oversized,
                ).status_code
                == 413
            )
            choose = page.get_by_role("button", name=re.compile("从资产库选择"))
            choose.click()
            picker = page.get_by_role("dialog", name="从资产库选择")
            choice = picker.get_by_role("button", name="使用 reference.png")
            expect(choice).to_be_visible()
            expect(picker.get_by_role("button", name="使用 clip.mp4")).to_have_count(0)
            choice.click()
            expect(choose).to_be_focused()
            expect(page.get_by_text("reference.png", exact=True)).to_be_visible()
            selected_reference = reference
            if width == 320:
                selected_reference = picture("green", size=(40, 64))
                field = page.locator('.run-fields input[type="file"]')
                field.focus()
                with page.expect_response(
                    re.compile(r"/api/v1/assets/[^/?]+\?filename=pasted\.png")
                ) as pasted:
                    field.evaluate(
                        """(input, bytes) => {
                          const clipboardData = new DataTransfer();
                          clipboardData.items.add(new File(
                            [new Uint8Array(bytes)], 'pasted.png', {type: 'image/png'},
                          ));
                          input.dispatchEvent(new ClipboardEvent('paste', {
                            clipboardData, bubbles: true, cancelable: true,
                          }));
                        }""",
                        list(selected_reference),
                    )
                assert pasted.value.ok
                expect(page.get_by_text("pasted.png", exact=True)).to_be_visible()
            with page.expect_response(
                lambda response: (
                    response.url.endswith("/api/v1/tasks") and response.request.method == "POST"
                )
            ) as submitted:
                page.get_by_role("button", name="生成", exact=True).click()
            assert submitted.value.status == 201, submitted.value.text()
            task = submitted.value.json()
            assert task["status"] == "queued"
            claim = claim_body()
            job = worker.post("/api/v1/worker/claim", json=claim).raise_for_status().json()
            assert job["task"]["id"] == task["id"]
            (asset,) = job["assets"]
            headers = {"X-Task-Lease": claim["leaseSecret"]}
            assert (
                worker.get(
                    f"/api/v1/worker/tasks/{task['id']}/assets/{asset['id']}", headers=headers
                )
                .raise_for_status()
                .content
                == selected_reference
            )
            _, (output,) = run_group(web, worker, task["id"], claim["leaseSecret"], members=1)
            worker.post(
                f"/api/v1/worker/tasks/{task['id']}/complete", headers=headers
            ).raise_for_status()

            page.goto("/workspace/results")
            page.get_by_role("button", name=re.compile("查看 素材复用")).click()
            result = page.get_by_role("dialog", name="素材复用")
            originals = set(settings.original_dir.iterdir())
            with page.expect_response(f"**/artifacts/{output['id']}/library*") as saved:
                result.get_by_role("button", name="存入资产库").click()
            assert saved.value.ok
            saved_asset = saved.value.json()
            assert saved_asset["sha256"] == output["sha256"]
            assert set(settings.original_dir.iterdir()) == originals

            page.goto("/workspace/assets")
            output_card = page.get_by_role("button", name="预览 output-0-0.png")
            output_card.click()
            output_preview = page.get_by_role("dialog", name="output-0-0.png")
            output_preview.get_by_role("button", name="移出资产库").click()
            with page.expect_response(f"**/assets/{saved_asset['id']}/library*") as removed:
                page.get_by_role("alertdialog").get_by_role("button", name="确认删除").click()
            assert removed.value.status == 204
            expect(output_preview).not_to_be_visible()
            expect(page.get_by_role("tab", name="资产库")).to_be_visible()
            expect(output_card).to_have_count(0)
            assert page.request.get(output["media"]["src"]).ok
