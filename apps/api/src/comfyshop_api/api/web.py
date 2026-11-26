"""网页入口。页面路径返回单页应用，公开工作流的链接带上名称和封面供分享预览。"""

import re
from html import escape
from pathlib import Path
from urllib.parse import urlencode

from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.types import Scope

from comfyshop_api.core.i18n import SOURCE_LANGUAGE, localize, msg, request_language
from comfyshop_api.core.languages import LANGUAGES, language_menu
from comfyshop_api.models import Workflow
from comfyshop_api.services.workflows import visible_version, workflow_covers, workflow_text

WORKFLOW_PAGE = re.compile(r"workflows/([0-9a-f-]{36})")
TITLE = "<title>ComfyShop</title>"
_ENCODING = re.compile(
    r"(gzip|identity|\*)(?:\s*;\s*q\s*=\s*(0(?:\.\d{0,3})?|1(?:\.0{0,3})?))?",
    re.IGNORECASE | re.ASCII,
)


def _prefers_gzip(accept_encoding: str) -> bool:
    weights = {
        match[1].lower(): float(match[2] or 1)
        for entry in accept_encoding.split(",")
        if (match := _ENCODING.fullmatch(entry.strip()))
    }
    gzip = weights.get("gzip", weights.get("*", 0))
    if gzip > 0 and gzip >= weights.get("identity", 0):
        return True
    if weights.get("identity", weights.get("*", 1)) == 0:
        raise HTTPException(406, headers={"Vary": "Accept-Encoding"})
    return False


def _share_tags(
    scope: Scope, workflow_id: str, public_url: str | None, language: str
) -> str | None:
    """为公开工作流生成分享预览。私有页面继续由会话接口核对权限。

    预览图地址优先使用配置的平台地址 `public_url`。
    """
    with Session(scope["app"].state.engine) as db:
        workflow = db.scalar(
            select(Workflow).where(
                Workflow.id == workflow_id,
                Workflow.publicly_visible(),
                Workflow.published_version_id.is_not(None),
            )
        )
        if not workflow:
            return None
        title, description = workflow_text(workflow, visible_version(workflow, None), language)
        name = escape(title, quote=True)
        tags = [
            f"<title>{name} · ComfyShop</title>",
            f'<meta property="og:title" content="{name}" />',
            '<meta property="og:type" content="website" />',
        ]
        if description:
            summary = escape(description[:200], quote=True)
            tags.append(f'<meta property="og:description" content="{summary}" />')
        cover = workflow_covers(db, [workflow], None).get(workflow.id)
        if cover and cover.thumbnail and cover.thumbnail.sizes:
            base = public_url or str(Request(scope).base_url).rstrip("/")
            separator = "&" if "?" in cover.thumbnail.src else "?"
            size = urlencode({"size": cover.thumbnail.sizes[-1]})
            image = escape(f"{base}{cover.thumbnail.src}{separator}{size}", True)
            tags.append(f'<meta property="og:image" content="{image}" />')
            tags.append('<meta name="twitter:card" content="summary_large_image" />')
    return "\n    ".join(tags)


class WebStaticFiles(StaticFiles):
    def __init__(
        self, *, directory: Path, public_url: str | None, menu_languages: str | None
    ) -> None:
        super().__init__(directory=directory)
        self.gzip_scripts = {
            script.relative_to(directory).as_posix()
            for script in (directory / "assets").rglob("*.js")
            if script.with_suffix(".js.gz").is_file()
        }
        self.public_url = public_url
        self.menu = ",".join(language_menu(menu_languages))

    async def get_response(self, path: str, scope: Scope) -> Response:
        path = path.strip("/")
        if path == "index.html":
            raise HTTPException(404)
        if path in self.gzip_scripts and scope["method"] in {"GET", "HEAD"}:
            headers = Headers(scope=scope)
            gzip = _prefers_gzip(",".join(headers.getlist("accept-encoding")))
            response = await super().get_response(path + ".gz" if gzip else path, scope)
            response.headers.add_vary_header("Accept-Encoding")
            if gzip and isinstance(response, FileResponse):
                response.headers["Content-Encoding"] = "gzip"
                response.headers["Content-Type"] = "text/javascript; charset=utf-8"
                if "," in headers.get("range", ""):
                    # 多段响应的 MIME 边界不属于 gzip 数据流，直接发整份压缩脚本。
                    body = b""
                    if scope["method"] == "GET":
                        body = await run_in_threadpool(Path(response.path).read_bytes)
                    return Response(body, headers=response.headers)
            return response
        try:
            response = await super().get_response(path, scope)
            if path in {"service-worker.js", "manifest.webmanifest"}:
                response.headers["Cache-Control"] = "no-cache"
            return response
        except HTTPException as error:
            if (
                error.status_code != 404
                or path.split("/", 1)[0] in {"api", "assets", "downloads"}
                or (path != "." and Path(path).suffix)
            ):
                raise
        language = request_language(Request(scope))
        locale = LANGUAGES[language]["locale"]
        page = WORKFLOW_PAGE.fullmatch(path)
        tags = (
            await run_in_threadpool(_share_tags, scope, page.group(1), self.public_url, language)
            if page
            else None
        )
        html = await run_in_threadpool(
            (Path(str(self.directory)) / "index.html").read_text, encoding="utf-8"
        )
        attributes = f'lang="{locale}" data-language="{language}" data-menu-languages="{self.menu}"'
        html = html.replace('<html lang="zh-CN"', f"<html {attributes}", 1)
        description = msg("web.description")
        html = html.replace(
            localize(description, SOURCE_LANGUAGE),
            escape(localize(description, language), quote=True),
            1,
        )
        if tags:
            html = html.replace(TITLE, tags, 1)
        return HTMLResponse(
            html if scope["method"] == "GET" else "",
            headers={
                "Content-Language": locale,
                "Cache-Control": "no-cache",
                "Vary": "Cookie, Accept-Language",
            },
        )
