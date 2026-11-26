"""浏览器订阅、实例密钥与可在重启后继续投递的任务完成通知。"""

import base64
import json
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlencode, urlsplit

import http_ece
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import sign as sign_vapid
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import localize, msg
from comfyshop_api.models import (
    LoginSession,
    Status,
    Task,
    Team,
    TeamMember,
    User,
    WebPushDelivery,
    WebPushSubscription,
    now_ms,
)
from comfyshop_api.schemas import WebPushWrite
from comfyshop_api.security import digest

_PROVIDERS = {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
_TTL_SECONDS = 24 * 60 * 60
_DELIVERY_LEASE_MS = 60_000
_LOG = logging.getLogger(__name__)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def load_key(data_dir: Path) -> ec.EllipticCurvePrivateKey:
    """同一数据目录里的所有进程读取同一个 P-256 实例密钥。"""
    path = data_dir / "web-push-key.pem"
    if not path.exists():
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        key = ec.generate_private_key(ec.SECP256R1())
        with NamedTemporaryFile(dir=data_dir, prefix=".web-push-") as temporary:
            temporary.write(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            temporary.flush()
            os.fsync(temporary.fileno())
            try:
                os.link(temporary.name, path)
            except FileExistsError:
                pass
    stored = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(stored, ec.EllipticCurvePrivateKey) or not isinstance(
        stored.curve, ec.SECP256R1
    ):
        raise ValueError("Web Push key must use P-256")
    return stored


def public_key(key: ec.EllipticCurvePrivateKey) -> str:
    return _base64url(
        key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    )


def _provider_origin(endpoint: str) -> str:
    """订阅只能投递给受支持的浏览器推送服务，始终验证 HTTPS，不跟随跳转。"""
    url = urlsplit(endpoint)
    host = url.hostname or ""
    if (
        url.scheme != "https"
        or url.netloc.lower() != host
        or url.fragment
        or not url.path.strip("/")
        or any(ord(char) < 33 or ord(char) > 126 for char in endpoint)
        or not (host in _PROVIDERS or host.endswith((".push.apple.com", ".notify.windows.com")))
    ):
        raise ValueError("Unsupported Web Push endpoint")
    return f"https://{host}"


def subscription(db: Session, session_hash: str) -> WebPushSubscription | None:
    return db.scalar(
        select(WebPushSubscription).where(WebPushSubscription.session_hash == session_hash)
    )


def remove_subscription(db: Session, session_hash: str) -> None:
    db.execute(delete(WebPushSubscription).where(WebPushSubscription.session_hash == session_hash))


def save_subscription(db: Session, session_hash: str, data: WebPushWrite, language: str) -> None:
    _provider_origin(data.endpoint)
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _decode(data.p256dh))
    if len(_decode(data.auth)) != 16 or (
        data.expires_at is not None and data.expires_at <= now_ms()
    ):
        raise ValueError("Invalid Web Push subscription")
    current = subscription(db, session_hash)
    if current and (current.endpoint, current.p256dh, current.auth) == (
        data.endpoint,
        data.p256dh,
        data.auth,
    ):
        current.expires_at = data.expires_at
        current.language = language
        return
    endpoint_hash = digest(data.endpoint)
    remove_subscription(db, session_hash)
    db.add(
        WebPushSubscription(
            session_hash=session_hash,
            endpoint_hash=endpoint_hash,
            endpoint=data.endpoint,
            p256dh=data.p256dh,
            auth=data.auth,
            expires_at=data.expires_at,
            language=language,
        )
    )


def enqueue_task_notification(db: Session, task: Task, timestamp: int) -> None:
    if task.deleted_at is not None:
        return
    subscriptions = db.scalars(
        select(WebPushSubscription.id)
        .join(LoginSession, LoginSession.token_hash == WebPushSubscription.session_hash)
        .where(
            LoginSession.user_id == task.owner_id,
            LoginSession.expires_at > timestamp,
            or_(
                WebPushSubscription.expires_at.is_(None),
                WebPushSubscription.expires_at > timestamp,
            ),
        )
    )
    db.add_all(
        WebPushDelivery(
            task_id=task.id,
            subscription_id=subscription_id,
            retry_at=timestamp,
            expires_at=timestamp + _TTL_SECONDS * 1000,
        )
        for subscription_id in subscriptions
    )


def _claim(db: Session, timestamp: int) -> tuple[str, int] | None:
    candidate = db.scalar(
        select(WebPushDelivery.id)
        .where(WebPushDelivery.retry_at <= timestamp)
        .order_by(WebPushDelivery.retry_at, WebPushDelivery.id)
        .limit(1)
    )
    db.rollback()
    if candidate is None:
        return None
    row = db.execute(
        update(WebPushDelivery)
        .where(WebPushDelivery.id == candidate, WebPushDelivery.retry_at <= timestamp)
        .values(retry_at=timestamp + _DELIVERY_LEASE_MS, attempts=WebPushDelivery.attempts + 1)
        .returning(WebPushDelivery.attempts)
    ).scalar_one_or_none()
    db.commit()
    return (candidate, row) if row is not None else None


def _send(
    client: httpx.Client,
    key: ec.EllipticCurvePrivateKey,
    contact: str | None,
    endpoint: str,
    p256dh: str,
    auth: str,
    message: dict[str, str],
    ttl: int,
) -> int:
    claims: dict[str, str | int] = {
        "aud": _provider_origin(endpoint),
        "exp": now_ms() // 1000 + 3600,
    }
    if contact:
        claims["sub"] = contact
    encrypted = http_ece.encrypt(
        json.dumps(message, ensure_ascii=False).encode("utf-8"),
        private_key=ec.generate_private_key(ec.SECP256R1()),
        dh=_decode(p256dh),
        auth_secret=_decode(auth),
        version="aes128gcm",
    )
    with client.stream(
        "POST",
        endpoint,
        content=encrypted,
        headers={
            "Authorization": f"vapid t={sign_vapid(claims, key)},k={public_key(key)}",
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": str(ttl),
            "Topic": message["tag"],
        },
        follow_redirects=False,
    ) as response:
        return response.status_code


def _deliver(
    db: Session,
    client: httpx.Client,
    key: ec.EllipticCurvePrivateKey,
    contact: str | None,
    delivery_id: str,
    attempt: int,
    timestamp: int,
) -> None:
    pending = (WebPushDelivery.id == delivery_id, WebPushDelivery.attempts == attempt)
    member = (
        select(TeamMember.user_id)
        .where(TeamMember.team_id == Task.team_id, TeamMember.user_id == Task.owner_id)
        .exists()
    )
    row = db.execute(
        select(
            WebPushSubscription.id,
            WebPushSubscription.endpoint,
            WebPushSubscription.p256dh,
            WebPushSubscription.auth,
            WebPushSubscription.language,
            Task.id,
            Task.team_id,
            WebPushDelivery.expires_at,
        )
        .select_from(WebPushDelivery)
        .join(WebPushSubscription, WebPushDelivery.subscription_id == WebPushSubscription.id)
        .join(LoginSession, LoginSession.token_hash == WebPushSubscription.session_hash)
        .join(User, LoginSession.user_id == User.id)
        .join(Task, Task.id == WebPushDelivery.task_id)
        .where(
            *pending,
            WebPushDelivery.expires_at > timestamp,
            LoginSession.expires_at > timestamp,
            User.deleted_at.is_(None),
            or_(
                WebPushSubscription.expires_at.is_(None), WebPushSubscription.expires_at > timestamp
            ),
            Task.owner_id == LoginSession.user_id,
            Task.visible(),
            Task.status == Status.SUCCEEDED,
            Team.active_scope(Task.team_id),
            or_(Task.team_id.is_(None), member),
        )
    ).one_or_none()
    db.rollback()
    if row is None:
        db.execute(delete(WebPushDelivery).where(*pending))
        db.commit()
        return

    subscription_id, endpoint, client_key, auth, language, task_id, team_id, expires_at = row
    path, query = (
        (f"/workspace/teams/{team_id}/tasks", {"task": task_id})
        if team_id
        else ("/workspace/tasks", {"task": task_id, "space": "personal"})
    )
    message = {
        "title": localize(msg("webPush.completed"), language),
        "body": localize(msg("webPush.openTask"), language),
        "url": f"{path}?{urlencode(query)}",
        "tag": task_id.replace("-", ""),
    }
    try:
        status = _send(
            client,
            key,
            contact,
            endpoint,
            client_key,
            auth,
            message,
            max(1, (expires_at - timestamp) // 1000),
        )
    except httpx.RequestError:
        status = 503
    except (http_ece.ECEException, ValueError):
        status = 410
    if status in {404, 410}:
        db.execute(delete(WebPushSubscription).where(WebPushSubscription.id == subscription_id))
    elif status in {408, 429} or status >= 500:
        delay = min(3600, 30 * 2 ** min(attempt - 1, 8))
        db.execute(
            update(WebPushDelivery)
            .where(*pending)
            .values(retry_at=min(expires_at, now_ms() + delay * 1000))
        )
        _LOG.warning("任务通知推送服务暂时不可用，HTTP %d", status)
    else:
        db.execute(delete(WebPushDelivery).where(*pending))
        if not 200 <= status < 300:
            _LOG.warning("任务通知被推送服务拒绝，HTTP %d", status)
    db.commit()


def deliver_task_notifications(
    db: Session,
    client: httpx.Client,
    key: ec.EllipticCurvePrivateKey,
    settings: Settings,
) -> None:
    contact = settings.web_push_contact
    if not contact and settings.public_url and settings.public_url.startswith("https://"):
        contact = settings.public_url
    for _ in range(8):
        timestamp = now_ms()
        claimed = _claim(db, timestamp)
        if claimed is None:
            return
        _deliver(db, client, key, contact, *claimed, timestamp)
