from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select

from comfyshop_api.models import Machine, UserPreference
from comfyshop_api.schemas import (
    MachineCreate,
    MachineKey,
    MachineLinkRead,
    MachinePage,
    MachineRead,
    MachineReconnect,
)
from comfyshop_api.security import CurrentUser, DB, LockedWriter, client_address, owned_record
from comfyshop_api.services.machine_links import approve_link, read_link
from comfyshop_api.services import machines
from comfyshop_api.services.machines import machine_read

router = APIRouter(prefix="/machines", tags=["machines"])


def owned(db: DB, machine_id: str, owner_id: str) -> Machine:
    return owned_record(db, Machine, machine_id, owner_id, "工作机不存在")


@router.get("", response_model=MachinePage)
def list_machines(db: DB, user: CurrentUser) -> MachinePage:
    machines = db.scalars(
        select(Machine).where(Machine.owner_id == user.id).order_by(Machine.created_at)
    ).all()
    pref = db.get(UserPreference, user.id)
    return MachinePage(
        items=[machine_read(m) for m in machines],
        default_machine_id=pref.default_machine_id if pref else None,
    )


@router.post("", response_model=MachineKey, status_code=201)
def create_machine(body: MachineCreate, db: DB, user: LockedWriter) -> MachineKey:
    machine, raw = machines.create_machine(db, user.id, body.name)
    db.commit()
    return MachineKey(machine=machine_read(machine), api_key=raw)


# 工作机首次启动时打开的确认页读取申请与接入进度。
@router.get("/links/{code}", response_model=MachineLinkRead)
def get_machine_link(code: str, request: Request, db: DB, user: CurrentUser) -> MachineLinkRead:
    return read_link(db, code, user.id, client_address(request))


@router.post("/links/{code}/approve", status_code=204)
def approve_machine_link(
    code: str, body: MachineCreate | MachineReconnect, db: DB, user: LockedWriter
) -> Response:
    approve_link(db, code, user.id, body)
    db.commit()
    return Response(status_code=204)


@router.put("/{machine_id}/default", status_code=204)
def default_machine(machine_id: str, db: DB, user: LockedWriter) -> Response:
    machine = owned(db, machine_id, user.id)
    if machine.revoked_at:
        raise HTTPException(409, "工作机已撤销")
    pref = db.get(UserPreference, user.id)
    if pref:
        pref.default_machine_id = machine.id
    else:
        db.add(UserPreference(user_id=user.id, default_machine_id=machine.id))
    db.commit()
    return Response(status_code=204)


@router.post("/{machine_id}/rotate", response_model=MachineKey)
def rotate_key(machine_id: str, db: DB, user: LockedWriter) -> MachineKey:
    machine = owned(db, machine_id, user.id)
    raw = machines.reset_key(db, machine)
    db.commit()
    return MachineKey(machine=machine_read(machine), api_key=raw)


@router.delete("/{machine_id}", response_model=MachineRead)
def revoke_machine(machine_id: str, db: DB, user: LockedWriter) -> MachineRead:
    machine = owned(db, machine_id, user.id)
    machines.revoke(db, machine)
    db.commit()
    return machine_read(machine)
