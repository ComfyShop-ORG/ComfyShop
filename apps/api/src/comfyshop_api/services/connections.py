"""连接型工作机的密钥、可用范围及外部工作流导入。"""

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import msg
from comfyshop_api.models import (
    Execution,
    Machine,
    Status,
    Task,
    TeamRole,
    User,
    Workflow,
    WorkflowVersion,
    new_id,
    now_ms,
)
from comfyshop_api.schemas import ConnectionWrite, FieldWorkflow, NodeCatalog, ReferenceImport
from comfyshop_api.security import lock_session_account, owned_record, workspace_records
from comfyshop_api.services.teams import require_team
from comfyshop_api.services.worker_types import worker_type


def cipher(settings: Settings) -> Fernet:
    try:
        if settings.connection_encryption_key:
            return Fernet(settings.connection_encryption_key.get_secret_value().encode())
    except ValueError:
        pass
    raise HTTPException(503, msg("connection.encryptionRequired"))


def secret(machine: Machine, settings: Settings) -> str:
    if machine.revoked_at or machine.deleted_at or not machine.credential:
        raise HTTPException(409, msg("connection.removed"))
    try:
        return cipher(settings).decrypt(machine.credential.encode()).decode()
    except InvalidToken:
        raise HTTPException(503, msg("connection.cannotDecrypt")) from None


def matched(
    machine: Machine | None,
    kind: str,
    scope: str | None,
    owner_id: str,
    *,
    team_id: str | None = None,
) -> Machine:
    if (
        not machine
        or machine.team_id != team_id
        or (team_id is None and machine.owner_id != owner_id)
        or machine.revoked_at
        or machine.deleted_at
        or machine.worker_kind != kind
        or machine.connection_scope != scope
    ):
        raise HTTPException(409, msg("connection.workerMismatch"))
    return machine


def store_connection(
    db: Session,
    owner_id: str,
    body: ConnectionWrite,
    settings: Settings,
    machine: Machine | None = None,
    *,
    team_id: str | None = None,
) -> Machine:
    definition = worker_type(body.kind)
    if (
        definition.connection != "account"
        or body.scope not in definition.sites
        or (
            machine is not None
            and (machine.worker_kind != body.kind or machine.connection_scope != body.scope)
        )
    ):
        raise HTTPException(422, msg("connection.siteMismatch"))
    name = body.name.strip()
    key = body.api_key.get_secret_value().strip()
    if (
        not name
        or not key
        or not key.isascii()
        or not key.isprintable()
        or any(c.isspace() for c in key)
    ):
        raise HTTPException(422, msg("connection.nameAndKey"))
    if machine is None:
        # Only native work machines have a usable inbound bearer key. This unique marker cannot match a SHA-256 digest.
        machine = Machine(
            owner_id=owner_id,
            team_id=team_id,
            worker_kind=body.kind,
            connection_scope=body.scope,
            key_hash="account:" + new_id(),
            key_prefix="",
        )
        db.add(machine)
    if not machine.credential or secret(machine, settings) != key:
        machine.credential = cipher(settings).encrypt(key.encode()).decode()
        machine.connection_revision = new_id()
    machine.name = name
    db.flush()
    return machine


async def import_source(
    db: Session,
    owner: User,
    body: ReferenceImport,
    settings: Settings,
    *,
    session_hash: str,
    team_id: str | None = None,
) -> tuple[Workflow, WorkflowVersion]:
    from comfyshop_api.services.workflows import append_workflow_version, field_graph, parse_graph

    owner_id = owner.id
    machine = owned_record(
        db, Machine, body.machine_id, owner_id, msg("machine.notFound"), team_id=team_id
    )
    if machine.deleted_at or machine.revoked_at:
        raise HTTPException(404, msg("machine.notFound"))
    kind, scope, revision = (
        machine.worker_kind,
        machine.connection_scope,
        machine.connection_revision,
    )
    load = worker_type(kind).load_reference
    if not load or scope is None:
        raise HTTPException(422, msg("connection.importUnsupported"))
    key = secret(machine, settings)
    db.rollback()
    try:
        source = await load(scope, key, body.reference)
    except ValueError as error:
        raise HTTPException(422, str(error).replace(key, "[redacted]")[:400]) from None
    except httpx.HTTPError:
        raise HTTPException(422, msg("connection.cloudUnavailable")) from None
    graph = source.graph
    definition = worker_type(kind)
    try:
        if definition.form == "fields":
            graph, digest = field_graph(FieldWorkflow.model_validate(graph), definition)
        else:
            fmt, digest, _ = parse_graph(graph)
            if fmt != "api":
                raise HTTPException(422, msg("connection.noExecutableNodes"))
        catalog = {
            name: NodeCatalog.model_validate(value).model_dump(exclude_defaults=True)
            for name, value in source.catalog.items()
        }
    except (ValidationError, ValueError):
        raise HTTPException(422, msg("connection.invalidDefinition")) from None
    if len(source.reference) > 120:
        raise HTTPException(422, msg("connection.referenceTooLong"))
    lock_session_account(db, owner, session_hash)
    team = (
        require_team(db, team_id, owner_id, minimum=TeamRole.EDITOR, locked=True)
        if team_id is not None
        else None
    )
    machine = matched(
        db.get(Machine, body.machine_id, populate_existing=True),
        kind,
        scope,
        owner_id,
        team_id=team_id,
    )
    if machine.connection_revision != revision:
        raise HTTPException(409, msg("connection.changedDuringImport"))
    identity = f"{kind}:{scope}:{source.reference}"
    flow = db.scalar(
        select(Workflow)
        .where(
            workspace_records(Workflow.owner_id, Workflow.team_id, owner_id, team_id),
            Workflow.remote_source == identity,
            Workflow.visible(),
        )
        .order_by(Workflow.created_at, Workflow.id)
        .limit(1)
    )
    created = flow is None
    if flow is None:
        flow = Workflow(
            owner_id=owner_id,
            team_id=team_id,
            name=(body.name or "").strip() or f"{worker_type(kind).label} {source.reference}",
            category=body.category,
            remote_source=identity,
        )
        db.add(flow)
    previous = flow.versions[-1] if flow.versions else None
    data = {
        "reference": source.reference,
        "catalog": catalog,
        "limited": source.catalog_limited,
        "optional_assets": [list(item) for item in source.optional_assets],
    }
    if previous and previous.graph_hash == digest:
        if (
            source.catalog_limited
            and previous.worker_data
            and not previous.worker_data.get("limited")
        ):
            return flow, previous
        if data == previous.worker_data:
            return flow, previous
    version = append_workflow_version(
        flow,
        graph,
        digest,
        WorkflowVersion(
            format="remote",
            worker_kind=kind,
            connection_scope=scope,
            worker_data=data,
            requirements=[],
            parameter_layout=previous.parameter_layout if previous else None,
        ),
    )
    flow.updated_at = now_ms()
    if team:
        db.flush()
        team.record(db, "workflow.created" if created else "workflow.updated", flow.id)
    db.commit()
    return flow, version


def credentials(db: Session, task: Task, settings: Settings) -> dict[str, str]:
    machine = matched(
        db.get(Machine, task.machine_id) if task.machine_id else None,
        task.worker_kind,
        (task.worker_data or {}).get("scope"),
        task.owner_id,
        team_id=task.team_id,
    )
    if machine.connection_revision != task.connection_revision:
        raise HTTPException(409, msg("connection.taskKeyChanged"))
    return {"scope": machine.connection_scope or "", "apiKey": secret(machine, settings)}


async def cancel_remote(db: Session, task: Task, settings: Settings) -> None:
    cancel = worker_type(task.worker_kind).cancel
    if not cancel or task.cloud_cancel:
        db.commit()
        return
    rows = db.execute(
        select(Execution.prompt_id, Execution.submission_pending).where(
            Execution.task_id == task.id, Execution.status == Status.CANCELLED
        )
    ).all()
    ids = {row.prompt_id for row in rows if row.prompt_id}
    uncertain = any(row.submission_pending and not row.prompt_id for row in rows)
    task.cloud_cancel = "unconfirmed" if ids or uncertain else "not_submitted"
    auth = None
    if ids:
        try:
            auth = credentials(db, task, settings)
        except HTTPException:
            pass
    db.commit()
    if auth:
        for identifier in ids:
            try:
                await cancel(auth["scope"], auth["apiKey"], identifier)
            except (ValueError, httpx.HTTPError):
                uncertain = True
        if not uncertain:
            task.cloud_cancel = "accepted"
            db.commit()
