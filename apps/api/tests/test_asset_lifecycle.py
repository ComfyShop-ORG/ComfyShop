from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from comfyshop_api.models import Asset, MediaObject, OriginalDeletion, Task, now_ms
from comfyshop_media import renditions
from comfyshop_api.services.assets import expire_unused_assets
from comfyshop_api.services.originals import (
    UPLOAD_PENDING,
    delete_pending_originals,
    release_uploads,
    retire_unreferenced_originals,
)
from test_inputs import picture
from test_inputs import prepared as prepared


def upload(client, color="white"):
    return client.put(
        f"/api/v1/assets/{uuid4()}", params={"filename": "image.png"}, content=picture(color)
    )


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
    assert upload(client).status_code == 413
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


def test_an_asset_uploaded_again_during_cleanup_survives(authenticated, settings, monkeypatch):
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
            raced.append(upload(client, "green").json()["id"])
        return execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", upload_between_select_and_delete)
    with Session(client.app.state.engine) as db:
        expire_unused_assets(db, settings)
    monkeypatch.setattr(Session, "execute", execute)
    # 清理选出它之后，同一文件又被上传并刷新了保留期，返回的素材 ID 必须仍然可用。
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
