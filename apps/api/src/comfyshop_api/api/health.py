from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from comfyshop_api.core.config import Settings, get_settings
from comfyshop_api.core.i18n import Language
from comfyshop_api.core.languages import language_menu

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


@router.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name)


class PresentationResponse(BaseModel):
    language: str
    menu: list[str]


@router.get("/presentation")
def presentation(
    language: Language, settings: Annotated[Settings, Depends(get_settings)]
) -> PresentationResponse:
    return PresentationResponse(language=language, menu=language_menu(settings.menu_languages))
