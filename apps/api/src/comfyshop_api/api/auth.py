import secrets
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select

from comfyshop_api.core.i18n import Language, msg
from comfyshop_api.db import write_lock
from comfyshop_api.models import LoginSession, User
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    AccountDelete,
    Credentials,
    EmailConfirm,
    EmailUpdate,
    ErrorRead,
    NicknameUpdate,
    OfficialImportGrantPage,
    OfficialImportGrantWrite,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    Registration,
    SessionRead,
    UserRead,
)
from comfyshop_api.security import (
    COOKIE_NAME,
    DB,
    Config,
    CurrentUser,
    LockedWriter,
    MaybeSession,
    Origin,
    Writer,
    csrf_for,
    digest,
    establish_session,
    forgive,
    require_account_by_username,
    throttle,
    verify_password,
)
from comfyshop_api.services import accounts, avatars, profiles
from comfyshop_api.services.mail import send_mail

router = APIRouter(prefix="/auth", tags=["auth"])


def require_grant_manager(user: User, config: Config) -> None:
    if not config.is_official_owner(user.username):
        raise HTTPException(403, msg("grants.manageDenied"))


@router.get("/official-import-grants")
def official_import_grants(
    db: DB,
    user: CurrentUser,
    config: Config,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
) -> OfficialImportGrantPage:
    require_grant_manager(user, config)
    query = select(User).where(
        User.official_import_granted, User.deleted_at.is_(None), User.id != user.id
    )
    if position := decode_cursor(cursor, 1):
        query = query.where(User.id > position[0])
    records = db.scalars(query.order_by(User.id).limit(limit + 1)).all()
    items, next_cursor = split_page(records, limit, lambda account: (account.id,))
    return OfficialImportGrantPage(
        items=[account.username for account in items], next_cursor=next_cursor
    )


@router.put("/official-import-grants/{username}", status_code=204)
def set_official_import_grant(
    username: str, body: OfficialImportGrantWrite, db: DB, user: LockedWriter, config: Config
) -> Response:
    require_grant_manager(user, config)
    account = require_account_by_username(db, username)
    if account.id == user.id:
        raise HTTPException(409, msg("grants.configuredOwner"))
    write_lock(db, User, account.id)
    db.refresh(account)
    if account.deleted_at is not None:
        raise HTTPException(404, msg("grants.unknownAccount"))
    account.official_import_granted = body.granted
    db.commit()
    return Response(status_code=204)


def clear_cookie(response: Response, settings: Config) -> None:
    response.delete_cookie(
        COOKIE_NAME, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax"
    )


def schedule_email_confirmation(
    background: BackgroundTasks,
    settings: Config,
    user: User,
    email: str | None,
    token: str | None,
    language: str,
) -> None:
    if email and token:
        background.add_task(
            send_mail,
            settings,
            email,
            *accounts.email_confirmation_mail(settings, user, token, language),
        )


@router.get("/session")
def get_session(request: Request, session: MaybeSession) -> SessionRead:
    return SessionRead(
        user=UserRead.from_user(session.user) if session else None,
        csrf_token=csrf_for(request.cookies[COOKIE_NAME]) if session else None,
    )


# 填写了邮箱时发出确认邮件，点击其中的链接后邮箱才绑定到账号。
@router.post(
    "/register",
    status_code=201,
    responses={503: {"model": ErrorRead}},
)
def register(
    body: Registration,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    db: DB,
    settings: Config,
    _origin: Origin,
    language: Language,
) -> SessionRead:
    if body.email:
        accounts.ensure_mail_url(settings)
    throttle(request, db, body.username, "register")
    user, token = accounts.register(
        db,
        body.username,
        body.password.get_secret_value(),
        body.email,
        settings.email_confirm_ttl_seconds,
    )
    csrf = establish_session(user, request, response, db, settings)
    schedule_email_confirmation(background, settings, user, body.email, token, language)
    return SessionRead(user=UserRead.from_user(user), csrf_token=csrf)


@router.post("/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    db: DB,
    settings: Config,
    _origin: Origin,
) -> SessionRead:
    attempt = throttle(request, db, body.username, "login")
    user = db.scalar(select(User).where(User.username_key == body.username.casefold()))
    if not verify_password(body.password.get_secret_value(), user) or user is None:
        raise HTTPException(401, msg("auth.invalidCredentials"))
    forgive(db, attempt)
    csrf = establish_session(user, request, response, db, settings)
    return SessionRead(user=UserRead.from_user(user), csrf_token=csrf)


@router.post("/logout", status_code=204)
def logout(
    request: Request, response: Response, db: DB, settings: Config, _user: Writer
) -> Response:
    db.execute(
        delete(LoginSession).where(LoginSession.token_hash == digest(request.cookies[COOKIE_NAME]))
    )
    db.commit()
    clear_cookie(response, settings)
    response.status_code = 204
    return response


@router.post("/password", status_code=204)
def change_password(body: PasswordChange, request: Request, db: DB, user: Writer) -> Response:
    hashed = accounts.require_password(
        db,
        request,
        user,
        body.current_password.get_secret_value(),
        replacement=body.new_password.get_secret_value(),
    )
    assert hashed is not None
    accounts.change_password(db, user, hashed, digest(request.cookies[COOKIE_NAME]))
    db.commit()
    return Response(status_code=204)


@router.put("/profile")
def update_nickname(body: NicknameUpdate, request: Request, db: DB, user: Writer) -> UserRead:
    profiles.update_nickname(db, user, digest(request.cookies[COOKIE_NAME]), body.nickname)
    db.commit()
    return UserRead.from_user(user)


@router.put("/profile/avatar", openapi_extra=avatars.UPLOAD_BODY)
async def upload_avatar(request: Request, db: DB, user: Writer) -> UserRead:
    image = await avatars.receive_avatar(request)
    session_hash = digest(request.cookies[COOKIE_NAME])

    def save() -> UserRead:
        profiles.update_avatar(db, user, session_hash, image)
        db.commit()
        return UserRead.from_user(user)

    return await run_in_threadpool(save)


@router.delete("/profile/avatar")
def remove_avatar(request: Request, db: DB, user: Writer) -> UserRead:
    profiles.update_avatar(db, user, digest(request.cookies[COOKIE_NAME]), None)
    db.commit()
    return UserRead.from_user(user)


# 新邮箱先记为等待确认并发出确认邮件，原邮箱在确认前照常用于找回密码。空值立即解除绑定。
@router.put("/email", responses={503: {"model": ErrorRead}})
def update_email(
    body: EmailUpdate,
    request: Request,
    background: BackgroundTasks,
    db: DB,
    settings: Config,
    user: Writer,
    language: Language,
) -> UserRead:
    if body.email:
        accounts.ensure_mail_url(settings)
        # 每次申请都会向填写的地址发一封邮件，按账号和来源地址限制次数。
        throttle(request, db, user.id, "confirm")
    accounts.require_password(db, request, user, body.password.get_secret_value())
    token = None
    if body.email:
        token = accounts.request_email(db, user, body.email, settings.email_confirm_ttl_seconds)
    else:
        accounts.clear_email(db, user)
    db.commit()
    schedule_email_confirmation(background, settings, user, body.email, token, language)
    return UserRead.from_user(user)


# 确认邮件里的链接由网页提交到这里。不要求登录：邮件可能在另一台设备上打开。
@router.post("/email/confirm", status_code=204)
def confirm_email(body: EmailConfirm, db: DB, _origin: Origin) -> Response:
    accounts.confirm_email(db, body.token)
    db.commit()
    return Response(status_code=204)


# 找回密码。无论邮箱是否绑定了账号都返回 204，响应不透露账号是否存在。
@router.post("/password-reset", status_code=204, responses={503: {"model": ErrorRead}})
def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    background: BackgroundTasks,
    db: DB,
    settings: Config,
    _origin: Origin,
    language: Language,
) -> Response:
    accounts.ensure_mail_url(settings, msg("auth.thePlatformHasNoPasswordReset"))
    throttle(request, db, body.email, "reset")
    started = accounts.start_password_reset(db, body.email, settings.password_reset_ttl_seconds)
    db.commit()
    if started:
        user, token = started
        background.add_task(
            send_mail,
            settings,
            user.email or body.email,
            *accounts.password_reset_mail(settings, user, token, language),
        )
    return Response(status_code=204)


@router.post("/password-reset/confirm", status_code=204)
def confirm_password_reset(body: PasswordResetConfirm, db: DB, _origin: Origin) -> Response:
    accounts.finish_password_reset(db, body.token, body.password.get_secret_value())
    db.commit()
    return Response(status_code=204)


@router.post("/account/delete", status_code=204)
def delete_account(
    body: AccountDelete,
    request: Request,
    response: Response,
    db: DB,
    settings: Config,
    user: Writer,
) -> Response:
    placeholder = accounts.require_password(
        db, request, user, body.password.get_secret_value(), replacement=secrets.token_urlsafe(32)
    )
    assert placeholder is not None
    accounts.delete_account(db, user, placeholder)
    db.commit()
    clear_cookie(response, settings)
    response.status_code = 204
    return response
