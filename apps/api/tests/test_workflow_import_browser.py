import json
from pathlib import Path

import pytest
from helpers import serve_test_app
from official_test_support import OWNER, register, workflow_body
from playwright.sync_api import expect, sync_playwright


@pytest.mark.parametrize(("width", "height"), [(1440, 900), (390, 844)], ids=["desktop", "mobile"])
def test_personal_category_filter_and_authorized_import_methods(settings, graph, width, height):
    settings.official_owner = OWNER
    settings.static_dir = Path(__file__).resolve().parents[2] / "web" / "dist"
    with (
        serve_test_app(settings) as (address, http),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        manager = register(http, OWNER)
        author = register(http, "workflow-author")
        for category, name in [("image", "图像样例"), ("audio", "音频样例"), ("3d", "模型样例")]:
            http.post(
                "/api/v1/workflows", json={"name": name, "category": category, "graph": graph}
            ).raise_for_status()

        def sign_in(credentials):
            page = browser.new_page(base_url=address, viewport={"width": width, "height": height})
            assert page.request.post(
                "/api/v1/auth/login", data=credentials, headers={"Origin": address}
            ).ok
            page.goto("/workspace/workflows")
            return page

        def open_panel(page):
            page.get_by_role("button", name="导入工作流", exact=True).click()
            return page.get_by_role("dialog", name="导入工作流")

        page = sign_in(author)
        category = page.get_by_role("combobox", name="工作流分类")
        expect(category).to_have_text("全部分类")
        category.click()
        page.get_by_role("option", name="图像", exact=True).click()
        expect(page.get_by_role("button", name="图像样例", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="音频样例", exact=True)).to_have_count(0)
        expect(page.get_by_role("button", name="模型样例", exact=True)).to_have_count(0)
        page.reload()
        expect(category).to_have_text("图像")
        panel = open_panel(page)
        expect(panel.get_by_role("radiogroup")).to_have_count(0)
        expect(panel.get_by_role("combobox", name="导入分类")).to_have_text("自动分类")
        panel.locator('input[type="file"]').set_input_files(
            {
                "name": "保存音频.json",
                "mimeType": "application/json",
                "buffer": json.dumps({"1": {"class_type": "SaveAudio", "inputs": {}}}).encode(),
            }
        )
        with page.expect_response(
            lambda r: r.request.method == "POST" and r.url == address + "/api/v1/workflows"
        ) as created:
            panel.get_by_role("button", name="导入工作流", exact=True).click()
        assert created.value.ok and created.value.json()["category"] == "audio"
        page.wait_for_url("**/workflows/*")
        page.go_back()
        expect(category).to_have_text("图像")
        expect(page.get_by_role("button", name="保存音频", exact=True)).to_have_count(0)

        admin = sign_in(manager)
        manager_panel = open_panel(admin)
        manager_panel.get_by_role("radio", name="官方服务清单 JSON").click()
        manager_panel.get_by_role("button", name="管理导入权限").click()
        box = manager_panel.bounding_box()
        overlay = admin.locator(".ui-overlay").bounding_box()
        assert box and overlay and box["width"] == min(680, overlay["width"] - 32)
        assert manager_panel.evaluate("(dialog) => dialog.scrollWidth <= dialog.clientWidth")
        manager_panel.get_by_label("账号", exact=True).fill(author["username"])
        manager_panel.get_by_role("button", name="授权", exact=True).click()
        granted = manager_panel.get_by_role("listitem").filter(has_text=author["username"])
        expect(granted).to_be_visible()
        panel = open_panel(page)
        panel.get_by_role("radio", name="官方服务清单 JSON").click()
        expect(panel.get_by_role("button", name="管理导入权限")).to_have_count(0)
        expect(panel.get_by_role("radio", name="链接或 ID")).to_have_count(0)
        manifest = workflow_body(
            "browser-model", [{"name": "prompt", "kind": "string", "default": ""}]
        )["graph"]
        panel.locator('input[type="file"]').set_input_files(
            {
                "name": "model.json",
                "mimeType": "application/json",
                "buffer": json.dumps(manifest).encode(),
            }
        )
        with page.expect_response(
            lambda r: r.request.method == "POST" and r.url == address + "/api/v1/workflows"
        ) as imported:
            panel.get_by_role("button", name="导入工作流", exact=True).click()
        assert imported.value.ok and imported.value.json()["author"] == author["username"]
        granted.get_by_role("button", name="撤销授权").click()
        expect(granted).to_have_count(0)
        page.wait_for_url("**/workflows/*")
        page.go_back()
        panel = open_panel(page)
        expect(panel.get_by_role("radio", name="官方服务清单 JSON")).to_have_count(0)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
