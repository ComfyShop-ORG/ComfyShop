"""工作机接入申请：账号确认新增或重新连接，工作机随后换取密钥。"""

import secrets

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session, load_only

from comfyshop_api.db import write_lock
from comfyshop_api.models import Machine, MachineLink, User, now_ms
from comfyshop_api.schemas import MachineCreate, MachineLinkRead, MachineReconnect
from comfyshop_api.security import digest, owned_record, same_network
from comfyshop_api.services.machines import create_machine, machine_is_online, reset_key, rotate_key

LINK_TTL_MS = 600_000
POLL_SECONDS = 3
# 同时等待确认的申请上限。申请无需登录即可创建，超过上限时拒绝新的申请。
MAX_PENDING = 500
# 去掉 0/O、1/I/L 等易混字符，便于在另一台设备上手动输入。
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
MISSING = "接入申请不存在或已过期，请重新启动工作机"


def normalize_code(code: str) -> str:
    return "".join(character for character in code.upper() if character.isalnum())[:16]


def _require_offline(machine: Machine) -> None:
    if machine.revoked_at is not None:
        raise HTTPException(409, "工作机已撤销")
    now = now_ms()
    if machine_is_online(machine.last_seen, machine.revoked_at, now) or machine.busy_until > now:
        raise HTTPException(409, "请先停止原工作机，等它离线且空闲后重新连接")


def request_link(db: Session, name: str, source_ip: str | None) -> tuple[MachineLink, str]:
    """创建一份等待确认的申请，返回它和只交给工作机的原始凭据，由调用方提交。

    `source_ip` 是工作机的来源地址，确认页把它显示给账号核对。
    """
    stamp = now_ms()
    db.execute(delete(MachineLink).where(MachineLink.expires_at <= stamp))
    waiting = select(func.count()).select_from(MachineLink).where(MachineLink.owner_id.is_(None))
    if (db.scalar(waiting) or 0) >= MAX_PENDING:
        raise HTTPException(429, "等待确认的工作机过多，请稍后再试")
    secret = secrets.token_urlsafe(36)
    link = MachineLink(
        secret_hash=digest(secret),
        code="".join(secrets.choice(CODE_ALPHABET) for _ in range(8)),
        name=name.strip()[:80],
        source_ip=(source_ip or "")[:64],
        created_at=stamp,
        expires_at=stamp + LINK_TTL_MS,
    )
    db.add(link)
    db.flush()
    return link, secret


def read_link(db: Session, code: str, owner_id: str, browser_ip: str | None) -> MachineLinkRead:
    """按代码读取未过期的申请。确认后的进度只对确认账号可见。"""
    row = db.execute(
        select(MachineLink, Machine)
        .outerjoin(Machine, Machine.id == MachineLink.reconnect_machine_id)
        .options(load_only(Machine.revoked_at, Machine.last_seen, Machine.busy_until))
        .where(
            MachineLink.code == normalize_code(code),
            or_(MachineLink.owner_id.is_(None), MachineLink.owner_id == owner_id),
            MachineLink.expires_at > now_ms(),
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, MISSING)
    link, target = row
    if target is not None:
        _require_offline(target)
    status = "pending"
    if link.owner_id is not None:
        status = "linked" if link.machine_id is not None else "approved"
    return MachineLinkRead(
        code=link.code,
        name=link.name,
        status=status,
        requested_at=link.created_at,
        expires_at=link.expires_at,
        source=link.source_ip,
        same_network=same_network(link.source_ip, browser_ip),
    )


def approve_link(
    db: Session, code: str, owner_id: str, approval: MachineCreate | MachineReconnect
) -> None:
    """在调用方锁定的账号下确认接入，记录新名称或指定的离线工作机，由调用方提交。"""
    reconnect_id = None
    if isinstance(approval, MachineReconnect):
        target = owned_record(db, Machine, approval.machine_id, owner_id, "工作机不存在")
        _require_offline(target)
        name = target.name
        reconnect_id = target.id
    else:
        name = approval.name.strip()
    approved = db.scalar(
        update(MachineLink)
        .where(
            MachineLink.code == normalize_code(code),
            MachineLink.owner_id.is_(None),
            MachineLink.expires_at > now_ms(),
        )
        .values(owner_id=owner_id, name=name, reconnect_machine_id=reconnect_id)
        .returning(MachineLink.id)
    )
    if approved is None:
        raise HTTPException(404, MISSING)


def redeem_link(db: Session, secret: str) -> tuple[str, str] | None:
    """工作机凭原始凭据换取密钥，由调用方提交。

    尚未确认时返回 `None`。第一次换取创建工作机或重新连接指定工作机并记在申请上，
    返回原始密钥和工作机名称。目标仍在使用时返回 409。
    回复丢失时工作机会在申请到期前重试：平台不保存原始密钥，于是为同一台工作机换发密钥，
    之前那份随之失效，不会再建一台。只有这台工作机还没用密钥连上平台时才允许重试，
    已经在用的密钥不会被迟到的重复请求作废；用户在网页重置或撤销密钥时申请随之删除。
    申请不存在、已过期、工作机已连接过或已撤销返回 410。
    """
    link = db.scalar(select(MachineLink).where(MachineLink.secret_hash == digest(secret)))
    if link is None or link.expires_at <= now_ms():
        raise HTTPException(410, MISSING)
    if link.owner_id is None:
        return None
    # 账号锁也串行化注销；等待后重新读取，另一请求可能已兑换。
    write_lock(db, User, link.owner_id)
    link = db.get(MachineLink, link.id, populate_existing=True)
    if link is None or link.expires_at <= now_ms() or link.owner_id is None:
        raise HTTPException(410, MISSING)
    if link.machine_id is None:
        if link.reconnect_machine_id is None:
            machine, raw = create_machine(db, link.owner_id, link.name)
        else:
            machine = owned_record(db, Machine, link.reconnect_machine_id, link.owner_id, MISSING)
            _require_offline(machine)
            write_lock(db, Machine, machine.id)
            db.refresh(machine)
            _require_offline(machine)
            # 重置时作废其他申请，当前申请换取成功后仍可查询进度和重试。
            link.reconnect_machine_id = None
            raw = reset_key(db, machine)
        link.machine_id = machine.id
        return raw, machine.name
    write_lock(db, Machine, link.machine_id)
    machine = db.get(Machine, link.machine_id, populate_existing=True)
    if (
        machine is None
        or machine.revoked_at is not None
        or machine.owner_id != link.owner_id
        or machine.last_seen is not None
    ):
        raise HTTPException(410, MISSING)
    return rotate_key(db, machine), machine.name
