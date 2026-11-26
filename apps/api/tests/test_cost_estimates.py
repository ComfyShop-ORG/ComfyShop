"""A quote uses the active space and the provider request without making a task."""

import asyncio
import json
from decimal import Decimal
from functools import partial
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from helpers import serve_test_app
from official_test_support import (
    OWNER,
    TOKEN,
    asset,
    complete_official_artifact,
    image_bytes,
    import_official,
    register,
    submit,
    workflow_body,
)
from playwright.sync_api import expect, sync_playwright
from pydantic import SecretStr
from test_team_spaces import API, add_member, item_ids, open_space_picker
from test_workspace_sharing import ORIGIN, WEB_DIST

from comfyshop_api.services import cost_estimates
from comfyshop_official_worker.atlas_cloud import ADAPTER, ATLAS_ROOT, Atlas
from comfyshop_official_worker.quotes import quote_app, quote_atlas


@pytest.fixture
def atlas_prices(settings, monkeypatch):
    settings.official_quote_url = "http://official-worker:8690/quote"
    settings.official_owner = OWNER
    settings.worker_service_tokens["official"] = SecretStr(TOKEN)
    requests = []

    def provider(request):
        assert request.method == "POST"
        if request.url.path.endswith("/uploadMedia"):
            filename = next(
                name
                for name in ("reference.png", "reference.mp4")
                if name.encode() in request.content
            )
            return httpx.Response(200, json={"url": f"https://cdn.example/{filename}"})
        assert request.url.path.endswith("/calculate")
        payload = json.loads(request.content)
        requests.append(payload)
        if payload["prompt"] == "报价失败":
            return httpx.Response(503)
        price = Decimal("0.08") * payload["duration"]
        if payload["resolution"] == "1080p":
            price *= 2
        return httpx.Response(200, json={"data": {"price": str(price), "estimated": True}})

    upstream = httpx.AsyncClient(base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider))
    try:
        with TestClient(
            quote_app({ADAPTER: partial(quote_atlas, Atlas(upstream))}, TOKEN)
        ) as worker:
            assert worker.post("/quote").status_code == 401

            def forward(url, *, files, headers, **_):
                assert url == settings.official_quote_url
                response = worker.post("/quote", files=files, headers=headers)
                return httpx.Response(
                    response.status_code,
                    content=response.content,
                    request=httpx.Request("POST", url),
                )

            monkeypatch.setattr(cost_estimates.httpx, "post", forward)
            yield requests
    finally:
        asyncio.run(upstream.aclose())


def video_workflow(client, mode="text"):
    fields = [
        {"name": "prompt", "kind": "string", "label": "提示词", "default": ""},
        {
            "name": "duration",
            "kind": "integer",
            "label": "时长",
            "minimum": "1",
            "maximum": "15",
            "default": 5,
        },
        {
            "name": "resolution",
            "kind": "choice",
            "label": "分辨率",
            "default": "720p",
            "choices": ["720p", "1080p"],
        },
    ]
    media = {}
    if mode == "image":
        fields.append({"name": "frame", "kind": "image", "label": "参考图"})
        media["image"] = {"kind": "image", "fields": ["frame"], "min_items": 1}
    if mode == "reference":
        fields.append({"name": "clip", "kind": "video", "label": "参考视频"})
        media["reference_videos"] = {"kind": "video", "fields": ["clip"], "array": True}
    return import_official(
        client,
        workflow_body(
            f"quote-{mode}",
            fields,
            additional_outputs=("image",),
            config={
                "parameters": {name: name for name in ("prompt", "duration", "resolution")},
                "required_text": ["prompt"],
                "media": media,
            },
        ),
    )


def estimate_body(client, workflow, values, scope=None, **sources):
    form = (
        client.get(f"{API}/workflows/{workflow['id']}/service-inputs", params=scope)
        .raise_for_status()
        .json()
    )
    assert form["costEstimate"]
    return {
        "workflowId": workflow["id"],
        "versionId": workflow["versionId"],
        "inputSchemaHash": form["schemaHash"],
        "inputValues": values,
        **sources,
    }


@pytest.mark.parametrize("mode", ["text", "image", "reference"])
def test_quotes_use_provider_parameters_and_bound_media(official, atlas_prices, mode, request):
    workflow = video_workflow(official, mode)
    values = {"prompt": "海岸日出", "duration": 10, "resolution": "1080p"}
    expected = {"model": f"test/quote-{mode}", **values}
    if mode == "image":
        values["frame"] = {"assetId": asset(official, image_bytes("blue"))}
        expected["image"] = "https://cdn.example/reference.png"
    if mode == "reference":
        values["clip"] = {
            "assetId": asset(official, request.getfixturevalue("small_mp4"), "reference.mp4")
        }
        expected["reference_videos"] = ["https://cdn.example/reference.mp4"]
    body = estimate_body(official, workflow, values)
    quote = official.post(f"{API}/tasks/cost-estimate", json=body).raise_for_status().json()
    assert quote == {"unitPrice": "1.60", "currency": "USD", "estimated": True}
    assert atlas_prices == [expected]
    assert not item_ids(official.get(f"{API}/tasks"))
    assert (
        official.post(
            f"{API}/tasks/cost-estimate", json={**body, "inputSchemaHash": "0" * 64}
        ).status_code
        == 409
    )
    assert atlas_prices == [expected]
    task = (
        official.post(
            f"{API}/tasks", json={**body, "executionCount": 4, "idempotencyKey": str(uuid4())}
        )
        .raise_for_status()
        .json()
    )
    assert task["status"] == "queued" and task["executionCount"] == 4
    assert item_ids(official.get(f"{API}/tasks")) == {task["id"]}


def test_quote_shares_the_scope_and_replay_permissions(official, atlas_prices):
    workflow = video_workflow(official, "image")
    original = image_bytes("blue")
    values = {"prompt": "海岸日出", "frame": {"assetId": asset(official, original)}}
    task = submit(official, workflow, values)
    execution, artifact = complete_official_artifact(official, task, "result.png", original)
    official.post(f"{API}/workflows/{workflow['id']}/publish").raise_for_status()
    work = (
        official.post(
            f"{API}/works",
            json={
                "id": str(uuid4()),
                "executionId": execution["id"],
                "title": "海岸",
                "artifactIds": [artifact["id"]],
                "coverArtifactId": artifact["id"],
                "shareParameters": True,
                "shareAssets": True,
            },
        )
        .raise_for_status()
        .json()
    )
    editor = TestClient(official.app, headers={"Origin": ORIGIN})
    reader = TestClient(official.app, headers={"Origin": ORIGIN})
    register(editor, "quote-editor")
    register(reader, "quote-reader")
    team = official.post(f"{API}/teams", json={"name": "报价团队"}).raise_for_status().json()
    team_path = f"{API}/teams/{team['id']}"
    add_member(official, team_path, "quote-editor", "editor").raise_for_status()
    add_member(official, team_path, "quote-reader", "reader").raise_for_status()
    scope = {"workspace_team": team["id"]}
    body = estimate_body(editor, workflow, values, scope)
    route = f"{API}/tasks/cost-estimate"
    assert reader.post(route, json=body, params=scope).status_code == 403
    assert editor.post(route, json=body, params=scope).status_code == 404
    assert not atlas_prices

    shared_values = work["inputValues"]
    replay = estimate_body(editor, workflow, shared_values, scope, sourceWorkId=work["id"])
    assert (
        editor.post(route, json=replay, params=scope).raise_for_status().json()["unitPrice"]
        == "0.40"
    )
    assert atlas_prices[0]["image"] == "https://cdn.example/reference.png"
    assert not item_ids(editor.get(f"{API}/tasks", params=scope))
    assert not item_ids(editor.get(f"{API}/assets", params=scope))


@pytest.mark.parametrize("width", [1280, 320], ids=["desktop", "mobile"])
def test_quote_in_the_generation_form(settings, atlas_prices, tmp_path, width):
    settings.static_dir = WEB_DIST
    with (
        serve_test_app(settings) as (address, web),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        credentials = register(web, OWNER)
        workflow = video_workflow(web)
        task = submit(web, workflow, {"prompt": "海岸"})
        complete_official_artifact(web, task, "cover.png", image_bytes("blue"))
        web.post(f"{API}/workflows/{workflow['id']}/publish").raise_for_status()
        team = web.post(f"{API}/teams", json={"name": "视频团队"}).raise_for_status().json()
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 844},
            locale="zh-CN",
            has_touch=width == 320,
            is_mobile=width == 320,
            reduced_motion="reduce",
        )
        assert page.request.post(
            f"{API}/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/")
        if width == 320:
            open_space_picker(page).get_by_role("button", name=team["name"], exact=True).click()
        page.get_by_role("button", name=workflow["name"], exact=True).click()
        dialog = page.get_by_role("dialog", name=workflow["name"], exact=True)
        form = dialog.locator("form.run-fields")
        prompt = form.get_by_label("提示词", exact=True)
        total = dialog.get_by_text("本批预计费用", exact=False)
        prompt.fill("编辑中的提示词")
        prompt.fill("海岸日出")
        expect(total).to_contain_text("0.40")
        form.get_by_label("时长", exact=True).fill("10")
        expect(total).to_contain_text("0.80")
        form.get_by_role("combobox", name="分辨率", exact=True).click()
        page.get_by_role("option", name="1080p", exact=True).click()
        expect(total).to_contain_text("1.60")
        form.locator("#run-count").fill("4")
        expect(total).to_contain_text("6.40")
        expect(total).to_contain_text("4 次")
        assert len(atlas_prices) == 3
        assert dialog.evaluate("element => element.scrollWidth <= element.clientWidth + 1")
        dialog.screenshot(path=tmp_path / f"quote-{width}.png", animations="disabled")
        with page.expect_response("**/tasks/cost-estimate*") as failed:
            prompt.fill("报价失败")
        assert failed.value.status == 503
        expect(dialog.get_by_text("暂无法估价", exact=True)).to_be_visible()
        expect(total).to_have_count(0)
        generate = dialog.get_by_role("button", name="生成", exact=True)
        expect(generate).to_be_enabled()
        with page.expect_response(
            lambda result: (
                result.request.method == "POST" and result.url.split("?")[0].endswith("/tasks")
            )
        ) as response:
            generate.click()
        assert response.value.status == 201
        queued = response.value.json()
        assert queued["status"] == "queued" and queued["executionCount"] == 4
        scope = {"workspace_team": team["id"]} if width == 320 else None
        expected_tasks = {queued["id"]} if width == 320 else {queued["id"], task["id"]}
        assert item_ids(web.get(f"{API}/tasks", params=scope)) == expected_tasks
        assert (failed.value.url.endswith(f"workspace_team={team['id']}")) == (width == 320)
        assert len(atlas_prices) == 4


def test_private_reference_quote_waits_until_the_user_requests_it(settings, atlas_prices):
    settings.static_dir = WEB_DIST
    with (
        serve_test_app(settings) as (address, web),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        credentials = register(web, OWNER)
        workflow = video_workflow(web, "image")
        page = browser.new_page(base_url=address, viewport={"width": 390, "height": 844})
        assert page.request.post(
            f"{API}/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto(f"/workflows/{workflow['id']}")
        form = page.locator("form.run-fields")
        form.get_by_label("提示词", exact=True).fill("沿海散步")
        file = form.locator("#input-frame")
        file.set_input_files(
            {"name": "reference.png", "mimeType": "image/png", "buffer": image_bytes("blue")}
        )
        estimate = page.get_by_role("button", name="估算费用", exact=True)
        expect(estimate).to_be_enabled()
        assert not atlas_prices
        estimate.click()
        total = page.get_by_text("本批预计费用", exact=False)
        expect(total).to_contain_text("0.40")
        form.get_by_label("时长", exact=True).fill("10")
        expect(total).to_contain_text("0.80")
        file.set_input_files(
            {"name": "reference.png", "mimeType": "image/png", "buffer": image_bytes("red")}
        )
        expect(estimate).to_be_enabled()
        expect(total).to_have_count(0)
        assert len(atlas_prices) == 2
