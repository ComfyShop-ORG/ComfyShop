from io import BytesIO
from pathlib import Path

import pytest
from helpers import report_inventory, serve_test_app, task_body
from httpx import Client
from PIL import Image
from playwright.sync_api import expect, sync_playwright
from test_languages import publish_work_result

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


@pytest.fixture
def bilingual_app(settings, graph):
    credentials = {"username": "bilingual", "password": "bilingual-test-password"}
    configured = settings.model_copy(
        update={"static_dir": WEB_DIST, "menu_languages": "zh,en,zh-tw"}
    )
    with serve_test_app(configured) as (address, web):
        session = web.post("/api/v1/auth/register", json=credentials).raise_for_status().json()
        web.headers["X-CSRF-Token"] = session["csrfToken"]
        machine = (
            web.post("/api/v1/machines", json={"name": "Render node"}).raise_for_status().json()
        )
        workflow = (
            web.post(
                "/api/v1/workflows",
                json={
                    "name": "原文人像生成与光影风格、镜头焦段和面部细节的保真重绘",
                    "graph": graph,
                },
            )
            .raise_for_status()
            .json()
        )
        with Client(
            base_url=address,
            headers={"Authorization": "Bearer " + machine["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker)
            body = task_body(web, workflow, machine["machine"]["id"])
            _, execution, work, _ = publish_work_result(web, worker, workflow, body)
        yield address, credentials, workflow, execution, work


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "mobile"])
def test_language_switch_keeps_paths_catalog_and_session(bilingual_app, width):
    address, credentials, workflow, _, _ = bilingual_app
    viewport = {"width": width, "height": 850}
    compact = width == 320
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        context = browser.new_context(base_url=address, viewport=viewport, locale="zh-HK")
        page = context.new_page()
        page.goto("/?q=原文#catalog")
        expect(page.locator("html")).to_have_attribute("lang", "zh-TW")
        original_url = page.url
        card = page.get_by_role("button", name=workflow["name"], exact=True)
        expect(card).to_be_visible()
        title = card.locator(".media-card-caption strong")
        expect(title).to_have_css("white-space", "normal" if compact else "nowrap")
        if compact:
            assert title.evaluate(
                "title => title.clientHeight === Math.round(2 * parseFloat(getComputedStyle(title).lineHeight))"
            )
        display = "顯示與語言" if compact else "語言"
        page.get_by_role("button", name=display, exact=True).click()
        language_group = page.get_by_role("group", name="語言") if compact else page
        expect(language_group.get_by_role("menuitem")).to_have_text(
            ["简体中文", "English", "繁體中文（台灣）"]
        )
        page.get_by_role("menuitem", name="English", exact=True).click()
        expect(page.locator("html")).to_have_attribute("lang", "en")
        expect(page).to_have_url(original_url)
        expect(page.get_by_role("button", name=workflow["name"], exact=True)).to_be_visible()
        expect(page.get_by_role("combobox", name="Sort", exact=True)).to_have_css(
            "height", "44px" if compact else "40px"
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/workspace/assets?view=library#files")
        expect(page.get_by_role("tab", name="Asset library")).to_have_attribute(
            "aria-selected", "true"
        )
        asset_url = page.url
        display = "Display and language" if compact else "Language"
        page.get_by_role("button", name=display, exact=True).click()
        page.get_by_role("menuitem", name="简体中文", exact=True).click()
        expect(page.get_by_role("tab", name="资产库")).to_have_attribute("aria-selected", "true")
        expect(page).to_have_url(asset_url)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        saved = context.storage_state()
        context.close()
        localized = browser.new_context(
            base_url=address, viewport=viewport, locale="ko-KR", storage_state=saved
        ).new_page()
        localized.goto("/workspace/assets")
        expect(localized.locator("html")).to_have_attribute("lang", "zh-CN")
        expect(localized.get_by_role("tab", name="资产库")).to_be_visible()


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "mobile"])
def test_glass_preference_in_account_menu_stays_in_browser(bilingual_app, web_engine, width):
    address, credentials, _, _, _ = bilingual_app
    viewport = {"width": width, "height": 850}
    with web_engine.launch() as browser:
        page = browser.new_page(base_url=address, viewport=viewport, locale="zh-CN")
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/")
        root = page.locator("html")
        header = page.get_by_role("banner").first
        account = page.get_by_role("button", name="账户 bilingual")
        glass = page.get_by_role("menuitemcheckbox", name="玻璃效果（实验性）")
        expect(root).to_have_attribute("data-glass", "off")
        expect(header).to_have_css("backdrop-filter", "none")
        canvas = root.evaluate("(node) => getComputedStyle(node).backgroundColor")
        expect(header).to_have_css("background-color", canvas)

        def top_pixel():
            screenshot = page.screenshot(
                clip={"x": width // 2, "y": 0, "width": 1, "height": 1}, scale="css"
            )
            with Image.open(BytesIO(screenshot)) as image:
                return image.convert("RGB").getpixel((0, 0))

        solid_edge = top_pixel()

        account.click()
        expect(glass).to_have_attribute("aria-checked", "false")
        expect(glass).to_be_in_viewport()
        glass.click()
        expect(root).to_have_attribute("data-glass", "on")
        expect(header).to_have_css("backdrop-filter", "blur(12px)")
        assert top_pixel() == solid_edge
        page.reload()
        expect(root).to_have_attribute("data-glass", "on")
        expect(header).to_have_css("backdrop-filter", "blur(12px)")

        fresh = browser.new_page(base_url=address, viewport=viewport, locale="zh-CN")
        assert fresh.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        fresh.goto("/")
        expect(fresh.locator("html")).to_have_attribute("data-glass", "off")
        fresh.close()

        page.emulate_media(contrast="more")
        page.reload()
        expect(header).to_have_css("backdrop-filter", "none")
        expect(header).to_have_css("background-color", canvas)
        expect(root).to_have_attribute("data-glass", "on")
        page.emulate_media(contrast="no-preference")
        page.reload()
        expect(header).to_have_css("backdrop-filter", "blur(12px)")
        account.click()
        expect(glass).to_have_attribute("aria-checked", "true")
        glass.press("Enter")
        expect(header).to_have_css("backdrop-filter", "none")
        page.reload()
        expect(root).to_have_attribute("data-glass", "off")


@pytest.mark.parametrize("width", [2560, 320], ids=["wide-desktop", "mobile"])
def test_full_width_preference_follows_page_navigation(bilingual_app, web_engine, width):
    address, credentials, _, _, _ = bilingual_app
    with web_engine.launch() as browser:
        page = browser.new_page(
            base_url=address, viewport={"width": width, "height": 850}, locale="zh-CN"
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/")
        header = page.locator(".header-inner")
        main = page.get_by_role("main")
        account = page.get_by_role("button", name="账户 bilingual")
        full_width = page.get_by_role("menuitemcheckbox", name="全宽布局（实验性）")

        def expect_layout(max_width):
            available_width = page.locator("body").evaluate("body => body.clientWidth")
            expected = available_width if max_width == "none" else min(available_width, 1888)
            for container in (header, main):
                expect(container).to_have_css("max-width", max_width)
                expect(container).to_have_css("width", f"{expected}px")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

        expect_layout("1888px")
        account.click()
        expect(full_width).to_have_attribute("aria-checked", "false")
        full_width.click()
        expect_layout("none")

        page.get_by_role("link", name="我的", exact=True).click()
        assets = page.get_by_role("tab", name="资产库", exact=True)
        assets.click()
        expect(assets).to_have_attribute("aria-selected", "true")
        expect_layout("none")
        page.reload()
        expect(assets).to_have_attribute("aria-selected", "true")
        expect_layout("none")

        account.click()
        expect(full_width).to_have_attribute("aria-checked", "true")
        full_width.press("Enter")
        expect_layout("1888px")


@pytest.mark.parametrize("width", [1440, 320], ids=["desktop", "mobile"])
def test_workflow_fullscreen_preference_in_account_menu(bilingual_app, web_engine, width):
    address, credentials, workflow, _, _ = bilingual_app
    compact = width == 320
    path = f"{address}/workflows/{workflow['id']}"
    fullscreen_link = f"{path}?view=fullscreen"
    with web_engine.launch() as browser:
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 640 if compact else 850},
            locale="zh-CN",
            reduced_motion="reduce",
            has_touch=compact,
            is_mobile=compact and web_engine.name != "firefox",
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.add_init_script("""Object.defineProperty(navigator, 'clipboard', {
          value: { writeText: async (text) => { window.copiedWorkflowLink = text; } },
        });""")
        page.goto("/")
        account = page.get_by_role("button", name="账户 bilingual", exact=True)
        preference = page.get_by_role(
            "menuitemcheckbox", name="工作流弹框默认全屏（实验性）", exact=True
        )
        card = page.get_by_role("button", name=workflow["name"], exact=True)
        dialog = page.get_by_role("dialog", name=workflow["name"], exact=True)

        def close_dialog():
            dialog.get_by_role("button", name="关闭", exact=True).click()
            expect(dialog).to_have_count(0)

        account.click()
        expect(preference).to_have_attribute("aria-checked", "false")
        preference.click()
        card.click()
        expect(dialog).to_have_attribute("data-fullscreen", "true")
        expect(page).to_have_url(path)
        page.reload()
        expect(dialog).to_have_attribute("data-fullscreen", "true")

        if compact:
            expect(dialog).to_have_css("width", "320px")
            expect(dialog).to_have_css("height", "640px")
            expect(dialog.get_by_role("button", name="退出全屏", exact=True)).to_have_count(0)
        else:
            expect(dialog).to_have_css("width", "1440px")
            dialog.get_by_role("button", name="复制工作流链接", exact=True).click()
            page.wait_for_function("() => Boolean(window.copiedWorkflowLink)")
            assert page.evaluate("window.copiedWorkflowLink") == fullscreen_link
            dialog.get_by_role("button", name="退出全屏", exact=True).click()
            expect(page).to_have_url(f"{path}?view=dialog")
            expect(dialog).to_have_css("width", "1240px")
            page.reload()
            expect(dialog).to_have_css("width", "1240px")

        close_dialog()
        card.click()
        expect(dialog).to_have_attribute("data-fullscreen", "true")
        close_dialog()

        account.click()
        expect(preference).to_have_attribute("aria-checked", "true")
        preference.press("Enter")
        card.click()
        expect(dialog).to_be_visible()
        expect(dialog).not_to_have_attribute("data-fullscreen", "true")
        if compact:
            expect(dialog).to_have_css("width", "320px")
            expect(dialog.get_by_role("button", name="全屏", exact=True)).to_have_count(0)
        else:
            expect(dialog).to_have_css("width", "1240px")
        page.goto(fullscreen_link)
        expect(dialog).to_have_attribute("data-fullscreen", "true")


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "mobile"])
def test_work_and_version_links_are_shared_by_all_languages(bilingual_app, width):
    address, credentials, workflow, execution, work = bilingual_app
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        for locale in ("zh-CN", "en"):
            page = browser.new_page(
                base_url=address, viewport={"width": width, "height": 850}, locale=locale
            )
            assert page.request.post(
                "/api/v1/auth/login", data=credentials, headers={"Origin": address}
            ).ok
            work_path = f"/workflows/{workflow['id']}?work={work['id']}"
            page.add_init_script(
                """Object.defineProperties(navigator, {
                  canShare: { value: () => true },
                  share: { value: (data) => { window.sharedLink = data; return Promise.resolve(); } },
                })"""
            )
            page.goto(work_path)
            expect(page.locator("html")).to_have_attribute("lang", locale)
            work_dialog = page.get_by_role("dialog", name=work["title"]).last
            expect(work_dialog).to_be_visible()
            share = "系统分享" if locale == "zh-CN" else "System share"
            work_dialog.get_by_role("button", name=share, exact=True).click()
            assert page.evaluate("window.sharedLink.url") == address + work_path
            expect(page).to_have_url(address + work_path)
            page.goto(f"/workflows/{workflow['id']}?version={workflow['versionId']}")
            workflow_dialog = page.get_by_role("dialog", name=workflow["name"], exact=True)
            expect(workflow_dialog).to_be_visible()
            workflow_dialog.get_by_role("button", name=share, exact=True).click()
            assert page.evaluate("window.sharedLink.title") == workflow["name"]
            page.goto(f"/workspace/results?result={execution['id']}")
            expect(page.get_by_role("dialog", name=workflow["name"])).to_be_visible()
            page.close()


@pytest.mark.parametrize("width", [1200, 1024, 440], ids=["desktop", "narrow-desktop", "mobile"])
def test_workspace_filters_share_the_same_layout(bilingual_app, width, tmp_path):
    address, credentials, _, _, _ = bilingual_app
    mobile = width < 700
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 850},
            locale="zh-CN",
            has_touch=mobile,
            is_mobile=mobile,
            reduced_motion="reduce",
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/workspace/workflows")
        tabs = page.get_by_role("tablist", name="我的内容")
        expect(tabs).to_be_visible()
        original = tabs.bounding_box()
        assert original
        control_height = 44 if mobile else 40
        for tab, control in (
            ("工作流", page.get_by_role("combobox", name="工作流分类")),
            ("作品", page.get_by_role("combobox", name="作品分类")),
            ("结果", page.get_by_role("searchbox", name="工作流名称")),
            ("任务", page.get_by_role("combobox", name="任务状态")),
        ):
            trigger = tabs.get_by_role("tab", name=tab, exact=True)
            trigger.click()
            expect(trigger).to_have_attribute("aria-selected", "true")
            expect(control).to_have_css("height", f"{control_height}px")
            assert tabs.bounding_box() == original
            visible_control = control.locator("..") if tab == "结果" else control
            position = visible_control.bounding_box()
            assert position
            if mobile:
                assert position["y"] == original["y"] + original["height"] + 16
            else:
                assert position["y"] == original["y"]
            if tab == "结果":
                date = page.get_by_label("生成日期", exact=True)
                expect(date).to_have_css("height", f"{control_height}px")
                expect(page.get_by_text("生成日期", exact=True)).to_be_visible()
                date_position = date.bounding_box()
                assert date_position and date_position["y"] == position["y"]
                control.fill("原文")
                clear = page.get_by_role("button", name="清除筛选", exact=True)
                expect(clear).to_have_css("height", f"{control_height}px")
                if width >= 1200:
                    clear_position = clear.bounding_box()
                    assert clear_position and clear_position["y"] == position["y"]
                clear.click()
                expect(control).to_have_value("")
                expect(control).to_be_focused()
            if tab == "工作流":
                action = page.get_by_role("button", name="导入工作流", exact=True)
                expect(action).to_have_css("height", f"{control_height}px")
                action_position = action.bounding_box()
                assert action_position and action_position["y"] == position["y"]
        status = page.get_by_role("combobox", name="任务状态")
        sharing = page.get_by_role("button", name="共享空间", exact=True)
        expect(sharing).to_have_css("height", f"{control_height}px")
        status_box = status.bounding_box()
        share_box = sharing.bounding_box()
        toolbar_box = page.locator("main .tabbed-toolbar").bounding_box()
        assert status_box and share_box and toolbar_box
        assert status_box["y"] == share_box["y"]
        assert status_box["x"] + status_box["width"] + 8 == pytest.approx(share_box["x"])
        assert share_box["x"] + share_box["width"] == pytest.approx(
            toolbar_box["x"] + toolbar_box["width"]
        )
        page.screenshot(path=tmp_path / "task-toolbar.png", animations="disabled")
        status.click()
        page.get_by_role("option", name="失败", exact=True).click()
        expect(page.get_by_text("没有符合筛选的任务")).to_be_visible()
        page.get_by_role("button", name="查看全部任务", exact=True).click()
        expect(status).to_have_text("全部状态")
        expect(status).to_be_focused()


def test_narrow_english_tabs_keep_labels_inside_dialogs(bilingual_app):
    address, credentials, _, _, _ = bilingual_app
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        page = browser.new_page(
            base_url=address,
            viewport={"width": 320, "height": 640},
            locale="en-US",
            has_touch=True,
            is_mobile=True,
            reduced_motion="reduce",
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/")
        for label in ("Open search", "Display and language"):
            icon = page.get_by_role("button", name=label, exact=True)
            expect(icon).to_have_css("height", "44px")
            expect(icon).to_have_css("width", "44px")
        page.get_by_role("button", name="Display and language", exact=True).click()
        page.get_by_role("menuitem", name="Switch to light mode", exact=True).click()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        page.reload()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        for label in ("Workflow category", "Sort"):
            expect(page.get_by_role("combobox", name=label, exact=True)).to_have_css(
                "height", "44px"
            )
        page.get_by_role("button", name="Account: bilingual", exact=True).click()
        page.get_by_role("menuitem", name="Account settings", exact=True).click()

        def assert_tabs_fit(dialog):
            expect(dialog.get_by_role("button", name="Close", exact=True)).to_have_css(
                "width", "44px"
            )
            tabs = dialog.get_by_role("tab")
            expect(tabs).to_have_count(3)
            assert tabs.evaluate_all("""tabs => tabs.every(tab => {
              const rect = tab.getBoundingClientRect();
              const list = tab.closest('[role=tablist]').getBoundingClientRect();
              return tab.scrollWidth <= tab.clientWidth && rect.left >= list.left && rect.right <= list.right;
            })""")

        assert_tabs_fit(page.get_by_role("dialog"))
        page.keyboard.press("Escape")
        page.goto("/workspace/tasks")
        page.get_by_role("button", name="Task details", exact=True).click()
        assert_tabs_fit(page.get_by_role("dialog"))
