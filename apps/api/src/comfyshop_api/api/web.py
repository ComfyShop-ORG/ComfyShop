"""网页入口。页面路径返回单页应用，公开工作流的链接带上名称和封面供分享预览。"""

from html import escape
from pathlib import Path
import re

from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.types import Scope

from comfyshop_api.models import Workflow
from comfyshop_api.services.workflows import workflow_covers

WORKFLOW_PAGE = re.compile(r"workflows/([0-9a-f-]{36})")
TITLE = "<title>ComfyShop</title>"


def _share_tags(scope: Scope, workflow_id: str, public_url: str | None) -> str | None:
    """公开工作流的标题与预览标签。私有、已删除或不存在的工作流返回 `None`。

    预览图地址优先使用配置的平台地址 `public_url`。
    """
    with Session(scope["app"].state.engine) as db:
        workflow = db.get(Workflow, workflow_id)
        if not workflow or workflow.deleted_at or not workflow.published:
            return None
        name = escape(workflow.name, quote=True)
        tags = [
            f"<title>{name} · ComfyShop</title>",
            f'<meta property="og:title" content="{name}" />',
            '<meta property="og:type" content="website" />',
        ]
        if workflow.description:
            summary = escape(workflow.description[:200], quote=True)
            tags.append(f'<meta property="og:description" content="{summary}" />')
        cover = workflow_covers(db, [workflow], None).get(workflow.id)
        if cover and cover.thumbnail and cover.thumbnail.sizes:
            base = public_url or str(Request(scope).base_url).rstrip("/")
            image = escape(f"{base}{cover.thumbnail.src}?size={cover.thumbnail.sizes[-1]}", True)
            tags.append(f'<meta property="og:image" content="{image}" />')
            tags.append('<meta name="twitter:card" content="summary_large_image" />')
        return "\n    ".join(tags)


class WebStaticFiles(StaticFiles):
    def __init__(self, *, directory: Path, public_url: str | None) -> None:
        super().__init__(directory=directory)
        self.public_url = public_url

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if (
                error.status_code != 404
                or path.split("/", 1)[0] in {"api", "assets"}
                or Path(path).suffix
            ):
                raise
        page = WORKFLOW_PAGE.fullmatch(path.strip("/"))
        if (
            page
            and scope["method"] == "GET"
            and (tags := _share_tags(scope, page.group(1), self.public_url))
        ):
            html = (Path(str(self.directory)) / "index.html").read_text(encoding="utf-8")
            if TITLE in html:
                return HTMLResponse(html.replace(TITLE, tags, 1))
        return await super().get_response("index.html", scope)
