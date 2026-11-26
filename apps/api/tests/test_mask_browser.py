import re
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from helpers import CATALOG, report_inventory, serve_test_app
from official_test_support import register
from PIL import Image
from playwright.sync_api import expect
from test_inputs import picture
from test_team_spaces import open_space_picker

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def check_smart_selection(page, editor, surface, team, engine, scale, center_x, center_y):
    def fit_point(x, y):
        return center_x + (x - 320) * scale, center_y + (y - 200) * scale

    tap = page.touchscreen.tap if team else page.mouse.click
    overlay = surface.locator("canvas").nth(1)

    def expect_ink(point, selected):
        page.wait_for_function(
            """([canvas, x, y, selected]) => {
              const rect = canvas.getBoundingClientRect();
              const px = Math.floor((x - rect.left) * canvas.width / rect.width);
              const py = Math.floor((y - rect.top) * canvas.height / rect.height);
              return (canvas.getContext('2d').getImageData(px, py, 1, 1).data[3] > 0) === selected;
            }""",
            arg=[overlay.element_handle(), *point, selected],
            timeout=20_000,
        )

    # Select the helmet on the original photo after zooming and moving the view.
    helmet = fit_point(428, 318)
    dx, dy = -24, -20
    editor.get_by_role("radio", name="加选", exact=True).click()
    if team and engine == "chromium":
        cdp = page.context.new_cdp_session(page)
        first = {"x": helmet[0] - 15, "y": helmet[1], "id": 1}
        second = {"x": helmet[0] + 15, "y": helmet[1], "id": 2}
        for event, points in (
            ("touchStart", [first]),
            ("touchStart", [first, second]),
            (
                "touchMove",
                [
                    {**first, "x": helmet[0] + dx - 24, "y": helmet[1] + dy},
                    {**second, "x": helmet[0] + dx + 24, "y": helmet[1] + dy},
                ],
            ),
            ("touchEnd", []),
        ):
            cdp.send("Input.dispatchTouchEvent", {"type": event, "touchPoints": points})
        cdp.detach()
    else:
        page.mouse.move(*helmet)
        page.mouse.wheel(0, -150)
        expect(editor.get_by_role("button", name=re.compile(r"^缩放 "))).not_to_have_text("100%")
        page.keyboard.down("Space")
        page.mouse.down()
        page.mouse.move(helmet[0] + dx, helmet[1] + dy, steps=4)
        page.mouse.up()
        page.keyboard.up("Space")
    zoom = editor.get_by_role("button", name=re.compile(r"^缩放 "))
    expect(zoom).not_to_have_text("100%")
    point = (helmet[0] + dx, helmet[1] + dy)
    expect_ink(point, False)
    if not team and engine == "chromium":
        wasm = "**/vision_wasm_module_internal-*.wasm"
        page.context.route(wasm, lambda route: route.abort())
        try:
            tap(*point)
            expect(editor.get_by_role("alert")).to_contain_text("加载失败", timeout=15_000)
            editor.get_by_role("radio", name="画笔", exact=True).click()
            tap(*point)
            expect_ink(point, True)
            editor.get_by_role("button", name="撤销", exact=True).click()
            expect_ink(point, False)
        finally:
            page.context.unroute(wasm)
        editor.get_by_role("radio", name="加选", exact=True).click()
    tap(*point)
    expect_ink(point, True)
    editor.get_by_role("radio", name="减选", exact=True).click()
    tap(*point)
    expect_ink(point, False)
    editor.get_by_role("button", name="撤销", exact=True).click()
    expect_ink(point, True)
    editor.get_by_role("button", name="重做", exact=True).click()
    expect_ink(point, False)
    zoom.click()
    page.get_by_role("button", name="适合画布", exact=True).click()
    page.keyboard.press("Escape")
    expect(zoom).to_have_text("100%")

    editor.get_by_role("radio", name="加选", exact=True).click()
    for name, location in (
        ("头发", (296, 43)),
        ("面部皮肤", (300, 108)),
        ("背景", (375, 81)),
        ("衣服", (195, 248)),
    ):
        editor.get_by_role("button", name="人像分区", exact=True).click()
        page.get_by_role("menuitem", name=name, exact=True).click()
        expect_ink(fit_point(*location), True)
        if name != "衣服":
            editor.get_by_role("button", name="撤销", exact=True).click()
            expect_ink(fit_point(*location), False)
    editor.get_by_role("radio", name="橡皮擦", exact=True).click()
    tap(*fit_point(195, 248))
    expect_ink(fit_point(195, 248), False)
    expect_ink(fit_point(181, 277), True)


@pytest.mark.parametrize(
    ("width", "height", "team"),
    [(1440, 900, False), (320, 640, True)],
    ids=["personal-desktop", "team-mobile"],
)
@pytest.mark.parametrize("native", [False, True], ids=["separate", "native-alpha"])
def test_mask_zoom_exports_source_pixels_for_the_paired_input(
    settings, web_engine, width, height, team, tmp_path, native
):
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
        "2": {"class_type": "LoadImageMask", "inputs": {"image": "mask.png", "channel": "red"}},
        "3": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {"pixels": ["1", 0], "mask": ["2", 0]},
        },
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}},
    }
    reference_bytes = picture("blue", size=(640, 400))
    if native:
        del graph["2"]
        graph["3"]["inputs"]["mask"] = ["1", 1]
        stream = BytesIO()
        source = Image.new("RGBA", (640, 400), (30, 60, 140, 255))
        # NASA's public-domain astronaut portrait from scikit-image, on a non-square source.
        with Image.open(Path(__file__).parent / "fixtures/astronaut.jpg") as portrait:
            source.paste(portrait.resize((400, 400)), (120, 0))
        source.paste((30, 60, 140, 64), (0, 0, 24, 24))
        source.save(stream, format="PNG")
        reference_bytes = stream.getvalue()
    image_input = {"kind": "image"}
    catalog = {
        "nodes": CATALOG["nodes"]
        | {
            "LoadImage": {"inputs": {"image": image_input}},
            "LoadImageMask": {
                "inputs": {
                    "image": image_input,
                    "channel": {"kind": "choice", "choices": ["red", "alpha"]},
                },
            },
            "VAEEncodeForInpaint": {"inputs": {}},
        }
    }
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, web),
        web_engine.launch() as browser,
    ):
        credentials = register(web, "mask-author")
        team_id = (
            web.post("/api/v1/teams", json={"name": "遮罩团队"}).raise_for_status().json()["id"]
            if team
            else None
        )
        scope = {"workspace_team": team_id} if team_id else {}
        prefix = f"/api/v1/teams/{team_id}" if team_id else "/api/v1"
        machine = (
            web.post("/api/v1/machines", params=scope, json={"name": "重绘工作机"})
            .raise_for_status()
            .json()
        )
        with httpx.Client(
            base_url=address,
            headers={"Authorization": "Bearer " + machine["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker, catalog)
        workflow = (
            web.post(prefix + "/workflows", json={"name": "局部重绘", "graph": graph})
            .raise_for_status()
            .json()
        )
        inputs = (
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
        (source_id,) = [field["id"] for field in inputs["fields"] if field["nodeId"] == "1"]
        mask_id = inputs["parameterPresentation"][source_id]["mask"]["fieldId"]
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": height},
            locale="zh-CN",
            has_touch=team,
            reduced_motion="reduce",
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/workspace/workflows")
        model_requests = []
        page.context.on(
            "request",
            lambda r: (
                model_requests.append(r.url)
                if "/assets/" in r.url
                and any(
                    name in r.url
                    for name in (
                        "mask-selection.worker-",
                        "vision_wasm_",
                        "interactive_segmentation-",
                        "selfie_multiclass_",
                    )
                )
                else None
            ),
        )
        if team_id:
            open_space_picker(page).get_by_role("button", name="遮罩团队", exact=True).click()
        page.get_by_role("button", name=workflow["name"], exact=True).click()
        form = page.get_by_role("dialog", name=workflow["name"], exact=True)
        edit = form.get_by_role("button", name="编辑遮罩", exact=True)
        expect(edit).to_have_count(0)

        def asset_upload(response):
            return response.request.method == "PUT" and response.url.startswith(
                address + prefix + "/assets/"
            )

        with page.expect_response(asset_upload) as uploaded:
            form.get_by_label("参考图", exact=True).set_input_files(
                {
                    "name": "参考图.png",
                    "mimeType": "image/png",
                    "buffer": reference_bytes,
                }
            )
        reference = uploaded.value.json()
        edit.click()
        editor = page.get_by_role("dialog", name="编辑遮罩", exact=True)
        surface = editor.get_by_role("group", name="遮罩画布", exact=True)
        apply = editor.get_by_role("button", name="应用", exact=True)
        undo = editor.get_by_role("button", name="撤销", exact=True)
        zoom = editor.get_by_role("button", name=re.compile(r"^缩放 \d+%$"))
        expect(editor).to_be_in_viewport(ratio=1)
        expect(surface.locator("canvas").first).to_be_visible()
        expect(apply).to_be_disabled()
        viewport = surface.bounding_box()
        assert viewport
        gutter = surface.evaluate("node => parseFloat(getComputedStyle(node).paddingLeft)")
        scale = min((viewport["width"] - gutter * 2) / 640, (viewport["height"] - gutter * 2) / 400)
        center_x = viewport["x"] + viewport["width"] / 2
        center_y = viewport["y"] + viewport["height"] / 2
        anchor_x, anchor_y = center_x + round(40 * scale), center_y - round(15 * scale)

        if team and web_engine.name == "chromium":
            touch = page.context.new_cdp_session(page)
            first = {"x": anchor_x - 20, "y": anchor_y, "id": 1}
            second = {"x": anchor_x + 20, "y": anchor_y, "id": 2}
            touch.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [first]})
            touch.send(
                "Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [first, second]}
            )
            touch.send(
                "Input.dispatchTouchEvent",
                {
                    "type": "touchMove",
                    "touchPoints": [
                        {**first, "x": anchor_x - 50},
                        {**second, "x": anchor_x + 50},
                    ],
                },
            )
            touch.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            touch.detach()
            expect(zoom).to_have_text("250%")
            expect(undo).to_be_disabled()
            expect(apply).to_be_disabled()
        else:
            page.mouse.move(anchor_x, anchor_y)
            page.mouse.wheel(0, -150)
            expect(zoom).not_to_have_text("100%")

        def paint(x, y):
            if team:
                page.touchscreen.tap(x, y)
            else:
                page.mouse.click(x, y)

        if not team:
            page.keyboard.down("Space")
            page.mouse.down()
            page.mouse.move(anchor_x + 48, anchor_y + 24, steps=6)
            page.mouse.up()
            page.keyboard.up("Space")
            expect(undo).to_be_disabled()
            paint(anchor_x + 48, anchor_y + 24)
        else:
            paint(anchor_x, anchor_y)
        expect(apply).to_be_enabled()
        undo.click()
        expect(apply).to_be_disabled()
        editor.get_by_role("button", name="重做", exact=True).click()
        zoom.click()
        page.get_by_role("button", name="适合画布", exact=True).click()
        expect(zoom).to_have_text("100%")
        page.keyboard.press("Escape")
        expect(editor).to_be_visible()
        paint(center_x - 100 * scale, center_y)
        assert editor.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        editor.screenshot(path=tmp_path / "mask.png", animations="disabled")

        def save_mask():
            with page.expect_response(asset_upload) as saved:
                apply.click()
            asset = saved.value.json()
            expect(editor).to_have_count(0)
            response = page.request.get(asset["media"]["src"])
            assert response.ok
            with Image.open(BytesIO(response.body())) as output:
                assert output.size == (640, 400)
                return asset, output.convert("L")

        _, first_mask = save_mask()
        assert first_mask.getpixel((360, 185)) == 255
        assert first_mask.getpixel((220, 200)) == 255
        assert first_mask.getpixel((5, 5)) == (191 if native else 0)
        expect(edit).to_be_focused()
        form.get_by_role("button", name=re.compile("^本次参数")).click()
        panel = page.get_by_role("dialog", name="本次参数", exact=True)
        panel.get_by_role("button", name="编辑遮罩", exact=True).click()
        expect(editor).to_be_in_viewport(ratio=1)
        expect(surface.locator("canvas").first).to_be_visible()
        assert not model_requests
        if native:
            check_smart_selection(
                page, editor, surface, team, web_engine.name, scale, center_x, center_y
            )
        editor.get_by_role("radio", name="橡皮擦", exact=True).click()
        paint(anchor_x, anchor_y)
        mask, edited = save_mask()
        assert edited.getpixel((360, 185)) == 0
        assert edited.getpixel((220, 200)) == 255
        if native:
            assert edited.getpixel((181, 277)) == 255  # clothes
            assert all(
                edited.getpixel(point) == 0
                for point in [(195, 248), (428, 318), (300, 108), (375, 81)]
            )
        panel.get_by_role("button", name="应用", exact=True).click()

        with page.expect_response(
            lambda r: r.request.method == "POST" and "/api/v1/tasks" in r.url
        ) as queued:
            form.get_by_role("button", name="生成", exact=True).click()
        assert queued.value.status == 201, queued.value.text()
        assert queued.value.json()["status"] == "queued"
        values = queued.value.request.post_data_json["inputValues"]
        assert values[source_id] == {"assetId": reference["id"]}
        assert values[mask_id] == {"assetId": mask["id"]}
        if native:
            original = web.get(f"/api/v1/workflows/{workflow['id']}/graph", params=scope)
            assert original.raise_for_status().json()["graph"] == graph
