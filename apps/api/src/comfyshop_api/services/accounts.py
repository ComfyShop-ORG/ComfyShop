"""账号自助管理：修改密码、绑定邮箱、重置密码和注销。"""

import secrets

from fastapi import HTTPException, Request
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, load_only

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import Message, localize, msg
from comfyshop_api.db import write_lock
from comfyshop_api.models import (
    Artifact,
    Asset,
    Favorite,
    LoginSession,
    MachineLink,
    PasswordReset,
    Status,
    Task,
    TeamMember,
    User,
    Work,
    Workflow,
    WorkspaceShare,
    now_ms,
)
from comfyshop_api.security import digest, forgive, passwords, throttle, verify_password
from comfyshop_api.services.executions import fail_unfinished_executions
from comfyshop_api.services.machines import record_official_wait, revoke_all
from comfyshop_api.services.mail import branded_mail
from comfyshop_api.services.teams import ensure_account_can_leave_teams

# 注销后账号的显示名。新账号不能使用它，见注册接口。
DELETED_NAME = "已注销"


def register(
    db: Session, username: str, password: str, email: str | None, confirm_ttl_seconds: int
) -> tuple[User, str | None]:
    """新建账号，由调用方建立登录并提交。账号名已被占用返回 409。

    填写了邮箱时记为等待确认，并返回确认邮件里的一次性凭据。邮箱是否已绑定别的账号
    要到确认时才判断，注册的响应不透露。
    """
    username_key = username.casefold()
    # 注销后的账号显示为 DELETED_NAME，不能被新账号占用来冒充。
    if username_key == DELETED_NAME or db.scalar(
        select(User.id).where(User.username_key == username_key)
    ):
        raise HTTPException(409, msg("account.thisUsernameIsAlreadyRegistered"))
    user = User(
        username=username, username_key=username_key, password_hash=passwords.hash(password)
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, msg("account.thisUsernameIsAlreadyRegistered")) from None
    return user, request_email(db, user, email, confirm_ttl_seconds) if email else None


def ensure_mail_url(settings: Settings, error: Message | None = None) -> None:
    """发信但没有配置平台地址时返回 503：邮件链接不能取自请求的 Host。"""
    if settings.smtp_host and not settings.public_url:
        raise HTTPException(503, error or msg("account.thePlatformHasNoEmailLink"))


def _mail(
    settings: Settings,
    language: str,
    subject: str,
    title: str,
    intro: Message,
    action: tuple[str, str],
    validity: Message,
) -> tuple[str, str, str]:
    """带一个链接按钮的平台邮件：主题、纯文本正文和主题样式正文。"""
    label, path = action
    label = localize(msg(label), language)
    # 链接只取自配置的平台地址。未配置时给出站内路径，由运维拼到平台地址后使用。
    link = f"{settings.public_url or ''}{path}"
    ignore = msg("mail.ignoreNotice")
    return (
        localize(msg(subject), language),
        localize(
            msg(
                "mail.plainText",
                intro,
                label,
                validity,
                link,
                ignore,
            ),
            language,
        ),
        branded_mail(
            localize(msg(title), language),
            [
                localize(intro, language),
                localize(msg("mail.buttonInstructions", label, validity), language),
            ],
            (label, link),
            localize(ignore, language),
            language,
        ),
    )


def password_reset_mail(
    settings: Settings, user: User, token: str, language: str
) -> tuple[str, str, str]:
    """重置密码邮件的主题、纯文本正文和主题样式正文。"""
    minutes = settings.password_reset_ttl_seconds // 60
    return _mail(
        settings,
        language,
        "mail.resetSubject",
        "mail.resetTitle",
        msg("mail.resetIntro", user.username),
        ("mail.resetAction", f"/reset-password?token={token}"),
        msg("mail.expiresInMinutes", minutes),
    )


def email_confirmation_mail(
    settings: Settings, user: User, token: str, language: str
) -> tuple[str, str, str]:
    """确认绑定邮箱的邮件：主题、纯文本正文和主题样式正文。"""
    hours = max(1, settings.email_confirm_ttl_seconds // 3600)
    return _mail(
        settings,
        language,
        "mail.confirmSubject",
        "mail.confirmTitle",
        msg("mail.confirmIntro", user.username),
        ("mail.confirmAction", f"/confirm-email?token={token}"),
        msg("mail.expiresInHours", hours),
    )


def require_password(
    db: Session, request: Request, user: User, password: str, replacement: str | None = None
) -> str | None:
    """敏感操作前核对当前密码并取得账号写锁，不符或账号已注销返回 403。

    按账号和来源地址限制错误次数，核对成功的这次不计入。哈希计算较慢，全部在锁外进行：SQLite 的写锁会挡住全平台
    的写入。传入 `replacement` 时在锁外算好它的哈希并返回，供调用方写入新密码。
    加锁后重新读取账号，密码在核对期间被改过时同样拒绝，锁保持到调用方提交。
    """
    attempt = throttle(request, db, user.id, "password")
    checked = user.password_hash
    if not verify_password(password, user):
        raise HTTPException(403, msg("account.incorrectCurrentPassword"))
    forgive(db, attempt)
    hashed = passwords.hash(replacement) if replacement is not None else None
    write_lock(db, User, user.id)
    db.refresh(user)
    if user.deleted_at is not None or user.password_hash != checked:
        raise HTTPException(403, msg("account.incorrectCurrentPassword"))
    return hashed


def change_password(db: Session, user: User, password_hash: str, keep_session: str | None) -> None:
    """写入已在锁外算好的新密码哈希，退出其他设备并撤销全部工作机，由调用方提交。

    `keep_session` 是要保留的会话摘要。工作机密钥同样是账号的凭据：账号被盗后改密码，
    盗用者此前接入的工作机不能继续领取任务。ComfyUI 工作机可重置密钥重新接入，个人云端连接需重新添加。
    """
    user.password_hash = password_hash
    revoke_all(db, user.id)
    # 已确认但还没换取的接入申请也会换出新工作机，一并作废。
    db.execute(delete(MachineLink).where(MachineLink.owner_id == user.id))
    statement = delete(LoginSession).where(LoginSession.user_id == user.id)
    if keep_session:
        statement = statement.where(LoginSession.token_hash != keep_session)
    db.execute(statement)
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    # 等待确认的邮箱可能是盗用者填的，确认后就能用它重置密码，一并作废。
    _forget_pending_email(user)


def _forget_pending_email(user: User) -> None:
    user.pending_email = user.pending_email_token = user.pending_email_expires_at = None


def request_email(db: Session, user: User, email: str, ttl_seconds: int) -> str | None:
    """记下等待确认的邮箱并返回确认邮件里的一次性凭据，由调用方提交。

    确认前账号绑定的邮箱不变，之前没用过的确认链接随之失效。填的就是当前绑定的邮箱时
    只清除等待中的申请，返回 `None`。
    """
    if user.email_key == email.casefold():
        _forget_pending_email(user)
        return None
    token = secrets.token_urlsafe(32)
    user.pending_email = email
    user.pending_email_token = digest(token)
    user.pending_email_expires_at = now_ms() + ttl_seconds * 1000
    db.flush()
    return token


def clear_email(db: Session, user: User) -> None:
    """在已核对密码的账号锁内解除邮箱绑定，连同等待确认的邮箱和重置凭据，由调用方提交。"""
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    user.email = user.email_key = None
    _forget_pending_email(user)


def confirm_email(db: Session, token: str) -> None:
    """凭确认邮件里的凭据把等待确认的邮箱绑定到账号，由调用方提交。

    凭据无效或过期返回 400。邮箱在这期间已绑定别的账号返回 409：能走到这里的人收到了
    发往该邮箱的邮件，告诉他不算泄露。
    """

    def pending() -> User:
        user = db.scalar(
            select(User)
            .where(User.pending_email_token == digest(token))
            .execution_options(populate_existing=True)
        )
        if (
            user is None
            or user.deleted_at is not None
            or not user.pending_email
            or (user.pending_email_expires_at or 0) <= now_ms()
        ):
            raise HTTPException(400, msg("account.thisConfirmationLinkIsInvalidOr"))
        return user

    # 与改密码、换邮箱串行，等待锁后重新读取。
    write_lock(db, User, pending().id)
    user = pending()
    email = user.pending_email
    assert email is not None
    # 找回方式变了，按旧邮箱发出的重置凭据随之作废。
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    user.email = email
    user.email_key = email.casefold()
    _forget_pending_email(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, msg("account.thisEmailIsAlreadyLinkedTo")) from None


def start_password_reset(db: Session, email: str, ttl_seconds: int) -> tuple[User, str] | None:
    """为绑定了该邮箱的账号生成一次性凭据，由调用方提交。没有对应账号时返回 `None`。"""
    user = db.scalar(
        select(User).where(User.email_key == email.strip().casefold(), User.deleted_at.is_(None))
    )
    if user is None:
        return None
    write_lock(db, User, user.id)
    db.refresh(user)
    if user.deleted_at is not None or user.email_key != email.strip().casefold():
        return None
    stamp = now_ms()
    db.execute(
        delete(PasswordReset).where(
            (PasswordReset.user_id == user.id) | (PasswordReset.expires_at <= stamp)
        )
    )
    token = secrets.token_urlsafe(32)
    db.add(
        PasswordReset(
            token_hash=digest(token), user_id=user.id, expires_at=stamp + ttl_seconds * 1000
        )
    )
    return user, token


def finish_password_reset(db: Session, token: str, password: str) -> None:
    """凭邮件里的凭据设置新密码并退出所有设备，由调用方提交。凭据无效或过期返回 400。"""

    def usable() -> User:
        reset = db.get(PasswordReset, digest(token), populate_existing=True)
        user = db.get(User, reset.user_id) if reset and reset.expires_at > now_ms() else None
        if user is None or user.deleted_at:
            raise HTTPException(400, msg("account.thisResetLinkIsInvalidOr"))
        return user

    # 先确认凭据有效，再在锁外计算新密码的哈希，无效链接不会触发较慢的哈希计算。
    user = usable()
    hashed = passwords.hash(password)
    # 与改密码、换邮箱及其他重置请求串行，等待锁后重新读取，不能信任旧快照。
    write_lock(db, User, user.id)
    change_password(db, usable(), hashed, None)


def delete_account(db: Session, user: User, placeholder_hash: str) -> None:
    """注销账号，由调用方提交。

    撤销工作机并结束进行中的任务，隐藏该账号的工作流、作品、任务和成品，清除登录、
    收藏、邮箱和密码。账号名随即可以重新注册。原文件按软删除的约定保留在磁盘上。
    """
    ensure_account_can_leave_teams(db, user.id)
    revoke_all(db, user.id)
    active_tasks = db.scalars(
        select(Task)
        .options(load_only(Task.id, Task.worker_kind, Task.status, Task.lease_expires_at))
        .where(Task.owner_id == user.id, Task.team_id.is_(None), Task.status.in_(Status.ACTIVE))
        .order_by(Task.id)
        .with_for_update(of=Task)
    ).all()
    stamp = now_ms()
    for task in active_tasks:
        record_official_wait(db, task, stamp, "ended")
        fail_unfinished_executions(db, task.id, Status.CANCELLED)
    db.execute(
        update(Task)
        .where(Task.owner_id == user.id, Task.team_id.is_(None), Task.status.in_(Status.ACTIVE))
        .values(status=Status.CANCELLED, updated_at=stamp)
    )
    db.execute(
        update(Work).where(Work.owner_id == user.id, Work.team_id.is_(None)).values(published=False)
    )
    for model in (Work, Task):
        db.execute(
            update(model)
            .where(model.owner_id == user.id, model.team_id.is_(None), model.deleted_at.is_(None))
            .values(deleted_at=stamp)
        )
    db.execute(
        update(Artifact)
        .where(
            Artifact.owner_id == user.id,
            Artifact.visible(),
            Artifact.task_id.in_(select(Task.id).where(Task.team_id.is_(None))),
        )
        .values(deleted_at=stamp)
    )
    db.execute(
        update(Workflow)
        .where(Workflow.owner_id == user.id, Workflow.team_id.is_(None), Workflow.visible())
        .values(deleted_at=stamp)
    )
    db.execute(
        update(Asset)
        .where(Asset.owner_id == user.id, Asset.team_id.is_(None))
        .values(saved_at=None)
    )
    db.execute(delete(Favorite).where(Favorite.user_id == user.id))
    db.execute(delete(TeamMember).where(TeamMember.user_id == user.id))
    db.execute(
        delete(WorkspaceShare).where(
            (WorkspaceShare.owner_id == user.id) | (WorkspaceShare.viewer_id == user.id)
        )
    )
    db.execute(delete(MachineLink).where(MachineLink.owner_id == user.id))
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    user.username = DELETED_NAME
    user.username_key = f"deleted:{user.id}"
    user.official_import_granted = False
    user.nickname = user.avatar_digest = user.avatar_image = None
    # 占位哈希由调用方在锁外算好，原密码随即失效。
    user.password_hash = placeholder_hash
    user.email = user.email_key = None
    _forget_pending_email(user)
    user.deleted_at = stamp
