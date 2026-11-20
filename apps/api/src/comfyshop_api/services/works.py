"""管理作品公开的成品、参数和参考素材。"""

import json

from fastapi import HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from comfyshop_api.core.config import Settings
from comfyshop_api.db import write_lock
from comfyshop_api.models import (
    Status,
    Artifact,
    Asset,
    Execution,
    MediaObject,
    Task,
    TaskAsset,
    User,
    Work,
    WorkArtifact,
    WorkAsset,
    Workflow,
    WorkflowVersion,
    new_id,
)
from comfyshop_api.schemas import (
    MEDIA_INPUT_KINDS,
    AssetReference,
    AuthorRead,
    CoverUpdate,
    InputValue,
    WorkCreate,
    WorkRead,
)
from comfyshop_api.security import digest
from comfyshop_api.services.artifacts import lock_execution_media
from comfyshop_api.services.assets import reuse_shared_asset
from comfyshop_api.services.covers import (
    checked_cover_image,
    cover_from_asset,
    validate_cover_frame,
)
from comfyshop_api.services.executions import owned_execution
from comfyshop_api.services.media_records import (
    artifact_media,
    cover_image_read,
    detach_media_record,
    media_kind,
    preferred_cover,
)


def readable_work(db: Session, work_id: str, user_id: str | None) -> Work:
    work = db.get(Work, work_id)
    workflow = db.get(Workflow, work.workflow_id) if work else None
    if (
        not work
        or work.deleted_at is not None
        or not workflow
        or (
            work.owner_id != user_id
            and (not work.published or not workflow.published or workflow.deleted_at)
        )
    ):
        raise HTTPException(404, "作品不存在")
    return work


def readable_work_cover(db: Session, work_id: str, user_id: str | None, sha256: str) -> MediaObject:
    work = readable_work(db, work_id, user_id)
    return checked_cover_image(db, work.cover_image, sha256)


def update_work_cover(
    db: Session, work_id: str, owner_id: str, body: CoverUpdate, config: Settings
) -> Work:
    work = readable_work(db, work_id, owner_id)
    if work.owner_id != owner_id:
        raise HTTPException(404, "作品不存在")
    outputs = (
        select(Artifact)
        .join(WorkArtifact, WorkArtifact.artifact_id == Artifact.id)
        .where(WorkArtifact.work_id == work_id, Artifact.visible())
        .order_by(WorkArtifact.position)
    )
    if body.frame_ms:
        artifact = db.scalar(outputs.where(Artifact.id == body.artifact_id))
        if artifact is None:
            raise HTTPException(404, "成品不存在")
        validate_cover_frame(artifact, config, body.frame_ms)
    lock_execution_media(db, work.execution_id)
    write_lock(db, Work, work_id)
    db.refresh(work)
    if work.deleted_at is not None:
        raise HTTPException(404, "作品不存在")
    if body.asset_id is not None:
        work.cover_image = cover_from_asset(db, body.asset_id, owner_id)
        return work
    if body.artifact_id is not None:
        artifact = db.scalar(outputs.where(Artifact.id == body.artifact_id))
        if artifact is None:
            raise HTTPException(404, "成品不存在")
        if media_kind(artifact.media.content_type) not in {"image", "video"}:
            raise HTTPException(422, "请选择图片或视频画面作封面")
        work.cover_artifact_id = artifact.id
        work.cover_frame_ms = body.frame_ms or None
    else:
        members = db.scalars(outputs).all()
        if not members:
            raise HTTPException(404, "作品中没有可用的成品")
        work.cover_artifact_id = preferred_cover(members).id
        work.cover_frame_ms = None
    work.cover_image = None
    return work


def public_work_condition():
    return (
        Work.visible()
        & Work.published.is_(True)
        & Workflow.published.is_(True)
        & Workflow.visible()
    )


def restore_deleted_work(db: Session, work: Work) -> None:
    """在成品写锁内恢复作品。引用的成品已删除时返回 409，由调用方提交。"""
    lock_execution_media(db, work.execution_id)
    db.refresh(work)
    if work.deleted_at is None:
        return
    missing = (
        select(Artifact.id)
        .join(WorkArtifact, WorkArtifact.artifact_id == Artifact.id)
        .where(WorkArtifact.work_id == work.id, ~Artifact.visible())
        .exists()
    )
    if db.scalar(select(missing)):
        raise HTTPException(409, "作品中的成品已删除，请先恢复成品")
    work.restore()


def artifact_public(db: Session, artifact_id: str) -> bool:
    """成品是否被某个公开作品选中。调用方还需检查所属执行已经成功。"""
    return bool(
        db.scalar(
            select(
                exists(
                    select(WorkArtifact.artifact_id)
                    .join(Work)
                    .join(Workflow)
                    .where(WorkArtifact.artifact_id == artifact_id, public_work_condition())
                )
            )
        )
    )


def work_assets(db: Session, work_id: str) -> list[WorkAsset]:
    """读取已通过权限检查的作品公开的参考文件。"""
    return list(
        db.scalars(select(WorkAsset).where(WorkAsset.work_id == work_id).order_by(WorkAsset.id))
    )


def readable_work_asset(db: Session, work_id: str, asset_id: str, user_id: str | None) -> WorkAsset:
    """按作品权限校验参考素材，读取文件前释放数据库事务。"""
    readable_work(db, work_id, user_id)
    asset = db.get(WorkAsset, asset_id)
    if asset is None or asset.work_id != work_id:
        raise HTTPException(404, "作品素材不存在")
    detach_media_record(db, asset)
    return asset


def reuse_work_inputs(
    db: Session, work: Work, owner_id: str, values: dict[str, InputValue]
) -> tuple[dict[str, InputValue], bool]:
    """在接收账号锁内把本次选用的作品素材转为该账号的素材，由任务提交事务保存。"""
    references = {
        field_id: value.asset_id
        for field_id, value in values.items()
        if isinstance(value, AssetReference)
        and work.input_values.get(field_id) == {"assetId": value.asset_id}
    }
    if not references:
        return values, False
    wanted = set(references.values())
    shares = [asset for asset in work_assets(db, work.id) if asset.id in wanted]
    if len(shares) != len(wanted):
        raise HTTPException(404, "作品素材不存在")
    copies: dict[str, str] = {}
    includes_new = False
    for shared in shares:
        asset, created = reuse_shared_asset(db, owner_id, shared)
        copies[shared.id] = asset.id
        includes_new |= created
    return values | {
        field_id: AssetReference(asset_id=copies[asset_id])
        for field_id, asset_id in references.items()
    }, includes_new


def work_reads(db: Session, works: list[Work]) -> list[WorkRead]:
    if not works:
        return []
    covers = {
        a.id: a
        for a in db.scalars(
            select(Artifact).where(Artifact.id.in_([w.cover_artifact_id for w in works]))
        )
    }
    owners = {
        u.id: AuthorRead.from_user(u)
        for u in db.scalars(select(User).where(User.id.in_([w.owner_id for w in works])))
    }
    sources = {
        execution_id: (name, category)
        for execution_id, name, category in db.execute(
            select(Execution.id, Task.workflow_name, Workflow.category)
            .select_from(Execution)
            .join(Task, Task.id == Execution.task_id)
            .join(Workflow, Workflow.id == Task.workflow_id)
            .where(Execution.id.in_([w.execution_id for w in works]))
        )
    }
    counts: dict[str, int] = dict(
        db.execute(
            select(WorkArtifact.work_id, func.count())
            .where(WorkArtifact.work_id.in_([w.id for w in works]))
            .group_by(WorkArtifact.work_id)
        )
        .tuples()
        .all()
    )
    return [
        WorkRead(
            id=w.id,
            title=w.title,
            author=owners[w.owner_id].username,
            author_profile=owners[w.owner_id],
            owner=w.owner_id,
            workflow_id=w.workflow_id,
            workflow_name=sources[w.execution_id][0],
            category=sources[w.execution_id][1],
            version_id=w.version_id,
            execution_id=w.execution_id,
            cover_artifact_id=w.cover_artifact_id,
            cover_frame_ms=w.cover_frame_ms,
            cover_image=cover_image_read("works", w.id, w.cover_image),
            media=artifact_media(covers[w.cover_artifact_id], w.cover_frame_ms),
            asset_count=counts[w.id],
            published=w.published,
            input_values=w.input_values,
            created=w.created_at,
            description=w.description or "",
        )
        for w in works
    ]


def _published_before(db: Session, work_id: str, user_id: str, request_hash: str) -> Work | None:
    """返回同一发布编号已保存的作品。归属或内容不同、作品已删除返回 HTTP 409。"""
    prior = db.get(Work, work_id)
    if prior is None:
        return None
    if prior.owner_id != user_id or prior.request_hash != request_hash:
        raise HTTPException(409, "重复发布的内容不一致")
    if prior.deleted_at is not None:
        raise HTTPException(409, "作品已删除")
    return prior


def _publication_inputs(
    db: Session, work_id: str, execution: Execution, task: Task, share_assets: bool
) -> tuple[dict, list[WorkAsset]]:
    fields = task.input_schema.get("fields", [])
    scalar_ids = {field["id"] for field in fields if field["kind"] not in MEDIA_INPUT_KINDS}
    values = {
        key: value
        for key, value in execution.input_values.items()
        if key in scalar_ids and type(value) in {str, int, float, bool}
    }
    media_fields = [field for field in fields if field["kind"] in MEDIA_INPUT_KINDS]
    if not share_assets or not media_fields:
        return values, []

    # 发布时核对执行快照与原任务的素材绑定。等待提交时保留对应原件。
    bindings = {
        (node, name): asset
        for node, name, asset in db.execute(
            select(TaskAsset.node_id, TaskAsset.input_name, Asset)
            .join(Asset, Asset.id == TaskAsset.asset_id)
            .where(TaskAsset.task_id == task.id, Asset.owner_id == task.owner_id)
            .with_for_update(read=True, key_share=True, of=Asset)
        )
    }
    published: dict[str, WorkAsset] = {}
    for field in media_fields:
        asset = bindings.get((field["node_id"], field["input_name"]))
        if asset is None or execution.input_values.get(field["id"]) != {"assetId": asset.id}:
            raise HTTPException(409, "部分参考素材已不可用，请调整公开范围")
        if asset.id not in published:
            published[asset.id] = WorkAsset(
                id=new_id(), work_id=work_id, filename=asset.filename, sha256=asset.sha256
            )
        values[field["id"]] = {"assetId": published[asset.id].id}
    return values, list(published.values())


def publish_work(
    db: Session, user_id: str, body: WorkCreate, config: Settings
) -> tuple[Work, bool]:
    """从本人一次成功执行的所选成品建立作品，返回作品及是否新建。

    相同发布编号和内容返回原作品。执行未成功、来源版本或工作流未发布返回 HTTP 409，
    成品不属于此次执行返回 404，成品重复或未公开的封面成品不是图片返回 422。
    """
    # 禁用素材共享时保持旧发布请求的哈希，跨版本重试仍能找到同一作品。
    share_assets = body.share_assets is True
    excluded = set() if share_assets else {"share_assets"}
    for field in ("cover_asset_id", "execution_cover_sha256"):
        if getattr(body, field) is None:
            excluded.add(field)
    payload = body.model_dump(exclude=excluded)
    request_hash = digest(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    prior = _published_before(db, body.id, user_id, request_hash)
    if prior:
        return prior, False
    execution, task = owned_execution(db, body.execution_id, user_id)
    workflow = db.get(Workflow, task.workflow_id)
    if workflow is None:
        raise HTTPException(404, "工作流不存在")
    if execution.status != Status.SUCCEEDED:
        raise HTTPException(409, "只能发布成功执行的成品")
    # 作品公开来源版本的成品和参数说明，访客还要能用同一版本重跑，草稿版本的结果不能发布。
    version = db.get(WorkflowVersion, task.version_id)
    if workflow.deleted_at is None and (version is None or not version.published):
        raise HTTPException(409, "这次结果来自未发布的工作流版本，只能发布已发布版本的结果")
    if not workflow.published or workflow.deleted_at:
        raise HTTPException(409, "请先发布工作流")
    if len(set(body.artifact_ids)) != len(body.artifact_ids):
        raise HTTPException(422, "成品不能重复")
    if body.cover_frame_ms:
        preview = db.get(Artifact, body.cover_artifact_id)
        if preview and preview.execution_id == execution.id and preview.deleted_at is None:
            # 截帧在取得写锁之前完成。
            validate_cover_frame(preview, config, body.cover_frame_ms)
    lock_execution_media(db, execution.id)
    prior = _published_before(db, body.id, user_id, request_hash)
    if prior:
        return prior, False
    members = db.scalars(
        select(Artifact).where(
            Artifact.execution_id == execution.id,
            Artifact.id.in_(body.artifact_ids),
            Artifact.visible(),
        )
    ).all()
    if len(members) != len(body.artifact_ids):
        raise HTTPException(404, "所选成品不属于此次执行")
    cover_image = None
    if body.cover_asset_id is not None:
        cover_image = cover_from_asset(db, body.cover_asset_id, user_id)
    elif body.execution_cover_sha256 is not None:
        db.refresh(execution)
        cover_image = execution.cover_image
        if cover_image is None or cover_image.sha256 != body.execution_cover_sha256:
            raise HTTPException(409, "结果封面已更换，请返回后重新确认封面")
    cover_artifact_id = body.cover_artifact_id
    if cover_artifact_id is not None and cover_artifact_id not in body.artifact_ids:
        picture = db.scalar(
            select(Artifact).where(
                Artifact.id == cover_artifact_id,
                Artifact.execution_id == execution.id,
                Artifact.visible(),
            )
        )
        if picture is None:
            raise HTTPException(404, "封面成品不属于此次执行")
        if cover_image is not None or media_kind(picture.media.content_type) != "image":
            raise HTTPException(422, "未选中公开的成品只能使用一张图片作封面")
        cover_image = picture.media
        cover_artifact_id = None
    if cover_artifact_id is None and cover_image is not None:
        by_id = {item.id: item for item in members}
        cover_artifact_id = preferred_cover([by_id[item] for item in body.artifact_ids]).id
    if cover_artifact_id is None:
        original_ids = {
            item.id for item in members if media_kind(item.media.content_type) in {"audio", "3d"}
        }
        cover_artifact_id = next((item for item in body.artifact_ids if item in original_ids), None)
        if cover_artifact_id is None:
            raise HTTPException(422, "请选择作品封面")
    values, shared = (
        _publication_inputs(db, body.id, execution, task, share_assets)
        if body.share_parameters or share_assets
        else ({}, [])
    )
    work = Work(
        id=body.id,
        owner_id=user_id,
        workflow_id=task.workflow_id,
        version_id=task.version_id,
        execution_id=execution.id,
        title=body.title.strip(),
        description=body.description.strip() or None,
        request_hash=request_hash,
        cover_artifact_id=cover_artifact_id,
        cover_frame_ms=body.cover_frame_ms or None,
        cover_image=cover_image,
        input_values=values,
    )
    db.add(work)
    try:
        db.flush()
        db.add_all(shared)
        for position, artifact_id in enumerate(body.artifact_ids):
            db.add(WorkArtifact(work_id=work.id, artifact_id=artifact_id, position=position))
        db.commit()
    except IntegrityError:
        # 并发的同编号发布由主键拦下，按已保存的那一份应答。
        db.rollback()
        prior = _published_before(db, body.id, user_id, request_hash)
        if prior is None:
            raise HTTPException(409, "重复发布的内容不一致") from None
        return prior, False
    return work, True
