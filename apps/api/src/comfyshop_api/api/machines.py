from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select

from comfyshop_api.models import Machine, UserPreference
from comfyshop_api.schemas import (
    MachineCreate,
    MachineKey,
    MachineLinkRead,
    MachinePage,
    MachineRead,
)
from comfyshop_api.security import (
    COOKIE_NAME,
    CurrentUser,
    DB,
    Writer,
    client_address,
    digest,
    owned_record,
    same_network,
)
from comfyshop_api.services.machine_links import approve_link, pending_link
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
def create_machine(body: MachineCreate, db: DB, user: Writer) -> MachineKey:
    machine, raw = machines.create_machine(db, user.id, body.name)
    db.commit()
    return MachineKey(machine=machine_read(machine), api_key=raw)


# 工作机首次启动时打开的确认页读取申请，并由登录账号确认接入。
# 确认页同时显示申请时间和来源地址，并比较来源与当前浏览器的地址，帮助账号识别
# 别人发来的接入链接。
@router.get("/links/{code}", response_model=MachineLinkRead)
def get_machine_link(code: str, request: Request, db: DB, user: CurrentUser) -> MachineLinkRead:
    link = pending_link(db, code)
    return MachineLinkRead(
        code=link.code,
        name=link.name,
        requested_at=link.created_at,
        expires_at=link.expires_at,
        source=link.source_ip,
        # 无从比较时为空，确认页只在确知不同时提示。
        same_network=same_network(link.source_ip, client_address(request)),
    )


@router.post("/links/{code}/approve", status_code=204)
def approve_machine_link(
    code: str, body: MachineCreate, request: Request, db: DB, user: Writer
) -> Response:
    approve_link(db, code, user.id, body.name, digest(request.cookies[COOKIE_NAME]))
    db.commit()
    return Response(status_code=204)


@router.put("/{machine_id}/default", status_code=204)
def default_machine(machine_id: str, db: DB, user: Writer) -> Response:
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
def rotate_key(machine_id: str, db: DB, user: Writer) -> MachineKey:
    machine = owned(db, machine_id, user.id)
    raw = machines.reset_key(db, machine)
    db.commit()
    return MachineKey(machine=machine_read(machine), api_key=raw)


@router.delete("/{machine_id}", response_model=MachineRead)
def revoke_machine(machine_id: str, db: DB, user: Writer) -> MachineRead:
    machine = owned(db, machine_id, user.id)
    machines.revoke(db, machine)
    db.commit()
    return machine_read(machine)
