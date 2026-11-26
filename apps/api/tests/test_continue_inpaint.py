from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from helpers import CATALOG, report_inventory, serve_test_app
from official_test_support import register
from playwright.sync_api import expect
from test_inputs import picture
from test_outputs import run_group
from test_team_spaces import add_member, open_space_picker
from test_worker import claim_body

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


@pytest.mark.parametrize("team", [False, True], ids=["personal-desktop", "team-mobile"])
def test_continue_from_output_opens_editor_and_submits_only_on_generate(
    settings, web_engine, graph, team
):
    width = 320 if team else 1440
    with (
        serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, web),
        web_engine.launch() as browser,
    ):
        credentials = register(web, "continuation-owner")
        team_id = (
            web.post("/api/v1/teams", json={"name": "重绘团队"}).raise_for_status().json()["id"]
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
        mid = machine["machine"]["id"]
        source_workflow = (
            web.post(prefix + "/workflows", json={"name": "原始工作流", "graph": graph})
            .raise_for_status()
            .json()
        )
        catalog = {
            "nodes": CATALOG["nodes"]
            | {
                "LoadImage": {"inputs": {"image": {"kind": "image"}}},
                "LoadImageMask": {
                    "inputs": {
                        "image": {"kind": "image"},
                        "channel": {"kind": "choice", "choices": ["red", "alpha"]},
                    }
                },
                "VAEEncodeForInpaint": {"inputs": {}},
            }
        }
        with httpx.Client(
            base_url=address,
            headers={"Authorization": "Bearer " + machine["apiKey"]},
            trust_env=False,
        ) as worker:
            report_inventory(worker, catalog)
            source_form = (
                web.get(
                    f"/api/v1/workflows/{source_workflow['id']}/inputs",
                    params={**scope, "machine_id": mid},
                )
                .raise_for_status()
                .json()
            )
            source_task = (
                web.post(
                    "/api/v1/tasks",
                    params=scope,
                    json={
                        "workflowId": source_workflow["id"],
                        "versionId": source_workflow["versionId"],
                        "inputSchemaHash": source_form["schemaHash"],
                        "executionCount": 1,
                        "machineId": mid,
                        "inputValues": {},
                        "idempotencyKey": str(uuid4()),
                    },
                )
                .raise_for_status()
                .json()
            )
            claim = claim_body()
            job = worker.post("/api/v1/worker/claim", json=claim).raise_for_status().json()
            assert job["task"]["id"] == source_task["id"]
            run_group(
                web,
                worker,
                source_task["id"],
                claim["leaseSecret"],
                media=[("png", picture("blue", size=(160, 96)), "images")],
            )
            worker.post(
                f"/api/v1/worker/tasks/{source_task['id']}/complete",
                headers={"X-Task-Lease": claim["leaseSecret"]},
            ).raise_for_status()
        (output,) = web.get("/api/v1/artifacts", params=scope).raise_for_status().json()["items"]
        dest_graph = {
            "a": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
            "b": {
                "class_type": "VAEEncodeForInpaint",
                "inputs": {"pixels": ["a", 0], "mask": ["a", 1]},
            },
            "2": {"class_type": "SaveImage", "inputs": {"images": ["b", 0]}},
        }
        target = (
            web.post(prefix + "/workflows", json={"name": "单图重绘", "graph": dest_graph})
            .raise_for_status()
            .json()
        )
        web.post(
            prefix + "/workflows", json={"name": "另一重绘", "graph": dest_graph}
        ).raise_for_status()
        if team:
            with httpx.Client(
                base_url=address, headers={"Origin": address}, trust_env=False
            ) as reader:
                register(reader, "read-only")
                add_member(web, prefix, "read-only", "reader").raise_for_status()
                assert (
                    reader.put(f"/api/v1/artifacts/{output['id']}/input", params=scope).status_code
                    == 403
                )
                assert web.put(f"/api/v1/artifacts/{output['id']}/input").status_code == 404
            with httpx.Client(
                base_url=address, headers={"Origin": address}, trust_env=False
            ) as editor:
                credentials = register(editor, "inpaint-editor")
                add_member(web, prefix, "inpaint-editor", "editor").raise_for_status()
        page = browser.new_page(
            base_url=address,
            viewport={"width": width, "height": 760},
            has_touch=team,
            locale="zh-CN",
            reduced_motion="reduce",
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        result_url = "/workspace/results?result=" + output["executionId"]
        page.goto("/workspace/results")
        if team:
            open_space_picker(page).get_by_role("button", name="重绘团队", exact=True).click()
        page.goto(result_url)
        edit = page.get_by_role("button", name="局部重绘", exact=True)
        dialog = page.get_by_role("dialog", name="编辑遮罩", exact=True)
        submitted = []
        page.on(
            "request",
            lambda req: (
                submitted.append(req)
                if req.method == "POST" and "/api/v1/tasks" in req.url
                else None
            ),
        )

        def open_editor():
            edit.click()
            chooser = page.get_by_role("dialog", name="选择重绘工作流")
            source = chooser.get_by_role("combobox", name="工作流来源")
            search = chooser.get_by_role("searchbox", name="搜索工作流")
            expect(source).to_have_text("当前空间的工作流")
            expect(chooser.get_by_role("button", name="另一重绘", exact=True)).to_be_visible()
            expect(chooser.get_by_role("button", name="原始工作流", exact=True)).to_have_count(0)
            source.click()
            page.get_by_role("option", name="公共工作流", exact=True).click()
            expect(chooser.get_by_role("button", name="单图重绘", exact=True)).to_have_count(0)
            source.click()
            page.get_by_role("option", name="当前空间的工作流", exact=True).click()
            search.fill("单图")
            expect(chooser.get_by_role("button", name="另一重绘", exact=True)).to_have_count(0)
            chooser.get_by_role("button", name="单图重绘", exact=True).click()
            expect(
                dialog.get_by_role("group", name="遮罩画布").locator("canvas").first
            ).to_be_visible()

        open_editor()
        dialog.get_by_role("button", name="取消", exact=True).click()
        expect(edit).to_be_focused()
        assert not submitted
        assert (
            web.get("/api/v1/assets/usage", params=scope).raise_for_status().json()["usedBytes"]
            == 0
        )
        open_editor()
        surface = dialog.get_by_role("group", name="遮罩画布")
        surface.click()
        with page.expect_response(
            lambda res: (
                res.request.method == "PUT" and "/artifacts/" in res.url and "/input" in res.url
            )
        ) as asset_response:
            dialog.get_by_role("button", name="应用", exact=True).click()
        saved = asset_response.value.json()
        assert saved["sha256"] == output["sha256"] and saved["savedAt"] is None
        form = page.get_by_role("dialog", name=target["name"], exact=True)
        expect(form).to_be_visible()
        expect(form.get_by_role("button", name="编辑遮罩", exact=True)).to_be_visible()
        assert not submitted
        (mapping,) = [
            row
            for row in web.get(f"/api/v1/artifacts/{output['id']}/inpaint-targets", params=scope)
            .raise_for_status()
            .json()
            if row["workflowId"] == target["id"]
        ]
        assert "channelFieldId" not in mapping["mask"]
        with page.expect_response(
            lambda res: res.request.method == "POST" and "/api/v1/tasks" in res.url
        ) as task:
            form.get_by_role("button", name="生成", exact=True).click()
        assert task.value.status == 201 and len(submitted) == 1
        body = submitted[0].post_data_json
        assert body["inputValues"][mapping["fieldId"]] == {"assetId": saved["id"]}
        assert body["inputValues"][mapping["mask"]["fieldId"]]["assetId"] != saved["id"]
        assert body["workflowId"] == target["id"] and body["machineId"] == mid
        assert web.get("/api/v1/assets", params=scope).raise_for_status().json()["items"] == []
        page.go_back()
        expect(edit).to_be_visible()

        if not team:
            # A new graph must not replace the version that produced the finished image.
            tid = task.value.json()["id"]
            with httpx.Client(
                base_url=address,
                headers={"Authorization": "Bearer " + machine["apiKey"]},
                trust_env=False,
            ) as worker:
                lease = claim_body()
                assert (
                    worker.post("/api/v1/worker/claim", json=lease)
                    .raise_for_status()
                    .json()["task"]["id"]
                    == tid
                )
                run_group(
                    web,
                    worker,
                    tid,
                    lease["leaseSecret"],
                    media=[("png", picture("green"), "images")],
                )
                worker.post(
                    f"/api/v1/worker/tasks/{tid}/complete",
                    headers={"X-Task-Lease": lease["leaseSecret"]},
                ).raise_for_status()
            (repaint,) = (
                web.get("/api/v1/artifacts", params={"task_id": tid})
                .raise_for_status()
                .json()["items"]
            )
            web.patch(f"/api/v1/workflows/{target['id']}", json={"graph": graph}).raise_for_status()
            endpoint = f"/api/v1/artifacts/{repaint['id']}/inpaint-targets"
            (prior,) = [
                row
                for row in web.get(endpoint).raise_for_status().json()
                if row["workflowId"] == target["id"]
            ]
            assert prior["versionId"] == target["versionId"]
            page.goto("/workspace/results?result=" + repaint["executionId"])
            page.get_by_role("button", name="局部重绘", exact=True).click()
            expect(
                dialog.get_by_role("group", name="遮罩画布").locator("canvas").first
            ).to_be_visible()
            expect(page.get_by_role("dialog", name="选择重绘工作流")).to_have_count(0)
            dialog.get_by_role("button", name="取消", exact=True).click()

            web.delete(f"/api/v1/artifacts/{repaint['id']}").raise_for_status()
            assert web.get(endpoint).status_code == 404
