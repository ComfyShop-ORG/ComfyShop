from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_inputs import picture
from test_inputs import prepared as prepared
from test_team_spaces import add_member
from test_workspace_sharing import ORIGIN, register_account

from comfyshop_api.core.config import Settings
from comfyshop_api.models import Asset, MediaObject, OriginalDeletion, Task, now_ms
from comfyshop_api.services.assets import expire_unused_assets
from comfyshop_api.services.originals import (
    UPLOAD_PENDING,
    delete_pending_originals,
    release_uploads,
    retire_unreferenced_originals,
)
from comfyshop_media import renditions


def upload(client, color="white"):
    return client.put(
        f"/api/v1/assets/{uuid4()}", params={"filename": "image.png"}, content=picture(color)
    )


def test_team_quota_settings_use_stable_ids_and_validate_byte_limits(monkeypatch):
    team_id = str(uuid4())
    monkeypatch.setenv("COMFYSHOP_ASSET_QUOTA_BYTES", "8192")
    monkeypatch.setenv("COMFYSHOP_TEAM_ASSET_QUOTA_BYTES", f'{{"{team_id}":4096}}')
    settings = Settings(_env_file=None)
    assert settings.asset_quota_for(team_id) == 4096
    assert settings.asset_quota_for(str(uuid4())) == settings.asset_quota_for(None) == 8192
    monkeypatch.setenv("COMFYSHOP_TEAM_ASSET_QUOTA_BYTES", f'{{"{team_id}":1023}}')
    with pytest.raises(ValidationError, match="1024"):
        Settings(_env_file=None)


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_team_quotas_control_concurrent_uploads_and_keep_assets_after_reduction(client, settings):
    register_account(client, "quota-owner")
    first, second = [
        client.post("/api/v1/teams", json={"name": name}).raise_for_status().json()["id"]
        for name in ("摄影组", "视频组")
    ]
    blue, red = [picture(color, size=(512, 512)) for color in ("blue", "red")]
    one_file = max(len(blue), len(red))
    settings.team_asset_quota_bytes = {UUID(first): one_file, UUID(second): 2 * one_file}
    usage = "/api/v1/assets/usage"
    first_scope = {"workspace_team": first}
    second_scope = {"workspace_team": second}

    def upload_for(team_id, original):
        return client.put(
            f"/api/v1/teams/{team_id}/assets/{uuid4()}",
            params={"filename": "reference.png"},
            content=original,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda original: upload_for(first, original), (blue, red)))
    assert sorted(response.status_code for response in responses) == [200, 413]
    index = next(index for index, response in enumerate(responses) if response.is_success)
    saved = responses[index].json()
    original, other = ((blue, red), (red, blue))[index]
    assert client.get(usage, params=first_scope).json()["limitBytes"] == one_file

    personal = (
        client.put(f"/api/v1/assets/{uuid4()}", params={"filename": "personal.png"}, content=other)
        .raise_for_status()
        .json()
    )
    assert client.post(f"/api/v1/teams/{first}/assets/{personal['id']}/copy").status_code == 413
    upload_for(second, original).raise_for_status()
    client.post(f"/api/v1/teams/{second}/assets/{personal['id']}/copy").raise_for_status()
    assert client.get(usage, params=second_scope).json() == {
        "usedBytes": len(blue) + len(red),
        "remainingBytes": 2 * one_file - len(blue) - len(red),
        "limitBytes": 2 * one_file,
    }
    assert client.get(usage).json()["limitBytes"] == settings.asset_quota_bytes

    assert len(original) > 1024
    settings.team_asset_quota_bytes[UUID(first)] = 1024
    assert client.get(usage, params=first_scope).json() == {
        "usedBytes": len(original),
        "remainingBytes": 0,
        "limitBytes": 1024,
    }
    assert client.get(saved["media"]["src"]).content == original
    assert upload_for(first, original).raise_for_status().json()["id"] == saved["id"]
    assert upload_for(first, other).status_code == 413


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_copy_counts_an_original_once_even_with_different_audio_formats(client, settings):
    register_account(client, "audio-quota-owner")
    team_id = client.post("/api/v1/teams", json={"name": "录音组"}).raise_for_status().json()["id"]
    team = f"/api/v1/teams/{team_id}"
    scope = {"workspace_team": team_id}
    recording = b"\x16\x04" * 8000
    team_recording = (
        client.put(
            f"{team}/assets/{uuid4()}",
            params={"filename": "recording.pcm", "save_to_library": True},
            content=recording,
        )
        .raise_for_status()
        .json()
    )
    settings.team_asset_quota_bytes = {UUID(team_id): 1024}

    def copy_recording(data):
        personal = (
            client.put(
                f"/api/v1/assets/{uuid4()}", params={"filename": "recording.ulaw"}, content=data
            )
            .raise_for_status()
            .json()
        )
        return client.post(f"{team}/assets/{personal['id']}/copy")

    copied = copy_recording(recording).raise_for_status().json()
    assert copied["id"] != team_recording["id"]
    assert copied["contentType"] == "audio/x-mulaw"
    assert copied["sha256"] == team_recording["sha256"]
    assert client.get(copied["media"]["src"]).content == recording
    assert copy_recording(b"\x16\x05" * 8000).status_code == 413
    assert client.get("/api/v1/assets/usage", params=scope).json() == {
        "usedBytes": len(recording),
        "remainingBytes": 0,
        "limitBytes": 1024,
    }
    assert {
        asset["id"] for asset in client.get("/api/v1/assets", params=scope).json()["items"]
    } == {
        team_recording["id"],
        copied["id"],
    }


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_asset_usage_counts_originals_in_the_selected_space(client, settings):
    owner_id = register_account(client, "usage-owner")
    reader = TestClient(client.app, headers={"Origin": ORIGIN})
    register_account(reader, "usage-reader")
    first, second = [
        client.post("/api/v1/teams", json={"name": name}).raise_for_status().json()["id"]
        for name in ("摄影组", "排版组")
    ]
    team = f"/api/v1/teams/{first}"
    assert add_member(client, team, "usage-reader", "reader").status_code == 204
    usage = "/api/v1/assets/usage"
    assert TestClient(client.app).get(usage).status_code == 401
    assert reader.get(usage, params={"workspace_team": second}).status_code == 404
    assert reader.get(usage, params={"workspace_owner": owner_id}).status_code == 404

    personal = upload(client, "blue").raise_for_status().json()
    team_assets = [
        client.put(f"{team}/assets/{uuid4()}", params={"filename": name}, content=picture("blue"))
        .raise_for_status()
        .json()
        for name in ("first.png", "repeat.png")
    ]
    assert team_assets[0]["id"] == team_assets[1]["id"]
    size = personal["size"]
    expected = {
        "usedBytes": size,
        "remainingBytes": settings.asset_quota_bytes - size,
        "limitBytes": settings.asset_quota_bytes,
    }
    assert client.get(usage).raise_for_status().json() == expected
    assert reader.get(usage, params={"workspace_team": first}).raise_for_status().json() == expected
    assert client.get(usage, params={"workspace_team": second}).json()["usedBytes"] == 0
    assert reader.get(usage).json()["usedBytes"] == 0
    client.put("/api/v1/workspace/shares/by-name/usage-reader").raise_for_status()
    assert reader.get(usage, params={"workspace_owner": owner_id}).json() == expected

    client.delete(
        f"/api/v1/assets/{team_assets[0]['id']}/library", params={"workspace_team": first}
    ).raise_for_status()
    assert reader.get(usage, params={"workspace_team": first}).json()["usedBytes"] == 0
    assert client.get(usage).json() == expected


def test_asset_quota_and_expiry_preserve_task_references(prepared, settings):
    client, _, _, _, _, bound, body, _ = prepared
    task = client.post("/api/v1/tasks", json=body)
    assert task.status_code == 201
    unused = upload(client).json()
    with Session(client.app.state.engine) as db:
        for asset_id in [bound["id"], unused["id"]]:
            db.get(Asset, asset_id).created_at = (
                now_ms() - 2 * settings.unused_asset_ttl_seconds * 1000
            )
        db.commit()
        expire_unused_assets(db, settings)
        assert db.get(Asset, unused["id"]) is None
        assert db.get(Asset, bound["id"]) is not None
    assert client.get(bound["media"]["src"]).status_code == 200
    assert client.get(unused["media"]["src"]).status_code == 404
    assert client.delete(f"/api/v1/assets/{bound['id']}").status_code == 409
    settings.asset_quota_bytes = bound["size"]
    before = set(settings.original_dir.iterdir())
    assert upload(client).status_code == 413
    assert set(settings.original_dir.iterdir()) == before


def test_only_owner_can_delete_unbound_asset(authenticated):
    client = authenticated
    asset = upload(client).json()
    anonymous = TestClient(client.app)
    assert anonymous.delete(f"/api/v1/assets/{asset['id']}").status_code == 401
    other = TestClient(client.app, headers={"Origin": "http://testserver"})
    session = other.post(
        "/api/v1/auth/register", json={"username": "other-owner", "password": "password-long"}
    ).json()
    other.headers["X-CSRF-Token"] = session["csrfToken"]
    assert other.delete(f"/api/v1/assets/{asset['id']}").status_code == 404
    assert client.delete(f"/api/v1/assets/{asset['id']}").status_code == 204
    assert client.get(asset["media"]["src"]).status_code == 404


def test_library_lists_and_filters_only_the_current_accounts_saved_assets(authenticated):
    client = authenticated
    png = (
        client.put(
            f"/api/v1/assets/{uuid4()}",
            params={"filename": "label_100%.png", "save_to_library": True},
            content=picture("blue"),
        )
        .raise_for_status()
        .json()
    )
    jpeg = (
        client.put(
            f"/api/v1/assets/{uuid4()}",
            params={"filename": "portrait.jpg"},
            content=picture("red", format_="JPEG"),
        )
        .raise_for_status()
        .json()
    )
    assert client.get("/api/v1/assets").json()["items"] == [png]
    jpeg_url = f"/api/v1/assets/{jpeg['id']}/library"
    saved = client.put(jpeg_url).raise_for_status().json()
    assert client.put(jpeg_url).json() == saved
    assert (
        client.put(
            f"/api/v1/assets/{uuid4()}",
            params={"filename": "duplicate.png", "save_to_library": True},
            content=picture("blue"),
        ).json()
        == png
    )

    first = client.get("/api/v1/assets", params={"limit": 1}).raise_for_status().json()
    second = (
        client.get("/api/v1/assets", params={"limit": 1, "cursor": first["nextCursor"]})
        .raise_for_status()
        .json()
    )
    assert first["nextCursor"] and second["nextCursor"] is None
    assert {item["id"] for item in first["items"] + second["items"]} == {png["id"], jpeg["id"]}
    assert client.get("/api/v1/assets", params={"search": "%"}).json()["items"] == [png]
    assert client.get("/api/v1/assets", params={"kind": "video"}).json()["items"] == []
    formats = [("content_types", "image/jpeg"), ("content_types", "video/mp4")]
    assert client.get("/api/v1/assets", params=formats).json()["items"] == [saved]

    other = TestClient(client.app, headers={"Origin": "http://testserver"})
    assert other.get("/api/v1/assets").status_code == 401
    session = other.post(
        "/api/v1/auth/register", json={"username": "library-other", "password": "password-long"}
    ).json()
    other.headers["X-CSRF-Token"] = session["csrfToken"]
    assert other.get("/api/v1/assets").json()["items"] == []
    assert other.get(png["media"]["src"]).status_code == 404
    assert other.put(jpeg_url).status_code == other.delete(jpeg_url).status_code == 404
    assert client.delete(jpeg_url).status_code == 204
    assert client.get(saved["media"]["src"]).status_code == 404
    assert client.get("/api/v1/assets").json()["items"] == [png]


def test_library_preserves_assets_after_task_deletion_and_charges_quota(prepared, settings):
    client, _, _, _, _, bound, body, _ = prepared
    task = client.post("/api/v1/tasks", json=body).raise_for_status().json()
    assert client.post(f"/api/v1/tasks/{task['id']}/cancel").status_code == 200
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204
    library_url = f"/api/v1/assets/{bound['id']}/library"
    assert client.put(library_url).status_code == 200
    with Session(client.app.state.engine) as db:
        stale = now_ms() - 2 * settings.unused_asset_ttl_seconds * 1000
        db.get(Asset, bound["id"]).created_at = stale
        db.get(Task, task["id"]).deleted_at = stale
        db.commit()
        expire_unused_assets(db, settings)

    settings.asset_quota_bytes = bound["size"] + len(picture("white")) - 1
    assert upload(client).status_code == 413
    assert client.delete(library_url).status_code == 204
    inputs = client.get(f"/api/v1/tasks/{task['id']}/inputs").raise_for_status().json()
    assert inputs["assets"][0]["id"] == bound["id"]
    assert client.get(bound["media"]["src"]).status_code == 200
    assert upload(client).status_code == 200
    assert client.put(library_url).status_code == 413
    assert client.get("/api/v1/assets").json()["items"] == []
    with Session(client.app.state.engine) as db:
        expire_unused_assets(db, settings)
    assert client.get(bound["media"]["src"]).status_code == 404


def test_concurrent_uploads_cannot_exceed_account_quota(authenticated, settings):
    from concurrent.futures import ThreadPoolExecutor

    colors = ["red", "blue"]
    settings.asset_quota_bytes = max(len(picture(color)) for color in colors)
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(lambda color: upload(authenticated, color).status_code, colors))
    assert statuses == [200, 413]
    with Session(authenticated.app.state.engine) as db:
        delete_pending_originals(db, settings.media_storage)
    assert len(list(settings.original_dir.iterdir())) == 1


def test_file_cleanup_failure_does_not_stop_background_maintenance(
    authenticated, settings, monkeypatch, caplog
):
    asset = upload(authenticated).json()
    with Session(authenticated.app.state.engine) as db:
        record = db.get(Asset, asset["id"])
        path = settings.original_dir / record.media.storage_name
        record.created_at = now_ms() - 2 * settings.unused_asset_ttl_seconds * 1000
        db.commit()
        unlink = Path.unlink

        def unavailable(file, **kwargs):
            if file == path:
                raise PermissionError("storage unavailable")
            return unlink(file, **kwargs)

        monkeypatch.setattr(Path, "unlink", unavailable)
        expire_unused_assets(db, settings)
        assert db.get(Asset, asset["id"]) is None
        assert path.is_file() and db.get(OriginalDeletion, path.name) is None
        retire_unreferenced_originals(db)
        delete_pending_originals(db, settings.media_storage)
        assert "媒体原文件清理失败" in caplog.text
        pending = db.get(OriginalDeletion, path.name)
        assert pending and path.is_file()

        monkeypatch.setattr(Path, "unlink", unlink)
        pending.retry_at = 0
        db.commit()
        delete_pending_originals(db, settings.media_storage)
        assert db.get(OriginalDeletion, path.name) is None
        assert not path.exists()


def test_the_same_file_is_staged_on_the_volume_and_stored_once(
    authenticated, settings, monkeypatch
):
    put = settings.media_storage.put
    staged = []

    def measure(name, source, content_type):
        assert source.is_relative_to(settings.data_dir / "staging")
        put(name, source, content_type)
        assert source.samefile(settings.original_dir / name)
        staged.append(source.parent)

    monkeypatch.setattr(settings.media_storage, "put", measure)
    first = upload(authenticated, "green").json()
    again = upload(authenticated, "green")
    assert again.status_code == 200 and again.json()["id"] == first["id"]
    assert len(list(settings.original_dir.iterdir())) == 1
    assert len(staged) == 1 and not staged[0].exists()


@pytest.mark.parametrize("committed", [False, True])
def test_upload_database_failure_only_reclaims_uncommitted_originals(
    authenticated, settings, monkeypatch, committed
):
    commit = Session.commit

    def interrupted(db):
        if any(isinstance(record, Asset) for record in db.new):
            if committed:
                commit(db)
            raise OperationalError("COMMIT", None, RuntimeError("lost connection"))
        return commit(db)

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", interrupted)
        with pytest.raises(OperationalError):
            upload(authenticated)
    with Session(authenticated.app.state.engine) as db:
        delete_pending_originals(db, settings.media_storage)
        asset = db.scalar(select(Asset))
        assert bool(asset) == committed
        assert list(db.scalars(select(OriginalDeletion.storage_name))) == []
        files = list(settings.original_dir.iterdir())
        assert len(files) == int(committed)
        if committed:
            assert files[0].read_bytes() == picture("white")


def test_abandoned_upload_reservation_survives_an_active_sweep(authenticated, settings):
    storage = settings.media_storage
    stage = storage.staging_directory()
    with Session(authenticated.app.state.engine) as db:
        with stage as directory:
            source = Path(directory) / uuid4().hex
            source.write_bytes(picture())
            db.add(OriginalDeletion(storage_name=source.name, retry_at=UPLOAD_PENDING))
            db.commit()
            storage.put(source.name, source, "image/png")
            storage.prune_abandoned_staging(lambda _: pytest.fail("active upload reclaimed"))
            delete_pending_originals(db, storage)
            assert storage.original_path(source.name).read_bytes() == picture()
            stage.keep_for_recovery = True
        storage.prune_abandoned_staging(
            lambda path: release_uploads(db, [p.name for p in path.iterdir()])
        )
        delete_pending_originals(db, storage)
        assert not source.parent.exists()
        assert not (settings.original_dir / source.name).exists()


def test_accounts_reuse_original_and_thumbnail_bytes_without_sharing_access(
    authenticated, settings, monkeypatch
):
    owner = authenticated
    other = TestClient(owner.app, headers={"Origin": "http://testserver"})
    session = other.post(
        "/api/v1/auth/register", json={"username": "other-owner", "password": "password-long"}
    )
    assert session.status_code == 201
    other.headers["X-CSRF-Token"] = session.json()["csrfToken"]
    with BytesIO() as output:
        Image.new("RGB", (1024, 768), "green").save(output, "PNG")
        content = output.getvalue()

    def upload_to(client):
        response = client.put(
            f"/api/v1/assets/{uuid4()}", params={"filename": "reference.png"}, content=content
        )
        assert response.status_code == 200
        return response.json()

    with ThreadPoolExecutor(2) as pool:
        first, second = pool.map(upload_to, (owner, other))
    assert first["id"] != second["id"]
    digest = first["sha256"]
    engine = owner.app.state.engine
    with Session(engine) as db:
        original = settings.original_dir / db.get(MediaObject, digest).storage_name
        assert set(db.scalars(select(Asset.id).where(Asset.sha256 == digest))) == {
            first["id"],
            second["id"],
        }
        delete_pending_originals(db, settings.media_storage)
    assert len(list(settings.original_dir.iterdir())) == 1

    image = renditions._image
    decoded = []

    def measure(path, sizes):
        decoded.append(sizes)
        return image(path, sizes)

    monkeypatch.setattr(renditions, "_image", measure)
    first_thumbnail = first["media"]["thumbnail"]["src"]
    second_thumbnail = second["media"]["thumbnail"]["src"]
    result = owner.get(first_thumbnail, params={"size": 384})
    assert result.status_code == 200
    with Image.open(BytesIO(result.content)) as thumbnail:
        assert thumbnail.size == (384, 288)
    assert other.get(second_thumbnail, params={"size": 512}).status_code == 200
    assert decoded == [[384, 512]]
    conditional = {"If-None-Match": result.headers["etag"]}
    assert owner.get(first_thumbnail, params={"size": 384}, headers=conditional).status_code == 304
    assert other.get(first_thumbnail, params={"size": 384}, headers=conditional).status_code == 404

    assert owner.delete(f"/api/v1/assets/{first['id']}").status_code == 204
    with Session(engine) as db:
        retire_unreferenced_originals(db)
        delete_pending_originals(db, settings.media_storage)
        assert db.get(MediaObject, digest)
    assert other.get(second["media"]["src"]).content == content
    assert other.delete(f"/api/v1/assets/{second['id']}").status_code == 204
    assert original.is_file()
    with Session(engine) as db:
        retire_unreferenced_originals(db)
        assert db.get(MediaObject, digest) is None
        assert db.get(OriginalDeletion, original.name)
    # 后台尚未删物理文件时重新上传同一内容，新登记使用独立键。
    third = upload_to(owner)
    with Session(engine) as db:
        delete_pending_originals(db, settings.media_storage)
    assert not original.exists()
    assert owner.get(third["media"]["src"]).content == content


def test_deleting_the_task_releases_its_assets(prepared, settings):
    client, _, _, _, _, bound, body, _ = prepared
    task = client.post("/api/v1/tasks", json=body).json()
    assert client.post(f"/api/v1/tasks/{task['id']}/cancel").status_code == 200
    settings.asset_quota_bytes = bound["size"] + len(picture("white")) - 1
    usage = "/api/v1/assets/usage"
    assert client.get(usage).json()["usedBytes"] == bound["size"]
    assert upload(client).status_code == 413
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204
    assert client.get(usage).json()["usedBytes"] == 0
    assert client.post(f"/api/v1/tasks/{task['id']}/restore").status_code == 204
    assert client.get(usage).json()["usedBytes"] == bound["size"]
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204
    # 删除任务后它引用的素材不再计入配额，文件等过了保留期再清理，撤销删除仍可用。
    assert upload(client).status_code == 200
    with Session(client.app.state.engine) as db:
        expire_unused_assets(db, settings)
        assert db.get(Asset, bound["id"]) is not None
        record = db.get(Task, task["id"])
        record.deleted_at = now_ms() - 2 * settings.unused_asset_ttl_seconds * 1000
        db.get(Asset, bound["id"]).created_at = record.deleted_at
        db.commit()
        expire_unused_assets(db, settings)
        assert db.get(Asset, bound["id"]) is None
    assert client.get(bound["media"]["src"]).status_code == 404


def test_an_upload_waiting_for_the_write_lock_does_not_stall_the_server(prepared, monkeypatch):
    """上传在线程里等写锁。另一个请求持锁后才报错时，锁能及时释放，上传不会等到超时。"""
    import asyncio
    import time

    import httpx

    from comfyshop_api.db import write_lock
    from comfyshop_api.services import tasks as task_service

    client, _, _, _, _, _, body, _ = prepared
    task = client.post("/api/v1/tasks", json=body).json()
    original = task_service.delete_task

    def hold_then_refuse(db, record):
        # 排队中的任务不能删除：先持有写锁一会儿，再按原逻辑返回 409。
        write_lock(db, Task, record.id)
        time.sleep(0.5)
        return original(db, record)

    monkeypatch.setattr(task_service, "delete_task", hold_then_refuse)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=client.app),
            base_url="http://testserver",
            headers=dict(client.headers),
            cookies=dict(client.cookies.items()),
        ) as browser:

            async def upload():
                await asyncio.sleep(0.2)
                started = time.perf_counter()
                response = await browser.put(
                    f"/api/v1/assets/{uuid4()}",
                    params={"filename": "w.png"},
                    content=picture("white"),
                )
                return time.perf_counter() - started, response.status_code

            refused, (elapsed, status) = await asyncio.gather(
                browser.delete(f"/api/v1/tasks/{task['id']}"), upload()
            )
            assert refused.status_code == 409
            assert status == 200 and elapsed < 3

    asyncio.run(run())


def test_reusing_a_released_asset_takes_quota_again(prepared, settings):
    client, _, _, _, _, bound, body, _ = prepared
    task = client.post("/api/v1/tasks", json=body).json()
    client.post(f"/api/v1/tasks/{task['id']}/cancel")
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204
    settings.asset_quota_bytes = bound["size"] + len(picture("white")) - 1
    # 释放出来的空间用来上传别的文件后，旧素材不能再不占配额地拿回来。
    assert upload(client).status_code == 200
    again = client.put(
        f"/api/v1/assets/{uuid4()}", params={"filename": "image.png"}, content=picture()
    )
    assert again.status_code == 413
    resubmit = client.post("/api/v1/tasks", json={**body, "idempotencyKey": str(uuid4())})
    assert resubmit.status_code == 413
    # 撤销删除同样要让旧素材重新占用配额，放不下时任务保持删除。
    assert client.post(f"/api/v1/tasks/{task['id']}/restore").status_code == 413
    settings.asset_quota_bytes = bound["size"] + len(picture("white"))
    assert client.post(f"/api/v1/tasks/{task['id']}/restore").status_code == 204


@pytest.mark.parametrize("save_to_library", [False, True], ids=["reupload", "save"])
def test_an_asset_saved_during_cleanup_survives(
    authenticated, settings, monkeypatch, save_to_library
):
    client = authenticated
    first = upload(client, "green").json()
    with Session(client.app.state.engine) as db:
        db.get(Asset, first["id"]).created_at = (
            now_ms() - 2 * settings.unused_asset_ttl_seconds * 1000
        )
        db.commit()
    execute = Session.execute
    raced = []

    def upload_between_select_and_delete(self, statement, *args, **kwargs):
        if not raced and getattr(statement, "is_delete", False):
            response = (
                client.put(f"/api/v1/assets/{first['id']}/library")
                if save_to_library
                else upload(client, "green")
            )
            raced.append(response.raise_for_status().json()["id"])
        return execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", upload_between_select_and_delete)
    with Session(client.app.state.engine) as db:
        expire_unused_assets(db, settings)
    monkeypatch.setattr(Session, "execute", execute)
    # 清理选出它之后重新上传或保存，返回的素材 ID 必须仍然可用。
    assert raced == [first["id"]]
    assert client.get(f"/api/v1/assets/{first['id']}").status_code == 200


def test_resuming_needs_the_machine_and_the_assets(prepared, settings):
    client, _, _, _, _, bound, body, _ = prepared
    first = client.post("/api/v1/tasks", json=body).json()
    client.post(f"/api/v1/tasks/{first['id']}/cancel")
    # 素材过了保留期被清理后，恢复删除的任务不能回到队列。
    assert client.delete(f"/api/v1/tasks/{first['id']}").status_code == 204
    with Session(client.app.state.engine) as db:
        stale = now_ms() - 2 * settings.unused_asset_ttl_seconds * 1000
        db.get(Task, first["id"]).deleted_at = stale
        db.get(Asset, bound["id"]).created_at = stale
        db.commit()
        expire_unused_assets(db, settings)
    assert client.post(f"/api/v1/tasks/{first['id']}/restore").status_code == 204
    resumed = client.post(f"/api/v1/tasks/{first['id']}/resume")
    assert resumed.status_code == 409 and "素材" in resumed.json()["detail"]

    asset = upload(client, "blue").json()
    field = next(key for key, value in body["inputValues"].items() if isinstance(value, dict))
    second = client.post(
        "/api/v1/tasks",
        json={
            **body,
            "idempotencyKey": str(uuid4()),
            "inputValues": {**body["inputValues"], field: {"assetId": asset["id"]}},
        },
    ).json()
    client.post(f"/api/v1/tasks/{second['id']}/cancel")
    # 取消后工作机被撤销，恢复排队会永远等不到工作机。
    assert client.delete(f"/api/v1/machines/{second['machineId']}").status_code == 200
    resumed = client.post(f"/api/v1/tasks/{second['id']}/resume")
    assert resumed.status_code == 409 and "工作机" in resumed.json()["detail"]
