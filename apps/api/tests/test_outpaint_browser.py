import re
from pathlib import Path

import httpx
import pytest
from helpers import CATALOG, report_inventory, serve_test_app
from official_test_support import register
from playwright.sync_api import expect
from test_inputs import picture
from test_team_spaces import open_space_picker

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


@pytest.mark.parametrize(
    ("width", "height", "team"),
    [(1440, 900, False), (320, 640, True)],
    ids=["personal-desktop", "team-mobile"],
)
def test_outpaint_applies_padding_to_one_queued_task(
    settings, web_engine, width, height, team, tmp_path
):
    directions = ("left", "top", "right", "bottom")
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
        "2": {
            "class_type": "ImagePadForOutpaint",
            "inputs": {"image": ["1", 0], **dict.fromkeys(directions, 0)},
        },
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
    }
    bounds = {"kind": "integer", "minimum": "0", "maximum": "16384", "step": "8"}
    catalog = {
        "nodes": CATALOG["nodes"]
        | {
            "LoadImage": {"inputs": {"image": {"kind": "image"}}},
            "ImagePadForOutpaint": {"inputs": dict.fromkeys(directions, bounds)},
        }
    }
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, web),
        web_engine.launch() as browser,
    ):
        credentials = register(web, "outpaint-author")
        team_info = (
            web.post("/api/v1/teams", json={"name": "扩图团队"}).raise_for_status().json()
            if team
            else None
        )
        scope = {"workspace_team": team_info["id"]} if team_info else {}
        machine = (
            web.post("/api/v1/machines", params=scope, json={"name": "扩图工作机"})
            .raise_for_status()
            .json()
        )
        with httpx.Client(
            base_url=address,
            headers={"Authorization": "Bearer " + machine["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker, catalog)
        workflow_path = (
            f"/api/v1/teams/{team_info['id']}/workflows" if team_info else "/api/v1/workflows"
        )
        workflow = (
            web.post(workflow_path, json={"name": "横幅扩图", "graph": graph})
            .raise_for_status()
            .json()
        )
        form = (
            web.get(
                f"/api/v1/workflows/{workflow['id']}/inputs",
                params={
                    **scope,
                    "machine_id": machine["machine"]["id"],
                    "version_id": workflow["versionId"],
                },
            )
            .raise_for_status()
            .json()
        )
        (image_field,) = [field["id"] for field in form["fields"] if field["kind"] == "image"]
        padding_fields = form["parameterPresentation"][image_field]["outpaint"]

        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": height},
            has_touch=team,
            locale="zh-CN",
            reduced_motion="reduce",
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/workspace/workflows")
        if team_info:
            open_space_picker(page).get_by_role(
                "button", name=team_info["name"], exact=True
            ).click()
        page.get_by_role("button", name=workflow["name"], exact=True).click()
        workflow_dialog = page.get_by_role("dialog", name=workflow["name"], exact=True)
        trigger = workflow_dialog.get_by_role("button", name="扩图范围", exact=True)
        expect(trigger).to_have_count(0)
        uploads_url = address + workflow_path.removesuffix("/workflows") + "/assets/"
        with page.expect_response(
            lambda r: r.request.method == "PUT" and r.url.startswith(uploads_url)
        ) as uploaded:
            workflow_dialog.locator('form.run-fields input[type="file"]').set_input_files(
                {
                    "name": "参考素材.png",
                    "mimeType": "image/png",
                    "buffer": picture("blue", size=(640, 480)),
                }
            )
        asset = uploaded.value.json()
        trigger.click()
        editor = page.get_by_role("dialog", name="扩图范围", exact=True)
        heading = editor.locator(".outpaint-heading")
        precision = heading.get_by_role("button", name="精确边距", exact=True)
        padding_panel = page.get_by_role("dialog", name="精确边距", exact=True)
        left = padding_panel.get_by_role("spinbutton", name="左侧补画", exact=True)
        right = padding_panel.get_by_role("spinbutton", name="右侧补画", exact=True)
        dimensions = editor.locator(".outpaint-dimensions")
        toolbar = heading.locator(".outpaint-toolbar")
        viewport = editor.locator(".outpaint-viewport")
        expect(editor).to_be_in_viewport(ratio=1)
        expect(dimensions).to_contain_text("扩图尺寸 640 × 480 像素")
        original_info = dimensions.bounding_box()
        expect(
            editor.get_by_role("radiogroup", name="画面比例").get_by_role("radio")
        ).to_have_count(10)
        editor.get_by_role("radio", name="16:9", exact=True).click()
        expect(editor.get_by_text("扩图尺寸 856 × 480 像素")).to_be_visible()
        expect(editor.get_by_text("原图占 75%")).to_be_visible()
        bounds = editor.bounding_box()
        assert bounds == pytest.approx({"x": 0, "y": 0, "width": width, "height": height}, abs=1)
        frame = editor.get_by_role("group", name="调整扩图边界", exact=True)
        expect(editor.locator("canvas")).to_be_visible()
        before_zoom = frame.bounding_box()
        assert before_zoom
        viewport.press("Equal")
        expect(editor.get_by_role("button", name="缩放 125%", exact=True)).to_be_visible()
        page.wait_for_function(
            "([node, width]) => Math.abs(node.getBoundingClientRect().width - width) <= 1",
            arg=[frame.element_handle(), before_zoom["width"] * 1.25],
            timeout=3_000,
        )
        expect(dimensions).to_contain_text("扩图尺寸 856 × 480 像素")
        viewport.press("0")
        expect(editor.get_by_role("button", name="缩放 100%", exact=True)).to_be_visible()
        board, info, tools = (
            viewport.bounding_box(),
            dimensions.bounding_box(),
            toolbar.bounding_box(),
        )
        assert board and info and tools and original_info
        assert tools["y"] + tools["height"] <= board["y"]
        assert board["y"] <= info["y"]
        assert 0 < board["y"] + board["height"] - info["y"] - info["height"] <= 16
        assert info["y"] + info["height"] == pytest.approx(
            original_info["y"] + original_info["height"], abs=1
        )
        for box in (info, tools):
            assert box["x"] + box["width"] / 2 == pytest.approx(width / 2, abs=1)
        assert heading.get_by_role("button", name="取消", exact=True).is_visible()
        apply = heading.get_by_role("button", name="应用", exact=True)
        apply_rect = apply.bounding_box()
        assert apply_rect and apply_rect["y"] + apply_rect["height"] <= board["y"]
        assert apply_rect["x"] + apply_rect["width"] == pytest.approx(
            board["x"] + board["width"], abs=1
        )
        if team:
            assert apply_rect["y"] + apply_rect["height"] <= tools["y"]
        else:
            assert apply_rect["y"] + apply_rect["height"] / 2 == pytest.approx(
                tools["y"] + tools["height"] / 2, abs=1
            )
        expect(editor.locator(".outpaint-band")).to_have_count(0)

        def drag(x, y, dx, dy=0):
            if team and web_engine.name == "chromium":
                touch = page.context.new_cdp_session(page)
                for kind, points in (
                    ("touchStart", [{"x": x, "y": y}]),
                    ("touchMove", [{"x": x + dx, "y": y + dy}]),
                    ("touchEnd", []),
                ):
                    touch.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": points})
                touch.detach()
            else:
                page.mouse.move(x, y)
                page.mouse.down()
                page.mouse.move(x + dx, y + dy, steps=8)
                page.mouse.up()

        box = frame.bounding_box()
        assert box
        drag(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, -box["width"] / 4)
        centered = editor.get_by_role("button", name="居中", exact=True)
        expect(centered).to_be_enabled()
        centered.click()
        expect(centered).to_be_disabled()
        expect(editor.get_by_text("扩图尺寸 856 × 480 像素")).to_be_visible()

        edge = editor.get_by_role("button", name="调整左边", exact=True)
        frame_before = frame.bounding_box()
        handle = edge.bounding_box()
        assert frame_before and handle
        drag(
            handle["x"] + handle["width"] / 2,
            handle["y"] + handle["height"] / 2,
            -32 * frame_before["width"] / 856,
        )
        expect(editor.get_by_text("扩图尺寸 888 × 480 像素")).to_be_visible()
        page.wait_for_function(
            "([node, x]) => node.getBoundingClientRect().left < x - 1",
            arg=[frame.element_handle(), frame_before["x"]],
        )
        expanded = frame.bounding_box()
        assert expanded
        assert expanded["x"] < frame_before["x"]
        assert expanded["x"] + expanded["width"] == pytest.approx(
            frame_before["x"] + frame_before["width"], abs=1
        )
        editor.get_by_role("button", name="撤销", exact=True).click()
        expect(editor.get_by_text("扩图尺寸 856 × 480 像素")).to_be_visible()
        editor.get_by_role("button", name="重做", exact=True).click()
        expect(editor.get_by_text("扩图尺寸 888 × 480 像素")).to_be_visible()
        editor.get_by_role("button", name="调整右下角", exact=True).press("ArrowDown")
        expect(editor.get_by_text("扩图尺寸 888 × 488 像素")).to_be_visible()
        expect(apply).to_be_in_viewport(ratio=1)
        assert editor.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        editor.screenshot(path=tmp_path / "outpaint.png", animations="disabled")

        editor.get_by_role("button", name="还原", exact=True).click()
        expect(editor.get_by_text("扩图尺寸 640 × 480 像素")).to_be_visible()
        editor.get_by_role("radio", name="9:16", exact=True).click()
        editor.get_by_role("button", name="取消", exact=True).click()
        expect(trigger).to_be_focused()
        trigger.click()
        expect(editor).to_be_in_viewport(ratio=1)
        expect(editor.locator("canvas")).to_be_visible()
        expect(dimensions).to_contain_text("扩图尺寸 640 × 480 像素")
        board = viewport.bounding_box()
        expect(padding_panel).to_have_count(0)
        precision.click()
        expect(padding_panel.get_by_role("spinbutton")).to_have_count(4)
        expect(padding_panel).to_have_attribute("data-side", "bottom")
        expect(padding_panel).to_be_in_viewport(ratio=1)
        assert viewport.bounding_box() == pytest.approx(board, abs=1)
        expect(left).to_have_value("0")
        expect(right).to_have_value("0")
        right.fill("7")
        expect(apply).to_be_disabled()
        expect(padding_panel.get_by_role("alert")).to_be_visible()
        right.fill("")
        expect(apply).to_be_disabled()
        page.keyboard.press("Escape")
        expect(padding_panel).to_have_count(0)
        expect(editor).to_be_visible()
        expect(precision).to_be_focused()
        expect(apply).to_be_enabled()
        precision.click()
        expect(right).to_have_value("0")
        left.fill("32")
        right.fill("216")
        expect(dimensions).to_contain_text("扩图尺寸 888 × 480 像素")
        apply.click()
        expect(editor).to_have_count(0)

        workflow_dialog.get_by_role("button", name=re.compile("^本次参数")).click()
        panel = page.get_by_role("dialog", name="本次参数", exact=True)
        expect(panel.get_by_role("spinbutton", name="左侧补画", exact=True)).to_have_value("32")
        expect(panel.get_by_role("spinbutton", name="右侧补画", exact=True)).to_have_value("216")
        panel.get_by_role("button", name="扩图范围", exact=True).click()
        precision.click()
        expect(right).to_have_value("216")
        page.keyboard.press("Escape")
        expect(padding_panel).to_have_count(0)
        expect(editor).to_be_visible()
        page.keyboard.press("Escape")
        expect(editor).to_have_count(0)
        panel.get_by_role("button", name="扩图范围", exact=True).click()
        precision.click()
        right.fill("224")
        apply.click()
        expect(panel.get_by_role("spinbutton", name="右侧补画", exact=True)).to_have_value("224")
        panel.get_by_role("button", name="应用", exact=True).click()
        expect(panel).to_have_count(0)

        tasks_url = f"{address}/api/v1/tasks" + (
            f"?workspace_team={team_info['id']}" if team_info else ""
        )
        tasks = []
        page.on(
            "request",
            lambda request: (
                tasks.append(request)
                if request.method == "POST" and request.url == tasks_url
                else None
            ),
        )
        with page.expect_response(
            lambda r: r.request.method == "POST" and r.url == tasks_url
        ) as submitted:
            workflow_dialog.get_by_role("button", name="生成", exact=True).click()
        assert submitted.value.status == 201, submitted.value.text()
        assert submitted.value.json()["status"] == "queued"
        (request,) = tasks
        expected_padding = {"left": 32, "top": 0, "right": 224, "bottom": 0}
        assert request.post_data_json["inputValues"] == {
            image_field: {"assetId": asset["id"]},
            **{field_id: expected_padding[side] for side, field_id in padding_fields.items()},
        }
