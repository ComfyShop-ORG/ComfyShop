"""浏览器登录与写请求校验。工作机的 Bearer 密钥由 `services.machines` 处理。"""

import hashlib
import hmac
import secrets
from ipaddress import ip_address, ip_network
from typing import Annotated, Literal, cast

from fastapi import Depends, Header, HTTPException, Request, Response
from fastapi.security import APIKeyCookie
from pwdlib import PasswordHash
from sqlalchemy import case, delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.engine import CursorResult

from comfyshop_api.core.config import Settings, get_settings
from comfyshop_api.db import get_db, write_lock
from comfyshop_api.models import AuthAttempt, LoginSession, User, now_ms

COOKIE_NAME = "comfyshop_session"
cookie_auth = APIKeyCookie(name=COOKIE_NAME, scheme_name="SessionCookie", auto_error=False)
passwords = PasswordHash.recommended()
_dummy_hash = passwords.hash(secrets.token_urlsafe(32))
DB = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def check_origin(request: Request, settings: Config) -> None:
    """检查浏览器的 `Origin` 是否与请求同源或在配置名单中，失败返回 403。"""
    origin = request.headers.get("origin")
    allowed = set(settings.allowed_origins) | {str(request.base_url).rstrip("/")}
    if origin not in allowed:
        raise HTTPException(403, "请求来源无效")


Origin = Annotated[None, Depends(check_origin)]


def session_or_none(
    db: DB, token: Annotated[str | None, Depends(cookie_auth)]
) -> LoginSession | None:
    """用 Cookie 的摘要查找未过期会话。访客或失效 Cookie 对应 `None`。"""
    if not token or len(token) > 128:
        return None
    session = db.get(LoginSession, digest(token))
    if session and session.expires_at > now_ms():
        return session
    return None


def current_user(session: Annotated[LoginSession | None, Depends(session_or_none)]) -> User:
    if not session:
        raise HTTPException(401, "请先登录")
    return session.user


CurrentUser = Annotated[User, Depends(current_user)]
MaybeSession = Annotated[LoginSession | None, Depends(session_or_none)]


def owned_record[T](db: Session, model: type[T], record_id: str, owner_id: str, missing: str) -> T:
    """按主键读取带 `owner_id` 的记录。记录不存在或属于他人都以 `missing` 返回 HTTP 404。"""
    record = db.get(model, record_id)
    if record is None or getattr(record, "owner_id") != owner_id:
        raise HTTPException(404, missing)
    return record


def csrf_for(token: str) -> str:
    return digest(f"csrf:{token}")


def protect_write(
    request: Request,
    user: CurrentUser,
    _origin: Origin,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> User:
    """通过会话、来源和 `X-CSRF-Token` 校验后返回用户。校验失败返回 401 或 403。"""
    token = request.cookies.get(COOKIE_NAME, "")
    if not hmac.compare_digest((csrf_token or "").encode(), csrf_for(token).encode()):
        raise HTTPException(403, "会话校验失败，请刷新后重试")
    return user


Writer = Annotated[User, Depends(protect_write)]


def lock_session_account(db: Session, user: User, session_hash: str) -> None:
    """锁住账号并重新核对会话，避免旧会话在改密码或注销后继续写入。"""
    write_lock(db, User, user.id)
    db.refresh(user)
    session = db.get(LoginSession, session_hash, populate_existing=True)
    if (
        user.deleted_at is not None
        or session is None
        or session.user_id != user.id
        or session.expires_at <= now_ms()
    ):
        raise HTTPException(401, "请先登录")


def lock_writer(request: Request, db: DB, user: Writer) -> User:
    lock_session_account(db, user, digest(request.cookies[COOKIE_NAME]))
    return user


LockedWriter = Annotated[User, Depends(lock_writer)]


def establish_session(
    user: User, request: Request, response: Response, db: Session, settings: Settings
) -> str:
    """替换当前浏览器的会话，在响应中设置 HttpOnly Cookie，并返回给前端使用的 CSRF 值。"""
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == digest(old_token)))
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now_ms()))
    token = secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            token_hash=digest(token),
            user_id=user.id,
            expires_at=now_ms() + settings.session_ttl_seconds * 1000,
        )
    )
    db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return csrf_for(token)


def client_address(request: Request) -> str | None:
    """请求的来源 IP 地址，不是合法地址时返回 `None`。

    部署在反向代理后时，需让应用信任代理转发的地址，代理也必须覆盖客户端自带的
    `X-Forwarded-For`，见部署文档。
    """
    host = request.client.host if request.client else None
    try:
        return str(ip_address(host)) if host else None
    except ValueError:
        return None


def _address_bucket(address: str | None) -> str:
    """频率限制按地址计数的键。IPv6 按 /64 网段归并，一个网段不能换地址绕过限制。"""
    if address is None:
        return "unknown"
    parsed = ip_address(address)
    if parsed.version == 6:
        return str(ip_network(f"{parsed}/64", strict=False))
    return address


def same_network(first: str | None, second: str | None) -> bool | None:
    """两个来源地址是否在同一网络，无从比较时返回 `None`。

    IPv4 比较地址，IPv6 比较 /64 网段：同一台机器的临时地址会轮换。任一地址未知，或一个
    是 IPv4 一个是 IPv6（双栈机器上两个连接各走一种）时不下结论。
    """
    if not first or not second:
        return None
    try:
        addresses = [ip_address(value) for value in (first, second)]
    except ValueError:
        return None
    # 双栈监听时 IPv4 连接会显示为 ::ffff:a.b.c.d，还原后再比较。
    plain = [getattr(address, "ipv4_mapped", None) or address for address in addresses]
    if plain[0].version != plain[1].version:
        return None
    return _address_bucket(str(plain[0])) == _address_bucket(str(plain[1]))


def verify_password(password: str, user: User | None) -> bool:
    valid = passwords.verify(password, user.password_hash if user else _dummy_hash)
    return bool(user and valid)


THROTTLE_WINDOW_MS = 600_000
# 每个来源地址和每个对象在一个窗口内允许的次数。
THROTTLE_LIMITS = {"ip": 30, "subject": 10}


def throttle(
    request: Request,
    db: Session,
    subject: str | None,
    purpose: Literal["register", "login", "reset", "password", "link", "confirm"],
) -> list[str]:
    """计一次 `purpose` 请求，超过窗口内的次数时返回 429，返回本次计数的键。

    按来源地址和 `subject`（账号名、邮箱或用户 ID，为 `None` 时只按地址）分别计数。
    计数持久化在数据库里，重启不会重置，多个服务进程共享。核对密码的调用方在核对成功
    后用 `forgive` 退回这次计数，因此只有错误次数会累积。来源地址取自连接，部署在
    反向代理后时需让应用信任代理转发的地址，见部署文档。
    """
    stamp = now_ms()
    cutoff = stamp - THROTTLE_WINDOW_MS
    ip = _address_bucket(client_address(request))
    keys = [(digest(f"{purpose}:ip:{ip}"), THROTTLE_LIMITS["ip"])]
    if subject is not None:
        keys.append((digest(f"{purpose}:user:{subject.casefold()}"), THROTTLE_LIMITS["subject"]))
    for key, limit in keys:
        statement = (
            update(AuthAttempt)
            .where(AuthAttempt.key == key)
            .values(
                attempts=case(
                    (AuthAttempt.window_start <= cutoff, 1), else_=AuthAttempt.attempts + 1
                ),
                window_start=case(
                    (AuthAttempt.window_start <= cutoff, stamp), else_=AuthAttempt.window_start
                ),
            )
        )
        if cast(CursorResult, db.execute(statement)).rowcount == 0:
            try:
                with db.begin_nested():
                    db.add(AuthAttempt(key=key, window_start=stamp, attempts=1))
                    db.flush()
            except IntegrityError:
                db.execute(statement)
        counter = db.get(AuthAttempt, key, populate_existing=True)
        db.commit()
        if counter and counter.attempts > limit:
            retry = max(1, (counter.window_start + THROTTLE_WINDOW_MS - stamp) // 1000)
            raise HTTPException(
                429, "请求过于频繁，请稍后再试", headers={"Retry-After": str(retry)}
            )
    return [key for key, _ in keys]


def forgive(db: Session, keys: list[str]) -> None:
    """密码核对成功后退回 `throttle` 的计数并提交，正确的密码不计入错误次数。"""
    db.execute(
        update(AuthAttempt)
        .where(AuthAttempt.key.in_(keys), AuthAttempt.attempts > 0)
        .values(attempts=AuthAttempt.attempts - 1)
    )
    db.commit()


def expire_auth_attempts(db: Session) -> None:
    """删除窗口已过的计数，由后台维护调用。"""
    db.execute(delete(AuthAttempt).where(AuthAttempt.window_start <= now_ms() - THROTTLE_WINDOW_MS))
    db.commit()
