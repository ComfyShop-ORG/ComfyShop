"""工作机接入申请：首次启动的工作机申请接入，账号在网页确认后换取密钥。"""

import secrets

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from comfyshop_api.db import write_lock
from comfyshop_api.models import LoginSession, Machine, MachineLink, User, now_ms
from comfyshop_api.security import digest
from comfyshop_api.services.machines import create_machine, rotate_key

LINK_TTL_MS = 600_000
POLL_SECONDS = 3
# 同时等待确认的申请上限。申请无需登录即可创建，超过上限时拒绝新的申请。
MAX_PENDING = 500
# 去掉 0/O、1/I/L 等易混字符，便于在另一台设备上手动输入。
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
MISSING = "接入申请不存在或已过期，请重新启动工作机"


def normalize_code(code: str) -> str:
    return "".join(character for character in code.upper() if character.isalnum())[:16]


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


def pending_link(db: Session, code: str) -> MachineLink:
    """按网页上的代码找到尚未确认、未过期的申请，否则返回 404。"""
    link = db.scalar(
        select(MachineLink).where(
            MachineLink.code == normalize_code(code),
            MachineLink.owner_id.is_(None),
            MachineLink.expires_at > now_ms(),
        )
    )
    if link is None:
        raise HTTPException(404, MISSING)
    return link


def approve_link(db: Session, code: str, owner_id: str, name: str, session_hash: str) -> None:
    """账号确认接入并给工作机命名，由调用方提交。

    `session_hash` 是发起确认的会话摘要。取得账号锁后重新确认会话仍有效：同时进行的
    改密码或重置密码会删除其他会话，被它们结束的会话不能再确认申请。
    """
    write_lock(db, User, owner_id)
    user = db.get(User, owner_id, populate_existing=True)
    session = db.get(LoginSession, session_hash, populate_existing=True)
    if user is None or user.deleted_at is not None or session is None:
        raise HTTPException(401, "请先登录")
    approved = db.scalar(
        update(MachineLink)
        .where(
            MachineLink.code == normalize_code(code),
            MachineLink.owner_id.is_(None),
            MachineLink.expires_at > now_ms(),
        )
        .values(owner_id=owner_id, name=name.strip()[:80])
        .returning(MachineLink.id)
    )
    if approved is None:
        raise HTTPException(404, MISSING)


def redeem_link(db: Session, secret: str) -> tuple[str, str] | None:
    """工作机凭原始凭据换取密钥，由调用方提交。

    尚未确认时返回 `None`。第一次换取新建工作机并记在申请上，返回原始密钥和工作机名称。
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
        machine, raw = create_machine(db, link.owner_id, link.name)
        link.machine_id = machine.id
        return raw, machine.name
    machine = db.get(Machine, link.machine_id, populate_existing=True)
    if (
        machine is None
        or machine.revoked_at is not None
        or machine.owner_id != link.owner_id
        or machine.last_seen is not None
    ):
        raise HTTPException(410, MISSING)
    return rotate_key(db, machine), machine.name
