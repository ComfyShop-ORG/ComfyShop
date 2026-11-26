"""当前登录设备的生成完成通知设置。"""

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

from comfyshop_api.core.i18n import Language, msg
from comfyshop_api.models import now_ms
from comfyshop_api.schemas import WebPushRead, WebPushWrite
from comfyshop_api.security import COOKIE_NAME, DB, CurrentUser, LockedWriter, digest
from comfyshop_api.services import web_push

router = APIRouter(prefix="/web-push", tags=["web-push"])


@router.get("")
def preference(request: Request, response: Response, db: DB, _user: CurrentUser) -> WebPushRead:
    key = request.app.state.web_push_key
    response.headers["Cache-Control"] = "no-store"
    current = web_push.subscription(db, digest(request.cookies[COOKIE_NAME]))
    return WebPushRead(
        public_key=web_push.public_key(key) if key is not None else None,
        enabled=current is not None
        and (current.expires_at is None or current.expires_at > now_ms()),
    )


@router.put("", status_code=204)
def enable(
    body: WebPushWrite, request: Request, db: DB, _user: LockedWriter, language: Language
) -> None:
    if request.app.state.web_push_key is None:
        raise HTTPException(503, msg("webPush.disabled"))
    try:
        web_push.save_subscription(db, digest(request.cookies[COOKIE_NAME]), body, language)
        db.commit()
    except ValueError as error:
        raise HTTPException(422, msg("webPush.invalidSubscription")) from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, msg("webPush.subscriptionChanged")) from error


@router.delete("", status_code=204)
def disable(request: Request, db: DB, _user: LockedWriter) -> None:
    web_push.remove_subscription(db, digest(request.cookies[COOKIE_NAME]))
    db.commit()
