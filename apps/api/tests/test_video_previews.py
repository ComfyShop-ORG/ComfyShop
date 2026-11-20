import json
import shutil
import subprocess
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from comfyshop_api.models import Artifact
from test_covers import add_result


def test_video_preview_is_silent_bounded_and_uses_the_current_media_permission(
    authenticated, settings, graph, tmp_path, monkeypatch
):
    if not shutil.which(settings.ffmpeg) or not shutil.which(settings.ffprobe):
        pytest.skip("ffmpeg and ffprobe are required for the video preview check")
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            settings.ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=800x450:rate=30:duration=11",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=11",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-threads",
            "1",
            "-c:a",
            "aac",
            str(source),
        ],
        capture_output=True,
        check=True,
    )
    original = source.read_bytes()
    client = authenticated
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    workflow = client.post(
        "/api/v1/workflows", json={"name": "视频预览", "graph": graph, "category": "video"}
    ).json()
    artifact_id = add_result(
        client,
        settings,
        workflow,
        owner,
        1,
        content=original,
        content_type="video/mp4",
        width=800,
        height=450,
    )
    media = client.get("/api/v1/workflows?scope=mine").json()["items"][0]["media"]
    url = f"/api/v1/artifacts/{artifact_id}/video-preview"
    assert media["videoPreview"] == {"src": url, "sizes": [160, 256, 384, 512, 768]}
    guest = TestClient(client.app)
    assert guest.get(url, params={"size": 256}).status_code == 404
    assert client.get(url, params={"size": 769}).status_code == 422
    assert not settings.video_preview_dir.exists()

    partial = client.get(url, params={"size": 200}, headers={"Range": "bytes=0-31"})
    assert partial.status_code == 206
    assert partial.headers["content-range"].startswith("bytes 0-31/")
    path = next(settings.video_preview_dir.glob("*-256.mp4"))
    clip = path.read_bytes()
    assert partial.content == clip[:32]
    info = json.loads(
        subprocess.check_output(
            [
                settings.ffprobe,
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,codec_name,width,height:format=duration",
                "-of",
                "json",
                str(path),
            ]
        )
    )
    assert info["streams"] == [
        {"codec_name": "h264", "codec_type": "video", "width": 256, "height": 144}
    ]
    assert float(info["format"]["duration"]) == pytest.approx(10.0, abs=0.05)

    with monkeypatch.context() as patch:
        patch.setattr(settings, "ffmpeg", "unavailable-ffmpeg")
        cached = client.get(url, params={"size": 256})
        assert cached.headers["content-type"] == "video/mp4"
        assert cached.headers["cache-control"] == "no-store"
        assert cached.content == clip
        assert client.get(url, params={"size": 384}).status_code == 503
        assert list(settings.video_preview_dir.iterdir()) == [path]
    assert client.get(url, params={"size": 384}).status_code == 200
    assert len(list(settings.video_preview_dir.glob("*-384.mp4"))) == 1

    workflow_url = f"/api/v1/workflows/{workflow['id']}"
    assert client.post(f"{workflow_url}/publish").status_code == 200
    assert guest.get(url, params={"size": 256}).status_code == 404
    execution_id = client.get("/api/v1/executions").json()["items"][0]["id"]
    work = {
        "id": str(uuid4()),
        "executionId": execution_id,
        "title": "clip",
        "artifactIds": [artifact_id],
        "coverArtifactId": artifact_id,
    }
    assert client.post("/api/v1/works", json=work).status_code == 201
    assert guest.get(url, params={"size": 256}).content == clip
    assert client.delete(f"/api/v1/works/{work['id']}").status_code == 204
    assert guest.get(url, params={"size": 256}).status_code == 404
    assert client.post(f"/api/v1/works/{work['id']}/delete").status_code == 204

    shutil.rmtree(settings.video_preview_dir)
    assert client.get(media["video"], params={"download": True}).content == original
    assert not settings.video_preview_dir.exists()
    assert client.get(url, params={"size": 256}).content == clip

    image_id = add_result(client, settings, workflow, owner, 2)
    assert client.get(f"/api/v1/artifacts/{image_id}/video-preview?size=256").status_code == 404

    artifact_url = f"/api/v1/artifacts/{artifact_id}"
    assert client.get(artifact_url + "/thumbnail").status_code == 200
    assert client.delete(artifact_url).json()["videoCount"] == 0
    assert client.get(url, params={"size": 256}).status_code == 404
    assert client.get(artifact_url + "/thumbnail").status_code == 404
    assert client.get(media["video"]).status_code == 404
    with Session(client.app.state.engine) as db:
        stored = settings.original_dir / db.get(Artifact, artifact_id).media.storage_name
    assert stored.read_bytes() == original
    assert path.read_bytes() == clip
    assert len(list(settings.thumbnail_dir.glob("*.jpg"))) == 1
