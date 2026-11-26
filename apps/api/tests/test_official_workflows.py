import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import wave
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from zipfile import ZipFile

import httpx
import pytest
from comfyshop_worker_protocol import PROTOCOL_VERSION
from comfyshop_worker_protocol.platform import Platform
from helpers import serve_test_app
from official_test_support import (
    AUTH,
    OWNER,
    TOKEN,
    asset,
    image_bytes,
    import_official,
    register,
    submit,
    worker_client,
)
from PIL import Image
from playwright.sync_api import expect, sync_playwright
from pydantic import SecretStr
from sqlalchemy.orm import Session
from test_outputs import glb_bytes
from test_worker import claim_body

from comfyshop_api.core.languages import LANGUAGES
from comfyshop_api.models import Task
from comfyshop_official_worker.atlas_cloud import (
    ADAPTER,
    ATLAS_ROOT,
    Atlas,
    AtlasSpec,
    ImageReferenceObjects,
    MediaBinding,
    RunError,
)
from comfyshop_official_worker.runner import Runner

pytestmark = pytest.mark.official_catalog
SEEDANCE = "bytedance/seedance-2.5-flash/text-to-video"
SEEDANCE_IMAGE = "bytedance/seedance-2.5-flash/image-to-video"
SEEDANCE_REFERENCE = "bytedance/seedance-2.5-flash/reference-to-video"
SEEDREAM = "bytedance/seedream-v4.7/edit-sequential"
SEEDREAM_TEXT = "bytedance/seedream-v4.7/text-to-image"
SEEDREAM_EDIT = "bytedance/seedream-v4.7/edit"
SEEDREAM_SEQUENCE = "bytedance/seedream-v4.7/sequential"
H3_MAX = "minimax/h3-max/text-to-video"
H3_MAX_IMAGE = "minimax/h3-max/image-to-video"
H3_MAX_REFERENCE = "minimax/h3-max/reference-to-video"
H3_FAST_REFERENCE = "minimax/h3-fast/reference-to-video"
H3_FAST_TEXT = "minimax/h3-fast/text-to-video"
H3_FAST_IMAGE = "minimax/h3-fast/image-to-video"
H3_DEVELOPER_TEXT = "minimax/h3-developer/text-to-video"
H3_DEVELOPER_IMAGE = "minimax/h3-developer/image-to-video"
H3_DEVELOPER_REFERENCE = "minimax/h3-developer/reference-to-video"
H3_IMAGE_TEXT = "minimax/h3-image/text-to-image"
H3_IMAGE_HIGHSPEED_TEXT = "minimax/h3-image-highspeed/text-to-image"
H3_IMAGE_EDIT = "minimax/h3-image/edit"
H3_IMAGE_HIGHSPEED_EDIT = "minimax/h3-image-highspeed/edit"
H3_MAX_TURBO = "minimax/h3-max-turbo/text-to-video"
H3_MAX_TURBO_IMAGE = "minimax/h3-max-turbo/image-to-video"
GEMINI_FLASH_TTS = "google/gemini-2.5-flash-tts"
GEMINI_PRO_TTS = "google/gemini-2.5-pro-tts"
GEMINI_31_TTS = "google/gemini-3.1-flash-tts"
TRIPO_IMAGE = "tripo-h3.1/image-to-3d"
TRIPO_TEXT = "tripo-h3.1/text-to-3d"
MESHY_MULTI = "meshy-v7/multi-image-to-3d"
MESHY_IMAGE = "meshy-v7/image-to-3d"
MESHY_TEXT = "meshy-v7/text-to-3d"
HUNYUAN_RAPID_TEXT = "tencent/hunyuan3d-rapid/text-to-3d"
HUNYUAN_RAPID_IMAGE = "tencent/hunyuan3d-rapid/image-to-3d"
HUNYUAN_PRO_TEXT = "tencent/hunyuan3d-pro/text-to-3d"
HUNYUAN_PRO_IMAGE = "tencent/hunyuan3d-pro/image-to-3d"
SEED3D_IMAGE = "bytedance/seed3d-v2.0/image-to-3d"
HI3D_MASTER = "hi3d/v3.0-master/image-to-3d"
SEED_ASR = "bytedance/seed-asr-2.0"
SEED_AUDIO = "bytedance/seed-audio-1.0"
XAI_STT = "xai/stt-v1"
XAI_TTS = "xai/tts-v1"
KLING_CUSTOM_VOICE = "kwaivgi/kling-v4.0/custom-voice"
SUNO_V6 = "suno/chirp-v6"
TENCENT_IMAGE_UPSCALER = "tencent/image/upscaler"
SEEDREAM_50_PRO_EDIT = "bytedance/seedream-v5.0-pro/edit"
SEEDREAM_50_PRO_LAYERS = "bytedance/seedream-v5.0-pro/layer-decomposition"
MINIMAX_MUSIC_30 = "minimax/music-3.0"
MINIMAX_LYRICS = "minimax/lyrics-generation"
ELEVENLABS_MUSIC = "elevenlabs/music-v2.5/text-to-music"
ELEVENLABS_DETAILED = "elevenlabs/music-v2.5/text-to-music-detailed"
ELEVENLABS_TTS_V3 = "elevenlabs/v3/text-to-speech"
ELEVENLABS_TTS_V4 = "elevenlabs/v4/text-to-speech"
OBJ_BYTES = b"mtllib mesh.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
FBX_BYTES = b"; FBX 7.4.0 project file\nFBXHeaderExtension: {\n FBXVersion: 7400\n}\n"
OFFICIAL_WORKER_DIR = Path(__file__).resolve().parents[3] / "integrations" / "official-worker"
WORKFLOWS_DIR = OFFICIAL_WORKER_DIR / "comfyshop_official_worker/workflows/atlas-cloud"
BUILTINS = tuple(
    path.parent.relative_to(WORKFLOWS_DIR).as_posix()
    for path in sorted(WORKFLOWS_DIR.rglob("workflow.json"))
)
# These three templates shipped before the expanded catalog and can be tested on their own.
EXPANDED_CATALOG = bool(set(BUILTINS) - {SEEDANCE, SEEDREAM, H3_MAX})
BROWSER_MODELS = (
    SEEDANCE,
    SEEDANCE_IMAGE,
    SEEDANCE_REFERENCE,
    SEEDREAM,
    SEEDREAM_TEXT,
    H3_MAX,
    H3_MAX_IMAGE,
    H3_MAX_TURBO,
    H3_MAX_TURBO_IMAGE,
    GEMINI_FLASH_TTS,
    TRIPO_IMAGE,
    MESHY_MULTI,
)


def source(model):
    if not EXPANDED_CATALOG and model not in BUILTINS:
        pytest.skip("Requires the expanded Atlas Cloud workflow catalog")
    return files("comfyshop_official_worker").joinpath(
        "workflows", "atlas-cloud", *model.split("/"), "workflow.json"
    )


def upload_body(filename):
    graph = json.loads(source(filename).read_text(encoding="utf-8"))
    return {"name": graph["name"], "category": graph["category"], "graph": graph}


def upload(client, filename, language="zh"):
    return import_official(client, upload_body(filename), language)


def sync_workflows(address, *args, env=None):
    return subprocess.run(
        [sys.executable, "-m", "comfyshop_official_worker", "sync", *args],
        cwd=OFFICIAL_WORKER_DIR,
        env=os.environ
        | {"COMFYSHOP_SERVER_URL": address, "COMFYSHOP_WORKER_SERVICE_TOKENS__OFFICIAL": TOKEN}
        | (env or {}),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )


def iter_workflows(web, language="zh", **params):
    while True:
        page = (
            web.get("/api/v1/workflows", params=params, headers={"Accept-Language": language})
            .raise_for_status()
            .json()
        )
        yield from page["items"]
        cursor = page["nextCursor"]
        if cursor is None:
            return
        params["cursor"] = cursor


def wav_bytes(*, seconds=1):
    audio = BytesIO()
    with wave.open(audio, "wb") as output:
        output.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        output.writeframes(bytes(48000 * seconds))
    return audio.getvalue()


def archive_bytes(entries):
    target = BytesIO()
    with ZipFile(target, "w") as package:
        for filename, content in entries.items():
            package.writestr(filename, content)
    return target.getvalue()


@pytest.mark.skipif(not BUILTINS, reason="Requires bundled workflows")
def test_official_init_registers_and_reuses_default_owner(settings):
    settings.worker_service_tokens["official"] = SecretStr(TOKEN)
    settings.official_owner = "ComfyShop"
    password = "initial-test-password"
    with serve_test_app(settings) as (address, web):
        synced = None
        for configured_password, level in ((password, ""), ("short", "debug"), ("", "WARNING")):
            result = sync_workflows(
                address,
                "--init-owner",
                str(source(SEEDANCE)),
                env={
                    "COMFYSHOP_OFFICIAL_OWNER": "",
                    "COMFYSHOP_OFFICIAL_OWNER_PASSWORD": configured_password,
                    "COMFYSHOP_WORKER_LOG_LEVEL": level,
                },
            )
            assert all(secret not in result.stdout + result.stderr for secret in (password, TOKEN))
            assert ("官方工作流同步完成" in result.stderr) == (level != "WARNING")
            assert ("默认封面已同步" in result.stderr) == (level == "debug")
            draft = json.loads(result.stdout)
            assert synced is None or synced == draft
            synced = draft
        web.post(
            "/api/v1/auth/login", json={"username": "ComfyShop", "password": password}
        ).raise_for_status()
        (workflow,) = list(iter_workflows(web, scope="mine"))
        assert workflow["id"] == synced["workflowId"]
        assert workflow["author"] == "ComfyShop" and workflow["published"]
        assert workflow["media"]["width"] == 1254
        assert web.get("/api/v1/tasks").raise_for_status().json()["items"] == []


def test_official_init_draft_registers_default_owner_without_publishing(settings):
    settings.worker_service_tokens["official"] = SecretStr(TOKEN)
    settings.official_owner = "ComfyShop"
    password = "initial-test-password"
    with serve_test_app(settings) as (address, web):
        result = sync_workflows(
            address,
            "--init-owner",
            "--draft",
            str(source(SEEDANCE)),
            env={
                "COMFYSHOP_OFFICIAL_OWNER": "",
                "COMFYSHOP_OFFICIAL_OWNER_PASSWORD": password,
            },
        )
        draft = json.loads(result.stdout)
        detail_url = f"/api/v1/workflows/{draft['workflowId']}"
        assert list(iter_workflows(web)) == []
        assert web.get(detail_url).status_code == 404

        register(web, "another-account")
        assert list(iter_workflows(web, scope="mine")) == []
        assert web.get(detail_url).status_code == 404

        web.cookies.clear()
        web.post(
            "/api/v1/auth/login", json={"username": "ComfyShop", "password": password}
        ).raise_for_status()
        [workflow] = list(iter_workflows(web, scope="mine"))
        assert workflow["id"] == draft["workflowId"]
        assert workflow["versionId"] == draft["versionId"]
        assert workflow["author"] == "ComfyShop"
        assert workflow["published"] is False


@pytest.mark.skipif(not BUILTINS, reason="Requires bundled workflows")
def test_official_sync_preserves_execution_versions_and_localizes_the_shared_catalog(
    settings, tmp_path
):
    settings.worker_service_tokens["official"] = SecretStr(TOKEN)
    settings.official_owner = OWNER
    manifests = {filename: upload_body(filename)["graph"] for filename in BUILTINS}
    by_key = {spec["key"]: filename for filename, spec in manifests.items()}
    assert len(manifests) == len(by_key)
    cover_hashes = {}
    for key, filename in by_key.items():
        for name in ("cover.webp", "cover.png"):
            cover = source(filename).parent.joinpath(name)
            if cover.is_file():
                cover_hashes[key] = hashlib.sha256(cover.read_bytes()).hexdigest()
                break

    with serve_test_app(settings) as (address, web):
        register(web, OWNER)
        edited = upload_body(SEEDANCE)
        field = edited["graph"]["fields"][0]["name"]
        edited["graph"]["translations"]["en"]["fields"][field]["label"] = "Previous label"
        original = import_official(web, edited, "en")
        detail_url = f"/api/v1/workflows/{original['id']}"
        before = (
            web.get(f"{detail_url}/service-inputs", headers={"Accept-Language": "en"})
            .raise_for_status()
            .json()
        )
        assert before["fields"][0]["label"] == "Previous label"

        copied = tmp_path / "workflow.json"
        copied.write_bytes(source(SEEDANCE).read_bytes())
        targeted = json.loads(sync_workflows(address, str(copied)).stdout)
        assert targeted["workflowId"] == original["id"]
        assert targeted["versionId"] == original["versionId"]
        after = (
            web.get(f"{detail_url}/service-inputs", headers={"Accept-Language": "en"})
            .raise_for_status()
            .json()
        )
        assert after["fields"][0]["label"] != before["fields"][0]["label"]
        assert after["fields"][0]["default"] == before["fields"][0]["default"]
        assert after["schemaHash"] == before["schemaHash"]
        explicit_cover = web.get(detail_url).raise_for_status().json()["media"]
        assert f"/cover/{cover_hashes[manifests[SEEDANCE]['key']]}/" in explicit_cover["src"]

        drafts = [json.loads(line) for line in sync_workflows(address).stdout.splitlines()]
        assert len(drafts) == len({draft["workflowId"] for draft in drafts}) == len(BUILTINS)
        assert targeted in drafts
        ids = {}
        for draft in drafts:
            url = f"/api/v1/workflows/{draft['workflowId']}"
            exported = web.get(f"{url}/graph").raise_for_status().json()["graph"]
            key = exported["key"]
            ids[key] = draft["workflowId"]
            manifest = manifests[by_key[key]]
            assert set(manifest["translations"]) == set(LANGUAGES)
            assert exported["execution"] == {"additionalOutputKinds": [], **manifest["execution"]}
            assert draft["version"] == 1
        assert ids.keys() == by_key.keys()

        for language in LANGUAGES:
            catalog = list(iter_workflows(web, language=language, scope="mine", limit=100))
            assert {item["id"] for item in catalog} == set(ids.values())
            by_id = {item["id"]: item for item in catalog}
            for key, workflow_id in ids.items():
                item = by_id[workflow_id]
                expected = manifests[by_key[key]]["translations"][language]
                assert item["name"] == expected["name"]
                assert item["description"] == expected["description"]
                assert not item["published"]
                if key in cover_hashes:
                    cover = item["media"]
                    assert (cover["kind"], cover["width"], cover["height"]) == ("image", 1254, 1254)
                    assert f"/cover/{cover_hashes[key]}/thumbnail" in cover["src"]
                    assert cover["src"] == cover["thumbnail"]["src"]
                else:
                    assert item["media"] is None
        thumbnail = web.get(explicit_cover["src"], params={"size": 256}).raise_for_status()
        assert thumbnail.headers["Content-Type"] == "image/webp"
        assert web.post(f"{detail_url}/publish").status_code == 409
        web.patch(
            detail_url, json={"name": "作者的原文", "description": "保留原文简介"}
        ).raise_for_status()
        authored = web.get(detail_url, headers={"Accept-Language": "en"}).raise_for_status().json()
        assert (authored["name"], authored["description"]) == ("作者的原文", "保留原文简介")
        assert json.loads(sync_workflows(address, str(copied)).stdout) == targeted
        resynced = web.get(detail_url, headers={"Accept-Language": "en"}).raise_for_status().json()
        assert (resynced["name"], resynced["description"]) == ("作者的原文", "保留原文简介")
        originals = list(settings.original_dir.iterdir())
        assert sorted(
            hashlib.sha256(path.read_bytes()).hexdigest() for path in originals
        ) == sorted(cover_hashes.values())

        seedream_url = f"/api/v1/workflows/{ids[manifests[SEEDREAM]['key']]}"
        seedream = web.get(seedream_url).raise_for_status().json()
        cover_url = f"{seedream_url}/cover"
        uploaded = web.put(cover_url, json={"assetId": asset(web, image_bytes("blue"))})
        author_cover = uploaded.raise_for_status().json()["media"]
        output_png = image_bytes("red")
        reference = asset(web, output_png)
        task = submit(
            web, seedream, {"prompt": "Official cover", "reference_1": {"assetId": reference}}
        )
        lease = uuid4().hex
        headers = AUTH | {"X-Task-Lease": lease}
        job = (
            web.post(
                "/api/v1/worker/services/official/claim",
                headers=AUTH,
                json={
                    "protocolVersion": PROTOCOL_VERSION,
                    "claimId": str(uuid4()),
                    "leaseSecret": lease,
                    "adapters": [ADAPTER],
                },
            )
            .raise_for_status()
            .json()
        )
        assert job["task"]["id"] == task["id"]
        task_url = f"/api/v1/worker/tasks/{task['id']}"
        execution_url = f"{task_url}/executions/0"
        web.post(f"{execution_url}/reserve", headers=headers).raise_for_status()
        web.post(
            f"{execution_url}/start", headers=headers, json={"promptId": "offline-cover-test"}
        ).raise_for_status()
        result = (
            web.put(
                f"{task_url}/artifacts/result",
                headers=headers,
                content=output_png,
                params={
                    "filename": "result.png",
                    "sha256": hashlib.sha256(output_png).hexdigest(),
                    "execution_index": 0,
                    "output_node_id": "official",
                    "output_slot": "outputs",
                    "output_index": 0,
                },
            )
            .raise_for_status()
            .json()
        )
        execution = (
            web.post(f"{execution_url}/complete", headers=headers, json={"clientIds": ["result"]})
            .raise_for_status()
            .json()
        )
        web.post(f"{seedream_url}/publish").raise_for_status()
        work_id = str(uuid4())
        web.post(
            "/api/v1/works",
            json={
                "id": work_id,
                "executionId": execution["id"],
                "title": "Official cover example",
                "artifactIds": [result["id"]],
                "coverArtifactId": result["id"],
            },
        ).raise_for_status()
        pinned = web.put(cover_url, json={"workId": work_id}).raise_for_status().json()
        assert f"/artifacts/{result['id']}/" in pinned["media"]["src"]
        assert json.loads(sync_workflows(address, str(source(SEEDREAM))).stdout) in drafts
        current = web.get(seedream_url).raise_for_status().json()
        assert current["published"] and current["coverWorkId"] == work_id
        assert current["media"] == pinned["media"]
        cleared = web.put(cover_url, json={"workId": None}).raise_for_status().json()
        assert cleared["coverWorkId"] is None and cleared["media"] == author_cover


@pytest.mark.parametrize(
    ("model", "resolution", "ratio", "duration"),
    [
        (H3_FAST_TEXT, "480P", "1:1", 8),
        (H3_FAST_IMAGE, "480P", "adaptive", 8),
        (H3_DEVELOPER_TEXT, "768P", "1:1", 4),
        (H3_DEVELOPER_IMAGE, "768P", "adaptive", 4),
    ],
    ids=["fast-text", "fast-image", "developer-text", "developer-image"],
)
def test_h3_video_applies_model_parameters(official, model, resolution, ratio, duration):
    workflow = upload(official, model)
    prompt = "海边的风吹过芦苇。"
    values = {"prompt": prompt}
    if duration != 8:
        values = values | {"duration_seconds": duration}
    task = submit(official, workflow, values)
    config = upload_body(model)["graph"]["execution"]["config"]
    assert AtlasSpec.model_validate(config).payload(task["inputValues"]) == {
        "model": model,
        "prompt": prompt,
        "resolution": resolution,
        "duration": duration,
        "ratio": ratio,
        "prompt_expansion": False,
    }


def test_seedance_reference_video_uploads_each_media_type_in_slot_order(
    official, settings, tmp_path, small_mp4
):
    workflow = upload(official, SEEDANCE_REFERENCE)
    spec = AtlasSpec.model_validate(upload_body(SEEDANCE_REFERENCE)["graph"]["execution"]["config"])
    with pytest.raises(RunError, match="reference_audios"):
        spec.assets_by_parameter({}, {"audio_1": {"contentType": "audio/flac"}})
    references = {}
    for suffix in ("wav", "mp3"):
        path = tmp_path / f"reference.{suffix}"
        subprocess.run(
            [settings.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=duration=2.2", str(path)],
            check=True,
        )
        references[path.name] = path.read_bytes()
    references["first.png"] = image_bytes("red", size=(320, 320))
    references["second.png"] = image_bytes("blue", size=(320, 320))
    references["reference.mp4"] = small_mp4

    values = {
        "prompt": "让 @Image1 和 @Image2 中的物体随 @Audio1 的节奏在 @Video1 的场景里移动。",
        "reference_task_type": "reference",
    }
    for slot, filename in (
        ("image_5", "second.png"),
        ("image_2", "first.png"),
        ("video_3", "reference.mp4"),
        ("audio_5", "reference.mp3"),
        ("audio_2", "reference.wav"),
    ):
        values[slot] = {"assetId": asset(official, references[filename], filename)}

    assert set(spec.media["reference_audios"].content_types) == {"audio/wav", "audio/mpeg"}
    task = submit(official, workflow, values)

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            (name,) = [name for name, content in references.items() if content in request.content]
            return httpx.Response(200, json={"url": f"https://cdn.example/{name}"})
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": SEEDANCE_REFERENCE,
                "prompt": values["prompt"],
                "duration": 5,
                "ratio": "adaptive",
                "resolution": "720p",
                "output_format": "mp4",
                "generate_audio": True,
                "watermark": False,
                "return_last_frame": False,
                "omni_reference_task_type": "reference",
                "reference_images": [
                    "https://cdn.example/first.png",
                    "https://cdn.example/second.png",
                ],
                "reference_videos": ["https://cdn.example/reference.mp4"],
                "reference_audios": [
                    "https://cdn.example/reference.wav",
                    "https://cdn.example/reference.mp3",
                ],
            }
            return httpx.Response(200, json={"data": {"id": "prediction-reference"}})
        assert request.url.path.endswith("/prediction/prediction-reference")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.mp4"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=small_mp4, headers={"Content-Type": "video/mp4"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["media"]["kind"] == "video"


@pytest.mark.parametrize(
    ("model", "resolution", "ratio", "duration"),
    [
        (H3_MAX_REFERENCE, "768P", "adaptive", 8),
        (H3_FAST_REFERENCE, "480P", "16:9", 8),
        (H3_DEVELOPER_REFERENCE, "768P", "adaptive", 4),
    ],
    ids=["max", "fast", "developer"],
)
def test_h3_reference_video_sends_typed_references(
    official, settings, tmp_path, small_mp4, model, resolution, ratio, duration
):
    workflow = upload(official, model)
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    with pytest.raises(RunError, match="refers.*image、video"):
        spec.assets_by_parameter({}, {"audio_1": {"contentType": "audio/wav"}})
    with pytest.raises(RunError, match="refers.*12"):
        spec.assets_by_parameter(
            {},
            {f"image_{slot}": {"contentType": "image/png"} for slot in range(1, 10)}
            | {f"video_{slot}": {"contentType": "video/mp4"} for slot in range(1, 4)}
            | {"audio_1": {"contentType": "audio/wav"}},
        )

    camera = tmp_path / "camera.mp4"
    subprocess.run(
        [
            settings.ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=320x320:r=24:d=2.2",
            "-c:v",
            "libx264",
            str(camera),
        ],
        check=True,
    )
    references = {
        "opening.png": image_bytes("red", size=(320, 320)),
        "subject.png": image_bytes("blue", size=(320, 320)),
        "camera.mp4": camera.read_bytes(),
        "beat.wav": wav_bytes(seconds=3),
    }
    prompt = "保留参考图中的静物，跟随视频的运镜和音频的节奏。"
    task = submit(
        official,
        workflow,
        {"prompt": prompt, "duration_seconds": duration}
        | {
            field: {"assetId": asset(official, references[name], name)}
            for field, name in (
                ("audio_2", "beat.wav"),
                ("image_5", "subject.png"),
                ("video_3", "camera.mp4"),
                ("image_2", "opening.png"),
            )
        },
    )
    uploaded = []

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            (name,) = [name for name, content in references.items() if content in request.content]
            uploaded.append(name)
            return httpx.Response(200, json={"url": f"https://cdn.example/ref-{len(uploaded)}"})
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": model,
                "prompt": prompt,
                "resolution": resolution,
                "duration": duration,
                "ratio": ratio,
                "prompt_expansion": False,
                "refers": [
                    {"url": "https://cdn.example/ref-1", "type": "image"},
                    {"url": "https://cdn.example/ref-2", "type": "image"},
                    {"url": "https://cdn.example/ref-3", "type": "video"},
                    {"url": "https://cdn.example/ref-4", "type": "audio"},
                ],
            }
            return httpx.Response(200, json={"data": {"id": "prediction-typed-references"}})
        assert request.url.path.endswith("/prediction/prediction-typed-references")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.mp4"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=small_mp4, headers={"Content-Type": "video/mp4"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    assert uploaded == ["opening.png", "subject.png", "camera.mp4", "beat.wav"]
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["media"]["kind"] == "video"
    assert official.get(artifact["media"]["video"]).content == small_mp4


@pytest.mark.parametrize("model", [SEEDREAM, SEEDREAM_EDIT], ids=["sequential", "edit"])
def test_seedream_uses_media_bindings_and_preserves_reference_order(official, worker_logs, model):
    workflow = upload(official, model)
    red, blue = image_bytes("red"), image_bytes("blue")
    task = submit(
        official,
        workflow,
        {
            "prompt": "编辑参考图",
            "reference_3": {"assetId": asset(official, blue)},
            "reference_1": {"assetId": asset(official, red)},
            "reference_2": None,
        },
    )
    uploads = []
    outputs = {"https://cdn.example/red.png?signature=private-signed-download": red}
    if model == SEEDREAM:
        outputs["https://cdn.example/blue.png?signature=private-signed-download"] = blue

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            content = red if red in request.content else blue
            assert content in request.content
            uploads.append(content)
            return httpx.Response(200, json={"url": f"https://cdn.example/ref-{len(uploads)}.png"})
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            payload = json.loads(request.content)
            expected = {
                "model": model,
                "prompt": "编辑参考图",
                "enable_base64_output": False,
                "prompt_expansion_mode": "standard",
                "size": "2048*2048",
                "images": ["https://cdn.example/ref-1.png", "https://cdn.example/ref-2.png"],
            }
            if model == SEEDREAM:
                expected["num_images"] = 2
            assert payload == expected
            return httpx.Response(200, json={"data": {"id": "prediction-images"}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "outputs": list(outputs),
                }
            },
        )

    def download(request):
        return httpx.Response(
            200,
            content=outputs[str(request.url)],
            headers={"Content-Type": "image/png"},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    assert uploads == [red, blue]
    logs = "".join(worker_logs)
    assert task["id"] in logs and "'execution_index': 0" in logs
    assert "'prediction_id': 'prediction-images'" in logs
    assert "'asset_count': 2" in logs
    assert logs.count("DEBUG | 平台成品回传响应") == len(outputs)
    assert "INFO | 官方成品已入库" in logs and f"'output_count': {len(outputs)}" in logs
    assert all(
        value not in logs
        for value in ("编辑参考图", "cdn.example", "private-signed-download", TOKEN)
    )
    artifacts = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    ordered = sorted(artifacts, key=lambda artifact: artifact["outputIndex"])
    assert len({artifact["executionId"] for artifact in ordered}) == 1
    assert [official.get(artifact["media"]["src"]).content for artifact in ordered] == list(
        outputs.values()
    )


def test_seedream_text_sequence_sends_count_and_saves_inline_images_in_order(official):
    workflow = upload(official, SEEDREAM_SEQUENCE)
    prompt = "绘制两张风格一致的图片"
    submit(official, workflow, {"prompt": prompt, "image_count": 15}, expected_status=422)

    task = submit(official, workflow, {"prompt": prompt, "image_count": 2, "base64_output": True})
    images = [image_bytes("red"), image_bytes("blue")]

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": SEEDREAM_SEQUENCE,
                "prompt": prompt,
                "num_images": 2,
                "size": "2048*2048",
                "prompt_expansion_mode": "standard",
                "enable_base64_output": True,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-sequence"}})
        assert request.url.path.endswith("/prediction/prediction-sequence")
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "outputs": [base64.b64encode(image).decode("ascii") for image in images],
                }
            },
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: pytest.fail("Base64 images are inline"))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    artifacts = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    ordered = sorted(artifacts, key=lambda artifact: artifact["outputIndex"])
    assert [artifact["filename"] for artifact in ordered] == ["result-1.png", "result-2.png"]
    assert [official.get(artifact["media"]["src"]).content for artifact in ordered] == images


@pytest.mark.parametrize("model", [GEMINI_PRO_TTS, GEMINI_31_TTS])
def test_gemini_tts_sends_selected_voice_and_saves_wav(official, model):
    workflow = upload(official, model)
    text = "Please read this sentence at a steady pace."
    task = submit(official, workflow, {"text": text, "voice": "Charon"})
    if model == GEMINI_31_TTS:
        submit(official, workflow, {"text": "字" * 10001}, expected_status=422)
    wav = wav_bytes()
    url = "https://cdn.example/speech.wav"

    def result(status, **fields):
        payload = {"id": "prediction-speech", "status": status, **fields}
        return httpx.Response(200, json=payload if model == GEMINI_31_TTS else {"data": payload})

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateAudio")
            assert json.loads(request.content) == {
                "model": model,
                "text": text,
                "voice": "Charon",
            }
            return result("created")
        assert request.url.path.endswith("/prediction/prediction-speech")
        return result("completed", outputs=[url])

    def download(request):
        assert str(request.url) == url
        return httpx.Response(200, content=wav, headers={"Content-Type": "audio/wav"})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["contentType"] == "audio/wav" and artifact["media"]["kind"] == "audio"
    assert official.get(artifact["media"]["src"]).content == wav


@pytest.mark.parametrize(
    ("values", "error"),
    [
        ({"image_size": "auto", "expand_prompt": False}, "自动尺寸"),
        ({"image_size": "2048x2048"}, "宽\\*高"),
        ({"image_size": "468*468"}, "尺寸超出范围"),
        ({"image_size": "468*3000"}, "尺寸超出范围"),
        ({"image_size": "7800*2600"}, "尺寸超出范围"),
        ({"prompt": "a" * 32001}, "32000"),
    ],
)
def test_h3_image_rejects_invalid_size_and_text(values, error):
    config = upload_body(H3_IMAGE_TEXT)["graph"]["execution"]["config"]
    with pytest.raises(RunError, match=error) as failure:
        AtlasSpec.model_validate(config).payload({"prompt": "静物摄影"} | values)
    assert failure.value.retryable


@pytest.mark.parametrize("sync_mode", [False, True], ids=["async", "sync"])
@pytest.mark.parametrize(
    "model", [H3_IMAGE_TEXT, H3_IMAGE_HIGHSPEED_TEXT], ids=["standard", "highspeed"]
)
def test_h3_image_saves_outputs_from_prediction_or_submission(official, sync_mode, model):
    workflow = upload(official, model)
    prompt = "绘制白色茶杯和木勺。"
    values = {"prompt": prompt, "output_format": "png"}
    if sync_mode:
        values = values | {
            "image_size": "2048*1536",
            "expand_prompt": False,
            "synchronous_response": True,
            "base64_output": True,
        }
    task = submit(official, workflow, values)
    png = image_bytes("green", size=(320, 320))
    url = "https://cdn.example/image.png"
    prediction_id = "prediction-h3-image"
    calls = []

    def provider(request):
        calls.append(request.method)
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": model,
                "prompt": prompt,
                "size": "2048*1536" if sync_mode else "auto",
                "num_images": 1,
                "enable_prompt_expansion": not sync_mode,
                "output_format": "png",
                "output_compression": 95,
                "enable_sync_mode": sync_mode,
                "enable_base64_output": sync_mode,
            }
            data = {"id": prediction_id, "status": "created"}
            if sync_mode:
                assert request.extensions["timeout"]["read"] == 30 * 60
                data = {
                    "id": prediction_id,
                    "status": "completed",
                    "outputs": [base64.b64encode(png).decode("ascii")],
                }
            return httpx.Response(200, json={"data": data})
        assert not sync_mode and request.url.path.endswith(f"/prediction/{prediction_id}")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [url]}})

    def download(request):
        assert not sync_mode and str(request.url) == url
        return httpx.Response(200, content=png, headers={"Content-Type": "image/png"})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    assert calls == (["POST"] if sync_mode else ["POST", "GET"])
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["filename"] == "result-1.png"
    assert official.get(artifact["media"]["src"]).content == png
    with Session(official.app.state.engine) as db:
        result = db.get(Task, task["id"])
        assert result is not None and result.prompt_id == prediction_id


@pytest.mark.parametrize(
    "model", [H3_IMAGE_EDIT, H3_IMAGE_HIGHSPEED_EDIT], ids=["standard", "highspeed"]
)
def test_h3_image_edit_validates_and_orders_reference_images(official, model):
    workflow = upload(official, model)
    config = upload_body(model)["graph"]["execution"]["config"]
    spec = AtlasSpec.model_validate(config)
    small = {"size": 123, "contentType": "image/png", "media": {"width": 120, "height": 512}}
    with pytest.raises(RunError, match="参考图尺寸或宽高比"):
        spec.assets_by_parameter({}, {"reference_1": small})
    with pytest.raises(RunError, match="67108864"):
        spec.assets_by_parameter({}, {"reference_1": small | {"size": 64 * 1024**2 + 1}})

    red = image_bytes("red", size=(320, 320))
    blue = image_bytes("blue", size=(320, 320))
    prompt = "保留第一张图的构图，使用第二张图的颜色。"
    task = submit(
        official,
        workflow,
        {
            "prompt": prompt,
            "reference_16": {"assetId": asset(official, blue, "blue.png")},
            "reference_1": {"assetId": asset(official, red, "red.png")},
            "output_format": "png",
        },
    )
    uploads = []

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            (name,) = [
                name for name, data in (("red", red), ("blue", blue)) if data in request.content
            ]
            uploads.append(name)
            return httpx.Response(200, json={"url": f"https://cdn.example/{name}.png"})
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": model,
                "prompt": prompt,
                "reference_images": ["https://cdn.example/red.png", "https://cdn.example/blue.png"],
                "size": "auto",
                "num_images": 1,
                "output_format": "png",
                "output_compression": 95,
                "enable_sync_mode": False,
                "enable_base64_output": False,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-h3-edit"}})
        assert request.url.path.endswith("/prediction/prediction-h3-edit")
        return httpx.Response(
            200, json={"data": {"status": "completed", "outputs": ["https://cdn.example/edit.png"]}}
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=blue, headers={"Content-Type": "image/png"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    assert uploads == ["red", "blue"]
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert official.get(artifact["media"]["src"]).content == blue


def test_tripo_text_maps_prompt_and_seeds_and_saves_model_with_preview(official):
    workflow = upload(official, TRIPO_TEXT)
    spec = AtlasSpec.model_validate(upload_body(TRIPO_TEXT)["graph"]["execution"]["config"])
    with pytest.raises(RunError, match="1024"):
        spec.payload({"prompt": "a" * 1025})
    prompt = "蓝色陶瓷花盆"
    task = submit(
        official,
        workflow,
        {
            "prompt": prompt,
            "negative_prompt": "文字",
            "model_seed": 17,
            "image_seed": 23,
            "texture_seed": 42,
            "face_limit": 50000,
        },
    )
    glb, image = glb_bytes(), image_bytes("blue")
    files_by_path = {"/mesh.glb": (glb, "model/gltf-binary"), "/preview.png": (image, "image/png")}

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": TRIPO_TEXT,
                "prompt": prompt,
                "negative_prompt": "文字",
                "texture": True,
                "pbr": True,
                "texture_quality": "standard",
                "geometry_quality": "standard",
                "model_seed": 17,
                "image_seed": 23,
                "texture_seed": 42,
                "face_limit": 50000,
                "auto_size": False,
                "quad": False,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-tripo-text"}})
        assert request.url.path.endswith("/prediction/prediction-tripo-text")
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "outputs": [f"https://cdn.example{path}" for path in files_by_path],
                }
            },
        )

    def download(request):
        data, content_type = files_by_path[request.url.path]
        return httpx.Response(200, content=data, headers={"Content-Type": content_type})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    artifacts = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    by_kind = {artifact["media"]["kind"]: artifact["media"]["src"] for artifact in artifacts}
    assert set(by_kind) == {"3d", "image"}
    assert official.get(by_kind["3d"]).content == glb
    assert official.get(by_kind["image"]).content == image


def test_meshy_multi_image_maps_formats_and_preserves_model_files(official):
    workflow = upload(official, MESHY_MULTI)
    spec = AtlasSpec.model_validate(upload_body(MESHY_MULTI)["graph"]["execution"]["config"])
    with pytest.raises(RunError, match="target_formats"):
        spec.payload({})

    geometry = {"contentType": "image/png", "id": "front"}
    texture = {"contentType": "image/png", "id": "surface"}
    with pytest.raises(RunError, match="texture_images.*texture_prompt"):
        spec.assets_by_parameter(
            {"texture_prompt": "matte ceramic"},
            {"reference_1": geometry, "texture_reference_1": texture},
        )
    payload = spec.payload(
        {"export_glb": True, "textured": False, "pbr": True, "remesh": False, "topology": "quad"}
    )
    assert payload == {
        "model": MESHY_MULTI,
        "target_formats": ["glb"],
        "should_texture": False,
        "should_remesh": False,
    }
    assert spec.assets_by_parameter(
        payload, {"reference_1": geometry, "texture_reference_1": texture}
    ) == {"reference_images": [geometry]}

    inputs = {
        "front.png": image_bytes("red"),
        "side.png": image_bytes("blue"),
        "texture.png": image_bytes("green"),
    }
    formats = ["glb", "obj", "fbx", "stl", "usdz", "3mf"]
    task = submit(
        official,
        workflow,
        {
            "reference_1": {"assetId": asset(official, inputs["front.png"], "front.png")},
            "reference_4": {"assetId": asset(official, inputs["side.png"], "side.png")},
            "texture_reference_4": {
                "assetId": asset(official, inputs["texture.png"], "texture.png")
            },
            "pbr": True,
            "remesh": True,
            "decimation_level": 3,
            "additional_previews": True,
        }
        | {f"export_{kind}": True for kind in formats},
    )

    outputs = {
        "mesh.glb": (glb_bytes(), "model/gltf-binary"),
        "mesh.obj": (OBJ_BYTES, "model/obj"),
        "mesh.fbx": (FBX_BYTES, "application/x-fbx"),
        "mesh.stl": (bytes(80) + b"\x01\x00\x00\x00" + bytes(50), "model/stl"),
        "mesh.usdz": (archive_bytes({"scene.usda": "#usda 1.0\n"}), "model/vnd.usdz+zip"),
        "mesh.3mf": (
            archive_bytes({"[Content_Types].xml": "<Types/>", "3D/model.model": "<model/>"}),
            "model/3mf",
        ),
        "mesh.mtl": (b"newmtl surface\nmap_Kd surface.png\n", "model/mtl"),
        "surface.png": (inputs["texture.png"], "image/png"),
    }
    urls = {f"https://cdn.example/{index}": name for index, name in enumerate(outputs)}
    uploaded = []

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            (name,) = [name for name, data in inputs.items() if data in request.content]
            uploaded.append(name)
            return httpx.Response(200, json={"url": f"https://cdn.example/{name}"})
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": MESHY_MULTI,
                "reference_images": [
                    "https://cdn.example/front.png",
                    "https://cdn.example/side.png",
                ],
                "texture_images": ["https://cdn.example/texture.png"],
                "should_texture": True,
                "ultra_mode": False,
                "enable_pbr": True,
                "texture_resolution": "2k",
                "image_enhancement": True,
                "remove_lighting": True,
                "should_remesh": True,
                "topology": "triangle",
                "target_polycount": 30000,
                "decimation_mode": 3,
                "save_pre_remeshed_model": False,
                "pose_mode": "",
                "target_formats": formats,
                "auto_size": False,
                "alpha_thumbnail": False,
                "multi_view_thumbnails": True,
                "moderation": False,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-meshy-multi"}})
        assert request.url.path.endswith("/prediction/prediction-meshy-multi")
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "outputs": list(urls),
                    "files": [
                        {"url": url, "file_name": f"exports/{name}"} for url, name in urls.items()
                    ],
                }
            },
        )

    def download(request):
        content, _ = outputs[urls[str(request.url)]]
        return httpx.Response(
            200, content=content, headers={"Content-Type": "application/octet-stream"}
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    assert sorted(uploaded) == sorted(inputs)
    assert uploaded.index("front.png") < uploaded.index("side.png")
    artifacts = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert {item["filename"] for item in artifacts} == set(outputs)
    for item in artifacts:
        expected_bytes, expected_type = outputs[item["filename"]]
        response = official.get(item["media"]["src"])
        assert response.content == expected_bytes
        assert item["contentType"] == expected_type
        if item["filename"] not in {"mesh.glb", "surface.png"}:
            assert response.headers["Content-Disposition"].startswith("attachment;")
    (execution,) = official.get("/api/v1/executions", params={"task_id": task["id"]}).json()[
        "items"
    ]
    assert execution["modelCount"] == len(formats) and execution["artifactCount"] == len(outputs)


def test_meshy_single_image_sends_scalar_references_and_default_format(official):
    workflow = upload(official, MESHY_IMAGE)
    source_image, texture_image = image_bytes("red"), image_bytes("blue")
    task = submit(
        official,
        workflow,
        {
            "reference_image": {"assetId": asset(official, source_image, "object.png")},
            "texture_image": {"assetId": asset(official, texture_image, "texture.png")},
            "texture_prompt": "matte blue ceramic",
        },
    )
    output_url = "https://cdn.example/opaque"

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            if source_image in request.content:
                return httpx.Response(200, json={"url": "https://cdn.example/object.png"})
            assert texture_image in request.content
            return httpx.Response(200, json={"url": "https://cdn.example/texture.png"})
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": MESHY_IMAGE,
                "image": "https://cdn.example/object.png",
                "texture_image": "https://cdn.example/texture.png",
                "texture_prompt": "matte blue ceramic",
                "should_texture": True,
                "ultra_mode": False,
                "enable_pbr": False,
                "texture_resolution": "2k",
                "image_enhancement": True,
                "should_remesh": False,
                "pose_mode": "",
                "target_formats": ["glb"],
                "auto_size": False,
                "alpha_thumbnail": False,
                "multi_view_thumbnails": False,
                "moderation": False,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-meshy-image"}})
        assert request.url.path.endswith("/prediction/prediction-meshy-image")
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "outputs": [output_url],
                    "files": [{"url": output_url, "type": "GLB"}],
                }
            },
        )

    glb = glb_bytes()

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=glb))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["filename"] == "result-1.glb"
    assert official.get(artifact["media"]["src"]).content == glb


@pytest.mark.parametrize("mode", ["full", "preview"])
def test_meshy_text_mode_controls_texture_payload(official, mode):
    workflow = upload(official, MESHY_TEXT)
    prompt = "一把浅色木椅"
    task = submit(
        official,
        workflow,
        {
            "prompt": prompt,
            "generation_mode": mode,
            "texture_prompt": "natural wood",
            "pbr": True,
            "texture_image": {"assetId": asset(official, image_bytes("brown"))},
        },
    )
    expected = {
        "model": MESHY_TEXT,
        "prompt": prompt,
        "mode": mode,
        "ultra_mode": False,
        "should_remesh": False,
        "pose_mode": "",
        "target_formats": ["glb"],
        "auto_size": False,
        "alpha_thumbnail": False,
        "moderation": False,
    }
    if mode == "full":
        expected |= {
            "enable_pbr": True,
            "texture_resolution": "2k",
            "texture_prompt": "natural wood",
            "texture_image": "https://cdn.example/texture.png",
        }
    output = "https://cdn.example/mesh.glb"

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert mode == "full"
            return httpx.Response(200, json={"url": "https://cdn.example/texture.png"})
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == expected
            return httpx.Response(200, json={"data": {"id": "prediction-meshy-text"}})
        assert request.url.path.endswith("/prediction/prediction-meshy-text")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [output]}})

    glb = glb_bytes()

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=glb))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["filename"] == "result-1.glb"
    assert official.get(artifact["media"]["src"]).content == glb


def test_hunyuan_rapid_accepts_video_and_preview_in_3d_workflow(official, small_mp4):
    workflow = upload(official, HUNYUAN_RAPID_TEXT)
    prompt = "浅绿色玻璃花瓶"
    task = submit(official, workflow, {"prompt": prompt, "output_format": "MP4"})
    preview = image_bytes("green")
    outputs = {
        "https://cdn.example/turntable.mp4": (small_mp4, "video/mp4"),
        "https://cdn.example/preview.png": (preview, "image/png"),
    }

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": HUNYUAN_RAPID_TEXT,
                "prompt": prompt,
                "format": "MP4",
                "enable_pbr": False,
                "enable_geometry": False,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-rapid"}})
        assert request.url.path.endswith("/prediction/prediction-rapid")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": list(outputs)}})

    def download(request):
        content, content_type = outputs[str(request.url)]
        return httpx.Response(200, content=content, headers={"Content-Type": content_type})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    artifacts = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    media = {artifact["media"]["kind"]: artifact["media"] for artifact in artifacts}
    assert set(media) == {"video", "image"}
    assert official.get(media["video"]["video"]).content == small_mp4
    assert official.get(media["image"]["src"]).content == preview


def test_hunyuan_rapid_image_sends_verified_base64_and_keeps_geometry(official):
    workflow = upload(official, HUNYUAN_RAPID_IMAGE)
    config = upload_body(HUNYUAN_RAPID_IMAGE)["graph"]["execution"]["config"]
    spec = AtlasSpec.model_validate(config)
    reference = {
        "size": 4500001,
        "contentType": "image/png",
        "media": {"width": 320, "height": 320},
    }
    with pytest.raises(RunError, match="4500000"):
        spec.assets_by_parameter({}, {"reference_image": reference})
    with pytest.raises(RunError, match="参考图尺寸"):
        spec.assets_by_parameter(
            {}, {"reference_image": reference | {"size": 8, "media": {"width": 127, "height": 320}}}
        )

    png = image_bytes("green", size=(320, 320))
    task = submit(
        official,
        workflow,
        {
            "reference_image": {"assetId": asset(official, png)},
            "pbr": True,
            "include_geometry": True,
        },
    )
    urls = ["https://cdn.example/model.glb", "https://cdn.example/geometry.glb"]

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            encoded = base64.b64encode(png).decode("ascii")
            assert json.loads(request.content) == {
                "model": HUNYUAN_RAPID_IMAGE,
                "image": f"data:image/png;base64,{encoded}",
                "format": "GLB",
                "enable_pbr": True,
                "enable_geometry": True,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-rapid-image"}})
        assert request.url.path.endswith("/prediction/prediction-rapid-image")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": urls}})

    glb = glb_bytes()

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=glb))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    artifacts = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert {artifact["filename"] for artifact in artifacts} == {"result-1.glb", "result-2.glb"}
    assert all(artifact["media"]["kind"] == "3d" for artifact in artifacts)


def test_hunyuan_pro_text_maps_geometry_and_face_count(official):
    workflow = upload(official, HUNYUAN_PRO_TEXT)
    prompt = "浅绿色玻璃花瓶"
    values = {"prompt": prompt, "generation_type": "Geometry", "pbr": True, "face_count": 40000}
    submit(official, workflow, values | {"face_count": 39999}, expected_status=422)
    task = submit(official, workflow, values)
    config = upload_body(HUNYUAN_PRO_TEXT)["graph"]["execution"]["config"]
    assert AtlasSpec.model_validate(config).payload(task["inputValues"]) == {
        "model": HUNYUAN_PRO_TEXT,
        "prompt": prompt,
        "generate_type": "Geometry",
        "face_count": 40000,
    }


def test_hunyuan_pro_image_sends_pbr_and_keeps_model_archive(official):
    workflow = upload(official, HUNYUAN_PRO_IMAGE)
    spec = AtlasSpec.model_validate(upload_body(HUNYUAN_PRO_IMAGE)["graph"]["execution"]["config"])
    reference = {
        "size": 6000000,
        "contentType": "image/webp",
        "media": {"width": 128, "height": 5000},
    }
    assert spec.assets_by_parameter({}, {"reference_image": reference}) == {"image": [reference]}
    with pytest.raises(RunError, match="6000000"):
        spec.assets_by_parameter({}, {"reference_image": reference | {"size": 6000001}})

    png = image_bytes("blue", size=(320, 320))
    task = submit(
        official, workflow, {"reference_image": {"assetId": asset(official, png)}, "pbr": True}
    )
    bundle = archive_bytes({"mesh.obj": OBJ_BYTES, "texture.png": png})
    output = "https://cdn.example/model.zip"

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            source = base64.b64encode(png).decode("ascii")
            assert json.loads(request.content) == {
                "model": HUNYUAN_PRO_IMAGE,
                "image": f"data:image/png;base64,{source}",
                "generate_type": "Normal",
                "enable_pbr": True,
                "face_count": 500000,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-pro-image"}})
        assert request.url.path.endswith("/prediction/prediction-pro-image")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [output]}})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=bundle))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["filename"] == "result-1.zip"
    assert official.get(artifact["media"]["src"]).content == bundle


def test_seed3d_reference_image_bounds():
    spec = AtlasSpec.model_validate(upload_body(SEED3D_IMAGE)["graph"]["execution"]["config"])
    reference = {
        "size": 10000000,
        "contentType": "image/bmp",
        "media": {"width": 4096, "height": 4095},
    }
    assert spec.assets_by_parameter({}, {"reference_image": reference}) == {"image": [reference]}
    for width, height in ((4096, 4096), (250, 100), (100, 250)):
        invalid = reference | {"media": {"width": width, "height": height}}
        with pytest.raises(RunError, match="尺寸或宽高比"):
            spec.assets_by_parameter({}, {"reference_image": invalid})
    with pytest.raises(RunError, match="10000000"):
        spec.assets_by_parameter({}, {"reference_image": reference | {"size": 10000001}})


@pytest.mark.parametrize("inline", [False, True], ids=["url", "base64"])
def test_seed3d_maps_options_and_preserves_original_zip(official, inline):
    workflow = upload(official, SEED3D_IMAGE)
    bmp = image_bytes("blue", size=(320, 320), format="BMP")
    reference = asset(official, bmp, filename="reference.bmp")
    task = submit(
        official,
        workflow,
        {"reference_image": {"assetId": reference}, "file_format": "obj", "base64_output": inline},
    )
    bundle = archive_bytes({"mesh.obj": OBJ_BYTES})
    url = "https://cdn.example/model.zip"

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            encoded = base64.b64encode(bmp).decode("ascii")
            assert json.loads(request.content) == {
                "model": SEED3D_IMAGE,
                "image": f"data:image/bmp;base64,{encoded}",
                "subdivision_level": "medium",
                "file_format": "obj",
                "enable_base64_output": inline,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-seed3d"}})
        assert request.url.path.endswith("/prediction/prediction-seed3d")
        output = base64.b64encode(bundle).decode("ascii") if inline else url
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [output]}})

    def downloads(request):
        assert not inline and str(request.url) == url
        return httpx.Response(200, content=bundle)

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(downloads)) as transport,
        ):
            assert await Runner(platform, Atlas(atlas), transport).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["filename"] == "result-1.zip"
    assert artifact["media"]["kind"] == "3d"
    response = official.get(artifact["media"]["src"])
    assert response.content == bundle and response.headers["content-type"] == "application/zip"


def test_seed3d_browser_accepts_bmp_at_desktop_and_mobile_widths(settings):
    settings = settings.model_copy(
        update={
            "static_dir": Path(__file__).resolve().parents[2] / "web" / "dist",
            "worker_service_tokens": {"official": SecretStr(TOKEN)},
            "official_owner": OWNER,
        }
    )
    bmp = image_bytes("blue", size=(320, 320), format="BMP")
    gif = image_bytes("navy", size=(320, 320), format="GIF")
    with (
        serve_test_app(settings) as (address, web),
        sync_playwright() as playwright,
        playwright.chromium.launch() as chromium,
    ):
        owner = register(web, OWNER)
        workflow = upload(web, SEED3D_IMAGE)
        for width, height in ((1440, 900), (390, 844)):
            page = chromium.new_page(base_url=address, viewport={"width": width, "height": height})
            assert page.request.post(
                "/api/v1/auth/login", data=owner, headers={"Origin": address}
            ).ok
            page.goto(f"/workflows/{workflow['id']}")
            form = page.locator("form.run-fields")
            image_input = form.locator("#input-reference_image")
            expect(image_input).to_have_attribute(
                "accept", "image/jpeg,image/png,image/webp,image/bmp,.bmp"
            )
            expect(form.get_by_text("支持 JPEG, PNG, WebP, BMP。", exact=True)).to_be_visible()
            with page.expect_response(
                lambda response: (
                    "/api/v1/assets/" in response.url and response.request.method == "PUT"
                )
            ) as uploaded:
                image_input.set_input_files(
                    {"name": "reference.bmp", "mimeType": "image/bmp", "buffer": bmp}
                )
            result = uploaded.value.json()
            assert uploaded.value.ok and result["contentType"] == "image/bmp"
            assert (result["media"]["width"], result["media"]["height"]) == (320, 320)
            expect(form.get_by_text("reference.bmp", exact=True)).to_be_visible()
            image_input.set_input_files(
                {"name": "reference.gif", "mimeType": "image/gif", "buffer": gif}
            )
            expect(form.get_by_role("alert")).to_contain_text("reference.gif")
            expect(form.get_by_text("当前素材 reference.bmp", exact=True)).to_be_visible()
            page.close()


def test_hi3d_master_checks_view_slots_and_returns_model_and_preview(official):
    workflow = upload(official, HI3D_MASTER)
    front = image_bytes("red")
    left = image_bytes("blue")
    values = {
        "reference_image": {"assetId": asset(official, front)},
        "view_2": {"assetId": asset(official, left)},
        "view_slots": "1010",
        "texture": False,
        "target_faces": 5000000,
        "output_format": "obj",
    }
    task = submit(official, workflow, values)
    spec = AtlasSpec.model_validate(upload_body(HI3D_MASTER)["graph"]["execution"]["config"])
    reference = {"contentType": "image/png", "size": 20000000}
    assets = {"reference_image": reference, "view_2": reference}
    for invalid in ("1000", "10x0", "11"):
        with pytest.raises(RunError, match="multi_images_bit"):
            spec.assets_by_parameter({"multi_images_bit": invalid}, assets)
    assert spec.assets_by_parameter({}, assets) == {
        "image": [reference],
        "reference_images": [reference],
    }
    assert spec.prediction_timeout_seconds == 3900

    front_url, left_url = "https://cdn.example/front.png", "https://cdn.example/left.png"
    output, preview = "https://cdn.example/resource", "https://cdn.example/preview.png"

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            reference_url = front_url if front in request.content else left_url
            assert front in request.content or left in request.content
            return httpx.Response(200, json={"url": reference_url})
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": HI3D_MASTER,
                "image": front_url,
                "reference_images": [left_url],
                "multi_images_bit": "1010",
                "should_texture": False,
                "rmbg": True,
                "target_polycount": 5000000,
                "output_format": "obj",
            }
            return httpx.Response(200, json={"data": {"id": "prediction-hi3d"}})
        assert request.url.path.endswith("/prediction/prediction-hi3d")
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "outputs": [output, preview],
                    "files": [{"url": output, "type": "OBJ", "file_name": "mesh"}],
                }
            },
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200, content={output: OBJ_BYTES, preview: front}[str(request.url)]
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    result = {
        item["media"]["kind"]: item
        for item in official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()[
            "items"
        ]
    }
    assert result["3d"]["filename"] == "mesh.obj"
    assert official.get(result["3d"]["media"]["src"]).content == OBJ_BYTES
    assert official.get(result["image"]["media"]["src"]).content == front


def test_seed_asr_accepts_audio_formats_and_checks_context(official):
    pcm = bytes(32000)
    raw_id = asset(official, pcm, filename="recording.raw")
    raw = official.get(f"/api/v1/assets/{raw_id}").raise_for_status().json()
    assert raw["contentType"] == "audio/x-pcm" and raw["media"]["kind"] == "audio"
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        ogg_audio = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-f",
                "wav",
                "-i",
                "pipe:0",
                "-c:a",
                "libopus",
                "-f",
                "ogg",
                "pipe:1",
            ],
            input=wav_bytes(),
            capture_output=True,
            check=True,
            timeout=10,
        ).stdout
        ogg_id = asset(official, ogg_audio, filename="recording.ogg")
        ogg = official.get(f"/api/v1/assets/{ogg_id}").raise_for_status().json()
        assert ogg["contentType"] == "audio/ogg" and ogg["media"]["kind"] == "audio"
    spec = AtlasSpec.model_validate(upload_body(SEED_ASR)["graph"]["execution"]["config"])
    assert spec.assets_by_parameter({"format": "raw"}, {"audio": raw}) == {"audio_url": [raw]}
    with pytest.raises(RunError, match="文件格式须与 mp3 一致"):
        spec.assets_by_parameter({"format": "mp3"}, {"audio": raw})
    with pytest.raises(RunError, match="JSON 对象"):
        spec.payload({"hotwords": "ComfyShop"})
    assert "context" not in spec.payload({"hotwords": ""})


def test_seed_asr_browser_reads_transcript_and_details_at_both_widths(settings):
    settings = settings.model_copy(
        update={
            "static_dir": Path(__file__).resolve().parents[2] / "web" / "dist",
            "worker_service_tokens": {"official": SecretStr(TOKEN)},
            "official_owner": OWNER,
        }
    )
    audio = wav_bytes()
    audio_url = "https://cdn.example/session.wav"
    transcript = "https://example.com/会话"
    details = {
        "text": transcript,
        "duration": 1.0,
        "words": [
            {"text": transcript, "start": 0.1, "end": 0.8, "type": "utterance", "speaker_id": "1"}
        ],
    }
    hotwords = json.dumps({"hotwords": [{"word": "ComfyShop"}]})

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert audio in request.content
            return httpx.Response(200, json={"url": audio_url})
        if request.method == "POST":
            assert request.url.path.endswith("/generateAudio")
            assert json.loads(request.content) == {
                "model": SEED_ASR,
                "audio_url": audio_url,
                "format": "wav",
                "language": "zh-CN",
                "enable_itn": True,
                "enable_punc": True,
                "enable_ddc": False,
                "enable_speaker_info": True,
                "show_utterances": True,
                "context": hotwords,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-asr"}})
        assert request.url.path.endswith("/prediction/prediction-asr")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": [transcript], "stt_result": details}},
        )

    with serve_test_app(settings) as (address, web):
        credentials = register(web, OWNER)
        workflow = upload(web, SEED_ASR)
        task = submit(
            web,
            workflow,
            {
                "audio": {"assetId": asset(web, audio, filename="recording.wav")},
                "format": "wav",
                "language": "zh-CN",
                "punctuation": True,
                "speaker_labels": True,
                "timestamps": True,
                "hotwords": hotwords,
            },
        )

        async def run():
            async with (
                Platform(address, TOKEN) as platform,
                httpx.AsyncClient(
                    base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
                ) as atlas,
                httpx.AsyncClient(
                    transport=httpx.MockTransport(
                        lambda _: pytest.fail("Transcript is inline text")
                    )
                ) as downloads,
            ):
                assert await Runner(platform, Atlas(atlas), downloads).run_once()

        asyncio.run(run())
        (execution,) = web.get("/api/v1/executions", params={"task_id": task["id"]}).json()["items"]
        assert execution["textCount"] == execution["artifactCount"] == 2
        assert execution["media"]["kind"] == "text"
        with sync_playwright() as playwright, playwright.chromium.launch() as chromium:
            for width, height in ((1440, 900), (390, 844)):
                page = chromium.new_page(
                    base_url=address, viewport={"width": width, "height": height}
                )
                assert page.request.post(
                    "/api/v1/auth/login", data=credentials, headers={"Origin": address}
                ).ok
                page.goto(f"/workspace/results?result={execution['id']}")
                dialog = page.get_by_role("dialog", name=workflow["name"])
                dialog.get_by_role("button", name="查看 result-1.txt").click()
                expect(dialog.get_by_text(transcript, exact=True)).to_be_visible()
                text_link = dialog.get_by_role("link", name="下载原文件", exact=True)
                assert (
                    page.request.get(text_link.get_attribute("href")).body() == transcript.encode()
                )
                dialog.get_by_role("button", name="返回成品列表").click()
                dialog.get_by_role("button", name="查看 result-2.json").click()
                expect(dialog.locator(".text-preview pre")).to_contain_text('"speaker_id": "1"')
                json_link = dialog.get_by_role("link", name="下载原文件", exact=True)
                assert page.request.get(json_link.get_attribute("href")).json() == details
                page.close()


def test_xai_stt_validates_key_terms_and_conditional_parameters():
    spec = AtlasSpec.model_validate(upload_body(XAI_STT)["graph"]["execution"]["config"])
    for inputs, required in (
        ({"normalize_numbers": True}, "language"),
        ({"audio_format": "alaw"}, "sample_rate"),
        ({"audio_format": "mulaw", "sample_rate": 8000, "multichannel": True}, "channels"),
    ):
        with pytest.raises(RunError, match=required):
            spec.payload(inputs)
    for terms in ("x" * 51, "\n".join(["term"] * 101)):
        with pytest.raises(RunError, match="每项最多 50"):
            spec.payload({"key_terms": terms})
    assert spec.payload({"key_terms": "  Atlas\n\nComfyShop "})["keyterm"] == ["Atlas", "ComfyShop"]


def test_xai_stt_browser_accepts_video_and_keeps_sync_channels(settings, small_mp4):
    settings = settings.model_copy(
        update={
            "static_dir": Path(__file__).resolve().parents[2] / "web" / "dist",
            "worker_service_tokens": {"official": SecretStr(TOKEN)},
            "official_owner": OWNER,
        }
    )
    video_url = "https://cdn.example/recording.mp4"
    details = {
        "channels": [{"index": 0, "text": "First speaker"}, {"index": 1, "text": "Second speaker"}]
    }

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert small_mp4 in request.content
            return httpx.Response(200, json={"url": video_url})
        assert request.method == "POST" and request.url.path.endswith("/generateAudio")
        assert json.loads(request.content) == {
            "model": XAI_STT,
            "audio": video_url,
            "audio_format": "auto",
            "language": "en",
            "text_normalization": True,
            "diarize": False,
            "filler_words": False,
            "multichannel": True,
            "enable_sync_mode": True,
            "keyterm": ["Atlas", "ComfyShop"],
        }
        return httpx.Response(
            200,
            json={"data": {"id": "prediction-xai", "status": "completed", "stt_result": details}},
        )

    with serve_test_app(settings) as (address, web):
        owner = register(web, OWNER)
        workflow = upload(web, XAI_STT)
        video_id = asset(web, small_mp4, filename="recording.mp4")
        task = submit(
            web,
            workflow,
            {
                "source_audio": {"assetId": video_id},
                "normalize_numbers": True,
                "language": "en",
                "key_terms": "Atlas\nComfyShop",
                "multichannel": True,
                "sync_mode": True,
            },
        )

        async def run():
            async with (
                Platform(address, TOKEN) as platform,
                httpx.AsyncClient(
                    base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
                ) as atlas,
                httpx.AsyncClient(
                    transport=httpx.MockTransport(lambda _: pytest.fail("Transcripts are inline"))
                ) as downloads,
            ):
                assert await Runner(platform, Atlas(atlas), downloads).run_once()

        asyncio.run(run())
        outputs = {
            item["filename"]: item["media"]["src"]
            for item in web.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
        }
        assert web.get(outputs["result-1.txt"]).text == "First speaker\n\nSecond speaker"
        assert web.get(outputs["result-2.json"]).json() == details
        with sync_playwright() as playwright, playwright.chromium.launch() as chromium:
            for width, height in ((1440, 900), (390, 844)):
                page = chromium.new_page(
                    base_url=address, viewport={"width": width, "height": height}
                )
                assert page.request.post(
                    "/api/v1/auth/login", data=owner, headers={"Origin": address}
                ).ok
                page.goto(f"/workflows/{workflow['id']}")
                form = page.locator("form.run-fields")
                source = form.locator("#input-source_audio")
                expect(source).to_have_attribute("accept", re.compile(r"audio/mpeg.*video/mp4"))
                with page.expect_response(
                    lambda response: (
                        "/api/v1/assets/" in response.url and response.request.method == "PUT"
                    )
                ) as uploaded:
                    source.set_input_files(
                        {"name": "recording.mp4", "mimeType": "video/mp4", "buffer": small_mp4}
                    )
                assert uploaded.value.ok and uploaded.value.json()["media"]["kind"] == "video"
                expect(form.get_by_text("recording.mp4", exact=True)).to_be_visible()
                page.close()


def test_seed_audio_constraints_and_exclusive_reference_sources():
    spec = AtlasSpec.model_validate(upload_body(SEED_AUDIO)["graph"]["execution"]["config"])
    binding = spec.reference_arrays["references"]
    with pytest.raises(RunError, match="3000"):
        spec.payload({"text": "字" * 3001})
    audio = {"contentType": "audio/wav", "size": 10000000, "media": {"durationMs": 30000}}
    assert binding.sources("references", {}, {"audio_1": audio})[0].key == "audio_url"
    with pytest.raises(RunError, match="30000"):
        binding.sources("references", {}, {"audio_1": audio | {"media": {"durationMs": 30001}}})
    with pytest.raises(RunError, match="只能选择一种"):
        binding.sources("references", {"speaker_1": "preset", "voice_id_1": "other"}, {})
    with pytest.raises(RunError, match="须单独使用"):
        binding.sources(
            "references",
            {"voice_id_2": "custom"},
            {"reference_image": {"contentType": "image/png", "size": 1}},
        )


@pytest.mark.parametrize("with_image", [False, True], ids=["voices-and-audio", "image"])
def test_seed_audio_maps_reference_objects_and_keeps_pcm(official, with_image):
    workflow = upload(official, SEED_AUDIO)
    png, wav = image_bytes("blue"), wav_bytes()
    speaker = "zh_female_vv_uranus_bigtts"
    prompt = "朗读一段文字" if with_image else "@Audio1 和 @Audio2 各说一句问候"
    values = {"text": prompt, "format": "pcm", "pitch": 2}
    if with_image:
        values["reference_image"] = {"assetId": asset(official, png)}
        references = [{"image_url": "https://cdn.example/reference.png"}]
    else:
        values |= {
            "speaker_1": speaker,
            "audio_2": {"assetId": asset(official, wav, filename="reference.wav")},
            "inline_2": True,
            "voice_id_3": "registered-voice",
        }
        references = [
            {"speaker": speaker},
            {"audio_data": base64.b64encode(wav).decode("ascii")},
            {"speaker": "registered-voice"},
        ]
    task = submit(official, workflow, values)
    pcm = bytes(32000)
    output = "https://cdn.example/result"

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert with_image and png in request.content
            return httpx.Response(200, json={"url": references[0]["image_url"]})
        if request.method == "POST":
            assert request.url.path.endswith("/generateAudio")
            assert json.loads(request.content) == {
                "model": SEED_AUDIO,
                "text": prompt,
                "format": "pcm",
                "sample_rate": 24000,
                "pitch_rate": 2,
                "speech_rate": 0,
                "loudness_rate": 0,
                "references": references,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-seed-audio"}})
        assert request.url.path.endswith("/prediction/prediction-seed-audio")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [output]}})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=pcm))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["contentType"] == "audio/x-pcm" and artifact["filename"] == "result-1.pcm"
    assert artifact["media"]["kind"] == "audio"
    assert official.get(artifact["media"]["src"]).content == pcm


def test_minimax_music_30_checks_generation_mode():
    spec = AtlasSpec.model_validate(upload_body(MINIMAX_MUSIC_30)["graph"]["execution"]["config"])
    for values, name in (
        ({"prompt": "warm piano", "lyrics": "  "}, "lyrics"),
        ({"instrumental": True, "prompt": ""}, "prompt"),
        ({"automatic_lyrics": True, "prompt": "\n"}, "prompt"),
    ):
        with pytest.raises(RunError, match=name):
            spec.payload(values)
    for parameter, values, limit in (
        ("prompt", {"instrumental": True, "prompt": "x" * 2001}, 2000),
        ("lyrics", {"lyrics": "x" * 3501}, 3500),
    ):
        with pytest.raises(RunError, match=f"{parameter} 最多 {limit}"):
            spec.payload(values)
    request = spec.payload({"automatic_lyrics": True, "prompt": "warm piano", "lyrics": "Text"})
    with pytest.raises(RunError, match="lyrics 和 lyrics_optimizer"):
        spec.assets_by_parameter(request, {})


def test_midjourney_saves_all_base64_videos(official, small_mp4):
    model = "midjourney/v8.2/image-to-video"
    image = "https://cdn.example/first.png"
    prompt = "慢慢拉近镜头"
    task = submit(
        official,
        upload(official, model),
        {
            "first_frame_source": image,
            "prompt": prompt,
            "resolution": "720p",
            "motion": "high",
            "enable_base64_output": True,
        },
    )
    encoded = base64.b64encode(small_mp4).decode("ascii")

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": model,
                "image": image,
                "prompt": prompt,
                "resolution": "720p",
                "motion": "high",
                "enable_base64_output": True,
            }
            return httpx.Response(200, json={"data": {"id": "midjourney-prediction"}})
        assert request.url.path.endswith("/prediction/midjourney-prediction")
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "outputs": [encoded, f"data:video/mp4;base64,{encoded}"] * 2,
                }
            },
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: pytest.fail("Expected inline video"))
            ) as transport,
        ):
            assert await Runner(platform, Atlas(atlas), transport).run_once()

    asyncio.run(run())
    artifacts = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert {item["filename"] for item in artifacts} == {
        f"result-{index}.mp4" for index in range(1, 5)
    }
    for item in artifacts:
        assert item["contentType"] == "video/mp4" and item["media"]["kind"] == "video"
        assert official.get(item["media"]["video"]).content == small_mp4


def test_ltx_quality_uploads_avif_with_original_dimensions(official):
    model = "ltx-2.3-quality/image-to-video"
    image = image_bytes("blue", (96, 64), format="AVIF")
    response = (
        official.put(
            f"/api/v1/assets/{uuid4()}",
            params={"filename": "first.avif"},
            content=image,
            headers={"Content-Type": "application/octet-stream"},
        )
        .raise_for_status()
        .json()
    )
    assert response["contentType"] == "image/avif"
    assert (response["media"]["width"], response["media"]["height"]) == (96, 64)
    task = submit(
        official,
        upload(official, model),
        {"prompt": "镜头缓慢推进", "first_frame": {"assetId": response["id"]}},
    )
    assert task["inputValues"]["first_frame"]["assetId"] == response["id"]


def test_pixverse_reference_values_remain_with_their_images(official, small_mp4):
    model = "pixverse/v6/reference-to-video"
    workflow = upload(official, model)
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    binding = spec.reference_arrays["images"]
    assert isinstance(binding, ImageReferenceObjects)
    first = "https://cdn.example/scene.png"
    second = "https://cdn.example/upload.png"
    third = base64.b64encode(image_bytes("red", (300, 300))).decode("ascii")
    uploaded = image_bytes("blue", (300, 300))
    with pytest.raises(RunError, match="至少需要一张参考图"):
        binding.sources("images", {}, {})
    with pytest.raises(RunError, match="引用名最多 30 字节"):
        binding.sources(
            "images", {"reference_image_1_source": first, "reference_name_1": "景" * 11}, {}
        )
    values = {
        "prompt": "让 @人物 在 @场景 中慢慢转身",
        "reference_image_1_source": first,
        "reference_type_1": "background",
        "reference_name_1": "场景",
        "reference_image_2": {"assetId": asset(official, uploaded)},
        "reference_type_2": "subject",
        "reference_name_2": "人物",
        "reference_image_3_source": third,
    }
    task = submit(official, workflow, values)
    output = "https://cdn.example/output.mp4"

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert uploaded in request.content
            return httpx.Response(200, json={"data": {"url": second}})
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": model,
                "prompt": values["prompt"],
                "duration": 5,
                "aspect_ratio": "16:9",
                "quality": "720p",
                "sound": True,
                "images": [
                    {"image": first, "type": "background", "ref_name": "场景"},
                    {"image": second, "type": "subject", "ref_name": "人物"},
                    {"image": third},
                ],
            }
            return httpx.Response(200, json={"data": {"id": "pixverse-refs"}})
        assert request.url.path.endswith("/result/pixverse-refs")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [output]}})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=small_mp4))
            ) as transport,
        ):
            assert await Runner(platform, Atlas(atlas), transport).run_once()

    asyncio.run(run())
    (video,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert official.get(video["media"]["video"]).content == small_mp4


@pytest.mark.parametrize(("audio_format", "sync_mode"), [("wav", False), ("pcm", True)])
def test_minimax_music_30_returns_original_base64_audio(official, audio_format, sync_mode):
    workflow = upload(official, MINIMAX_MUSIC_30)
    prompt = "吉他和木管的短曲"
    task = submit(
        official,
        workflow,
        {
            "prompt": prompt,
            "lyrics": "暂存歌词",
            "instrumental": True,
            "automatic_lyrics": True,
            "format": audio_format,
            "sync_mode": sync_mode,
            "base64_output": True,
        },
    )
    wav = audio_format == "wav"
    audio = wav_bytes() if wav else bytes(32000)
    mime = "audio/wav" if wav else "audio/x-pcm"
    encoded = base64.b64encode(audio).decode("ascii")
    result = {
        "status": "completed",
        "outputs": [encoded if wav else f"data:audio/pcm;base64,{encoded}"],
    }

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateAudio")
            assert json.loads(request.content) == {
                "model": MINIMAX_MUSIC_30,
                "prompt": prompt,
                "is_instrumental": True,
                "format": audio_format,
                "sample_rate": 44100,
                "enable_sync_mode": sync_mode,
                "enable_base64_output": True,
            }
            data = {"id": "prediction-minimax-music"}
            return httpx.Response(200, json={"data": data | (result if sync_mode else {})})
        assert not sync_mode and request.url.path.endswith("/prediction/prediction-minimax-music")
        return httpx.Response(200, json={"data": result})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: pytest.fail("Expected inline audio"))
            ) as transport,
        ):
            assert await Runner(platform, Atlas(atlas), transport).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["filename"] == f"result-1.{audio_format}"
    assert artifact["contentType"] == mime and artifact["media"]["kind"] == "audio"
    assert official.get(artifact["media"]["src"]).content == audio


def test_minimax_lyrics_allows_empty_theme_and_preserves_structure(official):
    spec = AtlasSpec.model_validate(upload_body(MINIMAX_LYRICS)["graph"]["execution"]["config"])
    new_song = spec.payload({"mode": "write_full_song", "prompt": "", "lyrics": "旧歌词"})
    assert new_song["prompt"] == "" and "lyrics" not in new_song
    with pytest.raises(RunError, match="lyrics"):
        spec.payload({"mode": "edit", "prompt": "改写结尾", "lyrics": " "})

    workflow = upload(official, MINIMAX_LYRICS)
    previous = "[Verse]\n月光照在海堤上"
    title = "回家的路"
    task = submit(
        official,
        workflow,
        {
            "mode": "edit",
            "prompt": "增加副歌",
            "lyrics": previous,
            "title": title,
            "sync_mode": True,
        },
    )
    lyrics = previous + "\n[Chorus]\n灯火引我们回到岸边"
    details = {"lyrics": lyrics, "song_title": title, "style_tags": ["Folk", "Acoustic"]}

    def provider(request):
        assert request.method == "POST" and request.url.path.endswith("/generateAudio")
        assert json.loads(request.content) == {
            "model": MINIMAX_LYRICS,
            "mode": "edit",
            "prompt": "增加副歌",
            "lyrics": previous,
            "title": title,
            "enable_sync_mode": True,
        }
        data = {"id": "prediction-minimax-lyrics", "status": "completed", "lyrics_result": details}
        return httpx.Response(200, json={"data": data})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: pytest.fail("Lyrics are inline"))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    result = {
        item["filename"]: item
        for item in official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()[
            "items"
        ]
    }
    assert {item["media"]["kind"] for item in result.values()} == {"text"}
    assert official.get(result["result-1.txt"]["media"]["src"]).content == lyrics.encode("utf-8")
    assert official.get(result["result-2.json"]["media"]["src"]).json() == details


def test_elevenlabs_music_plan_validates_modes_and_structure():
    spec = AtlasSpec.model_validate(upload_body(ELEVENLABS_MUSIC)["graph"]["execution"]["config"])
    with pytest.raises(RunError, match="请填写音乐描述或分段方案"):
        spec.payload({"prompt": " "})
    assert spec.payload({"prompt": "Gentle jazz"})["prompt"] == "Gentle jazz"
    chunk = {"text": "[Intro]", "duration_ms": 3001, "positive_styles": ["jazz"]}
    values = {"composition_plan": json.dumps({"chunks": [chunk]}), "duration": 4}
    with pytest.raises(RunError, match="清空音乐描述"):
        spec.payload(values | {"prompt": "Jazz"})
    with pytest.raises(RunError, match="关闭纯音乐"):
        spec.payload(values | {"instrumental": True})
    with pytest.raises(RunError, match="4 秒"):
        spec.payload(values | {"duration": 3})
    for invalid in (
        chunk | {"text": "x" * 201},
        chunk | {"text": "\n".join(["line"] * 31)},
        chunk | {"positive_styles": []},
        chunk | {"context_adherence": "other"},
    ):
        with pytest.raises(RunError, match="分段方案"):
            spec.payload(values | {"composition_plan": json.dumps({"chunks": [invalid]})})


@pytest.fixture
def small_mp3():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg is needed for the MP3 fixture")
    return subprocess.run(
        [ffmpeg, "-v", "error", "-i", "pipe:0", "-f", "mp3", "pipe:1"],
        input=wav_bytes(),
        capture_output=True,
        check=True,
        timeout=10,
    ).stdout


def test_elevenlabs_music_accepts_full_length_plan_and_returns_mp3(official, small_mp3):
    workflow = upload(official, ELEVENLABS_MUSIC)
    chunk = {
        "text": "\n".join(["字" * 200] * 30),
        "duration_ms": 3000,
        "positive_styles": ["lo-fi jazz"],
        "negative_styles": ["distorted guitar"],
        "context_adherence": "medium",
    }
    plan = {"chunks": [chunk] * 29 + [chunk | {"duration_ms": 3001}]}
    serialized = json.dumps(plan, ensure_ascii=False)
    assert len(serialized) > 65536
    task = submit(
        official, workflow, {"prompt": "", "duration": 91, "composition_plan": serialized}
    )
    url = "https://cdn.example/track.mp3"

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateAudio")
            assert json.loads(request.content) == {
                "model": ELEVENLABS_MUSIC,
                "duration": 91,
                "composition_plan": plan,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-music-plan"}})
        assert request.url.path.endswith("/prediction/prediction-music-plan")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [url]}})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=small_mp3))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["contentType"] == "audio/mpeg"
    assert official.get(artifact["media"]["src"]).content == small_mp3


def test_elevenlabs_detailed_keeps_metadata_files_and_reuses_the_plan(official, small_mp3):
    workflow = upload(official, ELEVENLABS_DETAILED)
    prompt = "轻柔民谣，木吉他和人声"
    task = submit(official, workflow, {"prompt": prompt, "timestamps": True})
    plan = {"chunks": [{"text": "[Intro]", "duration_ms": 30000, "positive_styles": ["folk"]}]}
    metadata = {
        "song_metadata": {"title": "夜色", "genres": ["folk"], "languages": ["zh"]},
        "composition_plan": plan,
        "words_timestamps": [{"word": "夜色", "start": 1.5, "end": 2.0}],
    }
    original = json.dumps(metadata, ensure_ascii=False).encode()
    audio_url, metadata_url = "https://cdn.example/song.mp3", "https://cdn.example/file"

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateAudio")
            assert json.loads(request.content) == {
                "model": ELEVENLABS_DETAILED,
                "prompt": prompt,
                "duration": 30,
                "force_instrumental": False,
                "with_timestamps": True,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-eleven-details"}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "outputs": [audio_url],
                    "files": [
                        {"url": audio_url, "type": "AUDIO", "file_name": "song.mp3"},
                        {"url": metadata_url, "type": "METADATA", "file_name": "exports/song-info"},
                    ],
                }
            },
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200,
                        content={audio_url: small_mp3, metadata_url: original}[str(request.url)],
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    result = {
        item["filename"]: item
        for item in official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()[
            "items"
        ]
    }
    assert set(result) == {"song.mp3", "song-info.json"}
    assert result["song.mp3"]["media"]["kind"] == "audio"
    details = result["song-info.json"]
    assert details["contentType"] == "application/json" and details["media"]["kind"] == "text"
    response = official.get(details["media"]["src"]).raise_for_status()
    assert response.content == original
    spec = AtlasSpec.model_validate(upload_body(ELEVENLABS_MUSIC)["graph"]["execution"]["config"])
    values = {
        "prompt": "",
        "duration": 30,
        "composition_plan": json.dumps(response.json()["composition_plan"]),
    }
    assert spec.payload(values)["composition_plan"] == plan


def test_elevenlabs_tts_v3_uses_voice_id_and_enforces_language_constraint(official):
    workflow = upload(official, ELEVENLABS_TTS_V3)
    spec = AtlasSpec.model_validate(upload_body(ELEVENLABS_TTS_V3)["graph"]["execution"]["config"])
    voice = "IKne3meq5aSn9XLyUdCD"
    values = {"text": "欢迎收听今晚的故事", "voice": voice}
    task = submit(official, workflow, values | {"language": "zh"})
    assert spec.payload(task["inputValues"]) == {
        "model": ELEVENLABS_TTS_V3,
        "text": values["text"],
        "voice": voice,
        "language_code": "zh",
        "stability": 0.5,
        "apply_text_normalization": "auto",
    }
    assert "language_code" not in spec.payload(values | {"language": " "})
    with pytest.raises(RunError, match="language_code 为 zh"):
        spec.payload(values | {"language": "ja"})
    submit(official, workflow, values | {"text": "字" * 5001}, expected_status=422)


def test_elevenlabs_tts_v3_browser_shows_localized_voice_choices(settings):
    settings = settings.model_copy(
        update={
            "static_dir": Path(__file__).resolve().parents[2] / "web" / "dist",
            "worker_service_tokens": {"official": SecretStr(TOKEN)},
            "official_owner": OWNER,
        }
    )
    with (
        serve_test_app(settings) as (address, web),
        sync_playwright() as playwright,
        playwright.chromium.launch() as chromium,
    ):
        owner = register(web, OWNER)
        workflow = upload(web, ELEVENLABS_TTS_V3)
        for width, height in ((1440, 900), (390, 844)):
            page = chromium.new_page(base_url=address, viewport={"width": width, "height": height})
            assert page.request.post(
                "/api/v1/auth/login", data=owner, headers={"Origin": address}
            ).ok
            page.goto(f"/workflows/{workflow['id']}")
            voice = page.locator("form.run-fields").get_by_role("combobox", name="音色", exact=True)
            expect(voice).to_contain_text("Bella · 英语（美国）")
            voice.click()
            page.get_by_role("option", name="Charlie · 中文", exact=True).click()
            expect(voice).to_contain_text("Charlie · 中文")
            page.close()


def test_elevenlabs_tts_v4_checks_dialogue_limits():
    spec = AtlasSpec.model_validate(upload_body(ELEVENLABS_TTS_V4)["graph"]["execution"]["config"])
    assert spec.payload({"text": "Hello", "dialogue": "[]"})["text"] == "Hello"
    with pytest.raises(RunError, match="朗读文本或对话"):
        spec.payload({"text": " ", "dialogue": "[]"})
    with pytest.raises(RunError, match="JSON 数组"):
        spec.payload({"dialogue": json.dumps([{"voice": "Roger"}])})
    with pytest.raises(RunError, match="10 种音色"):
        spec.payload(
            {"dialogue": json.dumps([{"text": "Hello", "voice": f"voice-{i}"} for i in range(11)])}
        )
    with pytest.raises(RunError, match="10000"):
        spec.payload({"dialogue": json.dumps([{"text": "字" * 10001}])})


def test_elevenlabs_tts_v4_maps_dialogue_and_keeps_raw_audio(official):
    workflow = upload(official, ELEVENLABS_TTS_V4)
    turns = [{"text": "[whispers] 欢迎来到录音室。"}, {"text": "午安。", "voice": "Bella"}]
    voice_id = "existing-voice-id"
    task = submit(
        official,
        workflow,
        {
            "custom_voice": voice_id,
            "dialogue": json.dumps(turns, ensure_ascii=False),
            "format": "ulaw_8000",
            "seed": 4294967295,
        },
    )
    recording = b"\xff" * 8000
    url = "https://cdn.example/audio"

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateAudio")
            assert json.loads(request.content) == {
                "model": ELEVENLABS_TTS_V4,
                "voice": voice_id,
                "output_format": "ulaw_8000",
                "stability": 0.5,
                "similarity_boost": 0.75,
                "apply_text_normalization": "auto",
                "seed": 4294967295,
                "inputs": turns,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-eleven-v4"}})
        assert request.url.path.endswith("/prediction/prediction-eleven-v4")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [url]}})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=recording))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["filename"] == "result-1.ulaw"
    assert artifact["contentType"] == "audio/x-mulaw" and artifact["media"]["kind"] == "audio"
    assert official.get(artifact["media"]["src"]).content == recording


def test_xai_tts_applies_voice_language_and_saves_alaw(official):
    workflow = upload(official, XAI_TTS)
    text = "开始。[pause] <whisper>再轻一点。</whisper>"
    values = {"text": text, "voice_id": "jpi39icg", "codec": "alaw", "sample_rate": 8000}
    task = submit(official, workflow, values)
    submit(official, workflow, values | {"text": "字" * 15001}, expected_status=422)
    spec = AtlasSpec.model_validate(upload_body(XAI_TTS)["graph"]["execution"]["config"])
    with pytest.raises(RunError, match="language 为 zh"):
        spec.payload(values | {"language": "en"})
    assert spec.payload({"text": text, "voice_id": "eve", "language": "auto"})["language"] == "auto"
    recording = b"\xd5" * 8000
    asset(official, recording, "shared-original.pcm")
    url = "https://cdn.example/spoken"

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateAudio")
            assert json.loads(request.content) == {
                "model": XAI_TTS,
                "text": text,
                "voice_id": "jpi39icg",
                "language": "zh",
                "codec": "alaw",
                "sample_rate": 8000,
                "speed": 1,
                "text_normalization": False,
                "optimize_streaming_latency": 0,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-xai-tts"}})
        assert request.url.path.endswith("/prediction/prediction-xai-tts")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [url]}})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=recording))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (artifact,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert artifact["filename"] == "result-1.alaw"
    assert artifact["contentType"] == "audio/x-alaw" and artifact["media"]["kind"] == "audio"
    original = official.get(artifact["media"]["src"]).raise_for_status()
    assert original.content == recording and original.headers["content-type"] == "audio/x-alaw"


def test_qwen_tts_maps_optional_language_hint_and_opus_bitrate():
    model = "alibaba/qwen-audio-3.1-tts-plus/text-to-speech"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    fields = {"text": "今天有风。", "voice": "longanhuan_v3.1", "seed": -1, "bit_rate": 64}
    assert spec.payload(fields | {"output_format": "opus", "language_hint": "zh"}) == {
        "model": model,
        "text": "今天有风。",
        "voice": "longanhuan_v3.1",
        "seed": -1,
        "output_format": "opus",
        "bit_rate": 64,
        "language_hints": ["zh"],
    }
    payload = spec.payload(fields | {"output_format": "mp3", "language_hint": ""})
    assert "language_hints" not in payload and "bit_rate" not in payload


def test_qwen_tts_flash_can_use_a_supported_voice_id():
    model = "alibaba/qwen-audio-3.1-tts-flash/text-to-speech"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"text": "侬好。", "voice": "longanlingxin_v3.1", "instruction": "请讲上海话。"}
    assert spec.payload(values | {"custom_voice": "  "})["voice"] == "longanlingxin_v3.1"
    assert spec.payload(values | {"custom_voice": " saved-voice-id "}) == {
        "model": model,
        "text": "侬好。",
        "voice": "saved-voice-id",
        "instruction": "请讲上海话。",
    }


def test_kling_custom_voice_checks_source_and_sample_duration(official, small_mp4):
    spec = AtlasSpec.model_validate(upload_body(KLING_CUSTOM_VOICE)["graph"]["execution"]["config"])
    payload = spec.payload({"voice_name": "旁白", "video_id": " "})
    assert "video_id" not in payload
    with pytest.raises(RunError, match="必须选择一项"):
        spec.assets_by_parameter(payload, {})

    clip_id = asset(official, small_mp4, "speech.mp4")
    clip = official.get(f"/api/v1/assets/{clip_id}").raise_for_status().json()
    assert clip["media"]["durationMs"] == 200
    with pytest.raises(RunError, match="至少 5000"):
        spec.assets_by_parameter(payload, {"audio": clip})

    recording = {"size": 1024, "contentType": "audio/wav", "media": {"durationMs": 30000}}
    assert spec.assets_by_parameter(payload, {"audio": recording}) == {"audio": [recording]}
    with pytest.raises(RunError, match="最长 30000"):
        spec.assets_by_parameter(payload, {"audio": recording | {"media": {"durationMs": 30001}}})
    with pytest.raises(RunError, match="必须选择一项"):
        spec.assets_by_parameter(payload | {"video_id": "provider-video-id"}, {"audio": recording})


@pytest.mark.parametrize("via_video_id", [False, True], ids=["sample", "video_id"])
def test_kling_custom_voice_saves_audio_and_precise_voice_id(official, via_video_id):
    workflow = upload(official, KLING_CUSTOM_VOICE)
    audio = wav_bytes(seconds=6)
    sample_url = "https://cdn.example/sample.wav"
    trial_url = "https://cdn.example/trial.wav"
    voice = {
        "voice_id": "098765432109876543",
        "voice_name": "旁白",
        "trial_url": trial_url,
        "owned_by": "provider-user",
    }
    route = {"video_id": "provider-video-id"} if via_video_id else {"audio": sample_url}
    source = route if via_video_id else {"audio": {"assetId": asset(official, audio, "sample.wav")}}
    task = submit(official, workflow, {"voice_name": "旁白", **source})

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert not via_video_id and audio in request.content
            return httpx.Response(200, json={"url": sample_url})
        if request.method == "POST":
            assert request.url.path.endswith("/generateAudio")
            assert json.loads(request.content) == {
                "model": KLING_CUSTOM_VOICE,
                "voice_name": "旁白",
                **route,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-custom-voice"}})
        assert request.url.path.endswith("/prediction/prediction-custom-voice")
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "voice_result": voice,
                    "outputs": [] if via_video_id else [trial_url],
                }
            },
        )

    def download(request):
        assert str(request.url) == trial_url
        return httpx.Response(200, content=audio, headers={"Content-Type": "audio/wav"})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    items = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    audition, identifier, metadata = sorted(items, key=lambda item: item["outputIndex"])
    assert [item["media"]["kind"] for item in (audition, identifier, metadata)] == [
        "audio",
        "text",
        "text",
    ]
    assert official.get(audition["media"]["src"]).content == audio
    assert official.get(identifier["media"]["src"]).text == voice["voice_id"] + "\n"
    assert official.get(metadata["media"]["src"]).json() == voice


def test_suno_v6_maps_parameters_for_each_mode():
    spec = AtlasSpec.model_validate(upload_body(SUNO_V6)["graph"]["execution"]["config"])
    values = {"prompt": "  ", "custom": False, "instrumental": True}
    with pytest.raises(RunError, match="prompt"):
        spec.payload(values)
    with pytest.raises(RunError, match="prompt"):
        spec.payload(values | {"custom": True, "instrumental": False})
    assert spec.payload(
        values
        | {
            "prompt": "短笛与海浪声",
            "instrumental": False,
            "title": "忽略的曲名",
            "style": "忽略的风格",
            "duration": 90,
            "auto_lyrics": True,
            "variety": "high",
            "vocal_gender": "Female",
        }
    ) == {
        "model": SUNO_V6,
        "prompt": "短笛与海浪声",
        "custom": False,
        "instrumental": False,
        "variety": "high",
        "vocal_gender": "Female",
    }


def test_suno_v6_saves_both_tracks_and_generated_art(official, small_mp3):
    workflow = upload(official, SUNO_V6)
    settings = {
        "prompt": " ",
        "custom": True,
        "instrumental": True,
        "title": "晨雨",
        "style": "爵士钢琴",
        "duration": 60,
        "variety": "normal",
    }
    task = submit(official, workflow, settings)
    submit(official, workflow, settings | {"prompt": "字" * 3001}, expected_status=422)
    tracks = ["https://cdn.example/song-a.mp3", "https://cdn.example/song-b.mp3"]
    cover = "https://cdn.example/artwork.png"
    png = image_bytes("blue")

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateAudio")
            assert json.loads(request.content) == {
                "model": SUNO_V6,
                **{name: value for name, value in settings.items() if name != "prompt"},
                "auto_lyrics": False,
            }
            return httpx.Response(200, json={"data": {"id": "prediction-suno"}})
        assert request.url.path.endswith("/prediction/prediction-suno")
        return httpx.Response(
            200, json={"data": {"status": "completed", "outputs": tracks, "thumbnail": cover}}
        )

    def download(request):
        if str(request.url) == cover:
            return httpx.Response(200, content=png, headers={"Content-Type": "image/png"})
        assert str(request.url) in tracks
        return httpx.Response(200, content=small_mp3, headers={"Content-Type": "audio/mpeg"})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    items = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    first, second, artwork = sorted(items, key=lambda item: item["outputIndex"])
    assert [a["media"]["kind"] for a in (first, second, artwork)] == ["audio", "audio", "image"]
    assert official.get(first["media"]["src"]).content == small_mp3
    assert official.get(second["media"]["src"]).content == small_mp3
    assert official.get(f"/api/v1/artifacts/{artwork['id']}/file").content == png


def test_tencent_upscaler_keeps_only_applicable_settings():
    spec = AtlasSpec.model_validate(
        upload_body(TENCENT_IMAGE_UPSCALER)["graph"]["execution"]["config"]
    )
    payload = spec.payload(
        {
            "mode": "percent",
            "percent": 2.5,
            "width": 1280,
            "height": 720,
            "encode_format": "JPEG",
            "encode_quality": 78,
            "output_dir": " ",
        }
    )
    assert payload == {
        "model": TENCENT_IMAGE_UPSCALER,
        "mode": "percent",
        "percent": 2.5,
        "encode_format": "JPEG",
        "encode_quality": 78,
    }
    with pytest.raises(RunError, match="percent"):
        spec.payload({"mode": "percent"})


@pytest.mark.parametrize(("mode", "fallback"), [("aspect", False), ("fixed", True)])
def test_tencent_upscaler_polls_model_endpoint_and_saves_bmp(official, mode, fallback):
    workflow = upload(official, TENCENT_IMAGE_UPSCALER)
    original = image_bytes("red")
    bmp = image_bytes("red", size=(80, 60), format="BMP")
    source_url = "https://cdn.example/source.png"
    output_url = "https://cdn.example/enhanced.bmp"
    values = {
        "mode": mode,
        "long_side": 80,
        "short_side": 60,
        "type": "fidelity",
        "encode_format": "BMP",
        "output_dir": "exports/images",
    }
    task = submit(official, workflow, values | {"image": {"assetId": asset(official, original)}})
    queries = []

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert original in request.content
            return httpx.Response(200, json={"url": source_url})
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": TENCENT_IMAGE_UPSCALER,
                **values,
                "image_url": source_url,
            }
            return httpx.Response(200, json={"data": {"id": "tencent-upscale"}})
        path = request.url.path.rsplit("/", 2)[-2:]
        queries.append(path[0])
        assert path[1] == "tencent-upscale"
        if fallback and path[0] == "result":
            return httpx.Response(404)
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [output_url]}})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=bmp, headers={"Content-Type": "image/bmp"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    assert queries == (["result", "prediction"] if fallback else ["result"])
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert item["contentType"] == "image/bmp" and item["filename"] == "result-1.bmp"
    assert official.get(f"/api/v1/artifacts/{item['id']}/file").content == bmp


@pytest.mark.parametrize(
    ("template", "minimum", "maximum"),
    [
        ("restore-720p", 1, 720),
        ("anime-enhance-1080p", 721, 1080),
        ("live-action-smallface-2k", 1081, 1440),
        ("seedance2-enhance-4k", 1441, 2160),
    ],
)
def test_tencent_video_checks_short_edge_for_template(template, minimum, maximum):
    model = "tencent/video/upscaler"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    for short in (0, minimum, maximum):
        assert spec.payload({"template": template, "short": short})["short"] == short
    for short in (minimum - 1 if minimum > 1 else -1, maximum + 1):
        with pytest.raises(RunError, match="short 必须在"):
            spec.payload({"template": template, "short": short})


def test_seedream_v4_accepts_custom_dimensions_with_documented_side_limits():
    spec = AtlasSpec.model_validate(
        upload_body("bytedance/seedream-v4")["graph"]["execution"]["config"]
    )
    for size in ("1024*4096", "4096*1024", "3072*2816"):
        assert spec.payload({"prompt": "森林光影", "size": size})["size"] == size
    for size in ("1023*2048", "2048*4097"):
        with pytest.raises(RunError, match="每边 1024–4096"):
            spec.payload({"prompt": "森林光影", "size": size})
    for size in ("auto", "4096x4096", "2048 * 2048"):
        with pytest.raises(RunError, match="宽\\*高"):
            spec.payload({"prompt": "森林光影", "size": size})


def test_seedream_lite_sequential_edit_checks_combined_count_for_external_references():
    model = "bytedance/seedream-v5.0-lite/edit-sequential"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"prompt": "制作同一构图的系列插画", "max_images": 15}
    references = [
        "https://cdn.example/reference.tiff",
        "data:image/png;base64," + base64.b64encode(image_bytes("blue")).decode("ascii"),
    ]
    assert spec.assets_by_parameter(spec.payload(values), {}) == {}
    values["reference_sources"] = "\n".join(references)
    with pytest.raises(RunError, match="素材和生成数量合计最多 15"):
        spec.assets_by_parameter(spec.payload(values), {})
    payload = spec.payload(values | {"max_images": 13})
    assert payload["images"] == references
    assert spec.assets_by_parameter(payload, {}) == {}
    with pytest.raises(RunError, match="素材和生成数量合计最多 15"):
        spec.assets_by_parameter(payload, {"reference_1": {"contentType": "image/png"}})


def test_seedream_pro_edit_checks_reference_count_format_and_alpha():
    graph = upload_body(SEEDREAM_50_PRO_EDIT)["graph"]
    spec = AtlasSpec.model_validate(graph["execution"]["config"])
    values = {"prompt": "重绘花瓶", "output_format": "png", "background": "transparent"}
    url = "https://cdn.example/reference.png"
    with pytest.raises(RunError, match="要求 output_format 为 png"):
        spec.payload(values | {"output_format": "jpeg"})
    with pytest.raises(RunError, match="需要 1 至 10 张"):
        spec.assets_by_parameter(spec.payload(values), {})
    with pytest.raises(RunError, match="一张带透明通道"):
        spec.assets_by_parameter(spec.payload(values | {"reference_sources": f"{url}\n{url}"}), {})
    rgb = base64.b64encode(image_bytes("blue")).decode("ascii")
    with pytest.raises(RunError, match="一张带透明通道"):
        spec.payload(values | {"reference_sources": "data:image/png;base64," + rgb})
    with pytest.raises(RunError, match="Base64 素材无效"):
        spec.payload(values | {"reference_sources": "data:image/png;base64,broken!"})
    payload = spec.payload(
        values | {"background": "opaque", "reference_sources": "\n".join([url] * 10)}
    )
    with pytest.raises(RunError, match="需要 1 至 10 张"):
        spec.assets_by_parameter(payload, {"reference_1": {"contentType": "image/png"}})


@pytest.mark.parametrize("kind", ["mixed", "transparent", "opaque_png"])
def test_seedream_pro_edit_submits_ordered_sources_and_checks_uploaded_alpha(
    official, worker_logs, kind
):
    workflow = upload(official, SEEDREAM_50_PRO_EDIT)
    sample = BytesIO()
    Image.new("RGBA" if kind == "transparent" else "RGB", (32, 32)).save(sample, format="PNG")
    source = sample.getvalue()
    upload_url = "https://cdn.example/uploaded.png"
    direct_urls = []
    if kind == "mixed":
        tiff = base64.b64encode(image_bytes("green", format="TIFF")).decode("ascii")
        direct_urls = ["https://cdn.example/alternate.heic", "data:image/tiff;base64," + tiff]
    background = "opaque" if kind == "mixed" else "transparent"
    task = submit(
        official,
        workflow,
        {
            "prompt": "重绘花瓶",
            "background": background,
            "output_format": "png",
            "reference_10": {"assetId": asset(official, source)},
            "reference_sources": "\n".join(direct_urls),
            "enable_base64_output": True,
        },
    )
    result = base64.b64encode(source).decode("ascii")

    def provider(request):
        assert kind != "opaque_png", "The source must be checked before calling Atlas"
        if request.url.path.endswith("/uploadMedia"):
            assert source in request.content
            return httpx.Response(200, json={"url": upload_url})
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": SEEDREAM_50_PRO_EDIT,
                "prompt": "重绘花瓶",
                "background": background,
                "output_format": "png",
                "size": "2048*2048",
                "thinking": "enabled",
                "prompt_optimization_mode": "standard",
                "enable_base64_output": True,
                "images": [upload_url, *direct_urls],
            }
            return httpx.Response(200, json={"data": {"id": "seedream-pro-edit"}})
        assert request.url.path.endswith("/prediction/seedream-pro-edit")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [result]}})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: pytest.fail("Image is inline"))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    items = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    if kind == "opaque_png":
        assert not items and any("带透明通道的 PNG" in line for line in worker_logs)
    else:
        (item,) = items
        assert official.get(f"/api/v1/artifacts/{item['id']}/file").content == source


def test_seedream_layer_decomposition_checks_image_dimensions_and_source():
    config = upload_body(SEEDREAM_50_PRO_LAYERS)["graph"]["execution"]["config"]
    spec = AtlasSpec.model_validate(config)
    payload = spec.payload({"prompt": "  ", "optimization": "fast"})
    assert payload == {"model": SEEDREAM_50_PRO_LAYERS, "optimize_prompt_options": {"mode": "fast"}}
    detached = spec.payload({"image_source": "https://cdn.example/reference.tiff"})
    assert detached["image"] == "https://cdn.example/reference.tiff"
    assert spec.assets_by_parameter(detached, {}) == {}
    valid = {"size": 1600, "contentType": "image/png", "media": {"width": 512, "height": 512}}
    assert spec.assets_by_parameter(payload, {"image": valid}) == {"image": [valid]}
    with pytest.raises(RunError, match="需要 1 张参考图"):
        spec.assets_by_parameter(detached, {"image": valid})
    for width, height in [(511, 512), (6000, 6001), (8192, 500)]:
        with pytest.raises(RunError, match="尺寸或宽高比"):
            spec.assets_by_parameter(
                payload, {"image": valid | {"media": {"width": width, "height": height}}}
            )


def test_seedream_layer_decomposition_keeps_images_and_aligned_metadata(official):
    workflow = upload(official, SEEDREAM_50_PRO_LAYERS)
    source = "https://cdn.example/poster.tiff"
    text = "拆出标题 <bbox>100 40 900 180</bbox>"
    values = {
        "image_source": source,
        "prompt": text,
        "size": "1K",
        "optimization": "fast",
        "enable_sync_mode": True,
        "enable_base64_output": True,
    }
    task = submit(official, workflow, values)
    base = image_bytes("white", format="JPEG")
    cutout = BytesIO()
    Image.new("RGBA", (16, 16), (10, 30, 50, 100)).save(cutout, format="PNG")
    pictures = [base, cutout.getvalue()]
    layers = [
        {"z_index": 0},
        {
            "z_index": 1,
            "name": "标题",
            "description": "海报的标题",
            "bounding_box": {"absolute": [1, 2, 17, 18], "normalized": [31, 62, 531, 562]},
        },
    ]

    def provider(request):
        assert request.method == "POST" and request.url.path.endswith("/generateImage")
        assert json.loads(request.content) == {
            "model": SEEDREAM_50_PRO_LAYERS,
            "image": source,
            "prompt": text,
            "size": "1K",
            "output_format": "jpeg",
            "optimize_prompt_options": {"mode": "fast"},
            "enable_sync_mode": True,
            "enable_base64_output": True,
        }
        return httpx.Response(
            200,
            json={
                "id": "seedream-layers",
                "status": "completed",
                "outputs": [base64.b64encode(item).decode("ascii") for item in pictures],
                "layers": layers,
            },
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: pytest.fail("Outputs are inline"))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    items = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    original, layer, metadata = sorted(items, key=lambda item: item["outputIndex"])
    assert [item["filename"] for item in (original, layer, metadata)] == [
        "result-1.jpg",
        "result-2.png",
        "result-3.json",
    ]
    assert [
        official.get(f"/api/v1/artifacts/{item['id']}/file").content for item in (original, layer)
    ] == pictures
    assert official.get(metadata["media"]["src"]).json() == {"layers": layers}


def test_seedream_55_keeps_transparent_png_and_reports_actual_background(official):
    model = "bytedance/seedream-v5.5/text-to-image"
    workflow = upload(official, model)
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {
        "prompt": "透明背景上的水彩树叶",
        "size": "1024*1024",
        "background": "transparent",
        "output_format": "png",
        "enable_sync_mode": True,
        "enable_base64_output": True,
    }
    with pytest.raises(RunError, match="要求 output_format 为 png"):
        spec.payload(values | {"output_format": "jpeg"})
    task = submit(official, workflow, values)
    image = BytesIO()
    Image.new("RGBA", (32, 32), (12, 43, 61, 128)).save(image, format="PNG")
    body = image.getvalue()
    image_results = [{"background": "transparent"}]

    def provider(request):
        assert request.method == "POST" and request.url.path.endswith("/generateImage")
        assert json.loads(request.content) == {"model": model, **values}
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "seedream-transparent",
                    "status": "completed",
                    "outputs": [base64.b64encode(body).decode("ascii")],
                    "image_results": image_results,
                }
            },
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: pytest.fail("Output is inline"))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    items = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    original, metadata = sorted(items, key=lambda item: item["outputIndex"])
    assert original["media"]["kind"] == "image" and metadata["media"]["kind"] == "text"
    assert official.get(f"/api/v1/artifacts/{original['id']}/file").content == body
    assert official.get(metadata["media"]["src"]).json() == {"image_results": image_results}


@pytest.mark.parametrize("output_format", ["gif", "svg"])
def test_sunburst_preserves_animation_or_vector_original(official, output_format):
    model = "openai/gpt-image-2.6-sunburst/text-to-image"
    workflow = upload(official, model)
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    vector = output_format == "svg"
    values = {
        "prompt": "围绕月亮飞行的纸鹤",
        "custom_size": "512x512",
        "output_format": output_format,
        "background": "transparent" if vector else "auto",
        "frame_count": 4,
        "frame_duration_ms": 123,
        "svg_model": "gpt-6-sol",
        "n": 1,
    }
    with pytest.raises(RunError, match="宽高须为 16"):
        spec.payload(values | {"custom_size": "496x501"})
    with pytest.raises(RunError, match="尺寸超出范围"):
        spec.payload(values | {"custom_size": "3840x3840"})
    with pytest.raises(RunError, match="要求 output_format 为"):
        spec.payload(values | {"background": "transparent", "output_format": "jpeg"})
    with pytest.raises(RunError, match="n 必须为 1"):
        spec.payload(values | {"output_format": "svg", "n": 2})
    assert "size" not in spec.payload(values | {"custom_size": " ", "size": ""})
    default_format = spec.payload(values | {"output_format": None})
    assert {"frame_count", "frame_duration_ms", "svg_model"}.isdisjoint(default_format)
    task = submit(official, workflow, values)
    expected = {
        "model": model,
        "prompt": values["prompt"],
        "size": "512x512",
        "quality": "medium",
        "complexity": "high",
        "background": values["background"],
        "output_format": output_format,
        "moderation": "auto",
        "n": 1,
    }
    if vector:
        expected["svg_model"] = values["svg_model"]
        original = (
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            b'<circle cx="16" cy="16" r="5"/></svg>'
        )
    else:
        expected.update(frame_count=4, frame_duration_ms=123)
        image = BytesIO()
        Image.new("RGB", (32, 32), "navy").save(
            image,
            format="GIF",
            save_all=True,
            append_images=[Image.new("RGB", (32, 32), "gold")],
            loop=0,
        )
        original = image.getvalue()

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == expected
            return httpx.Response(200, json={"data": {"id": "sunburst-prediction"}})
        assert request.url.path.endswith("/prediction/sunburst-prediction")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200,
                        content=original,
                        headers={
                            "Content-Type": "application/octet-stream" if vector else "image/gif"
                        },
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert item["filename"] == f"result-1.{output_format}"
    assert item["media"]["kind"] == ("text" if vector else "image")
    assert item["contentType"] == ("image/svg+xml" if vector else "image/gif")
    downloaded = official.get(item["media"]["src"]).raise_for_status()
    assert downloaded.content == original
    if vector:
        assert downloaded.headers["content-disposition"].startswith("attachment;")
        assert "sandbox" in downloaded.headers["content-security-policy"]
        assert downloaded.headers["x-content-type-options"] == "nosniff"
    else:
        with Image.open(BytesIO(downloaded.content)) as image:
            assert image.is_animated and image.n_frames == 2


def test_sunburst_edit_sends_ordered_sources_and_markup_for_gif(official):
    model = "openai/gpt-image-2.6-sunburst/edit"
    workflow = upload(official, model)
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    source = image_bytes("blue")
    marks = BytesIO()
    Image.new("RGBA", (32, 32), (255, 255, 0, 96)).save(marks, format="PNG")
    markup = marks.getvalue()
    stored_reference = "asset://example-reference"
    mask_source = "data:image/png;base64," + base64.b64encode(markup).decode("ascii")
    values = {"prompt": "让圈出的纸鹤飞起来", "output_format": "gif", "frame_count": 8}
    with pytest.raises(RunError, match="mask 不可与 gif"):
        spec.assets_by_parameter(
            spec.payload(
                values | {"reference_sources": stored_reference, "mask_source": mask_source}
            ),
            {},
        )
    with pytest.raises(RunError, match="mask 和 markup 请任选其一"):
        spec.assets_by_parameter(
            spec.payload(
                values
                | {
                    "output_format": "png",
                    "reference_sources": stored_reference,
                    "mask_source": mask_source,
                    "markup_source": "asset://example-markup",
                }
            ),
            {},
        )
    opaque = "data:image/png;base64," + base64.b64encode(source).decode("ascii")
    with pytest.raises(RunError, match="markup 需要一张带透明通道"):
        spec.payload(values | {"markup_source": opaque})
    with pytest.raises(RunError, match="需要图片地址"):
        spec.payload(values | {"reference_sources": "asset://example-reference/file"})

    task = submit(
        official,
        workflow,
        values
        | {
            "reference_3": {"assetId": asset(official, source)},
            "reference_sources": stored_reference,
            "markup": {"assetId": asset(official, markup)},
        },
    )
    file = image_bytes("blue", format="GIF")
    uploads = []

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            uploads.append(source if source in request.content else markup)
            assert uploads[-1] in request.content
            return httpx.Response(
                200, json={"url": f"https://cdn.example/input-{len(uploads)}.png"}
            )
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": model,
                **values,
                "images": ["https://cdn.example/input-1.png", stored_reference],
                "markup": "https://cdn.example/input-2.png",
                "background": "auto",
                "quality": "medium",
                "complexity": "high",
                "moderation": "auto",
                "n": 1,
                "frame_duration_ms": 200,
            }
            return httpx.Response(200, json={"data": {"id": "sunburst-edit"}})
        assert request.url.path.endswith("/prediction/sunburst-edit")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.gif"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=file, headers={"Content-Type": "image/gif"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    assert uploads == [source, markup]
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert item["contentType"] == "image/gif"
    assert official.get(item["media"]["src"]).content == file


def test_nano_banana_2_edit_accepts_public_image_urls():
    model = "google/nano-banana-2/edit"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    url = "https://cdn.example/reference.png"
    inputs = {"prompt": "重绘参考图", "reference_sources": url, "aspect_ratio": ""}
    payload = spec.payload(inputs)
    assert payload == {"model": model, "prompt": "重绘参考图", "images": [url]}
    assert spec.assets_by_parameter(payload, {}) == {}
    inline = "data:image/png;base64," + base64.b64encode(image_bytes("blue")).decode("ascii")
    with pytest.raises(RunError, match="图片地址"):
        spec.payload(inputs | {"reference_sources": inline})
    with pytest.raises(RunError, match="最多 14 张参考图"):
        spec.payload(inputs | {"reference_sources": "\n".join([url] * 15)})


def test_nano_banana_clip_validates_source_and_timing():
    model = "google/nano-banana-2.1/reference-to-image"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    bindings = spec.media["video_clips"]
    assert isinstance(bindings, MediaBinding) and bindings.video_clip
    with pytest.raises(RunError, match="需要 1 段参考视频"):
        spec.assets_by_parameter(spec.payload({"prompt": "制作封面"}), {})
    with pytest.raises(RunError, match=r"HTTP\(S\) 视频地址"):
        spec.payload({"prompt": "制作封面", "video_source": "file:///example.mp4"})
    clip = {"contentType": "video/mp4", "media": {"durationMs": 1_500_000}}
    values = {"prompt": "制作封面", "video_source": "https://example.com/clip.mp4"}
    with pytest.raises(RunError, match="需要 1 段参考视频"):
        spec.assets_by_parameter(spec.payload(values), {"video": clip})
    with pytest.raises(RunError, match="1500000"):
        spec.assets_by_parameter(
            spec.payload({"prompt": "制作封面"}),
            {"video": clip | {"media": {"durationMs": 1_500_001}}},
        )
    assert bindings.video_clip.settings({}) == {"start": 0, "ends": 0, "fps": 1}
    assert bindings.video_clip.settings({"video_start": 2.5, "video_fps": 0}) == {
        "start": 2.5,
        "ends": 0,
        "fps": 0,
    }
    for invalid in ({"video_start": 1, "video_end": 0.5}, {"video_fps": 24.5}):
        with pytest.raises(RunError, match="起止秒数和采样帧率"):
            bindings.video_clip.settings(invalid)


@pytest.mark.parametrize("use_upload", [False, True], ids=["url", "upload"])
def test_nano_banana_reference_builds_video_clip_objects(official, small_mp4, use_upload):
    model = "google/nano-banana-2.1/reference-to-image"
    workflow = upload(official, model)
    video_url = "https://cdn.example/clip.mp4"
    source_url = "https://www.youtube.com/watch?v=sample"
    image_url = "https://cdn.example/reference.png"
    values = {
        "prompt": "为短片生成一张封面",
        "video_start": 0.125,
        "video_end": 0.75,
        "video_fps": 2.5,
    }
    source = (
        {"video": {"assetId": asset(official, small_mp4, "source.mp4")}}
        if use_upload
        else {"video_source": source_url}
    )
    task = submit(official, workflow, values | source | {"reference_sources": image_url})
    body = image_bytes("teal")

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert use_upload and small_mp4 in request.content
            return httpx.Response(200, json={"url": video_url})
        if request.method == "POST":
            assert request.url.path.endswith("/generateImage")
            assert json.loads(request.content) == {
                "model": model,
                "prompt": values["prompt"],
                "video_clips": [
                    {
                        "url": video_url if use_upload else source_url,
                        "start": 0.125,
                        "ends": 0.75,
                        "fps": 2.5,
                    }
                ],
                "reference_images": [image_url],
                "aspect_ratio": "auto",
                "resolution": "1k",
                "thinking_level": "default",
                "enable_web_search": False,
                "enable_image_search": False,
                "media_resolution": "default",
                "top_p": 0.95,
                "temperature": 1,
                "seed": -1,
                "enable_sync_mode": False,
                "enable_base64_output": False,
            }
            return httpx.Response(200, json={"data": {"id": "nano-banana-video"}})
        assert request.url.path.endswith("/prediction/nano-banana-video")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.png"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=body, headers={"Content-Type": "image/png"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert item["media"]["kind"] == "image"
    assert official.get(item["media"]["src"]).content == body


def test_gemini_omni_requires_an_image_or_a_short_video_reference():
    model = "google/gemini-omni-1.1-flash/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    inputs = {"prompt": "按参考素材生成视频"}
    with pytest.raises(RunError, match="至少需要一项"):
        spec.assets_by_parameter(spec.payload(inputs), {})

    for sources in (
        {"reference_image_sources": "https://cdn.example/reference.webp"},
        {"reference_video_sources": "https://cdn.example/reference.mp4"},
    ):
        payload = spec.payload(inputs | sources)
        assert spec.assets_by_parameter(payload, {}) == {}

    with pytest.raises(RunError, match="3000"):
        spec.assets_by_parameter(
            spec.payload(inputs),
            {"reference_video_1": {"contentType": "video/mp4", "media": {"durationMs": 3001}}},
        )


def test_gemini_omni_sends_both_reference_lists(official, small_mp4):
    model = "google/gemini-omni-1.1-flash/reference-to-video"
    workflow = upload(official, model)
    prompt = "在 <IMAGE_REF_0> 的场景里复现 <VIDEO_REF_0> 的镜头"
    image_url = "https://cdn.example/reference.webp"
    video_url = "https://cdn.example/uploaded.mp4"
    second_video = "https://cdn.example/reference.mp4"
    task = submit(
        official,
        workflow,
        {
            "prompt": prompt,
            "duration": 4,
            "reference_image_sources": image_url,
            "reference_video_1": {"assetId": asset(official, small_mp4, "source.mp4")},
            "reference_video_sources": second_video,
        },
    )

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert small_mp4 in request.content
            return httpx.Response(200, json={"url": video_url})
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": model,
                "prompt": prompt,
                "duration": 4,
                "aspect_ratio": "16:9",
                "resolution": "720p",
                "thinking_level": "default",
                "seed": -1,
                "reference_images": [image_url],
                "reference_videos": [video_url, second_video],
            }
            return httpx.Response(200, json={"data": {"id": "omni-reference"}})
        assert request.url.path.endswith("/prediction/omni-reference")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.mp4"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=small_mp4, headers={"Content-Type": "video/mp4"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert item["media"]["kind"] == "video"
    assert official.get(item["media"]["video"]).content == small_mp4


def test_gemini_omni_limits_duration_when_a_last_frame_is_provided():
    model = "google/gemini-omni-1.2-flash/image-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    inputs = {"prompt": "让镜头缓慢升起", "first_frame_source": "https://cdn.example/start.png"}
    assert spec.assets_by_parameter(spec.payload(inputs | {"duration": 15}), {}) == {}

    last_frame = {"contentType": "image/png", "size": 128}
    upload = {"last_frame": last_frame}
    assert spec.assets_by_parameter(spec.payload(inputs | {"duration": 10}), upload) == {
        "last_image": [last_frame]
    }
    with pytest.raises(RunError, match="duration 最大为 10"):
        spec.assets_by_parameter(spec.payload(inputs | {"duration": 11}), upload)

    with_urls = inputs | {"last_frame_source": "https://cdn.example/end.png"}
    assert spec.assets_by_parameter(spec.payload(with_urls | {"duration": 10}), {}) == {}
    with pytest.raises(RunError, match="duration 最大为 10"):
        spec.assets_by_parameter(spec.payload(with_urls | {"duration": 11}), {})


def test_gemini_omni_counts_all_reference_clips_for_the_duration_limit():
    model = "google/gemini-omni-1.2-flash/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    inputs = {
        "prompt": "沿用参考视频的镜头",
        "reference_video_sources": "https://cdn.example/clip-one.mp4",
        "duration": 11,
    }
    assert spec.assets_by_parameter(spec.payload(inputs), {}) == {}
    uploaded = {"reference_video_1": {"contentType": "video/mp4", "media": {"durationMs": 3000}}}
    assert spec.assets_by_parameter(spec.payload(inputs | {"duration": 10}), uploaded) == {
        "reference_videos": list(uploaded.values())
    }
    with pytest.raises(RunError, match="duration 最大为 10"):
        spec.assets_by_parameter(spec.payload(inputs), uploaded)
    with pytest.raises(RunError, match="duration 最大为 10"):
        spec.assets_by_parameter(
            spec.payload(
                inputs
                | {
                    "reference_video_sources": inputs["reference_video_sources"]
                    + "\nhttps://cdn.example/clip-two.mp4"
                }
            ),
            {},
        )


def test_gemini_omni_developer_clip_settings_follow_the_integer_window():
    model = "google/gemini-omni-flash/reference-to-video-developer"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    binding = spec.media["video_clips"]
    assert isinstance(binding, MediaBinding) and binding.video_clip
    assert binding.video_clip.settings({}) == {"start": 0, "ends": 10}
    assert binding.video_clip.settings({"video_start": 20, "video_end": 30}) == {
        "start": 20,
        "ends": 30,
    }
    for invalid in (
        {"video_start": 19, "video_end": 30},
        {"video_start": 30, "video_end": 31},
        {"video_start": 10, "video_end": 10},
        {"video_start": 0.5, "video_end": 10},
    ):
        with pytest.raises(RunError, match="剪辑片段最长 10 秒"):
            binding.video_clip.settings(invalid)


def test_gemini_omni_developer_sends_only_documented_clip_fields(official, small_mp4):
    model = "google/gemini-omni-flash/reference-to-video-developer"
    workflow = upload(official, model)
    video_url = "https://cdn.example/source.mp4"
    prompt = "保留原片的镜头移动"
    task = submit(
        official,
        workflow,
        {"prompt": prompt, "video_source": video_url, "video_start": 20, "video_end": 30},
    )

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": model,
                "prompt": prompt,
                "duration": 8,
                "aspect_ratio": "16:9",
                "resolution": "720p",
                "seed": -1,
                "video_clips": [{"url": video_url, "start": 20, "ends": 30}],
            }
            return httpx.Response(200, json={"data": {"id": "omni-developer"}})
        assert request.url.path.endswith("/prediction/omni-developer")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.mp4"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=small_mp4, headers={"Content-Type": "video/mp4"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert item["media"]["kind"] == "video"
    assert official.get(item["media"]["video"]).content == small_mp4


def test_veo_lite_imports_numeric_choices_and_limits_1080p_to_eight_seconds():
    model = "google/veo3.1-lite/text-to-video"
    graph = upload_body(model)["graph"]
    assert next(field for field in graph["fields"] if field["name"] == "duration")["choices"] == [
        4,
        6,
        8,
    ]
    spec = AtlasSpec.model_validate(graph["execution"]["config"])
    values = {"prompt": "用广角拍摄山间列车", "duration": 4}
    assert spec.payload(values | {"resolution": "720p"})["duration"] == 4
    assert spec.payload(values | {"resolution": "1080p", "duration": 8})["duration"] == 8
    with pytest.raises(RunError, match="duration 必须为 8"):
        spec.payload(values | {"resolution": "1080p"})


def test_veo_lite_accepts_raw_base64_and_data_urls_for_the_opening_image():
    model = "google/veo3.1-lite/image-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    png = base64.b64encode(image_bytes("blue")).decode("ascii")
    values = {"prompt": "让盆栽随风摆动", "resolution": "1080p", "duration": 8}
    for source in (png, f"data:image/png;base64,{png}", "https://cdn.example/opening.jpg"):
        payload = spec.payload(values | {"first_frame_source": source})
        assert payload["image"] == source
        assert spec.assets_by_parameter(payload, {}) == {}

    with pytest.raises(RunError, match="Base64 图片格式不受支持"):
        spec.payload(values | {"first_frame_source": base64.b64encode(b"plain text").decode()})
    with pytest.raises(RunError, match="8000000 字节"):
        spec.assets_by_parameter(
            spec.payload(values),
            {"first_frame": {"contentType": "image/png", "size": 8_000_001}},
        )


def test_wan_prime_rejects_png_alpha_channels_before_atlas_upload(official):
    model = "alibaba/wan-3.0-prime/image-to-video"
    workflow = upload(official, model)
    image = BytesIO()
    Image.new("RGBA", (240, 240), (20, 40, 80, 255)).save(image, format="PNG")
    task = submit(
        official,
        workflow,
        {
            "prompt": "让纸船向前漂",
            "first_frame": {"assetId": asset(official, image.getvalue(), "alpha.png")},
        },
    )

    def unexpected_request(request):
        raise AssertionError(f"Invalid PNG reached Atlas via {request.url.path}")

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(unexpected_request)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(unexpected_request)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    progress = official.get(f"/api/v1/tasks/{task['id']}/progress").raise_for_status().json()
    assert progress["error"] == "上传的 PNG 不得包含透明通道"


def test_wan_prime_reference_validates_combined_counts_durations_and_document_inputs():
    model = "alibaba/wan-3.0-prime/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"prompt": "按参考资料生成视频"}
    video = {
        "contentType": "video/mp4",
        "size": 10_000,
        "media": {"durationMs": 7500, "width": 240, "height": 240},
    }
    assert spec.assets_by_parameter(
        spec.payload(values), {"reference_video_1": video, "reference_video_2": video}
    ) == {"refers": [video, video]}
    long = video | {"media": video["media"] | {"durationMs": 7501}}
    with pytest.raises(RunError, match="video 素材合计最长 15000"):
        spec.assets_by_parameter(
            spec.payload(values), {"reference_video_1": video, "reference_video_2": long}
        )
    links = "\n".join(f"https://cdn.example/source-{index}.mp4" for index in range(5))
    with pytest.raises(RunError, match="video 素材最多 5 份"):
        spec.assets_by_parameter(
            spec.payload(values | {"reference_video_sources": links}), {"reference_video_1": video}
        )
    document = {"file": " https://cdn.example/storyboard.pdf "}
    assert spec.payload(values | document)["file"] == document["file"].strip()
    assert "file" not in spec.payload(values | document | {"enable_thinking": False})
    with pytest.raises(RunError, match="需要公开的 HTTP"):
        spec.payload(values | {"file": "file:///storyboard.pdf"})
    with pytest.raises(RunError, match="file 和 link 请任选其一"):
        spec.assets_by_parameter(
            spec.payload(values | document | {"link": "https://cdn.example/storyboard"}), {}
        )


def test_wan_prime_reference_submits_uploaded_and_remote_media_together(official, small_mp4):
    model = "alibaba/wan-3.0-prime/reference-to-video"
    workflow = upload(official, model)
    image = image_bytes("blue", size=(240, 240))
    audio = wav_bytes(seconds=3)
    image_url = "https://cdn.example/uploaded.png"
    audio_url = "https://cdn.example/uploaded.wav"
    video_url = "https://cdn.example/camera.mov"
    document_url = "https://cdn.example/storyboard.pdf"
    prompt = "结合参考图、镜头和音频节奏"
    task = submit(
        official,
        workflow,
        {
            "prompt": prompt,
            "reference_image_1": {"assetId": asset(official, image)},
            "reference_audio_1": {"assetId": asset(official, audio, "beat.wav")},
            "reference_video_sources": video_url,
            "file": document_url,
        },
    )

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert image in request.content or audio in request.content
            return httpx.Response(
                200, json={"url": image_url if image in request.content else audio_url}
            )
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": model,
                "prompt": prompt,
                "resolution": "1080p",
                "duration": 5,
                "ratio": "adaptive",
                "audio": True,
                "enable_thinking": True,
                "file": document_url,
                "refers": [
                    {"url": image_url, "type": "image"},
                    {"url": audio_url, "type": "audio"},
                    {"url": video_url, "type": "video"},
                ],
            }
            return httpx.Response(200, json={"data": {"id": "wan-prime-reference"}})
        assert request.url.path.endswith("/prediction/wan-prime-reference")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.mp4"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=small_mp4, headers={"Content-Type": "video/mp4"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert item["media"]["kind"] == "video"
    assert official.get(item["media"]["video"]).content == small_mp4


def test_wan_27_uses_an_uploaded_soundtrack_as_a_url(official, small_mp4):
    model = "alibaba/wan-2.7/text-to-video"
    workflow = upload(official, model)
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    sound = wav_bytes(seconds=2)
    url = "https://cdn.example/sound.wav"
    values = {"prompt": "镜头沿海岸线移动", "resolution": "1440P-SR"}
    assert spec.payload(values | {"soundtrack_source": url})["audio"] == url
    with pytest.raises(RunError, match="音频地址"):
        spec.payload(values | {"soundtrack_source": "file:///sound.wav"})
    with pytest.raises(RunError, match="至少 2000 毫秒"):
        spec.assets_by_parameter(
            spec.payload(values),
            {
                "soundtrack": {
                    "contentType": "audio/wav",
                    "size": len(sound),
                    "media": {"durationMs": 1999},
                }
            },
        )
    task = submit(
        official,
        workflow,
        values | {"soundtrack": {"assetId": asset(official, sound, "sound.wav")}},
    )

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert sound in request.content
            return httpx.Response(200, json={"url": url})
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": model,
                **values,
                "ratio": "16:9",
                "duration": 5,
                "prompt_extend": True,
                "seed": -1,
                "audio": url,
            }
            return httpx.Response(200, json={"data": {"id": "wan-soundtrack"}})
        assert request.url.path.endswith("/prediction/wan-soundtrack")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.mp4"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=small_mp4, headers={"Content-Type": "video/mp4"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert official.get(item["media"]["video"]).content == small_mp4


def test_wan_27_counts_reference_images_and_videos_together():
    model = "alibaba/wan-2.7/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    image = {
        "contentType": "image/png",
        "size": 1000,
        "media": {"width": 240, "height": 240},
    }
    values = {
        "prompt": "character1 转向 character2",
        "reference_video_sources": "https://cdn.example/reference.mov",
        "reference_image_sources": "\n".join(
            f"https://cdn.example/subject-{index}.png" for index in range(3)
        ),
    }
    bound = {"reference_image_1": image}
    payload = spec.payload(values)
    assert spec.assets_by_parameter(payload, bound) == {"images": [image]}
    assert len(payload["images"]) == 3 and len(payload["videos"]) == 1

    two_uploads = bound | {"reference_image_2": image}
    with pytest.raises(RunError, match="images 和 videos 合计最多 5 份"):
        spec.assets_by_parameter(payload, two_uploads)


def test_wan_27_checks_custom_size_and_color_palette():
    model = "alibaba/wan-2.7/text-to-image"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"prompt": "雨后海湾", "size": "2K"}
    assert spec.payload(values | {"color_palette": " "})["size"] == "2K"
    assert "color_palette" not in spec.payload(values | {"color_palette": " "})
    assert spec.payload(values | {"custom_size": "2688*1536"})["size"] == "2688*1536"
    with pytest.raises(RunError, match="图片尺寸超出范围"):
        spec.payload(values | {"custom_size": "4096*4096"})
    with pytest.raises(RunError, match="3 至 10"):
        spec.payload(values | {"color_palette": '[{"hex":"#244764","ratio":"100.00%"}]'})
    too_low = [
        {"hex": "#244764", "ratio": "50.00%"},
        {"hex": "#80999F", "ratio": "30.00%"},
        {"hex": "#EADBC4", "ratio": "19.99%"},
    ]
    with pytest.raises(RunError, match="100.00%"):
        spec.payload(values | {"color_palette": json.dumps(too_low)})
    too_low[2]["hex"] = "#GADBC4"
    with pytest.raises(RunError, match="HEX"):
        spec.payload(values | {"color_palette": json.dumps(too_low)})


def test_wan_27_sends_palette_as_an_array_and_keeps_multiple_images(official):
    model = "alibaba/wan-2.7/text-to-image"
    workflow = upload(official, model)
    colors = [
        {"hex": "#244764", "ratio": "50.00%"},
        {"hex": "#80999F", "ratio": "30.00%"},
        {"hex": "#EADBC4", "ratio": "20.00%"},
    ]
    prompt = "使用调色板绘制雨后海湾"
    task = submit(
        official,
        workflow,
        {
            "prompt": prompt,
            "custom_size": "2688*1536",
            "color_palette": json.dumps(colors),
            "n": 2,
            "enable_sync_mode": True,
            "enable_base64_output": True,
        },
    )
    images = [image_bytes("blue"), image_bytes("teal")]

    def provider(request):
        assert request.method == "POST" and request.url.path.endswith("/generateImage")
        assert json.loads(request.content) == {
            "model": model,
            "prompt": prompt,
            "size": "2688*1536",
            "n": 2,
            "color_palette": colors,
            "thinking_mode": True,
            "seed": -1,
            "enable_sync_mode": True,
            "enable_base64_output": True,
        }
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "wan-palette",
                    "status": "completed",
                    "outputs": [base64.b64encode(image).decode("ascii") for image in images],
                }
            },
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: pytest.fail("Outputs are inline"))
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    items = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    result = sorted(items, key=lambda item: item["outputIndex"])
    assert [
        official.get(f"/api/v1/artifacts/{item['id']}/file").content for item in result
    ] == images


def test_wan_26_flash_requires_prompt_expansion_for_multiple_shots():
    model = "alibaba/wan-2.6/image-to-video-flash"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {
        "prompt": "从侧面拍摄街灯",
        "first_frame_source": "https://cdn.example/street.webp",
        "shot_type": "multi",
        "resolution": "720p",
    }
    with pytest.raises(RunError, match="要求开启 enable_prompt_expansion"):
        spec.payload(values | {"enable_prompt_expansion": False})
    with pytest.raises(RunError, match="要求开启 enable_prompt_expansion"):
        spec.payload(values)
    assert spec.payload(values | {"enable_prompt_expansion": True})["shot_type"] == "multi"
    single = spec.payload(values | {"shot_type": "single", "enable_prompt_expansion": False})
    assert single["enable_prompt_expansion"] is False


def test_wan_infinite_lora_sends_three_arrays_with_independent_weights():
    model = "atlascloud/wan-2.2-turbo/infinite-image-to-video-lora"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"prompt": "First scene\nSecond scene", "loras": '[{"provider_setting": 1}]'}
    high = [{"path": "https://cdn.example/high.safetensors", "scale": 0.75}]
    low = [{"path": "owner/wan-low-noise"}]
    payload = spec.payload(
        values | {"high_noise_loras": json.dumps(high), "low_noise_loras": json.dumps(low)}
    )
    assert payload["high_noise_loras"] == high
    assert payload["low_noise_loras"] == low
    assert payload["loras"] == [{"provider_setting": 1}]
    assert "loras" not in spec.payload(values | {"loras": " "})
    for invalid in ("{}", '[{"scale": 1}]', '[{"path": " "}]', '[{"path": "x", "scale": "1"}]'):
        with pytest.raises(RunError, match="high_noise_loras 需要 JSON 数组"):
            spec.payload(values | {"high_noise_loras": invalid})
    with pytest.raises(RunError, match="loras 需要 JSON 数组"):
        spec.payload(values | {"loras": "[1e999]"})


@pytest.mark.parametrize("name", ["high_noise_loras", "low_noise_loras", "loras"])
def test_wan_22_lora_checks_group_count_and_scale(name):
    model = "atlascloud/wan-2.2/image-to-video-lora"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    weights = [
        {"path": f"owner/wan-weights-{index}", "scale": scale}
        for index, scale in enumerate((0, 1.5, 4))
    ]
    values = {"prompt": "A close shot of a bicycle"}
    assert spec.payload(values | {name: json.dumps(weights)})[name] == weights
    with pytest.raises(RunError, match=f"{name} 最多 3 项"):
        spec.payload(values | {name: json.dumps(weights * 2)})
    with pytest.raises(RunError, match=f"{name} 的 scale 需要在 0 至 4 之间"):
        spec.payload(values | {name: '[{"path": "owner/wan-weights", "scale": 4.1}]'})


def test_studio_listing_requires_a_product_source_and_joins_selected_types():
    model = "atlascloud/studio/listing-image-set"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    choices = {"main_image": True, "detail_shot": True, "size_specs": True}
    with pytest.raises(RunError, match="visual_type 至少选择 1 个选项"):
        spec.payload({})
    payload = spec.payload(choices)
    assert payload["visual_type"] == "Main Image, Detail Shot, Size & Specs"
    with pytest.raises(RunError, match="link 和 product_image 至少需要一项"):
        spec.assets_by_parameter(payload, {})
    for sources in (
        {"link": "https://example.com/shop/product"},
        {"product_source": "https://example.com/product.png"},
        {
            "link": "https://example.com/shop/product",
            "product_source": "https://example.com/product.png",
        },
    ):
        assert not spec.assets_by_parameter(spec.payload(choices | sources), {})


def test_kling_o3_sends_ordered_storyboards_and_exact_subject_ids():
    model = "kwaivgi/kling-video-o3-4k/image-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    shots = [
        {"prompt": "Slow approach to <<<element_1>>>", "duration": 2},
        {"index": 2, "prompt": "Pan past the sculpture", "duration": 3},
    ]
    subjects = [
        {"element_id": 2**63 - 1},
        {
            "element_name": "Sculpture",
            "element_description": "A dark gray shape",
            "frontal_image": "https://cdn.example/front.png",
            "refer_images": ["https://cdn.example/side.png"],
        },
        {
            "element_name": "Bicycle",
            "reference_type": "video_refer",
            "refer_videos": ["https://cdn.example/bicycle.mp4"],
        },
    ]
    values = {
        "first_frame_source": "https://cdn.example/start.png",
        "last_frame_source": "https://cdn.example/end.png",
        "multi_shot": True,
        "multi_prompt": json.dumps(shots),
        "duration": 5,
        "prompt": "Automatic scene directions",
        "elements": json.dumps(subjects),
    }
    payload = spec.payload(values)
    assert payload["image"] == values["first_frame_source"]
    assert payload["end_image"] == values["last_frame_source"]
    assert payload["multi_prompt"] == shots and "prompt" not in payload
    assert payload["elements"] == subjects
    for switch in ({"multi_shot": False}, {"multi_prompt": "[]"}):
        automatic = spec.payload(values | switch)
        assert automatic["prompt"] == values["prompt"] and "multi_prompt" not in automatic
    with pytest.raises(RunError, match="请填写提示词"):
        spec.payload(values | {"multi_prompt": "", "prompt": ""})
    with pytest.raises(RunError, match="分镜时长之和"):
        spec.payload(values | {"duration": 6})
    with pytest.raises(RunError, match="multi_prompt 无效"):
        spec.payload(values | {"multi_prompt": json.dumps([{"prompt": "x" * 513, "duration": 5}])})
    with pytest.raises(RunError, match="主体引用最多 3 项"):
        spec.payload(values | {"elements": json.dumps([*subjects, subjects[0]])})
    with pytest.raises(RunError, match="elements 无效"):
        spec.payload(values | {"elements": '[{"element_id": 1, "element_name": "Also new"}]'})


def test_kling_o3_text_checks_limits_for_mixed_subject_types():
    model = "kwaivgi/kling-video-o3-4k/text-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    images = [
        {
            "element_name": f"Object {index}",
            "frontal_image": f"https://cdn.example/{index}-front.png",
            "refer_images": [f"https://cdn.example/{index}-side.png"],
        }
        for index in range(6)
    ]
    videos = [
        {
            "element_name": f"Motion {index}",
            "reference_type": "video_refer",
            "refer_videos": [f"https://cdn.example/{index}.mp4"],
        }
        for index in range(4)
    ]
    for subjects in (images, images[:3] + videos[:3], images[:5] + [{"element_id": 123}]):
        assert (
            spec.payload({"prompt": "A wide shot", "elements": json.dumps(subjects)})["elements"]
            == subjects
        )
    with pytest.raises(RunError, match="视频主体最多 3 项"):
        spec.payload({"prompt": "A wide shot", "elements": json.dumps(videos)})
    with pytest.raises(RunError, match="最多提供 4 项图片主体"):
        spec.payload({"prompt": "A wide shot", "elements": json.dumps(images[:5] + videos[:1])})


def test_kling_standard_indexes_shots_and_sends_durations_as_strings():
    model = "kwaivgi/kling-v3.0-std/image-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {
        "multi_shot": True,
        "multi_prompt": '[{"index": 8, "prompt": "Approach", "duration": 2},'
        '{"prompt": "Pan to the side", "duration": "3"}]',
        "duration": 5,
    }
    assert spec.payload(values)["multi_prompt"] == [
        {"index": 1, "prompt": "Approach", "duration": "2"},
        {"index": 2, "prompt": "Pan to the side", "duration": "3"},
    ]
    subject = {
        "element_name": "Vase",
        "frontal_image": "https://cdn.example/front.png",
        "refer_images": ["https://cdn.example/side.png"],
    }
    with pytest.raises(RunError, match="新建主体需要填写 reference_type"):
        spec.payload(values | {"elements": json.dumps([subject])})
    assert spec.payload(values | {"elements": '[{"element_id": 123}]'})["elements"] == [
        {"element_id": 123}
    ]


@pytest.mark.parametrize(("orientation", "limit"), [("image", 10_000), ("video", 30_000)])
def test_kling_motion_reference_duration_uses_orientation(orientation, limit):
    model = "kwaivgi/kling-v2.6-pro/motion-control"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    payload = spec.payload(
        {
            "appearance_source": "https://cdn.example/character.png",
            "character_orientation": orientation,
            "keep_original_audio": False,
        }
    )
    assert payload["keep_original_audio"] is False
    metadata = {"width": 960, "height": 540, "durationMs": limit}
    reference = {"size": 1000, "contentType": "video/mp4", "media": metadata}
    assert spec.assets_by_parameter(payload, {"motion": reference})["video"] == [reference]
    metadata["durationMs"] = limit + 1
    with pytest.raises(RunError, match=f"video 每段素材最长 {limit}"):
        spec.assets_by_parameter(payload, {"motion": reference})


def test_kling_video_edit_checks_directional_aspect_ratio_and_preserves_voice_ids():
    model = "kwaivgi/kling-video-o3-pro/video-edit"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    voice_id = "123456789012345678"
    payload = spec.payload(
        {"prompt": "Change the background", "voice_ids": f"{voice_id}\n  preset-a "}
    )
    assert payload["voice_ids"] == [voice_id, "preset-a"]
    with pytest.raises(RunError, match="voice_ids 最多 3 项"):
        spec.payload({"prompt": "Change the background", "voice_ids": "a\nb\nc\nd"})
    for width, height in ((700, 1750), (1440, 720)):
        reference = {
            "size": 1000,
            "contentType": "video/mp4",
            "media": {"width": width, "height": height, "durationMs": 15500},
        }
        assert spec.assets_by_parameter(payload, {"source_video": reference})["video"] == [
            reference
        ]
    for width, height in ((700, 1751), (1441, 720), (4000, 3000)):
        reference = {
            "size": 1000,
            "contentType": "video/mp4",
            "media": {"width": width, "height": height, "durationMs": 15500},
        }
        with pytest.raises(RunError, match="视频画面尺寸或宽高比超出范围"):
            spec.assets_by_parameter(payload, {"source_video": reference})


def test_kling_o3_reference_combines_uploads_urls_and_subjects():
    model = "kwaivgi/kling-video-o3-pro/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    urls = [f"https://cdn.example/reference-{index}.jpg" for index in range(7)]
    image = {
        "reference_2": {
            "size": 100,
            "contentType": "image/jpeg",
            "media": {"width": 640, "height": 640},
        }
    }
    image_subject = {
        "element_name": "Vase",
        "reference_type": "image_refer",
        "frontal_image": urls[0],
        "refer_images": urls[1:4],
    }
    video_subject = {
        "element_name": "Motion",
        "reference_type": "video_refer",
        "refer_videos": ["https://cdn.example/motion.mp4"],
    }
    inputs = {"prompt": "Follow the camera", "sound": True}
    reference = {"video_source": "https://cdn.example/reference.mp4"}
    payload = spec.payload(inputs | {"reference_sources": "\n".join(urls)})
    assert not spec.assets_by_parameter(payload, {}) and payload["sound"] is True
    with pytest.raises(RunError, match="合计最多 7 项"):
        spec.assets_by_parameter(
            spec.payload(
                inputs
                | {
                    "reference_sources": "\n".join(urls[1:]),
                    "elements": json.dumps([image_subject]),
                }
            ),
            image,
        )
    with_ref = (
        inputs
        | reference
        | {
            "reference_sources": "\n".join(urls[:2]),
            "elements": json.dumps([image_subject]),
        }
    )
    payload = spec.payload(with_ref)
    assert spec.assets_by_parameter(payload, image)["images"] == [image["reference_2"]]
    assert "sound" not in payload
    with pytest.raises(RunError, match="合计最多 4 项"):
        spec.assets_by_parameter(
            spec.payload(with_ref | {"reference_sources": "\n".join(urls[:3])}), image
        )
    video_only = spec.payload(inputs | reference | {"elements": json.dumps([video_subject])})
    assert not spec.assets_by_parameter(video_only, {})
    with pytest.raises(RunError, match="单个视频主体需单独使用"):
        spec.assets_by_parameter(video_only, image)
    storyboard = '{"prompt": "Pan slowly", "duration": 5}'
    with pytest.raises(RunError, match="仅支持自动分镜"):
        spec.assets_by_parameter(
            spec.payload(
                inputs | reference | {"multi_shot": True, "multi_prompt": f"[{storyboard}]"}
            ),
            {},
        )
    with pytest.raises(RunError, match="每个主体最多 3 张"):
        spec.payload(
            inputs | {"elements": json.dumps([image_subject | {"refer_images": urls[:4]}])}
        )


def test_kling_long_image_requires_references_only_for_ecommerce():
    model = "kwaivgi/kling-image-v4.0/long-image"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"skill": "ecommerce", "prompt": "Create a product detail page", "length": "short"}
    payload = spec.payload(values)
    assert payload["length"] == "short"
    with pytest.raises(RunError, match="至少需要一份 reference_images 素材"):
        spec.assets_by_parameter(payload, {})
    reference = {
        "size": 1000,
        "contentType": "image/png",
        "media": {"width": 640, "height": 640},
    }
    assert spec.assets_by_parameter(payload, {"reference_1": reference})["reference_images"] == [
        reference
    ]
    direct = spec.payload(values | {"reference_sources": "https://cdn.example/product.png"})
    assert direct["reference_images"] == ["https://cdn.example/product.png"]
    assert not spec.assets_by_parameter(direct, {})
    webpage = spec.payload(values | {"skill": "webpage"})
    assert "length" not in webpage
    assert not spec.assets_by_parameter(webpage, {})


def test_kling_4_flash_edit_binds_voice_and_checks_combined_reference_limits():
    model = "kwaivgi/kling-v4.0-flash/video-edit"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    subject = {
        "element_name": "Narrator",
        "reference_type": "image_refer",
        "frontal_image": "https://cdn.example/narrator.png",
        "element_voice_id": "123456789012345678",
    }
    values = {
        "prompt": "Edit @video_1 with @element_1",
        "video_source": "https://cdn.example/source.mp4",
        "audio_mode": "original",
        "elements": json.dumps([subject]),
    }
    images = [f"https://cdn.example/image-{index}.jpg" for index in range(10)]
    videos = [f"https://cdn.example/video-{index}.mp4" for index in range(3)]
    values |= {"image_sources": "\n".join(images), "reference_video_sources": "\n".join(videos)}
    payload = spec.payload(values)
    assert payload["elements"] == [subject]
    assert payload["reference_images"] == images and payload["reference_videos"] == videos
    assert payload["audio_mode"] == "original"
    assert not spec.assets_by_parameter(payload, {})
    with pytest.raises(RunError, match="合计最多 15 项"):
        spec.assets_by_parameter(
            spec.payload(values | {"voice_ids": subject["element_voice_id"]}), {}
        )
    with pytest.raises(RunError, match="主体名称最多 20"):
        spec.payload(values | {"elements": json.dumps([subject | {"element_name": "x" * 21}])})
    video_subject = {
        "element_name": "Narrator",
        "reference_type": "video_refer",
        "refer_videos": ["https://cdn.example/person.mp4"],
        "element_voice_id": subject["element_voice_id"],
    }
    with pytest.raises(RunError, match="可填写 element_voice_id"):
        spec.payload(values | {"elements": json.dumps([video_subject])})
    clip = {
        "size": 1000,
        "contentType": "video/mp4",
        "media": {"width": 1280, "height": 720, "durationMs": 10100},
    }
    with pytest.raises(RunError, match="素材合计最长 20000 毫秒"):
        spec.assets_by_parameter(
            spec.payload(values | {"reference_video_sources": ""}),
            {"reference_video_1": clip, "reference_video_2": clip},
        )


def test_kling_4_edit_requires_native_hdr_resolution_and_counts_the_source_duration():
    model = "kwaivgi/kling-v4.0/video-edit"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"prompt": "Make @video_1 warmer", "duration": "", "dynamic_range": "hdr"}
    for resolution in ("720p", "1080p-esr", "2k-esr", "4k-esr"):
        with pytest.raises(RunError, match="dynamic_range 要求 resolution"):
            spec.payload(values | {"resolution": resolution})
    for resolution in ("1080p", "4k"):
        payload = spec.payload(values | {"resolution": resolution})
        assert payload["dynamic_range"] == "hdr" and "duration" not in payload
    clip = {
        "size": 1000,
        "contentType": "video/mp4",
        "media": {"width": 1280, "height": 720, "durationMs": 15000},
    }
    assert spec.assets_by_parameter(payload, {"source_video": clip, "reference_video_1": clip}) == {
        "video": [clip],
        "reference_videos": [clip],
    }
    with pytest.raises(RunError, match="原视频与参考视频合计最长 30000"):
        spec.assets_by_parameter(
            payload, {"source_video": clip, "reference_video_1": clip, "reference_video_2": clip}
        )


def test_kling_4_reference_counts_keyframes_in_the_combined_image_limit():
    model = "kwaivgi/kling-v4.0/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    middle = [f"https://cdn.example/middle-{index}.jpg" for index in range(8)]
    values = {
        "prompt": "Connect @image_1 and @image_10 using the middle frames",
        "first_frame_source": "https://cdn.example/first.jpg",
        "middle_frame_sources": "\n".join(middle),
        "last_frame_source": "https://cdn.example/last.jpg",
    }
    payload = spec.payload(values)
    assert payload["image"] == values["first_frame_source"]
    assert payload["middle_images"] == middle
    assert payload["last_image"] == values["last_frame_source"]
    assert not spec.assets_by_parameter(payload, {})
    uploaded_frame = {"size": 1024, "contentType": "image/png"}
    payload = spec.payload(values | {"middle_frame_sources": "\n".join(middle[1:])})
    assert spec.assets_by_parameter(payload, {"middle_frame_1": uploaded_frame}) == {
        "middle_images": [uploaded_frame]
    }
    with pytest.raises(RunError, match="关键帧和参考图合计最多 10 张"):
        spec.assets_by_parameter(
            payload | {"reference_images": ["https://cdn.example/extra.jpg"]},
            {"middle_frame_1": uploaded_frame},
        )


def test_vidu_start_end_validates_individual_sources_and_pixel_count_ratio():
    model = "vidu/start-end-to-video-2.0"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"prompt": "Transition between the two frames"}
    first = {"size": 1000, "contentType": "image/png", "media": {"width": 256, "height": 256}}
    last = first | {"media": {"width": 320, "height": 256}}
    assert spec.assets_by_parameter(
        spec.payload(values), {"first_frame": first, "last_frame": last}
    ) == {"images": [first, last]}
    with pytest.raises(RunError, match="像素总数比须为 0.8 至 1.25"):
        spec.assets_by_parameter(
            spec.payload(values),
            {"first_frame": first, "last_frame": last | {"media": {"width": 321, "height": 256}}},
        )
    payload = spec.payload(values | {"first_frame_source": "https://cdn.example/opening.png"})
    with pytest.raises(RunError, match="images 需要 2"):
        spec.assets_by_parameter(payload, {})
    with pytest.raises(RunError, match="每个素材槽位只能选择一种来源"):
        spec.assets_by_parameter(payload, {"first_frame": first})


def test_vidu_start_end_sends_start_url_before_end_upload(official, small_mp4):
    model = "vidu/start-end-to-video-2.0"
    workflow = upload(official, model)
    first = "https://cdn.example/opening.png"
    last = "https://cdn.example/uploaded-ending.png"
    ending = image_bytes("teal", size=(256, 256))
    prompt = "Transition between the first and last frames"
    task = submit(
        official,
        workflow,
        {
            "prompt": prompt,
            "first_frame_source": first,
            "last_frame": {"assetId": asset(official, ending)},
            "duration": 8,
        },
    )

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert ending in request.content
            return httpx.Response(200, json={"url": last})
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": model,
                "images": [first, last],
                "prompt": prompt,
                "duration": 8,
                "movement_amplitude": "auto",
                "seed": 0,
            }
            return httpx.Response(200, json={"data": {"id": "vidu-start-end"}})
        assert request.url.path.endswith("/prediction/vidu-start-end")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.mp4"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=small_mp4, headers={"Content-Type": "video/mp4"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert item["media"]["kind"] == "video"
    assert official.get(item["media"]["video"]).content == small_mp4


def test_vidu_q1_optional_seed_preserves_submission_type(official):
    model = "vidu/q1/text-to-video"
    workflow = upload(official, model)
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"prompt": "A camera follows the car", "bgm": False, "generate_audio": False}
    task = submit(official, workflow, values | {"seed": ""})
    assert "seed" not in task["inputValues"]
    assert spec.payload(task["inputValues"]) == {
        "model": model,
        **values,
        "style": "general",
        "resolution": "1080p",
        "duration": 5,
        "aspect_ratio": "16:9",
        "movement_amplitude": "auto",
    }
    seed = 2**53 + 1
    task = submit(official, workflow, values | {"seed": str(seed)})
    assert task["inputValues"]["seed"] == str(seed)
    assert spec.payload(task["inputValues"])["seed"] == seed


def test_vidu_q1_start_end_compares_aspect_ratios_between_uploads():
    model = "vidu/q1/start-end-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"prompt": "Connect the first and last frames", "generate_audio": False}
    opening = {"contentType": "image/png", "media": {"width": 300, "height": 300}}
    ending = opening | {"media": {"width": 500, "height": 400}}
    assert spec.assets_by_parameter(
        spec.payload(values), {"first_frame": opening, "last_frame": ending}
    ) == {"image": [opening], "end_image": [ending]}
    with pytest.raises(RunError, match="宽高比之比须为 0.8 至 1.25"):
        spec.assets_by_parameter(
            spec.payload(values),
            {
                "first_frame": opening,
                "last_frame": ending | {"media": {"width": 501, "height": 400}},
            },
        )
    first_url = "https://cdn.example/opening.png"
    payload = spec.payload(values | {"first_frame_source": first_url})
    assert payload["image"] == first_url and payload["generate_audio"] is False
    assert spec.assets_by_parameter(payload, {"last_frame": ending}) == {"end_image": [ending]}


def test_vidu_q1_subject_sources_enforce_per_subject_and_total_image_limits():
    model = "vidu/q1/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    assert spec.image_subjects and spec.request_max_bytes == 20_000_000
    sound = {"prompt": "Show the traveler speaking", "generate_audio": True}
    assert spec.payload(sound | {"audio_type": "speech_only"})["audio_type"] == "speech_only"
    with pytest.raises(RunError, match="当前设置需要填写 audio_type"):
        spec.payload(sound)
    urls = [f"https://cdn.example/subject-{index}.png" for index in range(3)]
    values = {"subject_1_id": "traveler", "subject_1_sources": "\n".join(urls)}
    valid = {"contentType": "image/png", "media": {"width": 128, "height": 128}}
    (subject,) = spec.image_subjects.sources(values, {})
    assert subject.id == "traveler" and subject.images == urls
    with pytest.raises(RunError, match="主体 1 最多 3 张图片"):
        spec.image_subjects.sources(values, {"subject_1_image_1": valid})
    with pytest.raises(RunError, match="主体 1 需要主体 ID"):
        spec.image_subjects.sources({"subject_1_sources": urls[0]}, {})
    with pytest.raises(RunError, match="主体图片合计最多 7 张"):
        spec.image_subjects.sources(
            values
            | {
                "subject_2_id": "runner",
                "subject_2_sources": "\n".join(urls),
                "subject_3_id": "suitcase",
                "subject_3_sources": "\n".join(urls[:2]),
            },
            {},
        )
    limited = spec.model_copy(update={"request_max_bytes": 11})
    limited.validate_request_size({"p": "甲"})
    with pytest.raises(RunError, match="请求体最多 11 字节"):
        limited.validate_request_size({"p": "甲乙"})


def test_vidu_q1_reference_sends_nested_subject_images(official, small_mp4):
    model = "vidu/q1/reference-to-video"
    workflow = upload(official, model)
    portrait = image_bytes("teal", size=(128, 128))
    uploaded = "https://cdn.example/portrait.png"
    profile = "https://cdn.example/profile.png"
    suitcase = "https://cdn.example/suitcase.png"
    prompt = "@traveler walks past @suitcase"
    task = submit(
        official,
        workflow,
        {
            "prompt": prompt,
            "subject_1_id": "traveler",
            "subject_1_image_1": {"assetId": asset(official, portrait)},
            "subject_1_sources": profile,
            "subject_7_id": "suitcase",
            "subject_7_sources": suitcase,
            "generate_audio": False,
            "audio_type": "speech_only",
        },
    )

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert portrait in request.content
            return httpx.Response(200, json={"url": uploaded})
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": model,
                "subjects": [
                    {"id": "traveler", "images": [uploaded, profile]},
                    {"id": "suitcase", "images": [suitcase]},
                ],
                "prompt": prompt,
                "duration": 5,
                "resolution": "1080p",
                "aspect_ratio": "16:9",
                "movement_amplitude": "auto",
                "generate_audio": False,
                "seed": 0,
            }
            return httpx.Response(200, json={"data": {"id": "vidu-subjects"}})
        assert request.url.path.endswith("/prediction/vidu-subjects")
        return httpx.Response(
            200,
            json={"data": {"status": "completed", "outputs": ["https://cdn.example/result.mp4"]}},
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=small_mp4, headers={"Content-Type": "video/mp4"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert item["media"]["kind"] == "video"
    assert official.get(item["media"]["video"]).content == small_mp4


def test_vega_image_15_pro_allows_more_sources_than_upload_slots():
    extended = AtlasSpec.model_validate(
        upload_body("tencent/vega-image-1.5-pro/edit")["graph"]["execution"]["config"]
    )
    capped = AtlasSpec.model_validate(
        upload_body("tencent/vega-image-1.0-pro/edit")["graph"]["execution"]["config"]
    )
    urls = [f"https://cdn.example/reference-{index}.png" for index in range(16)]
    values = {
        "prompt": "Keep the shape of the original object",
        "primary_image_source": "https://cdn.example/primary.png",
        "image_sources": "\n".join(urls),
    }
    payload = extended.payload(values)
    assert payload["images"] == urls
    reference = {"contentType": "image/png"}
    assert extended.assets_by_parameter(payload, {"reference_image_15": reference}) == {
        "images": [reference]
    }
    with pytest.raises(RunError, match="images 最多 5 张参考图"):
        capped.payload(values)


def test_vega_reference_requires_a_source_and_counts_all_media_types():
    model = "tencent/vega-video-1.0-lite/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    values = {"prompt": "Follow the coast"}
    with pytest.raises(RunError, match="reference_audios 至少需要一项"):
        spec.assets_by_parameter(spec.payload(values), {})
    for field, parameter, filename in (
        ("first_frame_source", "image", "first.png"),
        ("image_sources", "reference_images", "coast.png"),
        ("video_sources", "reference_videos", "clip.mp4"),
        ("audio_sources", "reference_audios", "surf.mp3"),
    ):
        url = f"https://cdn.example/{filename}"
        payload = spec.payload(values | {field: url})
        assert payload[parameter] == (url if field == "first_frame_source" else [url])
        assert not spec.assets_by_parameter(payload, {})
    images = [f"https://cdn.example/image-{index}.jpg" for index in range(9)]
    clips = [f"https://cdn.example/clip-{index}.mp4" for index in range(3)]
    payload = spec.payload(
        values | {"image_sources": "\n".join(images), "video_sources": "\n".join(clips)}
    )
    assert not spec.assets_by_parameter(payload, {})
    audio = {"contentType": "audio/mpeg", "size": 1024}
    with pytest.raises(RunError, match="素材合计最多 12 项"):
        spec.assets_by_parameter(payload, {"reference_audio_1": audio})
    with pytest.raises(RunError, match="reference_images 和 image 合计最多 9"):
        spec.assets_by_parameter(
            payload | {"reference_videos": [], "image": "https://cdn.example/first.png"}, {}
        )


@pytest.mark.parametrize("draft_id", ["draft-seedance", None], ids=["explicit", "prediction-id"])
def test_seedance25_keeps_draft_id_with_video_and_last_frame(official, small_mp4, draft_id):
    model = "bytedance/seedance-2.5/text-to-video"
    prediction_id = "prediction-seedance25"
    workflow = upload(official, model, "en")
    task = submit(
        official,
        workflow,
        {"draft": True, "resolution": "1080p-esr & 60fps", "include_last_frame": True},
    )
    frame = image_bytes("blue")
    urls = ["https://cdn.example/draft.mp4", "https://cdn.example/last-frame.png"]

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            payload = json.loads(request.content)
            assert payload["model"] == model
            assert payload["resolution"] == "1080p-esr & 60fps"
            assert payload["draft"] is True and payload["return_last_frame"] is True
            return httpx.Response(200, json={"data": {"id": prediction_id}})
        assert request.url.path.endswith(f"/prediction/{prediction_id}")
        data = {"status": "completed", "outputs": urls, "draft": True}
        if draft_id is not None:
            data["draft_id"] = draft_id
        return httpx.Response(200, json={"data": data})

    def download(request):
        assert str(request.url) in urls
        return httpx.Response(
            200, content=frame if request.url.path.endswith(".png") else small_mp4
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    items = (
        official.get("/api/v1/artifacts", params={"task_id": task["id"]})
        .raise_for_status()
        .json()["items"]
    )
    by_kind = {item["media"]["kind"]: item for item in items}
    assert len(items) == 3 and by_kind.keys() == {"video", "image", "text"}
    assert official.get(by_kind["text"]["media"]["src"]).text == (draft_id or prediction_id) + "\n"


def test_minimax_h3_reference_enforces_https_and_independent_clip_limits():
    model = "minimax/h3/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    text = {"prompt": "Follow the references"}
    with pytest.raises(RunError, match="HTTPS"):
        spec.payload(text | {"image_sources": "http://cdn.example/reference.png"})
    payload = spec.payload(text | {"image_sources": "https://cdn.example/reference.png"})
    assert payload["refers"] == [{"url": "https://cdn.example/reference.png", "type": "image"}]
    video = {
        "size": 50000000,
        "contentType": "video/quicktime",
        "media": {"width": 1280, "height": 720, "durationMs": 15000},
    }
    audio = {"size": 15000000, "contentType": "audio/wav", "media": {"durationMs": 15000}}
    assert spec.assets_by_parameter(payload, {"video_1": video, "audio_1": audio}) == {
        "refers": [video, audio]
    }
    companion = audio | {"media": {"durationMs": 2000}}
    with pytest.raises(RunError, match="合计最长 15000"):
        spec.assets_by_parameter(payload, {"audio_1": audio, "audio_2": companion})


def test_flux3_keyframes_validate_unique_indices_and_duration():
    model = "black-forest-labs/flux-3/keyframes-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    keyframes = spec.reference_arrays["keyframes"]
    start = {"keyframe_1_url": "https://cdn.example/first.png", "keyframe_1_index": 0}
    end = {"keyframe_2_url": "https://cdn.example/second.webp", "keyframe_2_index": 120}
    values = start | end
    payload = {"duration": 5}
    assert [
        source.properties for source in keyframes.sources("keyframes", values, {}, payload)
    ] == [
        {"frame_index": 0},
        {"frame_index": 120},
    ]
    for index, message in [(0, "帧号必须唯一"), (121, "0 至 120"), (None, "0 至 120")]:
        with pytest.raises(RunError, match=message):
            keyframes.sources("keyframes", values | {"keyframe_2_index": index}, {}, payload)
    with pytest.raises(RunError, match="至少需要一张"):
        keyframes.sources("keyframes", {}, {}, payload)


def test_flux3_keyframes_upload_and_submit_picture_index_pairs(official, small_mp4):
    model = "black-forest-labs/flux-3/keyframes-to-video"
    workflow = upload(official, model, "en")
    first = image_bytes("blue")
    start = "https://cdn.example/uploaded.png"
    end = "https://cdn.example/final.png"
    result = "https://cdn.example/result.mp4"
    task = submit(
        official,
        workflow,
        {
            "keyframe_1_image": {"assetId": asset(official, first)},
            "keyframe_10_url": end,
            "keyframe_10_index": 120,
        },
    )

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            assert first in request.content
            return httpx.Response(200, json={"url": start})
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            payload = json.loads(request.content)
            assert payload["keyframes"] == [
                {"image_url": start, "frame_index": 0},
                {"image_url": end, "frame_index": 120},
            ]
            assert payload["model"] == model and payload["duration"] == 5
            return httpx.Response(200, json={"data": {"id": "prediction-flux-keyframes"}})
        assert request.url.path.endswith("/prediction/prediction-flux-keyframes")
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": [result]}})

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, content=small_mp4)
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (item,) = (
        official.get("/api/v1/artifacts", params={"task_id": task["id"]})
        .raise_for_status()
        .json()["items"]
    )
    assert official.get(item["media"]["video"]).content == small_mp4


def test_grok_video_reference_sends_preset_voices_in_slot_order():
    model = "xai/grok-imagine-video-v1.5/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    defaults = {"prompt": "The speaker from <IMAGE_0> describes the harbor"}
    assert "voice_ids" not in spec.payload(defaults)
    assert spec.payload(defaults | {"voice_1": "zenith", "voice_2": "", "voice_3": "ara"})[
        "voice_ids"
    ] == ["zenith", "ara"]
    with pytest.raises(RunError, match="voice_ids"):
        spec.payload(defaults | {"voice_2": "custom-voice"})


def test_grok_image_to_video_accepts_https_and_data_uri_sources():
    model = "xai/grok-imagine-video/image-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    encoded = base64.b64encode(image_bytes("blue")).decode("ascii")
    for source in ("https://cdn.example/start.png", f"data:image/png;base64,{encoded}"):
        payload = spec.payload(
            {"prompt": "The picture comes to life", "first_frame_source": source}
        )
        assert payload["image_url"] == source
        assert not spec.assets_by_parameter(payload, {})
    with pytest.raises(RunError, match="HTTPS"):
        spec.payload(
            {
                "prompt": "The picture comes to life",
                "first_frame_source": "http://cdn.example/start.png",
            }
        )


def test_seedance2_references_support_asset_ids_and_inline_audio():
    model = "bytedance/seedance-2.0/reference-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    audio = base64.b64encode(wav_bytes(seconds=2)).decode("ascii")
    values = {"audio_sources": f"{audio}\nasset://music-cue"}
    with pytest.raises(RunError, match="reference_audios.*reference_images.*reference_videos"):
        spec.assets_by_parameter(spec.payload(values), {})

    payload = spec.payload(values | {"video_sources": "asset://reference-clip"})
    assert payload == {
        "model": model,
        "reference_videos": ["asset://reference-clip"],
        "reference_audios": [audio, "asset://music-cue"],
    }
    assert not spec.assets_by_parameter(payload, {})

    with pytest.raises(RunError, match="Base64 音频格式"):
        spec.payload({"audio_sources": f"data:audio/mpeg;base64,{audio}"})


def test_seedance2_accepts_raw_bitmap_and_tiff_frame_sources():
    model = "bytedance/seedance-2.0/image-to-video"
    spec = AtlasSpec.model_validate(upload_body(model)["graph"]["execution"]["config"])
    bitmap = base64.b64encode(image_bytes("red", size=(320, 320), format="BMP")).decode("ascii")
    tiff = base64.b64encode(image_bytes("blue", size=(320, 320), format="TIFF")).decode("ascii")
    payload = spec.payload({"first_frame_source": bitmap, "last_frame_source": tiff})
    assert payload == {"model": model, "image": bitmap, "last_image": tiff}
    assert not spec.assets_by_parameter(payload, {})


def test_seedance_v1_saves_video_from_model_schema_output_array(official, small_mp4):
    model = "bytedance/seedance-v1-pro-t2v-480p"
    workflow = upload(official, model)
    prompt = "A pixel art tram moves through a quiet city"
    task = submit(official, workflow, {"prompt": prompt, "duration": 12})
    result = "https://cdn.example/seedance.mp4"

    def provider(request):
        if request.method == "POST":
            assert request.url.path.endswith("/generateVideo")
            assert json.loads(request.content) == {
                "model": model,
                "prompt": prompt,
                "aspect_ratio": "16:9",
                "duration": 12,
                "seed": -1,
            }
            return httpx.Response(200, json={"id": "seedance-v1", "status": "queued"})
        assert request.url.path.endswith("/prediction/seedance-v1")
        return httpx.Response(
            200, json={"id": "seedance-v1", "status": "completed", "output": [result]}
        )

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, content=small_mp4, headers={"Content-Type": "video/mp4"}
                    )
                )
            ) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    asyncio.run(run())
    (item,) = official.get("/api/v1/artifacts", params={"task_id": task["id"]}).json()["items"]
    assert item["media"]["kind"] == "video"
    assert official.get(item["media"]["video"]).content == small_mp4


@pytest.mark.parametrize(
    "models", [BROWSER_MODELS, (HUNYUAN_PRO_TEXT,)], ids=["representative", "model-archive"]
)
def test_official_browser_import_and_generation_at_desktop_and_mobile_widths(
    settings, small_mp4, models, tmp_path
):
    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    assert (web_dist / "index.html").is_file(), "Run this test with pnpm test:python"
    settings = settings.model_copy(
        update={
            "static_dir": web_dist,
            "worker_service_tokens": {"official": SecretStr(TOKEN)},
            "official_owner": OWNER,
        }
    )
    png = image_bytes("red", size=(320, 320))
    wav = wav_bytes()
    glb = glb_bytes()
    fbx = FBX_BYTES
    bundle = archive_bytes(
        {"mesh.obj": OBJ_BYTES, "mesh.mtl": "newmtl surface\n", "surface.png": png}
    )

    def submitted_prediction(kind):
        return httpx.Response(200, json={"data": {"id": f"{uuid4().hex}-{kind}"}})

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            return httpx.Response(200, json={"url": "https://cdn.example/reference.png"})
        if request.method == "POST":
            payload = json.loads(request.content)
            if payload["model"] == HUNYUAN_PRO_TEXT:
                assert request.url.path.endswith("/generateImage")
                assert payload == {
                    "model": HUNYUAN_PRO_TEXT,
                    "prompt": payload["prompt"],
                    "generate_type": "Normal",
                    "enable_pbr": False,
                    "face_count": 500000,
                }
                return submitted_prediction("test-hunyuan-archive")
            if payload["model"] == MESHY_MULTI:
                assert request.url.path.endswith("/generateImage")
                assert payload["reference_images"] == ["https://cdn.example/reference.png"]
                assert payload["target_formats"] in (["glb"], ["obj"])
                prediction = f"test-meshy-{payload['target_formats'][0]}"
                return submitted_prediction(prediction)
            if payload["model"] == SEEDREAM_TEXT:
                assert request.url.path.endswith("/generateImage")
                assert payload["prompt"] in {"试跑模型", "测试场景", "测试 Base64"}
                assert payload == {
                    "model": SEEDREAM_TEXT,
                    "prompt": payload["prompt"],
                    "size": "2048*2048",
                    "prompt_expansion_mode": "standard",
                    "enable_base64_output": payload["prompt"] == "测试 Base64",
                }
                prediction = (
                    "test-image-inline" if payload["enable_base64_output"] else "test-image-url"
                )
                return submitted_prediction(prediction)
            if payload["model"] == H3_MAX_TURBO:
                assert request.url.path.endswith("/generateVideo")
                assert payload["prompt"] in {"试跑模型", "测试场景"}
                assert payload == {
                    "model": H3_MAX_TURBO,
                    "prompt": payload["prompt"],
                    "duration": 8,
                    "resolution": "768P",
                    "ratio": "1:1",
                }
            if payload["model"] == GEMINI_FLASH_TTS:
                assert request.url.path.endswith("/generateAudio")
                assert payload == {
                    "model": GEMINI_FLASH_TTS,
                    "text": payload["text"],
                    "voice": "Kore",
                }
                assert payload["text"] in {"试跑模型", "测试场景"}
                return submitted_prediction("test-audio")
            if payload["model"] == SEEDANCE_IMAGE:
                assert payload["image"] == "https://cdn.example/reference.png"
                assert "last_image" not in payload and "prompt" not in payload
            if payload["model"] in {H3_MAX_IMAGE, H3_MAX_TURBO_IMAGE}:
                assert payload["image"] == "https://cdn.example/reference.png"
                assert payload["ratio"] == "adaptive" and payload["resolution"] == "768P"
                assert payload["duration"] == 8
                if payload["model"] == H3_MAX_IMAGE:
                    assert payload["prompt_expansion"] is False
                else:
                    assert "prompt_expansion" not in payload
                assert "last_image" not in payload
                if payload["prompt"] == "试跑模型":
                    assert payload["end_image"] == "https://cdn.example/reference.png"
                else:
                    assert "end_image" not in payload
            if payload["model"] == TRIPO_IMAGE:
                assert request.url.path.endswith("/generateImage")
                assert payload == {
                    "model": TRIPO_IMAGE,
                    "image_url": "https://cdn.example/reference.png",
                    "texture": True,
                    "pbr": True,
                    "texture_quality": "standard",
                    "geometry_quality": "standard",
                    "texture_alignment": "original_image",
                    "orientation": "default",
                    "auto_size": False,
                    "quad": payload["quad"],
                }
                prediction = "test-tripo-fbx" if payload["quad"] else "test-tripo-glb"
                return submitted_prediction(prediction)
            kind = "video" if request.url.path.endswith("generateVideo") else "image"
            return submitted_prediction(f"test-{kind}")
        urls = {
            "test-video": ["https://cdn.example/result.mp4"],
            "test-image": ["https://cdn.example/result-1.png", "https://cdn.example/result-2.png"],
            "test-image-url": ["https://cdn.example/result.png"],
            "test-image-inline": [base64.b64encode(png).decode("ascii")],
            "test-audio": ["https://cdn.example/result.wav"],
            "test-tripo-glb": ["https://cdn.example/mesh.glb", "https://cdn.example/preview.png"],
            "test-tripo-fbx": ["https://cdn.example/opaque", "https://cdn.example/preview.png"],
            "test-meshy-glb": ["https://cdn.example/mesh.glb", "https://cdn.example/preview.png"],
            "test-meshy-obj": ["https://cdn.example/mesh.obj", "https://cdn.example/preview.png"],
            "test-hunyuan-archive": [
                "https://cdn.example/mesh.glb",
                "https://cdn.example/bundle.zip",
                "https://cdn.example/preview.png",
            ],
        }[request.url.path.rsplit("/", 1)[-1].split("-", 1)[1]]
        return httpx.Response(200, json={"data": {"status": "completed", "outputs": urls}})

    def download(request):
        suffix = Path(request.url.path).suffix
        contents, content_type = {
            ".mp4": (small_mp4, "video/mp4"),
            ".png": (png, "image/png"),
            ".wav": (wav, "audio/wav"),
            ".glb": (glb, "model/gltf-binary"),
            ".obj": (OBJ_BYTES, "model/obj"),
            ".zip": (bundle, "application/zip"),
            "": (fbx, "application/octet-stream"),
        }[suffix]
        return httpx.Response(
            200,
            content=contents,
            headers={"Content-Type": content_type},
        )

    async def run_one(address):
        async with (
            Platform(address, TOKEN) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
        ):
            assert await Runner(platform, Atlas(atlas), downloads).run_once()

    with (
        serve_test_app(settings) as (address, web),
        ThreadPoolExecutor(max_workers=1) as runner,
        sync_playwright() as playwright,
        playwright.chromium.launch() as chromium,
    ):
        credentials = register(web, OWNER)
        assert (
            web.put(f"/api/v1/assets/{uuid4()}?filename=mesh.fbx", content=fbx).status_code == 400
        )
        admin = chromium.new_page(base_url=address, viewport={"width": 1440, "height": 900})
        assert admin.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        workflows = {}
        reference_inputs = {
            SEEDREAM: "reference_1",
            SEEDANCE_IMAGE: "first_frame",
            SEEDANCE_REFERENCE: "image_1",
            H3_MAX_IMAGE: "first_frame",
            H3_MAX_TURBO_IMAGE: "first_frame",
            TRIPO_IMAGE: "reference_image",
            MESHY_MULTI: "reference_1",
        }
        artifact_counts = {SEEDREAM: 2, TRIPO_IMAGE: 2, MESHY_MULTI: 2, HUNYUAN_PRO_TEXT: 3}
        for filename in models:
            admin.goto("/workspace/workflows")
            admin.get_by_role("button", name="导入工作流", exact=True).click()
            panel = admin.get_by_role("dialog", name="导入工作流")
            panel.get_by_role("radio", name="官方服务清单 JSON").click()
            panel.locator('input[type="file"]').set_input_files(
                {
                    "name": source(filename).name,
                    "mimeType": "application/json",
                    "buffer": source(filename).read_bytes(),
                }
            )
            with admin.expect_response(
                lambda response: (
                    "/api/v1/workflows" in response.url and response.request.method == "POST"
                )
            ) as imported:
                panel.get_by_role("button", name="导入工作流", exact=True).click()
            assert imported.value.status == 201
            workflow = imported.value.json()
            assert workflow["format"] == "service"
            workflows[filename] = workflow
            if filename == H3_MAX:
                admin.goto(f"/workflows/{workflow['id']}")
                admin.get_by_role("button", name="编辑参数", exact=True).click()
                editor = admin.get_by_role("dialog", name="编辑参数")
                editor.locator(".parameter-row-trigger").filter(has_text="扩写提示词").click()
                editor.get_by_label("提示", exact=True).fill("扩写提示词后生成视频")
                with admin.expect_response(
                    lambda response: urlsplit(response.url).path.endswith("/parameter-layout")
                ) as saved:
                    editor.get_by_role("button", name="保存", exact=True).click()
                assert saved.value.ok and "machineId" not in saved.value.request.post_data_json
                expect(editor).to_have_count(0)
            values = {} if filename == SEEDANCE_IMAGE else {"prompt": "试跑模型"}
            if filename == GEMINI_FLASH_TTS:
                values = {"text": "试跑模型"}
            if filename in {TRIPO_IMAGE, MESHY_MULTI}:
                values = {}
            if reference_field := reference_inputs.get(filename):
                values[reference_field] = {"assetId": asset(web, png)}
            if filename in {H3_MAX_IMAGE, H3_MAX_TURBO_IMAGE}:
                values["last_frame"] = {"assetId": asset(web, image_bytes("blue", size=(320, 320)))}
            submit(web, workflow, values)
            runner.submit(lambda: asyncio.run(run_one(address))).result(timeout=10)
            web.post(f"/api/v1/workflows/{workflow['id']}/publish").raise_for_status()
        admin.close()

        imported = sync_workflows(address, *(str(source(filename)) for filename in models))
        synchronized = [json.loads(line) for line in imported.stdout.splitlines()]
        assert {item["workflowId"] for item in synchronized} == {
            item["id"] for item in workflows.values()
        }

        viewer = register(web, "viewer-without-machine")
        assert web.get("/api/v1/machines").json()["items"] == []
        for width, height in ((1440, 900), (390, 844)):
            page = chromium.new_page(base_url=address, viewport={"width": width, "height": height})
            assert page.request.post(
                "/api/v1/auth/login", data=viewer, headers={"Origin": address}
            ).ok
            for filename, workflow in workflows.items():
                page.goto(f"/workflows/{workflow['id']}")
                form = page.locator("form.run-fields")
                expect(page.get_by_role("button", name="编辑参数", exact=True)).to_have_count(0)
                expect(form.get_by_text("工作机", exact=False)).to_have_count(0)
                if filename not in {TRIPO_IMAGE, MESHY_MULTI}:
                    text_label = "朗读文本" if filename == GEMINI_FLASH_TTS else "提示词"
                    prompt = form.get_by_label(text_label, exact=True)
                    expect(prompt).to_be_visible()
                    if filename != SEEDANCE_IMAGE:
                        prompt.fill("测试场景")
                video = workflow["category"] == "video"
                if reference_field := reference_inputs.get(filename):
                    with page.expect_response(
                        lambda response: (
                            "/api/v1/assets/" in response.url and response.request.method == "PUT"
                        )
                    ) as uploaded:
                        form.locator(f"#input-{reference_field}").set_input_files(
                            {"name": "reference.png", "mimeType": "image/png", "buffer": png}
                        )
                    assert uploaded.value.ok
                if filename == TRIPO_IMAGE and width == 390:
                    form.get_by_role("button", name="高级参数", exact=True).click()
                    quad = form.get_by_role("switch", name="四边面网格", exact=True)
                    quad.click()
                    expect(quad).to_be_checked()
                if filename == MESHY_MULTI and width == 390:
                    form.get_by_role("button", name="高级参数", exact=True).click()
                    expect(form.get_by_text("未设置", exact=True).first).to_be_visible()
                    form.get_by_role("switch", name="导出 GLB", exact=True).click()
                    form.get_by_role("switch", name="导出 OBJ", exact=True).click()
                if filename == SEEDREAM_TEXT and width == 390:
                    form.get_by_role("button", name="高级参数", exact=True).click()
                    inline = form.get_by_role("switch", name="Base64 成品", exact=True)
                    inline.click()
                    expect(inline).to_be_checked()
                    form.get_by_label("提示词", exact=True).fill("测试 Base64")
                if video:
                    page.get_by_role("button", name="本次参数").click()
                    parameters = page.get_by_role("dialog", name="本次参数")
                    expect(parameters.get_by_text("工作机", exact=False)).to_have_count(0)
                    if filename == SEEDANCE:
                        search = parameters.get_by_role("searchbox", name="搜索参数", exact=True)
                        search.fill("不存在的参数名称")
                        no_matches = parameters.get_by_text("没有符合条件的参数。", exact=True)
                        expect(no_matches).to_be_visible()
                        parameters.get_by_role("button", name="清除搜索", exact=True).click()
                        expect(search).to_be_focused()
                        expect(no_matches).to_have_count(0)
                        parameters.screenshot(
                            path=tmp_path / f"parameter-search-{width}.png", animations="disabled"
                        )
                    parameters.get_by_role("button", name="关闭").click()
                ahead = None
                if filename == SEEDANCE:
                    form.locator("#run-count").fill("2")
                    idle = web.post(
                        "/api/v1/worker/services/official/claim",
                        headers=AUTH,
                        json={**claim_body(), "adapters": [ADAPTER]},
                    )
                    assert idle.raise_for_status().json() is None
                    ahead = submit(web, workflows[H3_MAX], {"prompt": "先排队的任务"})
                with page.expect_response(
                    lambda response: (
                        response.url.split("?")[0].endswith("/api/v1/tasks")
                        and response.request.method == "POST"
                    )
                ) as queued:
                    page.get_by_role("button", name="生成", exact=True).click()
                assert (
                    queued.value.status == 201
                    and "machineId" not in queued.value.request.post_data_json
                )
                progress = page.get_by_role("region", name="生成进度")
                expect(progress).to_be_visible()
                if ahead:
                    expect(progress.get_by_text("已完成 0 / 2 次")).to_be_visible()
                    waiting = "等待官方工作机领取 · 前方还有 1 个任务待领取"
                    expect(progress.get_by_text(waiting, exact=True)).to_be_visible()
                    page.get_by_role("button", name="任务详情", exact=True).click()
                    details = page.get_by_role("dialog", name="任务详情")
                    expect(details.get_by_text(waiting, exact=True)).to_be_visible()
                    expect(details.get_by_role("button", name="换工作机")).to_have_count(0)
                    expect(details.get_by_role("link", name="查看工作机")).to_have_count(0)
                    assert details.evaluate("el => el.scrollWidth <= el.clientWidth")
                    web.post(f"/api/v1/tasks/{ahead['id']}/cancel").raise_for_status()
                    expect(details.get_by_text("前方还有 0 个任务待领取")).to_be_visible()
                    details.get_by_role("button", name="关闭", exact=True).click()
                expect(progress.get_by_text("前方还有 0 个任务待领取")).to_be_visible()
                runner.submit(lambda: asyncio.run(run_one(address))).result(timeout=10)
                results = page.get_by_role("region", name="生成结果")
                expect(results.get_by_role("button", name="再生成一次")).to_be_visible(
                    timeout=10000
                )
                task = queued.value.json()
                items = page.request.get(f"/api/v1/executions?task_id={task['id']}").json()["items"]
                assert len(items) == (2 if ahead else 1)
                assert all(
                    item["artifactCount"] == artifact_counts.get(filename, 1) for item in items
                )
                if filename in {TRIPO_IMAGE, MESHY_MULTI}:
                    artifacts = page.request.get(f"/api/v1/artifacts?task_id={task['id']}").json()[
                        "items"
                    ]
                    (model,) = [
                        artifact for artifact in artifacts if artifact["media"]["kind"] == "3d"
                    ]
                    assert items[0]["modelCount"] == 1
                    suffix, content = (".glb", glb)
                    if width == 390:
                        suffix, content = (
                            (".fbx", fbx) if filename == TRIPO_IMAGE else (".obj", OBJ_BYTES)
                        )
                    assert model["filename"].endswith(suffix)
                    assert page.request.get(model["media"]["src"]).body() == content
                    if width == 390:
                        page.get_by_role("button", name="查看与发布", exact=True).click()
                        page.locator(f"button[data-media-id='{model['id']}']").click()
                        expect(
                            page.get_by_text("无法预览此模型，可下载原件查看", exact=True)
                        ).to_be_visible()
                        expect(
                            page.get_by_role("link", name="下载原文件", exact=True)
                        ).to_be_visible()
                if filename == HUNYUAN_PRO_TEXT:
                    artifacts = page.request.get(f"/api/v1/artifacts?task_id={task['id']}").json()[
                        "items"
                    ]
                    (archive,) = [
                        item for item in artifacts if item["contentType"] == "application/zip"
                    ]
                    assert archive["media"]["kind"] == "3d"
                    assert archive["filename"].endswith(".zip")
                    page.get_by_role("button", name="查看与发布", exact=True).click()
                    page.locator(f"button[data-media-id='{archive['id']}']").click()
                    expect(
                        page.get_by_text("无法预览此模型，可下载原件查看", exact=True)
                    ).to_be_visible()
                    expect(page.get_by_role("link", name="下载原文件", exact=True)).to_be_visible()
                    response = page.request.get(archive["media"]["src"])
                    assert response.body() == bundle
                    assert response.headers["content-disposition"].startswith("attachment;")
                if filename == GEMINI_FLASH_TTS:
                    (artifact,) = page.request.get(
                        f"/api/v1/artifacts?task_id={task['id']}"
                    ).json()["items"]
                    assert artifact["media"]["kind"] == "audio"
                    assert artifact["contentType"] == "audio/wav"
                    assert page.request.get(artifact["media"]["src"]).body() == wav
                if filename == SEEDREAM_TEXT:
                    (artifact,) = page.request.get(
                        f"/api/v1/artifacts?task_id={task['id']}"
                    ).json()["items"]
                    assert artifact["filename"] == "result-1.png"
                    assert artifact["media"]["kind"] == "image"
                    assert page.request.get(artifact["media"]["src"]).body() == png
            page.close()
