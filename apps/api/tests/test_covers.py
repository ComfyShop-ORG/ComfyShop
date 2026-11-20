import hashlib
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy.orm import Session

from comfyshop_api.models import Artifact, Execution, MediaObject, Task, User
from comfyshop_media import renditions
from comfyshop_api.services.executions import finish_execution


def image_data():
    output = BytesIO()
    Image.new("RGB", (32, 48), "green").save(output, "PNG")
    return output.getvalue()


def add_result(
    client,
    settings,
    workflow,
    owner_id,
    created,
    status="succeeded",
    content=None,
    content_type="image/png",
    width=32,
    height=48,
):
    content = content if content is not None else image_data()
    digest = hashlib.sha256(content).hexdigest()
    with Session(client.app.state.engine) as db:
        media = db.get(MediaObject, digest)
        if media is None:
            media = MediaObject(
                storage_name=uuid4().hex,
                sha256=digest,
                size=len(content),
                content_type=content_type,
                width=width,
                height=height,
            )
            settings.original_dir.mkdir(parents=True, exist_ok=True)
            (settings.original_dir / media.storage_name).write_bytes(content)
        task = Task(
            owner_id=owner_id,
            workflow_id=workflow["id"],
            version_id=workflow["versionId"],
            workflow_name=workflow["name"],
            execution_count=1,
            input_values={},
            input_schema={"fields": []},
            input_graph=client.get(f"/api/v1/workflows/{workflow['id']}/graph").json()["graph"],
            status=status,
            progress=100,
            idempotency_key=str(uuid4()),
            request_hash="0" * 64,
            created_at=created,
        )
        db.add(task)
        db.flush()
        execution = Execution(
            task_id=task.id,
            index=0,
            input_values={},
            status="running",
            created_at=created,
        )
        db.add(execution)
        db.flush()
        artifact = Artifact(
            task_id=task.id,
            owner_id=owner_id,
            client_id=uuid4().hex,
            execution_id=execution.id,
            filename="output.png" if content_type.startswith("image/") else "output.mp4",
            media=media,
            created_at=created,
        )
        db.add(artifact)
        db.flush()
        if status == "succeeded":
            finish_execution(db, execution, [artifact.client_id])
        db.commit()
        return artifact.id


def test_workflow_cover_comes_from_the_authors_public_work(authenticated, settings, graph):
    client = authenticated
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    workflow = client.post("/api/v1/workflows", json={"name": "cover", "graph": graph}).json()
    url = f"/api/v1/workflows/{workflow['id']}"
    first = add_result(client, settings, workflow, owner, 1)
    latest = add_result(client, settings, workflow, owner, 2)
    add_result(client, settings, workflow, owner, 3, status="failed")
    with Session(client.app.state.engine) as db:
        viewer = User(username="viewer", username_key="viewer", password_hash="unused")
        db.add(viewer)
        db.commit()
        viewer_id = viewer.id
    add_result(client, settings, workflow, viewer_id, 4)

    # 没有公开作品时，作者看到自己最近一次成功执行的成品，其他人看不到封面。
    own = client.get("/api/v1/workflows?scope=mine").json()["items"][0]
    assert own["media"]["src"] == f"/api/v1/artifacts/{latest}/file"
    assert client.get(own["media"]["src"]).content == image_data()
    assert client.post(f"{url}/publish").status_code == 200
    anonymous = TestClient(client.app)
    assert anonymous.get("/api/v1/workflows").json()["items"][0]["media"] is None
    assert client.get("/api/v1/workflows").json()["items"][0]["media"] is None
    assert anonymous.get(own["media"]["src"]).status_code == 404

    # 作者公开作品后，作品封面成为所有人看到的工作流封面。
    executions = {
        item["id"]: item["executionId"] for item in client.get("/api/v1/artifacts").json()["items"]
    }
    work = {
        "id": str(uuid4()),
        "executionId": executions[first],
        "title": "cover",
        "artifactIds": [first],
        "coverArtifactId": first,
    }
    assert client.post("/api/v1/works", json=work).status_code == 201
    public = anonymous.get(url).json()
    assert public["media"]["src"] == f"/api/v1/artifacts/{first}/file"
    assert client.get(url).json()["media"]["src"] == public["media"]["src"]
    assert anonymous.get("/api/v1/workflows").json()["items"][0]["media"] == public["media"]
    assert anonymous.get(public["media"]["src"]).status_code == 200
    thumb = public["media"]["thumbnail"]["src"]
    assert anonymous.get(thumb).status_code == 200
    assert anonymous.get(f"/api/v1/artifacts/{latest}/file").status_code == 404

    # 新版本沿用同一封面；取消公开后封面与匿名访问一起撤回。
    revised = client.patch(
        url,
        json={"graph": {"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "new version"}}}},
    ).json()
    assert revised["media"]["src"] == public["media"]["src"]
    assert client.delete(f"/api/v1/works/{work['id']}").status_code == 204
    assert anonymous.get(url).json()["media"] is None
    assert anonymous.get(thumb).status_code == 404
    assert client.get(thumb).status_code == 200


def test_image_thumbnails_are_lazy_bounded_and_regenerable(
    authenticated, settings, graph, monkeypatch
):
    client = authenticated
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    workflow = client.post("/api/v1/workflows", json={"name": "portrait", "graph": graph}).json()
    source = BytesIO()
    orientation = Image.Exif()
    orientation[274] = 6
    Image.new("RGBA", (1440, 960), (30, 80, 120, 64)).save(source, "PNG", exif=orientation)
    original = source.getvalue()
    add_result(client, settings, workflow, owner, 1, content=original, width=1440, height=960)
    media = client.get("/api/v1/workflows?scope=mine").json()["items"][0]["media"]
    thumb = media["thumbnail"]["src"]
    assert media["thumbnail"]["sizes"] == [160, 256, 384, 512, 768, 1024, 1280]
    assert (media["width"], media["height"]) == (1440, 960)
    assert not settings.thumbnail_dir.exists()
    assert client.get(thumb, params={"size": 1281}).status_code == 422
    assert TestClient(client.app).get(thumb, params={"size": 256}).status_code == 404
    assert not settings.thumbnail_dir.exists()

    small = client.get(thumb, params={"size": 220})
    assert small.status_code == 200
    assert small.headers["content-type"] == "image/webp"
    # 浏览器可缓存，但每次使用前带 ETag 回来核对授权；同一档位的请求共用一个 ETag。
    assert small.headers["cache-control"] == "private, no-cache"
    revalidate = {"If-None-Match": small.headers["etag"]}
    unchanged = client.get(thumb, params={"size": 256}, headers=revalidate)
    assert unchanged.status_code == 304 and not unchanged.content
    # 反向代理压缩后会把 ETag 改成弱校验值，也可能带多个值，同样视为未变化。
    proxied = {"If-None-Match": f'"other", W/{small.headers["etag"]}'}
    assert client.get(thumb, params={"size": 256}, headers=proxied).status_code == 304
    assert (
        TestClient(client.app).get(thumb, params={"size": 256}, headers=revalidate).status_code
        == 404
    )
    with Image.open(BytesIO(small.content)) as image:
        assert image.size == (171, 256)
        assert image.getpixel((30, 30))[3] == 64
        assert not image.getexif()
    assert len(list(settings.thumbnail_dir.iterdir())) == 1
    with monkeypatch.context() as patch:

        def unexpected_decode(*_args):
            pytest.fail("a cache hit must not decode the original again")

        patch.setattr(renditions, "_image", unexpected_decode)
        assert client.get(thumb, params={"size": 256}).content == small.content

    large = client.get(thumb, params={"size": 513})
    with Image.open(BytesIO(large.content)) as image:
        assert image.size == (512, 768)
    assert len(list(settings.thumbnail_dir.iterdir())) == 2
    shutil.rmtree(settings.thumbnail_dir)
    assert client.get(media["src"], params={"download": True}).content == original
    assert not settings.thumbnail_dir.exists()
    assert client.get(thumb, params={"size": 256}).content == small.content
    assert len(list(settings.thumbnail_dir.iterdir())) == 1

    replace = Path.replace

    def clear_before_publish(temporary, target):
        if target.parent == settings.thumbnail_dir:
            shutil.rmtree(settings.thumbnail_dir)
        return replace(temporary, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", clear_before_publish)
        assert client.get(thumb, params={"size": 768}).content == large.content
    assert not settings.thumbnail_dir.exists()
    assert client.get(thumb, params={"size": 768}).content == large.content
    assert len(list(settings.thumbnail_dir.iterdir())) == 1


def test_video_cover_is_a_private_cached_first_frame(authenticated, settings, graph, tmp_path):
    if not shutil.which(settings.ffmpeg):
        pytest.skip("ffmpeg is required for the video thumbnail check")
    video = tmp_path / "source.mp4"
    subprocess.run(
        [
            settings.ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=640x360:d=0.2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    owner = authenticated.get("/api/v1/auth/session").json()["user"]["id"]
    workflow = authenticated.post(
        "/api/v1/workflows", json={"name": "video cover", "graph": graph, "category": "video"}
    ).json()
    artifact = add_result(
        authenticated,
        settings,
        workflow,
        owner,
        1,
        content=video.read_bytes(),
        content_type="video/mp4",
        width=640,
        height=360,
    )
    cover = authenticated.get("/api/v1/workflows?scope=mine").json()["items"][0]["media"]
    assert cover["src"] == f"/api/v1/artifacts/{artifact}/thumbnail"
    anonymous = TestClient(authenticated.app)
    assert anonymous.get(cover["src"]).status_code == 404
    response = authenticated.get(cover["src"])
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/jpeg"
    with Image.open(BytesIO(response.content)) as frame:
        assert frame.size == (640, 360)
    card = authenticated.get(cover["thumbnail"]["src"], params={"size": 200})
    assert card.headers["content-type"] == "image/jpeg"
    with Image.open(BytesIO(card.content)) as frame:
        assert frame.size == (256, 144)
    assert authenticated.get(cover["video"]).content == video.read_bytes()
    settings.ffmpeg = "unavailable-ffmpeg"
    assert authenticated.get(cover["src"]).content == response.content
    assert (
        authenticated.get(cover["thumbnail"]["src"], params={"size": 256}).content == card.content
    )
    assert len(list(settings.thumbnail_dir.iterdir())) == 2


def test_author_can_pin_one_of_their_public_works_as_the_workflow_cover(
    authenticated, settings, graph
):
    client = authenticated
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    workflow = client.post("/api/v1/workflows", json={"name": "pinned", "graph": graph}).json()
    url = f"/api/v1/workflows/{workflow['id']}"
    older = add_result(client, settings, workflow, owner, 1)
    newer = add_result(client, settings, workflow, owner, 2)
    private = add_result(client, settings, workflow, owner, 3)
    assert client.post(f"{url}/publish").status_code == 200
    executions = {
        item["id"]: item["executionId"] for item in client.get("/api/v1/artifacts").json()["items"]
    }

    def publish(artifact_id):
        body = {
            "id": str(uuid4()),
            "executionId": executions[artifact_id],
            "title": "work",
            "artifactIds": [artifact_id],
            "coverArtifactId": artifact_id,
        }
        assert client.post("/api/v1/works", json=body).status_code == 201
        return body["id"]

    first_work, second_work = publish(older), publish(newer)
    anonymous = TestClient(client.app)
    cover = lambda: anonymous.get(url).json()["media"]["src"]  # noqa: E731
    assert cover() == f"/api/v1/artifacts/{newer}/file"

    pinned = client.put(f"{url}/cover", json={"workId": first_work})
    assert pinned.status_code == 200 and pinned.json()["coverWorkId"] == first_work
    assert cover() == f"/api/v1/artifacts/{older}/file"
    assert anonymous.get("/api/v1/workflows").json()["items"][0]["media"]["src"] == cover()
    assert anonymous.get(f"/api/v1/artifacts/{private}/file").status_code == 404

    # 被指定的作品取消公开后，封面回到最近公开的作品，也不能再被指定。
    assert client.delete(f"/api/v1/works/{first_work}").status_code == 204
    assert cover() == f"/api/v1/artifacts/{newer}/file"
    assert client.put(f"{url}/cover", json={"workId": first_work}).status_code == 404
    assert client.put(f"{url}/cover", json={"workId": str(uuid4())}).status_code == 404
    assert client.put(f"{url}/cover", json={"workId": second_work}).status_code == 200
    cleared = client.put(f"{url}/cover", json={"workId": None})
    assert cleared.status_code == 200 and cleared.json()["coverWorkId"] is None
    assert anonymous.put(f"{url}/cover", json={"workId": second_work}).status_code == 401


def test_only_results_of_a_published_version_become_works(authenticated, settings, graph):
    client = authenticated
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    workflow = client.post("/api/v1/workflows", json={"name": "versions", "graph": graph}).json()
    url = f"/api/v1/workflows/{workflow['id']}"
    published = add_result(client, settings, workflow, owner, 1)
    assert client.post(f"{url}/publish").status_code == 200
    draft = client.patch(
        url,
        json={"graph": {"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "draft"}}}},
    ).json()
    assert draft["versionId"] != workflow["versionId"]
    unpublished = add_result(client, settings, draft, owner, 2)
    executions = {
        item["id"]: item["executionId"] for item in client.get("/api/v1/artifacts").json()["items"]
    }

    def publish(artifact_id):
        return client.post(
            "/api/v1/works",
            json={
                "id": str(uuid4()),
                "executionId": executions[artifact_id],
                "title": "work",
                "artifactIds": [artifact_id],
                "coverArtifactId": artifact_id,
            },
        )

    # 草稿版本的结果不能公开，也不会成为访客看到的封面。
    rejected = publish(unpublished)
    assert rejected.status_code == 409 and "未发布的工作流版本" in rejected.json()["detail"]
    assert TestClient(client.app).get(url).json()["media"] is None
    assert publish(published).status_code == 201


def test_a_chosen_video_frame_becomes_the_group_work_and_workflow_cover(
    authenticated, settings, graph, tmp_path
):
    if not shutil.which(settings.ffmpeg) or not shutil.which(settings.ffprobe):
        pytest.skip("ffmpeg and ffprobe are required for the video frame check")
    # 前一秒红色，后一秒蓝色：取到哪一刻的画面看颜色就知道。
    video = tmp_path / "source.mp4"
    subprocess.run(
        [
            settings.ffmpeg,
            "-v",
            "error",
            *("-f", "lavfi", "-i", "color=c=red:s=320x180:r=10:d=1"),
            *("-f", "lavfi", "-i", "color=c=blue:s=320x180:r=10:d=1"),
            *("-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]"),
            *("-c:v", "libx264", "-pix_fmt", "yuv420p"),
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    client = authenticated
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    workflow = client.post(
        "/api/v1/workflows", json={"name": "frame cover", "graph": graph, "category": "video"}
    ).json()
    clip = add_result(
        client,
        settings,
        workflow,
        owner,
        1,
        content=video.read_bytes(),
        content_type="video/mp4",
        width=320,
        height=180,
    )
    picture = add_result(client, settings, workflow, owner, 2)
    executions = {
        item["id"]: item["executionId"] for item in client.get("/api/v1/artifacts").json()["items"]
    }
    cover = f"/api/v1/executions/{executions[clip]}/cover"
    base = f"/api/v1/artifacts/{clip}"

    def color(url, source=client):
        response = source.get(url)
        assert response.status_code == 200, response.text
        with Image.open(BytesIO(response.content)) as image:
            red, _, blue = image.convert("RGB").getpixel((image.width // 2, image.height // 2))
        return "red" if red > blue else "blue"

    chosen = client.put(cover, json={"artifactId": clip, "frameMs": 1500}).json()
    assert chosen["coverFrameMs"] == 1500
    assert chosen["media"]["src"] == f"{base}/frames/1500/thumbnail"
    assert chosen["media"]["thumbnail"]["src"] == chosen["media"]["src"]
    assert color(chosen["media"]["src"]) == "blue"
    assert color(chosen["media"]["thumbnail"]["src"] + "?size=160") == "blue"
    assert color(f"{base}/thumbnail") == "red"
    # 只提供选定的画面，不能逐毫秒截取任意时刻。
    assert client.get(f"{base}/frames/1400/thumbnail").status_code == 404

    # 超出视频长度或给图片指定画面都被拒绝，原来的选择不变。
    assert client.put(cover, json={"artifactId": clip, "frameMs": 60_000}).status_code == 422
    still = f"/api/v1/executions/{executions[picture]}/cover"
    assert client.put(still, json={"artifactId": picture, "frameMs": 500}).status_code == 422
    assert client.get(f"/api/v1/executions/{executions[clip]}").json()["coverFrameMs"] == 1500

    # 作品带着所选画面发布，工作流封面跟随这件作品，访客也能读到这一帧。
    assert client.post(f"/api/v1/workflows/{workflow['id']}/publish").status_code == 200
    work = {
        "id": str(uuid4()),
        "executionId": executions[clip],
        "title": "frame",
        "artifactIds": [clip],
        "coverArtifactId": clip,
    }
    late = client.post("/api/v1/works", json={**work, "coverFrameMs": 60_000})
    assert late.status_code == 422
    published = client.post("/api/v1/works", json={**work, "coverFrameMs": 1200})
    assert published.status_code == 201, published.text
    assert published.json()["coverFrameMs"] == 1200
    anonymous = TestClient(client.app)
    shown = anonymous.get(f"/api/v1/workflows/{workflow['id']}").json()["media"]
    assert shown["src"] == f"{base}/frames/1200/thumbnail"
    assert color(shown["src"], anonymous) == "blue"
    # 结果组自己选的那一帧不属于公开作品以外的人，但视频已公开，同样可读。
    assert anonymous.get(f"{base}/frames/1500/thumbnail").status_code == 200

    # 不指定画面回到首帧。
    reset = client.put(cover, json={"artifactId": clip, "frameMs": 0}).json()
    assert reset["coverFrameMs"] is None and reset["media"]["src"] == f"{base}/thumbnail"
    assert client.get(f"{base}/frames/1500/thumbnail").status_code == 404
