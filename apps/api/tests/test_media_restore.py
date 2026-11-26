import hashlib
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_inputs import picture

from comfyshop_api.core.config import Settings
from comfyshop_api.db import make_engine
from comfyshop_api.models import (
    Artifact,
    Asset,
    Execution,
    MediaObject,
    Status,
    Task,
    TaskAsset,
    User,
    Work,
    WorkArtifact,
    Workflow,
    WorkflowVersion,
)
from comfyshop_api.restore_data import restore
from comfyshop_api.services.executions import finish_execution

INI = Path(__file__).parents[1] / "alembic.ini"
REFERENCE = "input-image"
OUTPUT = "output-image"


def migrate(settings: Settings) -> None:
    config = Config(str(INI))
    config.attributes["database_url"] = settings.database_dsn
    command.upgrade(config, "head")


def seed_library(settings: Settings) -> tuple[str, str]:
    migrate(settings)
    settings.original_dir.mkdir(parents=True)
    media = []
    for name, color in [(REFERENCE, "red"), (OUTPUT, "blue")]:
        content = picture(color)
        (settings.original_dir / name).write_bytes(content)
        media.append(
            MediaObject(
                storage_name=name,
                sha256=hashlib.sha256(content).hexdigest(),
                size=len(content),
                content_type="image/png",
                width=32,
                height=48,
            )
        )

    engine = make_engine(settings.database_dsn)
    with Session(engine) as db:
        user = User(username="owner", username_key="owner", password_hash="unused")
        db.add(user)
        db.flush()
        workflow = Workflow(owner_id=user.id, name="media")
        db.add(workflow)
        db.flush()
        version = WorkflowVersion(
            workflow_id=workflow.id,
            number=1,
            graph={},
            graph_hash="0" * 64,
            format="api",
            requirements=[],
        )
        db.add(version)
        db.flush()
        task = Task(
            owner_id=user.id,
            workflow_id=workflow.id,
            version_id=version.id,
            workflow_name=workflow.name,
            input_values={},
            input_schema={},
            input_graph={},
            status=Status.SUCCEEDED,
            progress=100,
            idempotency_key="request",
            request_hash="0" * 64,
        )
        db.add(task)
        db.flush()
        execution = Execution(task_id=task.id, index=0, input_values={}, status=Status.RUNNING)
        asset = Asset(
            id=str(uuid4()),
            owner_id=user.id,
            filename="input.png",
            content_type=media[0].content_type,
            media=media[0],
        )
        db.add_all([execution, asset])
        db.flush()
        artifacts = [
            Artifact(
                task_id=task.id,
                execution_id=execution.id,
                owner_id=user.id,
                client_id=f"output-{index}",
                filename=f"output-{index}.png",
                content_type=original.content_type,
                media=original,
                output_index=index,
            )
            for index, original in enumerate(media)
        ]
        db.add_all(artifacts)
        db.flush()
        finish_execution(db, execution, [artifact.client_id for artifact in artifacts])
        work = Work(
            owner_id=user.id,
            workflow_id=workflow.id,
            version_id=version.id,
            execution_id=execution.id,
            title="work",
            request_hash="0" * 64,
            cover_artifact_id=artifacts[0].id,
        )
        db.add_all(
            [work, TaskAsset(task_id=task.id, node_id="1", input_name="image", asset_id=asset.id)]
        )
        db.flush()
        db.add_all(
            WorkArtifact(work_id=work.id, artifact_id=artifact.id, position=index)
            for index, artifact in enumerate(artifacts)
        )
        ids = (asset.id, artifacts[0].id)
        db.commit()
    engine.dispose()
    return ids


def assert_references(settings: Settings, ids: tuple[str, str]) -> None:
    asset_id, artifact_id = ids
    engine = make_engine(settings.database_dsn)
    with Session(engine) as db:
        assert db.get(Asset, asset_id).media is db.get(Artifact, artifact_id).media
        assert db.scalar(select(TaskAsset.asset_id)) == asset_id
        assert db.scalar(select(Work.cover_artifact_id)) == artifact_id
        members = db.scalars(select(WorkArtifact.artifact_id).order_by(WorkArtifact.position)).all()
        assert len(members) == 2 and members[0] == artifact_id
    engine.dispose()
    storage = settings.media_storage
    assert storage.restore_inventory([REFERENCE, OUTPUT]) == {REFERENCE, OUTPUT}
    with storage.local_original(REFERENCE) as path:
        assert path.read_bytes() == picture("red")
    with storage.local_original(OUTPUT) as path:
        assert path.read_bytes() == picture("blue")


@pytest.fixture
def backup(tmp_path: Path) -> tuple[Path, Settings, tuple[str, str]]:
    source = Settings(
        data_dir=tmp_path / "source",
        database_url=f"sqlite:///{tmp_path / 'source/comfyshop.db'}",
        storage_backend="local",
    )
    ids = seed_library(source)
    archive = tmp_path / "backup.tar"
    with tarfile.open(archive, "w") as output:
        output.add(source.data_dir, arcname=".")
    return archive, source, ids


@pytest.fixture
def target(tmp_path: Path, pg_url: str) -> Settings:
    settings = Settings(data_dir=tmp_path / "target", database_url=pg_url, storage_backend="local")
    migrate(settings)
    return settings


def test_restore_keeps_media_and_business_references(backup, target):
    archive, _source, ids = backup
    with archive.open("rb") as stream:
        counts = restore(stream, target, INI)
    assert counts["media_objects"] == counts["artifacts"] == 2
    assert counts["assets"] == counts["works"] == 1
    assert_references(target, ids)


@pytest.mark.parametrize("committed", [False, True])
def test_restore_final_commit_preserves_only_registered_files(tmp_path, backup, target, committed):
    archive, source, ids = backup
    target_url = make_url(target.database_dsn)
    failed = False

    def fail_commit(conn):
        nonlocal failed
        if conn.engine.url == target_url and not failed:
            failed = True
            if committed:
                conn.connection.commit()
            raise OperationalError("COMMIT", None, RuntimeError("lost connection"))

    event.listen(Engine, "commit", fail_commit)
    try:
        with archive.open("rb") as stream:
            if committed:
                assert restore(stream, target, INI)["media_objects"] == 2
            else:
                with pytest.raises(OperationalError):
                    restore(stream, target, INI)
    finally:
        event.remove(Engine, "commit", fail_commit)
    if not committed:
        storage = target.media_storage
        storage.ensure_empty()
        # 上次中断的 PUT 可能已经到达存储。重试时只复用校验通过的原件。
        reference = source.original_dir / REFERENCE
        invalid = tmp_path / "invalid-original"
        invalid.write_bytes(b"\0" * reference.stat().st_size)
        storage.put("foreign", invalid, "image/png")
        with archive.open("rb") as stream, pytest.raises(ValueError, match="清单以外"):
            restore(stream, target, INI)
        assert (target.original_dir / "foreign").read_bytes() == invalid.read_bytes()
        storage.delete("foreign")
        storage.put(REFERENCE, invalid, "image/png")
        with archive.open("rb") as stream, pytest.raises(ValueError, match="与备份不符"):
            restore(stream, target, INI)
        assert (target.original_dir / REFERENCE).read_bytes() == invalid.read_bytes()
        storage.delete(REFERENCE)
        storage.put(REFERENCE, reference, "image/png")
        with archive.open("rb") as stream:
            assert restore(stream, target, INI)["media_objects"] == 2
    assert_references(target, ids)
