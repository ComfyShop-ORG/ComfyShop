import re
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from helpers import CATALOG, report_inventory, serve_test_app
from official_test_support import register
from playwright.sync_api import expect
from test_inputs import picture
from test_team_spaces import open_space_picker

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
SCREENS = pytest.mark.parametrize("mobile", [False, True], ids=["desktop-personal", "mobile-team"])
IMAGE = {"inputs": {"image": {"kind": "image"}}}


def pixel(minimum):
    return {"kind": "integer", "minimum": str(minimum), "maximum": "16384", "step": "1"}


@contextmanager
def open_frame_workflow(settings, web_engine, mobile, graph, nodes):
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, web),
        web_engine.launch() as browser,
    ):
        credentials = register(web, "frame-author")
        team_id = (
            web.post("/api/v1/teams", json={"name": "画布团队"}).raise_for_status().json()["id"]
            if mobile
            else None
        )
        scope = {"workspace_team": team_id} if team_id else {}
        prefix = f"/api/v1/teams/{team_id}" if team_id else "/api/v1"
        machine = (
            web.post("/api/v1/machines", params=scope, json={"name": "画布工作机"})
            .raise_for_status()
            .json()
        )
        with httpx.Client(
            base_url=address,
            headers={"Authorization": "Bearer " + machine["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker, {"nodes": CATALOG["nodes"] | {"LoadImage": IMAGE} | nodes})
        workflow = (
            web.post(prefix + "/workflows", json={"name": "画布测试", "graph": graph})
            .raise_for_status()
            .json()
        )
        schema = (
            web.get(
                f"/api/v1/workflows/{workflow['id']}/inputs",
                params={
                    **scope,
                    "version_id": workflow["versionId"],
                    "machine_id": machine["machine"]["id"],
                },
            )
            .raise_for_status()
            .json()
        )
        ids = {(f["nodeId"], f["inputName"]): f["id"] for f in schema["fields"]}
        page = browser.new_page(
            base_url=address,
            viewport={"width": 320 if mobile else 1440, "height": 700 if mobile else 900},
            is_mobile=mobile,
            has_touch=mobile,
            locale="zh-CN",
            reduced_motion="reduce",
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/workspace/workflows")
        if mobile:
            open_space_picker(page).get_by_role("button", name="画布团队", exact=True).click()
        page.get_by_role("button", name="画布测试", exact=True).click()
        form = page.get_by_role("dialog", name="画布测试", exact=True)
        yield page, form, ids


def upload_sample(form, field, name, color, size):
    form.locator(f'input[id="input-{field}"]').set_input_files(
        {
            "name": name,
            "mimeType": "image/png",
            "buffer": picture(color, size=size),
        }
    )
    expect(form.get_by_text(name, exact=True)).to_be_visible()


def generate(page, form):
    with page.expect_response(
        lambda response: response.request.method == "POST" and "/api/v1/tasks" in response.url
    ) as task:
        form.get_by_role("button", name="生成", exact=True).click()
    assert task.value.status == 201, task.value.text()
    return task.value.request.post_data_json["inputValues"]


@SCREENS
def test_crop_edits_form_pixels_and_preserves_cancel(settings, web_engine, mobile, tmp_path):
    initial = {"x": 12, "y": 20, "width": 320, "height": 240}
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
        "2": {"class_type": "ImageCrop", "inputs": {"image": ["1", 0], **initial}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
    }
    with open_frame_workflow(
        settings,
        web_engine,
        mobile,
        graph,
        {"ImageCrop": {"inputs": {k: pixel(int(k in {"width", "height"})) for k in initial}}},
    ) as (page, form, ids):
        upload_sample(form, ids["1", "image"], "风景.png", "green", (640, 400))
        edit = form.get_by_role("button", name="裁剪范围", exact=True)
        edit.click()
        editor = page.get_by_role("dialog", name="裁剪范围", exact=True)
        editor.get_by_role("radio", name="1:1", exact=True).click()
        expect(editor.get_by_text("400 × 400 像素")).to_be_visible()
        editor.get_by_role("button", name="取消", exact=True).click()
        expect(edit).to_be_focused()
        form.get_by_role("button", name=re.compile("^本次参数")).click()
        panel = page.get_by_role("dialog", name="本次参数", exact=True)
        panel.get_by_role("button", name="裁剪范围", exact=True).click()
        expect(editor.get_by_text("320 × 240 像素")).to_be_visible()
        editor.get_by_role("radio", name="1:1", exact=True).click()
        editor.get_by_role("button", name="居中", exact=True).click()
        surface = editor.locator(".canvas-editor-viewport")
        expect(editor.get_by_text("X 120 · Y 0")).to_be_visible()
        surface.focus()
        page.keyboard.press("Shift+ArrowRight")
        expect(editor.get_by_text("X 130 · Y 0")).to_be_visible()
        handle = editor.locator('[data-handle="bottomRight"]')
        handle.focus()
        page.keyboard.press("Shift+ArrowLeft")
        expect(editor.get_by_text("390 × 390 像素")).to_be_visible()
        editor.get_by_role("button", name="撤销").click()
        expect(editor.get_by_text("400 × 400 像素")).to_be_visible()
        assert editor.evaluate("e => e.scrollWidth <= e.clientWidth + 1")
        editor.screenshot(path=tmp_path / "crop.png", animations="disabled")
        editor.get_by_role("button", name="应用", exact=True).click()
        panel.get_by_role("button", name="应用", exact=True).click()
        values = generate(page, form)
        assert {k: values[ids["2", k]] for k in initial} == {
            "x": 130,
            "y": 0,
            "width": 400,
            "height": 400,
        }


@SCREENS
def test_layer_stack_writes_transforms_in_pixels(settings, web_engine, mobile, tmp_path):
    def node(kind, **inputs):
        return {"class_type": kind, "inputs": inputs}

    graph = {
        "1": node("LoadImage", image="background.png"),
        "2": node("LoadImage", image="first.png"),
        "3": node("LoadImage", image="second.png"),
        "4": node("ImageScaleBy", image=["2", 0], scale_by=1.0),
        "5": node("ImageRotate", image=["4", 0], rotation="none"),
        "6": node(
            "ImageCompositeMasked",
            destination=["1", 0],
            source=["5", 0],
            x=60,
            y=40,
            resize_source=False,
        ),
        "7": node(
            "ImageCompositeMasked",
            destination=["6", 0],
            source=["3", 0],
            x=40,
            y=40,
            resize_source=False,
        ),
        "8": node("SaveImage", images=["7", 0]),
    }
    nodes = {
        "ImageCompositeMasked": {
            "inputs": {"x": pixel(0), "y": pixel(0), "resize_source": {"kind": "boolean"}}
        },
        "ImageScaleBy": {
            "inputs": {
                "scale_by": {"kind": "number", "minimum": "0.01", "maximum": "8", "step": "0.01"}
            }
        },
        "ImageRotate": {
            "inputs": {
                "rotation": {
                    "kind": "choice",
                    "choices": ["none", "90 degrees", "180 degrees", "270 degrees"],
                }
            }
        },
    }
    with open_frame_workflow(settings, web_engine, mobile, graph, nodes) as (page, form, ids):
        upload_sample(form, ids["1", "image"], "底图.png", "gray", (1024, 640))
        edit = form.get_by_role("button", name="图层布局", exact=True)
        expect(edit).to_be_disabled()
        upload_sample(form, ids["2", "image"], "红图.png", "red", (100, 60))
        upload_sample(form, ids["3", "image"], "蓝图.png", "blue", (50, 50))
        edit.click()
        editor = page.get_by_role("dialog", name="图层布局", exact=True)
        if mobile:
            selection = editor.locator(".outpaint-frame")
            expect(selection.locator("[data-handle]")).to_have_count(2)
            rect = selection.bounding_box()
            assert rect
            cx, cy = rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2
            assert page.evaluate(
                "([x,y]) => !document.elementFromPoint(x,y).closest('[data-handle]')", [cx, cy]
            )
            tx = cx + rect["width"] / 4
            if web_engine.name == "chromium":
                touch = page.context.new_cdp_session(page)
                for action, points in (
                    ("touchStart", [{"x": cx, "y": cy}]),
                    ("touchMove", [{"x": tx, "y": cy}]),
                    ("touchEnd", []),
                ):
                    touch.send("Input.dispatchTouchEvent", {"type": action, "touchPoints": points})
                touch.detach()
            else:
                page.mouse.move(cx, cy)
                page.mouse.down()
                page.mouse.move(tx, cy, steps=3)
                page.mouse.up()
            expect(editor.get_by_text(re.compile(r"^X 8[4-6] · Y 40$"))).to_be_visible()
            expect(editor.get_by_text("100 × 60 像素")).to_be_visible()
            editor.get_by_role("button", name="撤销").click()
            expect(editor.get_by_text("X 60 · Y 40")).to_be_visible()
        editor.get_by_role("button", name="顺时针旋转 90°").click()
        expect(editor.get_by_text("60 × 100 像素")).to_be_visible()
        handle = editor.locator('[data-handle="bottomRight"]')
        handle.focus()
        page.keyboard.press("Shift+ArrowDown")
        expect(editor.get_by_text("66 × 110 像素")).to_be_visible()
        editor.get_by_role("button", name="居中", exact=True).click()
        expect(editor.get_by_text("X 479 · Y 265")).to_be_visible()
        editor.get_by_role("combobox", name="当前图层").click()
        page.get_by_role("option", name=re.compile("蓝图")).click()
        expect(editor.get_by_text("50 × 50 像素")).to_be_visible()
        expect(editor.get_by_role("button", name="顺时针旋转 90°")).to_have_count(0)
        surface = editor.locator(".canvas-editor-viewport")
        surface.focus()
        page.keyboard.press("Shift+ArrowRight")
        expect(editor.get_by_text("X 50 · Y 40")).to_be_visible()
        assert editor.evaluate("e => e.scrollWidth <= e.clientWidth + 1")
        editor.screenshot(path=tmp_path / "layers.png", animations="disabled")
        editor.get_by_role("button", name="应用", exact=True).click()
        values = generate(page, form)
        assert [
            values[ids[n, k]]
            for n, k in (
                ("4", "scale_by"),
                ("5", "rotation"),
                ("6", "x"),
                ("6", "y"),
                ("7", "x"),
                ("7", "y"),
            )
        ] == [1.1, "90 degrees", 479, 265, 50, 40]
