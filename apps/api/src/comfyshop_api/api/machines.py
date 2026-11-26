from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from comfyshop_api.api.teams import TeamManager, TeamReader
from comfyshop_api.core.i18n import msg
from comfyshop_api.models import Machine
from comfyshop_api.schemas import (
    ConnectionWrite,
    MachineCreate,
    MachineDetail,
    MachineKey,
    MachineLinkRead,
    MachinePage,
    MachinePause,
    MachineRead,
    MachineReconnect,
)
from comfyshop_api.security import (
    DB,
    Config,
    CurrentUser,
    client_address,
)
from comfyshop_api.services import machines
from comfyshop_api.services.connections import store_connection
from comfyshop_api.services.machine_links import approve_link, read_link
from comfyshop_api.services.machines import machine_read
from comfyshop_api.services.teams import TeamAccess
from comfyshop_api.services.worker_releases import published_worker
from comfyshop_api.services.worker_types import connection_types, worker_type

router = APIRouter(prefix="/machines", tags=["machines"])


@dataclass(frozen=True)
class MachineSpace:
    actor_id: str
    team: TeamAccess | None

    @property
    def team_id(self) -> str | None:
        return self.team.team.id if self.team else None

    def machine(self, db: Session, machine_id: str, *, include_deleted: bool = False) -> Machine:
        return machines.owned_machine(
            db, machine_id, self.actor_id, team_id=self.team_id, include_deleted=include_deleted
        )

    def record(self, db: Session, action: str, target_id: str) -> None:
        if self.team:
            self.team.record(db, action, target_id)


def read_machine_space(user: CurrentUser, team: TeamReader) -> MachineSpace:
    return MachineSpace(user.id, team)


def write_machine_space(user: CurrentUser, team: TeamManager) -> MachineSpace:
    return MachineSpace(user.id, team)


MachineReader = Annotated[MachineSpace, Depends(read_machine_space)]
MachineWriter = Annotated[MachineSpace, Depends(write_machine_space)]


@router.get("")
def list_machines(db: DB, space: MachineReader, config: Config) -> MachinePage:
    items = db.scalars(
        select(Machine)
        .where(machines.machine_scope(space.actor_id, space.team_id), Machine.visible())
        .order_by(Machine.revoked_at.is_not(None), Machine.created_at, Machine.id)
    ).all()
    pref = machines.machine_preference(db, space.actor_id, space.team_id)
    published = published_worker(config)
    release = published.release if published else None
    return MachinePage(
        items=[machine_read(m, release) for m in items],
        default_machine_id=pref.default_machine_id if pref else None,
        worker_release=release,
        connection_types=connection_types(),
    )


@router.post("", status_code=201)
def create_machine(body: MachineCreate, db: DB, space: MachineWriter) -> MachineKey:
    machine, raw = machines.create_machine(db, space.actor_id, body.name, team_id=space.team_id)
    space.record(db, "machine.created", machine.id)
    db.commit()
    return MachineKey(machine=machine_read(machine), api_key=raw)


@router.post("/connections", status_code=201)
def add_connection(
    body: ConnectionWrite, db: DB, space: MachineWriter, config: Config
) -> MachineRead:
    machine = store_connection(db, space.actor_id, body, config, team_id=space.team_id)
    space.record(db, "machine.created", machine.id)
    db.commit()
    return machine_read(machine)


@router.put("/{machine_id}/connection")
def update_connection(
    machine_id: str, body: ConnectionWrite, db: DB, space: MachineWriter, config: Config
) -> MachineRead:
    machine = space.machine(db, machine_id)
    if machine.revoked_at or worker_type(machine.worker_kind).connection != "account":
        raise HTTPException(409, msg("connection.notEditable"))
    store_connection(db, space.actor_id, body, config, machine)
    space.record(db, "machine.connectionUpdated", machine.id)
    db.commit()
    return machine_read(machine)


# 工作机首次启动时打开的确认页读取申请与接入进度。
@router.get("/links/{code}")
def get_machine_link(code: str, request: Request, db: DB, space: MachineReader) -> MachineLinkRead:
    return read_link(db, code, space.actor_id, client_address(request), team_id=space.team_id)


@router.post("/links/{code}/approve", status_code=204)
def approve_machine_link(
    code: str, body: MachineCreate | MachineReconnect, db: DB, space: MachineWriter
) -> Response:
    link_id = approve_link(db, code, space.actor_id, body, team_id=space.team_id)
    space.record(db, "machine.linkApproved", link_id)
    db.commit()
    return Response(status_code=204)


@router.put("/{machine_id}/default", status_code=204)
def default_machine(machine_id: str, db: DB, space: MachineWriter) -> Response:
    machine = space.machine(db, machine_id)
    if machine.revoked_at:
        raise HTTPException(409, msg("machine.workMachineRevoked"))
    machines.set_default_machine(db, machine)
    space.record(db, "machine.defaultChanged", machine.id)
    db.commit()
    return Response(status_code=204)


@router.put("/{machine_id}/pause", status_code=204)
def pause_machine(machine_id: str, body: MachinePause, db: DB, space: MachineWriter) -> Response:
    machine = space.machine(db, machine_id)
    if worker_type(machine.worker_kind).service:
        raise HTTPException(409, msg("connection.pauseUnavailable"))
    machines.set_paused(db, machine, body.paused)
    space.record(db, "machine.paused" if body.paused else "machine.resumed", machine.id)
    db.commit()
    return Response(status_code=204)


@router.put("/{machine_id}/update")
def update_machine(
    machine_id: str,
    db: DB,
    space: MachineWriter,
    config: Config,
    _: Annotated[None, Body()] = None,
) -> MachineRead:
    machine = space.machine(db, machine_id)
    published = published_worker(config)
    release = published.release if published else None
    machines.request_update(db, machine, release)
    space.record(db, "machine.updateRequested", machine.id)
    db.commit()
    return machine_read(machine, release)


@router.post("/{machine_id}/rotate")
def rotate_key(machine_id: str, db: DB, space: MachineWriter) -> MachineKey:
    machine = space.machine(db, machine_id)
    if worker_type(machine.worker_kind).connection != "machine":
        raise HTTPException(409, msg("connection.editKey"))
    raw = machines.reset_key(db, machine)
    space.record(db, "machine.keyRotated", machine.id)
    db.commit()
    return MachineKey(machine=machine_read(machine), api_key=raw)


@router.get("/{machine_id}")
def get_machine(machine_id: str, db: DB, space: MachineReader, config: Config) -> MachineDetail:
    machine = space.machine(db, machine_id)
    published = published_worker(config)
    return machines.machine_detail(db, machine, published.release if published else None)


@router.patch("/{machine_id}", status_code=204)
def rename_machine(machine_id: str, body: MachineCreate, db: DB, space: MachineWriter) -> Response:
    machine = space.machine(db, machine_id)
    machine.name = body.name.strip()
    space.record(db, "machine.renamed", machine.id)
    db.commit()
    return Response(status_code=204)


@router.delete("/{machine_id}")
def revoke_machine(machine_id: str, db: DB, space: MachineWriter) -> MachineRead:
    machine = space.machine(db, machine_id)
    machines.revoke(db, machine)
    space.record(db, "machine.revoked", machine.id)
    db.commit()
    return machine_read(machine)


@router.delete("/{machine_id}/record", status_code=204)
def delete_machine(machine_id: str, db: DB, space: MachineWriter) -> Response:
    """从列表删除已撤销的工作机，保留历史任务中的工作机名称。"""
    # 重复删除同一记录也返回 204。
    machine = space.machine(db, machine_id, include_deleted=True)
    if machine.deleted_at is not None:
        return Response(status_code=204)
    machines.delete_revoked(machine)
    space.record(db, "machine.deleted", machine.id)
    db.commit()
    return Response(status_code=204)
