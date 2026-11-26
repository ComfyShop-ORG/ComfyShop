import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from helpers import serve_test_app
from playwright.sync_api import expect, sync_playwright
from test_outputs import flac as flac
from test_outputs import run_group
from test_worker import claim_body, image_bytes, setup_job

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


@pytest.mark.parametrize(("width", "height"), [(1440, 900), (390, 844)], ids=["desktop", "mobile"])
def test_audio_cards_prefer_their_own_covers(authenticated, settings, graph, flac, width, height):
    name = "音频工作流"
    machine, task, _ = setup_job(authenticated, graph)
    workflow = f"/api/v1/workflows/{task['workflowId']}"
    authenticated.patch(workflow, json={"category": "audio", "name": name}).raise_for_status()
    worker = TestClient(authenticated.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    worker.post("/api/v1/worker/claim", json=claim).raise_for_status()
    execution, (artifact,) = run_group(
        authenticated, worker, task["id"], claim["leaseSecret"], media=[("flac", flac, "audio")]
    )
    assert artifact["media"]["kind"] == "audio" and artifact["media"]["thumbnail"] is None
    authenticated.post(workflow + "/publish").raise_for_status()

    assert (WEB_DIST / "index.html").is_file(), "请先构建网页再运行浏览器测试"
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, guest),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        page = browser.new_page(base_url=address, viewport={"width": width, "height": height})
        page.goto("/")
        card = page.get_by_role("button", name=name, exact=True)
        cover = card.locator(".media-card-surface > img")

        def expect_default(cover):
            expect(cover).to_be_visible()
            expect(cover).to_have_attribute("src", re.compile(r"/assets/audio-workflow-cover-"))
            assert (
                cover.evaluate("async img => { await img.decode(); return img.naturalWidth; }")
                == 768
            )

        assert guest.get(workflow).raise_for_status().json()["media"] is None
        expect_default(cover)

        work = (
            authenticated.post(
                "/api/v1/works",
                json={
                    "id": str(uuid4()),
                    "title": name,
                    "executionId": execution["id"],
                    "artifactIds": [artifact["id"]],
                },
            )
            .raise_for_status()
            .json()
        )
        assert guest.get(workflow).raise_for_status().json()["media"]["kind"] == "audio"
        page.reload()
        expect_default(cover)

        image = (
            authenticated.put(
                f"/api/v1/assets/{uuid4()}", params={"filename": "cover.png"}, content=image_bytes()
            )
            .raise_for_status()
            .json()
        )
        updated = (
            authenticated.put(f"/api/v1/works/{work['id']}/cover", json={"assetId": image["id"]})
            .raise_for_status()
            .json()
        )
        page.reload()
        expect(cover).to_have_attribute("src", re.compile(re.escape(updated["coverImage"]["src"])))
        assert cover.evaluate("async img => { await img.decode(); return img.naturalWidth; }") > 0

        login = page.request.post(
            "/api/v1/auth/login",
            data={"username": "owner", "password": "correct-horse-battery"},
            headers={"Origin": address},
        )
        assert login.ok, login.status
        page.goto(f"/workflows/{task['workflowId']}")
        dialog = page.locator(".workflow-dialog")
        results_tab = dialog.get_by_role("tab", name="我的结果")
        results_tab.click()
        result_card = dialog.locator(f"button[data-media-id='{execution['id']}']")
        result_cover = result_card.locator(".media-card-surface > img")
        expect_default(result_cover)

        updated_result = (
            authenticated.put(
                f"/api/v1/executions/{execution['id']}/cover", json={"assetId": image["id"]}
            )
            .raise_for_status()
            .json()
        )
        page.reload()
        results_tab.click()
        expect(result_cover).to_have_attribute(
            "src", re.compile(re.escape(updated_result["coverImage"]["src"]))
        )
        assert (
            result_cover.evaluate("async img => { await img.decode(); return img.naturalWidth; }")
            > 0
        )
