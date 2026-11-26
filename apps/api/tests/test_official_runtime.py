"""Exercise the official API and worker with self-contained workflow definitions."""

import asyncio
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
from comfyshop_worker_protocol.platform import Platform
from fastapi.testclient import TestClient
from helpers import serve_test_app
from official_test_support import (
    AUTH,
    OWNER,
    SVG_BYTES,
    TOKEN,
    asset,
    complete_official_artifact,
    image_bytes,
    import_official,
    register,
    submit,
    worker_client,
    workflow_body,
)
from playwright.sync_api import expect, sync_playwright
from pydantic import SecretStr
from sqlalchemy.orm import Session
from test_worker import claim_body, setup_job

from comfyshop_api.core.config import Settings
from comfyshop_api.models import OfficialWorkerPoll, Task
from comfyshop_media.errors import MediaError
from comfyshop_media.uploads import inspect_media
from comfyshop_official_worker.atlas_cloud import (
    ADAPTER,
    ATLAS_ROOT,
    SUBMISSION_UNKNOWN,
    Atlas,
    AtlasSpec,
)
from comfyshop_official_worker.runner import Runner


def text_video_body():
    return workflow_body(
        "text-video",
        [
            {"name": "prompt", "kind": "string", "label": "提示词", "default": ""},
            {"name": "duration", "kind": "integer", "default": 8},
            {
                "name": "aspect_ratio",
                "kind": "choice",
                "choices": ["1:1", "16:9"],
                "default": "1:1",
            },
            {"name": "expand_prompt", "kind": "boolean", "default": False},
        ],
        config={
            "parameters": {
                "prompt": "prompt",
                "duration": "duration",
                "ratio": "aspect_ratio",
                "prompt_expansion": "expand_prompt",
            },
            "fixed": {"resolution": "768P"},
        },
        layout=[{"fieldId": "aspect_ratio", "section": "advanced", "help": "画面宽高比"}],
    )


def test_official_layout_uses_platform_fields_and_applies_defaults(official):
    body = text_video_body()
    layout = body["graph"]["parameterLayout"]
    ratio = next(row for row in layout if row["fieldId"] == "aspect_ratio")
    ratio.update(section="hidden", defaultValue="adaptive")
    assert official.post("/api/v1/workflows", json=body).status_code == 422

    ratio["defaultValue"] = "16:9"
    workflow = official.post("/api/v1/workflows", json=body).raise_for_status().json()
    form = (
        official.get(f"/api/v1/workflows/{workflow['id']}/service-inputs").raise_for_status().json()
    )
    assert [(row["fieldId"], row["section"], row["help"]) for row in form["parameterLayout"]] == [
        (row["fieldId"], row["section"], row["help"]) for row in layout
    ]
    assert form["originalDefaults"]["aspect_ratio"] == "1:1"
    assert (
        next(field for field in form["fields"] if field["id"] == "aspect_ratio")["default"]
        == "16:9"
    )

    task = submit(official, workflow, {"prompt": "镜头向前推进"})
    with Session(official.app.state.engine) as db:
        stored = db.get(Task, task["id"])
        assert stored is not None
        spec = AtlasSpec.model_validate(stored.input_graph["config"])
        assert spec.payload(stored.input_values) == {
            "model": "test/text-video",
            "prompt": "镜头向前推进",
            "duration": 8,
            "resolution": "768P",
            "ratio": "16:9",
            "prompt_expansion": False,
        }


def test_official_owner_edits_layout_without_a_machine(official):
    body = text_video_body()
    workflow = import_official(official, body)
    base = f"/api/v1/workflows/{workflow['id']}"
    route = f"{base}/versions/{workflow['versionId']}/parameter-layout"
    original = official.get(f"{base}/service-inputs").raise_for_status().json()
    prior = submit(official, workflow, {"prompt": "调整前的提示词"})
    layout = [
        {
            "fieldId": "expand_prompt",
            "section": "hidden",
            "defaultValue": True,
            "help": "扩写后再生成",
        },
        {"fieldId": "aspect_ratio", "section": "default", "defaultValue": "16:9"},
    ]
    saved = official.put(route, json={"parameterLayout": layout}).raise_for_status().json()
    assert import_official(official, body)["versionId"] == workflow["versionId"]
    current = official.get(f"{base}/service-inputs").raise_for_status().json()
    assert current["parameterLayout"] == saved
    assert current["schemaHash"] != original["schemaHash"]
    exported = official.get(f"{base}/graph").raise_for_status().json()["graph"]
    assert exported["parameterLayout"] == saved

    edited = submit(official, workflow, {"prompt": "调整后的提示词"})
    with Session(official.app.state.engine) as db:
        before, after = db.get(Task, prior["id"]), db.get(Task, edited["id"])
        assert before and after
        assert (before.input_values["aspect_ratio"], before.input_values["expand_prompt"]) == (
            "1:1",
            False,
        )
        assert (after.input_values["aspect_ratio"], after.input_values["expand_prompt"]) == (
            "16:9",
            True,
        )

    register(official, "layout-viewer")
    assert official.put(route, json={"parameterLayout": layout}).status_code == 404


def test_official_video_duration_is_checked_before_atlas(official, small_mp4):
    body = workflow_body(
        "video-duration",
        [{"name": "video", "kind": "video", "label": "Video"}],
        config={
            "media": {
                "video": {
                    "kind": "video",
                    "fields": ["video"],
                    "min_items": 1,
                    "max_duration_ms": 100,
                },
            },
        },
    )
    workflow = import_official(official, body)
    asset_id = asset(official, small_mp4, "clip.mp4")
    info = official.get(f"/api/v1/assets/{asset_id}").raise_for_status().json()
    assert info["media"]["durationMs"] == 200
    task = submit(official, workflow, {"video": {"assetId": asset_id}})

    def unexpected_request(request):
        pytest.fail(f"Duration validation must precede Atlas requests: {request.url}")

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(unexpected_request)
            ) as atlas,
        ):
            assert await Runner(platform, Atlas(atlas), atlas).run_once()

    asyncio.run(run())
    failed = official.get(f"/api/v1/tasks/{task['id']}").raise_for_status().json()
    assert failed["status"] == "failed" and "每段素材最长 100 毫秒" in failed["error"]


def test_default_official_owner_applies_with_worker_token(client, settings, monkeypatch):
    monkeypatch.setenv("COMFYSHOP_OFFICIAL_OWNER", "")
    disabled = Settings(_env_file=None, worker_service_tokens={})
    settings.official_owner, settings.worker_service_tokens = (
        disabled.official_owner,
        disabled.worker_service_tokens,
    )
    register(client, "ComfyShop")
    body = text_video_body()
    assert client.post("/api/v1/workflows", json=body).status_code == 403

    monkeypatch.setenv("COMFYSHOP_WORKER_SERVICE_TOKENS__OFFICIAL", TOKEN)
    enabled = Settings(_env_file=None)
    settings.official_owner, settings.worker_service_tokens = (
        enabled.official_owner,
        enabled.worker_service_tokens,
    )
    draft = import_official(client, body, headers=AUTH)
    assert draft["author"] == "ComfyShop"
    assert import_official(client, body)["id"] == draft["id"]

    monkeypatch.setenv("COMFYSHOP_OFFICIAL_OWNER", OWNER)
    assert (
        Settings(
            _env_file=None, worker_service_tokens={"official": SecretStr(TOKEN)}
        ).official_owner
        == OWNER
    )


def test_official_bearer_and_browser_share_workflow_identity(official, graph):
    body = text_video_body()
    init = {"initialize": True}
    assert official.post("/api/v1/workflows", params=init, json=body).status_code == 403
    for fields, headers, status in (
        ({"workerKind": "runninghub"}, AUTH, 403),
        ({"format": "official"}, {}, 422),
    ):
        invalid = body | {"graph": body["graph"] | fields}
        assert (
            official.post("/api/v1/workflows", json=invalid, headers=headers).status_code == status
        )
    assert (
        official.post(
            "/api/v1/workflows",
            params=init,
            json={"name": "ComfyUI", "graph": graph},
            headers=AUTH,
        ).status_code
        == 403
    )
    en = import_official(official, body, "en", headers=AUTH)
    zh = import_official(official, body)
    assert (en["id"], en["versionId"]) == (zh["id"], zh["versionId"])
    assert not en["published"] and not zh["published"]
    assert import_official(official, body, "en")["versionId"] == en["versionId"]
    graph_url = f"/api/v1/workflows/{en['id']}/graph"
    exported = official.get(graph_url).raise_for_status().json()["graph"]
    assert (exported["format"], exported["workerKind"]) == ("service", "official")
    assert exported["execution"]["outputKind"] == "video"
    assert (
        import_official(official, body | {"graph": exported}, language="en")["versionId"]
        == en["versionId"]
    )
    modified = text_video_body()
    next(field for field in modified["graph"]["fields"] if field["name"] == "duration")[
        "default"
    ] = 6
    updated = (
        official.patch(
            f"/api/v1/workflows/{en['id']}",
            json={"graph": modified["graph"]},
        )
        .raise_for_status()
        .json()
    )
    assert updated["version"] == 2
    assert official.post(f"/api/v1/workflows/{en['id']}/publish").status_code == 409
    released = (
        official.post("/api/v1/workflows", params=init, json=body, headers=AUTH)
        .raise_for_status()
        .json()
    )
    assert released["published"] and released["versionId"] == en["versionId"]
    public = official.get("/api/v1/workflows").raise_for_status().json()["items"]
    assert [item["versionId"] for item in public] == [en["versionId"]]

    register(official, "ordinary-author")
    assert official.post("/api/v1/workflows", json=body).status_code == 403
    normal = (
        official.post("/api/v1/workflows", json={"name": "ComfyUI", "graph": graph})
        .raise_for_status()
        .json()
    )
    assert official.post(f"/api/v1/workflows/{normal['id']}/publish").status_code == 409
    assert official.get(f"/api/v1/workflows/{normal['id']}/inputs").status_code == 422


@pytest.mark.parametrize("with_frames", [False, True], ids=["text-to-video", "image-to-video"])
def test_official_worker_resumes_original_prediction_and_saves_video_and_frame(
    official, small_mp4, worker_logs, with_frames
):
    fields = [
        {
            "name": "prompt",
            "kind": "string",
            "optional": with_frames,
            "default": None if with_frames else "",
        },
        {"name": "include_last_frame", "kind": "boolean", "default": False},
    ]
    config = {
        "parameters": {"prompt": "prompt", "return_last_frame": "include_last_frame"},
        "fixed": {"duration": 5, "output_format": "mp4"},
    }
    if with_frames:
        config["fixed"]["ratio"] = "adaptive"
        fields.extend(
            [
                {"name": "first_frame", "kind": "image"},
                {"name": "last_frame", "kind": "image", "optional": True},
            ]
        )
        config["media"] = {
            "image": {"kind": "image", "fields": ["first_frame"], "min_items": 1},
            "last_image": {"kind": "image", "fields": ["last_frame"]},
        }
    body = workflow_body("video-results", fields, additional_outputs=["image"], config=config)
    workflow = import_official(official, body, "en")
    values = {"include_last_frame": True}
    frame_inputs = {}
    if with_frames:
        for field, color in (("first_frame", "red"), ("last_frame", "green")):
            image = image_bytes(color, size=(320, 320))
            values[field] = {"assetId": asset(official, image)}
            frame_inputs[image] = f"https://cdn.example/{field}.png"
    else:
        values["prompt"] = "海边日出"
    task = submit(official, workflow, values)
    frame = image_bytes("blue")
    calls = []

    async def run():
        polling = asyncio.Event()

        async def first(request):
            calls.append(request.url.path)
            if request.url.path.endswith("/uploadMedia"):
                (url,) = [url for image, url in frame_inputs.items() if image in request.content]
                return httpx.Response(200, json={"url": url})
            if request.method == "POST":
                payload = json.loads(request.content)
                assert (
                    payload["model"] == "test/video-results" and payload["output_format"] == "mp4"
                )
                if with_frames:
                    assert payload["image"] == "https://cdn.example/first_frame.png"
                    assert payload["last_image"] == "https://cdn.example/last_frame.png"
                    assert payload["ratio"] == "adaptive" and "prompt" not in payload
                else:
                    assert payload["prompt"] == "海边日出"
                assert payload["return_last_frame"] is True and payload["duration"] == 5
                return httpx.Response(200, json={"data": {"id": "prediction-video"}})
            polling.set()
            await asyncio.Future()

        def resumed(request):
            calls.append(request.url.path)
            assert request.method == "GET"
            assert request.url.path.endswith("/prediction/prediction-video")
            urls = (
                []
                if calls.count(request.url.path) == 2
                else ["https://cdn.example/video.mp4", "https://cdn.example/last-frame.png"]
            )
            return httpx.Response(200, json={"data": {"status": "completed", "outputs": urls}})

        def download(request):
            still = request.url.path.endswith(".png")
            return httpx.Response(
                200,
                content=frame if still else small_mp4,
                headers={"Content-Type": "image/png" if still else "video/mp4"},
            )

        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(base_url=ATLAS_ROOT, transport=httpx.MockTransport(first)) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            pending = asyncio.create_task(Runner(platform, Atlas(atlas), downloads).run_once())
            await asyncio.wait_for(polling.wait(), 10)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            with Session(official.app.state.engine) as db:
                record = db.get(Task, task["id"])
                assert record.prompt_id == "prediction-video"
                record.lease_expires_at = 0
                db.commit()
            async with httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(resumed)
            ) as atlas:
                assert await Runner(platform, Atlas(atlas, poll_seconds=0), downloads).run_once()

    asyncio.run(run())
    assert calls.count("/api/v1/model/generateVideo") == 1
    finished = (
        official.get(
            f"/api/v1/tasks/{task['id']}/progress",
            params={"include_takeover_history": True},
        )
        .raise_for_status()
        .json()
    )
    assert finished["status"] == "succeeded"
    assert [wait["outcome"] for wait in finished["takeoverHistory"]["waits"]] == ["resumed"]
    logs = "".join(worker_logs)
    assert "INFO | 续查 Atlas Cloud 生成" in logs and "'prediction_id': 'prediction-video'" in logs
    assert logs.count("INFO | Atlas Cloud 生成状态") == 1
    assert logs.count("DEBUG | Atlas Cloud 生成状态") == 1
    artifacts = (
        official.get("/api/v1/artifacts", params={"task_id": task["id"]})
        .raise_for_status()
        .json()["items"]
    )
    by_kind = {artifact["media"]["kind"]: artifact["media"] for artifact in artifacts}
    assert len(artifacts) == len(by_kind) == 2
    assert official.get(by_kind["image"]["src"]).content == frame
    media = by_kind["video"]
    assert (media["width"], media["height"]) == (64, 48)
    assert official.get(media["video"]).content == small_mp4
    official.post(f"/api/v1/workflows/{workflow['id']}/publish").raise_for_status()
    register(official, "official-viewer")
    assert official.get("/api/v1/workflows").json()["items"][0]["id"] == workflow["id"]
    assert (
        official.get("/api/v1/workflows", headers={"Accept-Language": "en"}).json()["items"][0][
            "id"
        ]
        == workflow["id"]
    )
    assert official.get("/api/v1/machines").json()["items"] == []
    viewer_values = {"prompt": "山上的云"}
    if with_frames:
        viewer_values["first_frame"] = {"assetId": asset(official, next(iter(frame_inputs)))}
    submit(official, workflow, viewer_values)


def test_official_asset_formats_replace_defaults_before_queueing(official, settings):
    settings.max_asset_bytes = 1024 * 1024
    allowed = ["image/jpeg", "image/png", "image/webp", "image/bmp"]
    body = workflow_body(
        "image-formats",
        [{"name": "reference_image", "kind": "image"}],
        operation="image",
        config={
            "media": {
                "image": {"kind": "image", "fields": ["reference_image"], "content_types": allowed}
            }
        },
    )
    workflow = import_official(official, body)
    form = (
        official.get(
            f"/api/v1/workflows/{workflow['id']}/service-inputs",
        )
        .raise_for_status()
        .json()
    )
    field = next(field for field in form["fields"] if field["id"] == "reference_image")
    assert form["maxAssetBytes"] == settings.max_asset_bytes
    assert field["acceptedContentTypes"] == allowed
    gif = asset(official, image_bytes("navy", size=(320, 320), format="GIF"), "reference.gif")
    submit(official, workflow, {"reference_image": {"assetId": gif}}, expected_status=422)
    assert official.get("/api/v1/tasks").json()["items"] == []


def test_official_transcription_shares_raw_bytes_but_keeps_each_asset_mime(official, settings):
    recording = b"\x16\x04" * 8000
    settings.asset_quota_bytes = len(recording)
    body = workflow_body(
        "audio-transcription",
        [
            {"name": "source_audio", "kind": "audio"},
            {
                "name": "audio_format",
                "kind": "choice",
                "choices": ["pcm", "mulaw"],
                "default": "pcm",
            },
            {"name": "sample_rate", "kind": "integer", "default": 8000},
            {"name": "sync_mode", "kind": "boolean", "default": False},
        ],
        operation="audio",
        output_kind="text",
        config={
            "parameters": {
                "audio_format": "audio_format",
                "sample_rate": "sample_rate",
                "enable_sync_mode": "sync_mode",
            },
            "media": {
                "audio": {
                    "kind": "audio",
                    "fields": ["source_audio"],
                    "min_items": 1,
                    "content_types": ["audio/x-pcm", "audio/x-mulaw"],
                    "format": {
                        "parameter": "audio_format",
                        "content_types": {"pcm": "audio/x-pcm", "mulaw": "audio/x-mulaw"},
                    },
                }
            },
        },
    )
    workflow = import_official(official, body)
    references = {}
    for suffix, mime in (("pcm", "audio/x-pcm"), ("ulaw", "audio/x-mulaw")):
        ref = asset(official, recording, f"recording.{suffix}")
        saved = official.get(f"/api/v1/assets/{ref}").raise_for_status().json()
        assert saved["contentType"] == mime and saved["filename"] == f"recording.{suffix}"
        assert saved["sha256"] == hashlib.sha256(recording).hexdigest()
        original = official.get(saved["media"]["src"]).raise_for_status()
        assert original.content == recording and original.headers["content-type"] == mime
        references[suffix] = saved

    assert references["pcm"]["id"] != references["ulaw"]["id"]
    assert asset(official, recording, "retry.raw") == references["pcm"]["id"]
    conflicting = official.put(
        f"/api/v1/assets/{references['pcm']['id']}",
        params={"filename": "retry.ulaw"},
        content=recording,
    )
    assert conflicting.status_code == 409
    (original_path,) = settings.original_dir.iterdir()
    assert original_path.read_bytes() == recording

    async def run(ref, audio_format):
        url = f"https://cdn.example/{ref['filename']}"

        def provider(request):
            if request.url.path.endswith("/uploadMedia"):
                assert recording in request.content
                assert f'filename="{ref["filename"]}"'.encode() in request.content
                assert f"Content-Type: {ref['contentType']}\r\n".encode() in request.content
                return httpx.Response(200, json={"url": url})
            assert request.url.path.endswith("/generateAudio")
            payload = json.loads(request.content)
            assert payload["audio"] == url and payload["audio_format"] == audio_format
            assert payload["sample_rate"] == 8000
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": f"prediction-{audio_format}",
                        "status": "completed",
                        "stt_result": {"text": f"Transcript for {audio_format}"},
                    }
                },
            )

        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: pytest.fail("Transcripts are inline"))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    for suffix, ref in references.items():
        audio_format = "mulaw" if suffix == "ulaw" else suffix
        task = submit(
            official,
            workflow,
            {
                "source_audio": {"assetId": ref["id"]},
                "audio_format": audio_format,
                "sample_rate": 8000,
                "sync_mode": True,
            },
        )
        asyncio.run(run(ref, audio_format))
        artifacts = (
            official.get("/api/v1/artifacts", params={"task_id": task["id"]})
            .raise_for_status()
            .json()["items"]
        )
        transcript = next(item for item in artifacts if item["filename"] == "result-1.txt")
        assert official.get(transcript["media"]["src"]).text == f"Transcript for {audio_format}"

    official.post(f"/api/v1/workflows/{workflow['id']}/publish").raise_for_status()
    work = (
        official.post(
            "/api/v1/works",
            json={
                "id": str(uuid4()),
                "executionId": transcript["executionId"],
                "title": "Raw audio transcription",
                "artifactIds": [transcript["id"]],
                "coverArtifactId": transcript["id"],
                "shareAssets": True,
            },
        )
        .raise_for_status()
        .json()
    )
    (shared,) = (
        official.get(f"/api/v1/works/{work['id']}/inputs").raise_for_status().json()["assets"]
    )
    assert shared["contentType"] == "audio/x-mulaw"
    response = official.get(shared["media"]["src"]).raise_for_status()
    assert response.content == recording and response.headers["content-type"] == "audio/x-mulaw"


def test_official_uncertain_submission_cannot_be_retried_as_another_paid_request(official):
    workflow = import_official(official, text_video_body())
    task = submit(official, workflow, {"prompt": "合成测试文本"})

    def provider(_request):
        raise httpx.ReadTimeout("The prediction may already exist")

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient() as downloads,
        ):
            runner = Runner(platform, Atlas(atlas), downloads)
            assert await runner.run_once()
            assert not await runner.run_once()

    asyncio.run(run())
    url = f"/api/v1/tasks/{task['id']}"
    progress = official.get(f"{url}/progress").raise_for_status().json()
    assert progress["error"] == SUBMISSION_UNKNOWN
    assert progress["executions"][0]["recovery"] == "unverified"
    retry = {"executionIndices": [0], "idempotencyKey": str(uuid4())}
    assert official.post(f"{url}/retry-executions", json=retry).status_code == 422
    assert (
        official.post(f"{url}/retry-executions", json={**retry, "service": True}).status_code == 409
    )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"<html/>", "SVG 根元素无效"),
        (b'<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>', "不能包含文档类型"),
        (b'<svg xmlns="http://www.w3.org/2000/svg">', "有效的 XML"),
    ],
)
def test_svg_export_requires_valid_xml_without_dtd(tmp_path, content, message):
    path = tmp_path / "download"
    path.write_bytes(content)
    with pytest.raises(MediaError, match=message):
        inspect_media(path, "ffprobe", "result.svg")


def test_svg_counts_as_one_text_artifact(official):
    body = workflow_body(
        "vector-output",
        [{"name": "prompt", "kind": "string", "default": ""}],
        operation="image",
        additional_outputs=["text"],
    )
    workflow = import_official(official, body)
    task = submit(official, workflow, {"prompt": "A circle"})
    execution, artifact = complete_official_artifact(official, task, "result.svg", SVG_BYTES)
    assert artifact["contentType"] == "image/svg+xml" and artifact["media"]["kind"] == "text"
    assert (execution["artifactCount"], execution["imageCount"], execution["textCount"]) == (
        1,
        0,
        1,
    )


def completed_text_result(client, filename, content):
    body = workflow_body(
        "text-output",
        [{"name": "prompt", "kind": "string", "default": ""}],
        operation="audio",
        output_kind="text",
    )
    workflow = import_official(client, body)
    task = submit(client, workflow, {"prompt": "A transcript"})
    result = complete_official_artifact(client, task, filename, content)
    client.post(f"/api/v1/workflows/{workflow['id']}/publish").raise_for_status()
    return result


@pytest.mark.parametrize(
    ("filename", "content", "mime"),
    [
        ("output.txt", b"A transcript", "text/plain"),
        ("output.json", b'{"text": "A transcript"}', "application/json"),
        ("output.svg", SVG_BYTES, "image/svg+xml"),
    ],
    ids=["txt", "json", "svg"],
)
def test_text_result_publishes_with_default_cover(official, filename, content, mime):
    execution, artifact = completed_text_result(official, filename, content)
    work = (
        official.post(
            "/api/v1/works",
            json={
                "id": str(uuid4()),
                "executionId": execution["id"],
                "title": "Published text output",
                "artifactIds": [artifact["id"]],
            },
        )
        .raise_for_status()
        .json()
    )
    assert work["coverArtifactId"] == artifact["id"]
    assert work["coverImage"] is None and work["media"]["kind"] == "text"
    assert work["media"]["filename"] == filename
    with TestClient(official.app) as visitor:
        public = visitor.get(f"/api/v1/works/{work['id']}").raise_for_status().json()
        original = visitor.get(public["media"]["src"]).raise_for_status()
        assert (
            original.content == content and original.headers["content-type"].split(";")[0] == mime
        )


@pytest.mark.parametrize(("width", "height"), [(1280, 900), (390, 844)], ids=["desktop", "mobile"])
def test_text_result_browser_publishes_without_selecting_a_cover(settings, width, height):
    dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    settings = settings.model_copy(
        update={
            "static_dir": dist,
            "worker_service_tokens": {"official": SecretStr(TOKEN)},
            "official_owner": OWNER,
        }
    )
    with (
        serve_test_app(settings) as (address, web),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        credentials = register(web, OWNER)
        _, artifact = completed_text_result(web, "transcript.txt", b"A transcript")
        page = browser.new_page(base_url=address, viewport={"width": width, "height": height})
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/workspace/results")
        page.get_by_role("button", name="Official test text-output", exact=False).click()
        page.get_by_role("button", name="发布作品", exact=True).click()
        dialog = page.get_by_role("dialog", name="发布作品", exact=True)
        expect(dialog.locator(".cover-picker-preview")).to_have_text("transcript.txt")
        with page.expect_response(
            lambda response: (
                urlsplit(response.url).path == "/api/v1/works" and response.request.method == "POST"
            )
        ) as published:
            dialog.get_by_role("button", name="发布作品", exact=True).click()
        assert published.value.status == 201
        assert published.value.json()["coverArtifactId"] == artifact["id"]
        expect(dialog).to_have_count(0)


def test_official_queue_reports_compatible_tasks_and_worker_activity(official, graph):
    def claim(adapter):
        return (
            official.post(
                "/api/v1/worker/services/official/claim",
                headers=AUTH,
                json={**claim_body(), "adapters": [adapter]},
            )
            .raise_for_status()
            .json()
        )

    def queue(task):
        progress = official.get(f"/api/v1/tasks/{task['id']}/progress").raise_for_status().json()
        return progress["queueAhead"], progress["waitReason"]

    setup_job(official, graph)
    other_model = text_video_body()
    other_model["graph"]["key"] = "alternate-video"
    other_model["graph"]["execution"]["adapter"] = "alternate"
    other = official.post("/api/v1/workflows", json=other_model).raise_for_status().json()
    unrelated = submit(official, other, {"prompt": "雨夜"})

    assert claim(ADAPTER) is None
    first = submit(official, import_official(official, text_video_body()), {"prompt": "海岸"})
    assert queue(first) == (0, "official_waiting")
    cancelled = submit(official, import_official(official, text_video_body()), {"prompt": "山峰"})
    official.post(f"/api/v1/tasks/{cancelled['id']}/cancel").raise_for_status()
    assert queue(cancelled) == (None, None)
    english = (
        official.post(
            "/api/v1/workflows?initialize=true",
            headers=AUTH,
            json=text_video_body(),
        )
        .raise_for_status()
        .json()
    )
    register(official, "queue-viewer")
    second = submit(official, english, {"prompt": "Sunrise"})
    assert queue(second) == (1, "official_waiting")
    assert official.get(f"/api/v1/tasks/{first['id']}/progress").status_code == 404

    engine = official.app.state.engine
    with Session(engine) as db:
        db.get(OfficialWorkerPoll, ADAPTER).last_polled_at = 0
        db.commit()
    assert claim("alternate")["task"]["id"] == unrelated["id"]
    assert queue(second) == (1, "official_no_recent_poll")
    assert claim(ADAPTER)["task"]["id"] == first["id"]
    assert queue(second) == (0, "official_busy")
    with Session(engine) as db:
        db.get(OfficialWorkerPoll, ADAPTER).last_polled_at = 0
        db.commit()
    assert queue(second) == (0, "official_busy")
    with Session(engine) as db:
        db.get(Task, first["id"]).lease_expires_at = 0
        db.commit()
    assert queue(second) == (1, "official_no_recent_poll")
    assert claim(ADAPTER)["task"]["id"] == first["id"]
    assert queue(second) == (0, "official_busy")
    assert claim(ADAPTER)["task"]["id"] == second["id"]
    assert queue(second) == (None, None)


def test_official_takeover_progress_follows_the_current_lease(official, settings, monkeypatch):
    task = submit(official, import_official(official, text_video_body()), {"prompt": "晨光"})
    task_path = f"/api/v1/tasks/{task['id']}"
    stamp = task["started"] + 1
    settings.worker_lease_seconds = 10
    for module in ("services.tasks", "services.machines", "api.worker"):
        monkeypatch.setattr(f"comfyshop_api.{module}.now_ms", lambda: stamp)

    def progress():
        return (
            official.get(f"{task_path}/progress", params={"include_takeover_history": True})
            .raise_for_status()
            .json()
        )

    def claim(body):
        job = (
            official.post("/api/v1/worker/services/official/claim", headers=AUTH, json=body)
            .raise_for_status()
            .json()
        )
        assert job["task"]["id"] == task["id"]
        return job["leaseExpiresAt"]

    def concurrent_claim(body, barrier):
        barrier.wait(timeout=5)
        return claim(body)

    assert progress()["takeoverHistory"] == {"waits": []}
    assert official.get(f"{task_path}/progress").json()["takeoverHistory"] is None
    first = {**claim_body(), "adapters": [ADAPTER]}
    claim(first)
    stamp = claim(first) - 1
    official.post(
        f"/api/v1/worker/tasks/{task['id']}/heartbeat",
        headers={**AUTH, "X-Task-Lease": first["leaseSecret"]},
        json={"sequence": 1, "executionIndex": 0, "stage": "executing", "progress": 20},
    ).raise_for_status()
    expires = stamp + 10_000
    stamp = expires - 1
    assert progress()["officialTakeover"] is None
    assert progress()["takeoverHistory"]["waits"] == []
    expected = []
    for number, duration in enumerate((2_345, 6_789), start=1):
        stamp = expires + duration
        current = {
            "number": number,
            "startedAt": expires,
            "endedAt": None,
            "durationMs": duration,
            "outcome": "waiting",
        }
        if number == 1:
            waiting = progress()
            assert waiting["officialTakeover"] == "waiting"
            assert waiting["takeoverHistory"]["waits"] == [current]
        # 第二段等待期间不查询进度，领取本身必须保存完整记录。
        successor = {**claim_body(), "adapters": [ADAPTER]}
        with ThreadPoolExecutor(max_workers=2) as workers:
            barrier = Barrier(2)
            retries = [workers.submit(concurrent_claim, successor, barrier) for _ in range(2)]
            expires = retries[0].result(timeout=10)
            assert retries[1].result(timeout=10) == expires
        expected.append(current | {"endedAt": stamp, "outcome": "resumed"})
        resumed = progress()
        assert resumed["officialTakeover"] == "resumed"
        assert resumed["takeoverHistory"]["waits"] == expected
    stamp = expires + 4_321
    official.post(f"{task_path}/cancel").raise_for_status()
    expected.append(
        {
            "number": 3,
            "startedAt": expires,
            "endedAt": stamp,
            "durationMs": 4_321,
            "outcome": "ended",
        }
    )
    stamp += 100_000
    official.post(f"{task_path}/cancel").raise_for_status()
    finished = progress()
    assert finished["officialTakeover"] is None and finished["status"] == "cancelled"
    assert finished["takeoverHistory"]["waits"] == expected
    register(official, "another-viewer")
    assert official.get(f"{task_path}/progress?include_takeover_history=true").status_code == 404


@pytest.mark.parametrize(
    ("provider_timeout", "width", "height", "recovery"),
    [(True, 1440, 900, "rerunnable"), (False, 390, 844, "unverified")],
    ids=["provider-timeout", "poll-deadline"],
)
def test_official_timeout_follows_the_viewing_site(
    settings, provider_timeout, width, height, recovery
):
    settings = settings.model_copy(
        update={
            "static_dir": Path(__file__).resolve().parents[2] / "web" / "dist",
            "worker_service_tokens": {"official": SecretStr(TOKEN)},
            "official_owner": OWNER,
        }
    )

    def provider(request):
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"id": "test-prediction"}})
        assert request.url.path.endswith("/prediction/test-prediction")
        if provider_timeout:
            return httpx.Response(200, json={"data": {"status": "timeout"}})
        raise TimeoutError

    async def run_worker(address):
        async with (
            Platform(address, TOKEN) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
        ):
            assert await Runner(platform, Atlas(atlas), atlas).run_once()

    with serve_test_app(settings) as (address, web):
        credentials = register(web, OWNER)
        cases = (
            ("zh", "任务详情", "Atlas Cloud 生成超时", "等待 Atlas Cloud 成品超时，请核实生成结果"),
            (
                "en",
                "Task details",
                "Atlas Cloud generation timed out",
                "Timed out waiting for the Atlas Cloud output. Check the generation result.",
            ),
            (
                "ja",
                "タスクの詳細",
                "Atlas Cloud での生成がタイムアウトしました",
                "Atlas Cloud の生成結果を待機中にタイムアウトしました。生成結果を確認してください。",
            ),
            (
                "ko",
                "작업 상세 정보",
                "Atlas Cloud 생성 시간이 초과되었습니다",
                "Atlas Cloud 결과물을 기다리는 시간이 초과되었습니다. 생성 결과를 확인하세요.",
            ),
            (
                "zh-tw",
                "任務詳情",
                "Atlas Cloud 生成逾時",
                "等待 Atlas Cloud 成品逾時，請確認生成結果。",
            ),
        )
        workflow = import_official(web, text_video_body())
        task = submit(web, workflow, {"prompt": "海上日出"})["id"]
        asyncio.run(run_worker(address))
        task_url = f"/api/v1/tasks/{task}"
        with sync_playwright() as playwright, playwright.chromium.launch() as browser:
            for language, details, generation, waiting in cases:
                expected = generation if provider_timeout else waiting
                headers = {"Accept-Language": language}
                listed = (
                    web.get("/api/v1/tasks", headers=headers).raise_for_status().json()["items"]
                )
                assert [row["id"] for row in listed] == [task]
                assert listed[0]["error"] == expected
                assert (
                    web.get(task_url, headers=headers).raise_for_status().json()["error"]
                    == expected
                )
                progress = (
                    web.get(task_url + "/progress", headers=headers).raise_for_status().json()
                )
                assert progress["error"] == expected
                assert progress["executions"][0]["recovery"] == recovery
                page = browser.new_page(
                    base_url=address, viewport={"width": width, "height": height}, locale=language
                )
                assert page.request.post(
                    "/api/v1/auth/login", data=credentials, headers={"Origin": address}
                ).ok
                page.goto("/workspace/tasks")
                page.get_by_role("button", name=details, exact=True).click()
                dialog = page.get_by_role("dialog", name=details)
                expect(dialog.get_by_text(expected, exact=True)).to_be_visible()
                assert dialog.evaluate("el => el.scrollWidth <= el.clientWidth")
                page.close()


@pytest.mark.parametrize(("width", "height"), [(1440, 900), (390, 844)], ids=["desktop", "mobile"])
def test_official_takeover_in_generation_and_task_details(settings, width, height):
    settings = settings.model_copy(
        update={
            "static_dir": Path(__file__).resolve().parents[2] / "web" / "dist",
            "worker_service_tokens": {"official": SecretStr(TOKEN)},
            "official_owner": OWNER,
            "worker_lease_seconds": 10,
        }
    )
    with (
        serve_test_app(settings) as (address, web),
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        credentials = register(web, OWNER)
        workflow = import_official(web, text_video_body())
        page = browser.new_page(base_url=address, viewport={"width": width, "height": height})
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto(f"/workflows/{workflow['id']}")
        page.locator("form.run-fields").get_by_label("提示词", exact=True).fill("海岸日出")
        with page.expect_response(
            lambda r: r.url.split("?")[0].endswith("/api/v1/tasks") and r.request.method == "POST"
        ) as submitted:
            page.get_by_role("button", name="生成", exact=True).click()
        assert submitted.value.status == 201
        task_id = submitted.value.json()["id"]
        generation = page.get_by_role("region", name="生成进度")
        summary = page.locator(".current-task")
        details = page.get_by_role("dialog", name="任务详情")

        def claim():
            body = {**claim_body(), "adapters": [ADAPTER]}
            job = web.post("/api/v1/worker/services/official/claim", headers=AUTH, json=body)
            assert job.raise_for_status().json()["task"]["id"] == task_id
            return {**AUTH, "X-Task-Lease": body["leaseSecret"]}

        def heartbeat(headers, sequence, stage, percent):
            web.post(
                f"/api/v1/worker/tasks/{task_id}/heartbeat",
                headers=headers,
                json={
                    "sequence": sequence,
                    "executionIndex": 0,
                    "stage": stage,
                    "progress": percent,
                },
            ).raise_for_status()

        heartbeat(claim(), 1, "executing", 32)
        expect(generation.get_by_text("32%", exact=True)).to_be_visible()
        waiting = "等待官方工作机接手"
        expect(generation.get_by_text(waiting, exact=True)).to_be_visible(timeout=18000)
        expect(summary.get_by_text(waiting, exact=True)).to_be_visible()
        expect(generation.get_by_text("32%", exact=True)).to_have_count(0)
        summary.get_by_role("button", name="任务详情", exact=True).click()
        expect(details.get_by_text(waiting, exact=True)).to_be_visible()
        expect(details.get_by_role("progressbar")).to_have_count(0)
        history = details.get_by_role("region", name="接管记录")
        expect(history.get_by_text("第 1 次等待 · 等待接手", exact=True)).to_be_visible()
        expect(history.locator("time")).to_have_count(1)
        elapsed = history.locator("li > span")
        expect(elapsed).not_to_have_text(elapsed.inner_text(), timeout=6000)

        successor = claim()
        heartbeat(successor, 2, "executing", 48)
        resumed = "官方工作机已接手 · 生成中"
        expect(details.get_by_text(resumed, exact=True)).to_be_visible()
        expect(details.get_by_text("48%", exact=True)).to_be_visible()
        expect(history.get_by_text("第 1 次等待 · 已接手", exact=True)).to_be_visible()
        expect(history.locator("time")).to_have_count(2)
        assert details.evaluate("el => el.scrollWidth <= el.clientWidth")
        details.get_by_role("button", name="关闭", exact=True).click()
        expect(generation.get_by_text(resumed, exact=True)).to_be_visible()
        expect(summary.get_by_text(f"{resumed} 48%", exact=True)).to_be_visible()
        heartbeat(successor, 3, "uploading", 75)
        uploading = "官方工作机已接手 · 回传中"
        expect(generation.get_by_text(uploading, exact=True)).to_be_visible()
        assert generation.evaluate("el => el.scrollWidth <= el.clientWidth")
        page.goto("/workspace/tasks")
        page.get_by_role("button", name="任务详情", exact=True).click()
        expect(details.get_by_text(uploading, exact=True)).to_be_visible()
        expect(history.get_by_text("第 2 次等待 · 等待接手", exact=True)).to_be_visible(
            timeout=18000
        )
        web.post(f"/api/v1/tasks/{task_id}/cancel").raise_for_status()
        expect(details.locator(".task-progress-heading strong")).to_have_text("已取消")
        expect(details.get_by_text(uploading, exact=True)).to_have_count(0)
        expect(history.get_by_text("第 2 次等待 · 等待中结束", exact=True)).to_be_visible()
        page.reload()
        page.get_by_role("button", name="任务详情", exact=True).click()
        expect(history.get_by_text("第 2 次等待 · 等待中结束", exact=True)).to_be_visible()
        rows = history.get_by_role("listitem")
        expect(rows).to_have_count(2)
        waits = web.get(f"/api/v1/tasks/{task_id}/progress?include_takeover_history=true").json()[
            "takeoverHistory"
        ]["waits"]
        for row, wait in zip(rows.all(), waits, strict=True):
            times = row.locator("time").evaluate_all(
                "nodes => nodes.map(node => Date.parse(node.dateTime))"
            )
            assert times == [wait["startedAt"], wait["endedAt"]]
            seconds = (times[1] - times[0] + 500) // 1000
            expect(
                row.get_by_text(f"等待 {seconds // 60}:{seconds % 60:02d}", exact=True)
            ).to_be_visible()
        assert history.evaluate("el => el.scrollWidth <= el.clientWidth")
