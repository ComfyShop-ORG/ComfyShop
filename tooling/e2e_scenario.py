"""Browser and API assertions shared by the native work machine regression runs."""

import time
from hashlib import sha256
from io import BytesIO
from secrets import token_hex, token_urlsafe
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

import httpx
from PIL import Image
from playwright.sync_api import expect

INPUT_NAME = "shared-input.png"
WORK_TITLE = "共享参考图"
WORKFLOW_NAME = "工作机端到端回归"


def wait_for(callback, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if value := callback():
            return value
        time.sleep(0.25)
    raise TimeoutError(f"Timed out waiting for {callback.__name__}")


def client_for(site):
    return httpx.Client(base_url=site, headers={"Origin": site}, trust_env=False, timeout=15)


def request(client, method, path, status=200, **kwargs):
    response = client.request(method, "/api/v1" + path, **kwargs)
    if response.status_code != status:
        raise RuntimeError(f"{method} {path} returned {response.status_code}; expected {status}")
    return response


def register(client):
    credentials = {"username": "E2E" + token_hex(5), "password": "Qa8!" + token_urlsafe(22)}
    session = request(client, "POST", "/auth/register", status=201, json=credentials).json()
    client.headers["X-CSRF-Token"] = session["csrfToken"]
    return credentials


def login(page, address, credentials):
    response = page.request.post(
        "/api/v1/auth/login", data=credentials, headers={"Origin": address}
    )
    if not response.ok:
        raise RuntimeError(f"Browser session login returned {response.status}")


def approve(browser, client, credentials, code, role, folder):
    name = {"publisher": "回归发布工作机", "reader": "回归访客工作机"}[role]
    address = str(client.base_url).rstrip("/")
    context = browser.new_context(base_url=address, viewport={"width": 1280, "height": 900})
    try:
        page = context.new_page()
        login(page, address, credentials)
        page.goto("/machines/link?" + urlencode({"code": code}))
        page.get_by_label("工作机名称", exact=True).fill(name)
        page.get_by_role("button", name="确认接入", exact=True).click()

        def online_machine():
            machines = request(client, "GET", "/machines").json()
            return next(
                (
                    row
                    for row in machines["items"]
                    if row["name"] == name and row["online"] and row["nodeCount"]
                ),
                None,
            )

        machine = wait_for(online_machine)
        request(client, "PUT", f"/machines/{machine['id']}/default", status=204)
        page.goto("/machines")
        entry = page.locator(".machine-item").filter(has=page.get_by_text(name, exact=True))
        expect(entry.get_by_text("在线", exact=True)).to_be_visible()
        page.screenshot(path=folder / f"{role}-online.png", animations="disabled")
        return machine
    finally:
        context.close()


def create_workflow(client, output_prefix):
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "reference-placeholder.png"}},
        "2": {
            "class_type": "ImageScaleBy",
            "inputs": {"image": ["1", 0], "upscale_method": "nearest-exact", "scale_by": 2},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": output_prefix},
        },
    }
    return request(
        client,
        "POST",
        "/workflows",
        status=201,
        json={"name": WORKFLOW_NAME, "category": "image", "graph": graph},
    ).json()


def submit_publisher(client, workflow, machine):
    buffer = BytesIO()
    Image.new("RGB", (24, 16), (41, 74, 135)).save(buffer, format="PNG")
    data = buffer.getvalue()
    asset = request(
        client,
        "PUT",
        f"/assets/{uuid4()}",
        content=data,
        params={"filename": INPUT_NAME},
        headers={"Content-Type": "application/octet-stream"},
    ).json()
    assert sha256(data).hexdigest() == asset["sha256"]
    form = request(
        client,
        "GET",
        f"/workflows/{workflow['id']}/inputs",
        params={"version_id": workflow["versionId"], "machine_id": machine["id"]},
    ).json()
    assert not form["issues"], form["issues"]
    (image,) = [field for field in form["fields"] if field["kind"] == "image"]
    task = request(
        client,
        "POST",
        "/tasks",
        status=201,
        json={
            "workflowId": workflow["id"],
            "versionId": workflow["versionId"],
            "machineId": machine["id"],
            "executionCount": 1,
            "inputValues": {image["id"]: {"assetId": asset["id"]}},
            "inputSchemaHash": form["schemaHash"],
            "idempotencyKey": str(uuid4()),
        },
    ).json()
    return task, asset


def real_result(client, comfy, task_id, folder, name):
    states = ["queued"]

    def finished_task():
        task = request(client, "GET", f"/tasks/{task_id}").json()
        if task["status"] != states[-1]:
            states.append(task["status"])
        return task if task["status"] in {"succeeded", "failed", "cancelled"} else None

    task = wait_for(finished_task, timeout=120)
    assert task["status"] == "succeeded", task.get("error")
    (execution,) = request(client, "GET", "/executions", params={"task_id": task_id}).json()[
        "items"
    ]
    prompt_id = execution["promptId"]
    assert prompt_id
    history = comfy.get(f"/history/{prompt_id}").raise_for_status().json()[prompt_id]
    assert history["status"]["completed"] and history["status"]["status_str"] == "success"
    (artifact,) = request(
        client,
        "GET",
        "/artifacts",
        params={"execution_id": execution["id"]},
    ).json()["items"]
    descriptor = history["outputs"][artifact["outputNodeId"]][artifact["outputSlot"]][
        artifact["outputIndex"]
    ]
    output = request(client, "GET", f"/artifacts/{artifact['id']}/file").content
    original = comfy.get(
        "/view", params={key: descriptor[key] for key in ("filename", "subfolder", "type")}
    )
    assert (
        sha256(output).hexdigest()
        == sha256(original.raise_for_status().content).hexdigest()
        == artifact["sha256"]
    )
    assert (artifact["media"]["width"], artifact["media"]["height"]) == (48, 32)
    (folder / f"{name}.png").write_bytes(output)
    return {
        "task": task_id,
        "states": states,
        "execution": execution["id"],
        "promptId": prompt_id,
        "artifact": artifact["id"],
        "sha256": artifact["sha256"],
        "bytes": len(output),
        "comfyInput": history["prompt"][2]["1"]["inputs"]["image"],
        "comfyOutput": {key: descriptor[key] for key in ("filename", "subfolder", "type")},
    }


def share(publisher, reader, workflow, asset, result):
    assert request(publisher, "POST", f"/workflows/{workflow['id']}/publish").json()["published"]
    work = request(
        publisher,
        "POST",
        "/works",
        status=201,
        json={
            "id": str(uuid4()),
            "executionId": result["execution"],
            "title": WORK_TITLE,
            "artifactIds": [result["artifact"]],
            "coverArtifactId": result["artifact"],
            "shareAssets": True,
        },
    ).json()
    request(reader, "GET", f"/assets/{asset['id']}/file", status=404)
    request(reader, "GET", f"/executions/{result['execution']}", status=404)
    (shared,) = request(reader, "GET", f"/works/{work['id']}/inputs").json()["assets"]
    assert shared["id"] != asset["id"] and shared["sha256"] == asset["sha256"]
    shared_file = request(reader, "GET", f"/works/{work['id']}/assets/{shared['id']}/file").content
    assert sha256(shared_file).hexdigest() == asset["sha256"]
    return work, shared


def replay(browser, reader, credentials, workflow, work, machine, shared, viewport, folder):
    address = str(reader.base_url).rstrip("/")
    size = {"desktop": {"width": 1280, "height": 900}, "mobile": {"width": 390, "height": 844}}[
        viewport
    ]
    context = browser.new_context(base_url=address, viewport=size, has_touch=viewport == "mobile")
    page = context.new_page()
    try:
        login(page, address, credentials)
        page.goto(f"/workflows/{workflow['id']}?" + urlencode({"work": work["id"]}))
        dialog = page.get_by_role("dialog").filter(
            has=page.get_by_role("heading", name=WORK_TITLE, exact=True)
        )
        expect(dialog).to_be_visible()
        with page.expect_response(
            lambda reply: urlsplit(reply.url).path == f"/api/v1/works/{work['id']}/replay"
        ) as replayed:
            dialog.get_by_role("button", name="载入参数", exact=True).click()
        assert replayed.value.ok and replayed.value.json()["sourceWorkId"] == work["id"]
        page.wait_for_url(
            lambda url: (
                parse_qs(urlsplit(url).query).get("version") == [workflow["versionId"]]
                and "work" not in parse_qs(urlsplit(url).query)
            )
        )
        fields = page.locator(".run-fields")
        expect(fields.get_by_role("combobox", name="本次执行工作机")).to_contain_text(
            "回归访客工作机"
        )
        expect(fields.get_by_text(INPUT_NAME, exact=True).first).to_be_visible()
        page.screenshot(path=folder / f"{viewport}-shared.png", animations="disabled")
        with page.expect_response(
            lambda reply: (
                urlsplit(reply.url).path == "/api/v1/tasks" and reply.request.method == "POST"
            )
        ) as created:
            page.get_by_role("button", name="生成", exact=True).click()
        assert created.value.status == 201
        body = created.value.request.post_data_json
        assert body["sourceWorkId"] == work["id"] and body["machineId"] == machine["id"]
        assert any(
            isinstance(value, dict) and value.get("assetId") == shared["id"]
            for value in body["inputValues"].values()
        )
        task = created.value.json()
        summary = page.locator('.generation-summary[data-status="succeeded"]')
        expect(summary).to_be_visible(timeout=120_000)
        expect(page.locator(".generation-results .generation-hero").first).to_be_visible(
            timeout=20_000
        )
        page.screenshot(path=folder / f"{viewport}-result.png", animations="disabled")
        (copied,) = request(reader, "GET", f"/tasks/{task['id']}/inputs").json()["assets"]
        assert copied["id"] != shared["id"] and copied["sha256"] == shared["sha256"]
        return task["id"]
    except Exception:
        if not page.is_closed():
            page.screenshot(
                path=folder / f"{viewport}-failure.png", animations="disabled", timeout=3000
            )
        raise
    finally:
        context.close()
