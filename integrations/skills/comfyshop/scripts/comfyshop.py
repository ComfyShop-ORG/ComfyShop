"""Install the ComfyShop Skill and call its user API using the standard library."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import warnings
from contextlib import contextmanager, nullcontext
from getpass import GetPassWarning, getpass
from hashlib import sha256
from http.client import HTTPException
from http.cookiejar import LWPCookieJar
from io import BytesIO
from pathlib import Path
from shutil import copyfileobj
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Literal, NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

ARCHIVE = "/downloads/comfyshop-skill.zip"
# 平台在下载时把自己的地址写进启动包，静态目录里的原始包不含地址。
WORKER_ARCHIVE = "/api/v1/worker/package"
SKILL_FILES = {"SKILL.md", "scripts/comfyshop.py"}
CLIENTS = {"codex": ".agents", "claude-code": ".claude"}
MAX_ARCHIVE_BYTES = 1024 * 1024
OFFICIAL_TEMPLATE_CATEGORIES = {
    "Image": "image",
    "Image Tools": "image_tool",
    "Video": "video",
    "Video Tools": "video_tool",
    "Audio": "audio",
    "3D Model": "3d",
    "Vector": "vector",
    "LLM": "llm",
    "Node Basics": "node_basics",
    "Product & Ads": "product_ads",
    "Character & Fashion": "character_fashion",
    "Brand & Design": "brand_design",
}
COMMIT_SHA = re.compile(r"[0-9a-f]{40}")


class Operation(NamedTuple):
    method: str
    path: str
    filters: tuple[str, ...] = ()
    payload: bool = False
    output: Literal["json", "graph", "file"] = "json"
    binary: bool = False
    repeatable_filters: tuple[str, ...] = ()


# BEGIN GENERATED API CONTRACT
WORKFLOW_CATEGORIES = (
    "image",
    "image_tool",
    "video",
    "video_tool",
    "audio",
    "3d",
    "vector",
    "llm",
    "node_basics",
    "product_ads",
    "character_fashion",
    "brand_design",
)

OPERATIONS = {
    "platform.health": Operation("GET", "/health"),
    "platform.presentation": Operation("GET", "/presentation"),
    "workspace.favorites": Operation("GET", "/workspace", ("workspace_team",)),
    "workspace.shares": Operation("GET", "/workspace/shares", ("direction", "cursor", "limit")),
    "workspace.shared": Operation("GET", "/workspace/shared/{owner_id}"),
    "workspace.grant": Operation("PUT", "/workspace/shares/by-name/{username}"),
    "workspace.revoke": Operation("DELETE", "/workspace/shares/{viewer_id}"),
    "project.list": Operation(
        "GET",
        "/projects",
        ("search", "archived", "cursor", "limit", "workspace_team", "workspace_owner"),
    ),
    "project.create": Operation("POST", "/projects", ("workspace_team",), payload=True),
    "project.get": Operation(
        "GET", "/projects/{project_id}", ("workspace_team", "workspace_owner")
    ),
    "project.update": Operation("PUT", "/projects/{project_id}", ("workspace_team",), payload=True),
    "project.archive": Operation(
        "PUT", "/projects/{project_id}/archive", ("workspace_team",), payload=True
    ),
    "project.delete": Operation("DELETE", "/projects/{project_id}", ("workspace_team",)),
    "project.restore": Operation("POST", "/projects/{project_id}/restore", ("workspace_team",)),
    "project.link-material": Operation(
        "PUT", "/projects/{project_id}/{kind}/{record_id}", ("workspace_team",)
    ),
    "project.unlink-material": Operation(
        "DELETE", "/projects/{project_id}/{kind}/{record_id}", ("workspace_team",)
    ),
    "team.list": Operation("GET", "/teams", ("cursor", "limit")),
    "team.create": Operation("POST", "/teams", payload=True),
    "team.get": Operation("GET", "/teams/{team_id}"),
    "team.public-profile": Operation("GET", "/teams/{team_id}/public"),
    "team.set-profile-visibility": Operation(
        "PUT", "/teams/{team_id}/profile-visibility", payload=True
    ),
    "team.rename": Operation("PATCH", "/teams/{team_id}", payload=True),
    "team.avatar-upload": Operation("PUT", "/teams/{team_id}/avatar", payload=True, binary=True),
    "team.avatar-remove": Operation("DELETE", "/teams/{team_id}/avatar"),
    "team.avatar": Operation("GET", "/teams/{team_id}/avatar/{version}", output="file"),
    "team.archive": Operation("DELETE", "/teams/{team_id}"),
    "team.archived": Operation("GET", "/teams/archived", ("cursor", "limit")),
    "team.restore": Operation("POST", "/teams/{team_id}/restore"),
    "team.members": Operation("GET", "/teams/{team_id}/members", ("cursor", "limit")),
    "team.events": Operation(
        "GET",
        "/teams/{team_id}/events",
        ("actor", "category", "created_from", "created_before", "cursor", "limit"),
    ),
    "team.set-member": Operation(
        "PUT", "/teams/{team_id}/members/by-name/{username}", payload=True
    ),
    "team.remove-member": Operation("DELETE", "/teams/{team_id}/members/{member_id}"),
    "team.transfer": Operation("PUT", "/teams/{team_id}/owner/{member_id}"),
    "team.import-workflow": Operation("POST", "/teams/{team_id}/workflows", payload=True),
    "team.update-workflow": Operation(
        "PATCH", "/teams/{team_id}/workflows/{workflow_id}", payload=True
    ),
    "team.copy-workflow": Operation(
        "POST", "/teams/{team_id}/workflows/{workflow_id}/copy", ("version_id",)
    ),
    "team.set-workflow-cover": Operation(
        "PUT", "/teams/{team_id}/workflows/{workflow_id}/cover", payload=True
    ),
    "team.favorite": Operation("PUT", "/teams/{team_id}/workflows/{workflow_id}/favorite"),
    "team.unfavorite": Operation("DELETE", "/teams/{team_id}/workflows/{workflow_id}/favorite"),
    "team.upload-asset": Operation(
        "PUT",
        "/teams/{team_id}/assets/{asset_id}",
        ("filename", "save_to_library"),
        payload=True,
        binary=True,
    ),
    "team.copy-asset": Operation("POST", "/teams/{team_id}/assets/{asset_id}/copy"),
    "account.official-import-grants": Operation(
        "GET", "/auth/official-import-grants", ("cursor", "limit")
    ),
    "account.set-official-import-grant": Operation(
        "PUT", "/auth/official-import-grants/{username}", payload=True
    ),
    "workflow.get": Operation(
        "GET", "/workflows/{workflow_id}", ("version_id", "workspace_team", "workspace_owner")
    ),
    "workflow.versions": Operation(
        "GET", "/workflows/{workflow_id}/versions", ("workspace_owner", "workspace_team")
    ),
    "workflow.service-inputs": Operation(
        "GET",
        "/workflows/{workflow_id}/service-inputs",
        ("workspace_team", "version_id", "execution_id", "work_id"),
    ),
    "workflow.import-reference": Operation(
        "POST", "/workflows/from-connection", ("workspace_team",), payload=True
    ),
    "workflow.import": Operation("POST", "/workflows", payload=True),
    "workflow.update": Operation("PATCH", "/workflows/{workflow_id}", payload=True),
    "workflow.restore": Operation("POST", "/workflows/{workflow_id}/restore", ("workspace_team",)),
    "workflow.delete": Operation("DELETE", "/workflows/{workflow_id}", ("workspace_team",)),
    "workflow.graph": Operation(
        "GET",
        "/workflows/{workflow_id}/graph",
        ("version_id", "workspace_team", "workspace_owner"),
        output="graph",
    ),
    "workflow.set-layout": Operation(
        "PUT",
        "/workflows/{workflow_id}/versions/{version_id}/parameter-layout",
        ("workspace_team",),
        payload=True,
    ),
    "workflow.publish": Operation("POST", "/workflows/{workflow_id}/publish", ("workspace_team",)),
    "workflow.set-cover": Operation("PUT", "/workflows/{workflow_id}/cover", payload=True),
    "workflow.cover-thumbnail": Operation(
        "GET", "/workflows/{workflow_id}/cover/{sha256}/thumbnail", ("size",), output="file"
    ),
    "workflow.favorite": Operation("PUT", "/workflows/{workflow_id}/favorite"),
    "workflow.unfavorite": Operation("DELETE", "/workflows/{workflow_id}/favorite"),
    "task.list": Operation(
        "GET",
        "/tasks",
        (
            "workflow_id",
            "version_id",
            "project_id",
            "state",
            "cursor",
            "limit",
            "workspace_team",
            "workspace_owner",
        ),
    ),
    "task.activity": Operation(
        "GET",
        "/tasks/activity",
        ("workflow_id", "version_id", "task_id", "project_id", "workspace_team", "workspace_owner"),
    ),
    "task.cost-estimate": Operation(
        "POST", "/tasks/cost-estimate", ("workspace_team",), payload=True
    ),
    "task.get": Operation("GET", "/tasks/{task_id}", ("workspace_team", "workspace_owner")),
    "task.inputs": Operation(
        "GET", "/tasks/{task_id}/inputs", ("workspace_team", "workspace_owner")
    ),
    "task.graph": Operation("GET", "/tasks/{task_id}/graph", ("workspace_team",), output="graph"),
    "task.restore": Operation("POST", "/tasks/{task_id}/restore", ("workspace_team",)),
    "task.resume": Operation("POST", "/tasks/{task_id}/resume", ("workspace_team",)),
    "task.change-machine": Operation(
        "PUT", "/tasks/{task_id}/machine", ("workspace_team",), payload=True
    ),
    "task.change-project": Operation(
        "PUT", "/tasks/{task_id}/project", ("workspace_team",), payload=True
    ),
    "task.retry-executions": Operation(
        "POST", "/tasks/{task_id}/retry-executions", ("workspace_team",), payload=True
    ),
    "task.cancel": Operation("POST", "/tasks/{task_id}/cancel", ("workspace_team",)),
    "task.delete": Operation("DELETE", "/tasks/{task_id}", ("workspace_team",)),
    "execution.list": Operation(
        "GET",
        "/executions",
        (
            "workflow_id",
            "version_id",
            "task_id",
            "project_id",
            "workflow_name",
            "created_from",
            "created_before",
            "cursor",
            "limit",
            "workspace_team",
            "workspace_owner",
        ),
    ),
    "execution.get": Operation(
        "GET", "/executions/{execution_id}", ("workspace_team", "workspace_owner")
    ),
    "execution.replay": Operation("GET", "/executions/{execution_id}/replay", ("workspace_team",)),
    "execution.set-cover": Operation(
        "PUT", "/executions/{execution_id}/cover", ("workspace_team",), payload=True
    ),
    "execution.cover-thumbnail": Operation(
        "GET", "/executions/{execution_id}/cover/{sha256}/thumbnail", ("size",), output="file"
    ),
    "execution.delete-artifacts": Operation(
        "DELETE", "/executions/{execution_id}/artifacts", ("workspace_team",)
    ),
    "execution.restore-artifacts": Operation(
        "POST", "/executions/{execution_id}/artifacts/restore", ("workspace_team",)
    ),
    "artifact.list": Operation(
        "GET",
        "/artifacts",
        (
            "workflow_id",
            "task_id",
            "execution_id",
            "cursor",
            "limit",
            "workspace_team",
            "workspace_owner",
        ),
    ),
    "artifact.thumbnail": Operation(
        "GET", "/artifacts/{artifact_id}/thumbnail", ("size",), output="file"
    ),
    "artifact.cover-frame": Operation(
        "GET", "/artifacts/{artifact_id}/frames/{frame_ms}/thumbnail", ("size",), output="file"
    ),
    "artifact.video-preview": Operation(
        "GET", "/artifacts/{artifact_id}/video-preview", ("size",), output="file"
    ),
    "artifact.delete": Operation("DELETE", "/artifacts/{artifact_id}", ("workspace_team",)),
    "artifact.restore": Operation("POST", "/artifacts/{artifact_id}/restore", ("workspace_team",)),
    "artifact.save-to-library": Operation(
        "PUT", "/artifacts/{artifact_id}/library", ("workspace_team",)
    ),
    "artifact.inpaint-targets": Operation(
        "GET", "/artifacts/{artifact_id}/inpaint-targets", ("workspace_team",)
    ),
    "artifact.use-as-input": Operation(
        "PUT", "/artifacts/{artifact_id}/input", ("workspace_team",)
    ),
    "asset.list": Operation(
        "GET",
        "/assets",
        (
            "kind",
            "content_types",
            "search",
            "project_id",
            "cursor",
            "limit",
            "workspace_team",
            "workspace_owner",
        ),
        repeatable_filters=("content_types",),
    ),
    "asset.usage": Operation("GET", "/assets/usage", ("workspace_team", "workspace_owner")),
    "asset.get": Operation("GET", "/assets/{asset_id}", ("workspace_team", "workspace_owner")),
    "asset.thumbnail": Operation("GET", "/assets/{asset_id}/thumbnail", ("size",), output="file"),
    "asset.download": Operation("GET", "/assets/{asset_id}/file", output="file"),
    "asset.delete": Operation("DELETE", "/assets/{asset_id}"),
    "asset.save-to-library": Operation("PUT", "/assets/{asset_id}/library", ("workspace_team",)),
    "asset.remove-from-library": Operation(
        "DELETE", "/assets/{asset_id}/library", ("workspace_team",)
    ),
    "work.list": Operation(
        "GET",
        "/works",
        (
            "scope",
            "category",
            "workflow_id",
            "version_id",
            "current_version_only",
            "author",
            "public_team_id",
            "project_id",
            "cursor",
            "limit",
            "workspace_team",
            "workspace_owner",
        ),
    ),
    "work.get": Operation("GET", "/works/{work_id}", ("workspace_team", "workspace_owner")),
    "work.set-cover": Operation("PUT", "/works/{work_id}/cover", ("workspace_team",), payload=True),
    "work.cover-thumbnail": Operation(
        "GET", "/works/{work_id}/cover/{sha256}/thumbnail", ("size",), output="file"
    ),
    "work.artifacts": Operation(
        "GET",
        "/works/{work_id}/artifacts",
        ("cursor", "limit", "workspace_team", "workspace_owner"),
    ),
    "work.inputs": Operation(
        "GET", "/works/{work_id}/inputs", ("workspace_team", "workspace_owner")
    ),
    "work.asset-download": Operation(
        "GET", "/works/{work_id}/assets/{asset_id}/file", ("download",), output="file"
    ),
    "work.asset-thumbnail": Operation(
        "GET", "/works/{work_id}/assets/{asset_id}/thumbnail", ("size",), output="file"
    ),
    "work.replay": Operation("GET", "/works/{work_id}/replay", ("workspace_team",)),
    "work.publish": Operation("POST", "/works", ("workspace_team",), payload=True),
    "work.unpublish": Operation("DELETE", "/works/{work_id}", ("workspace_team",)),
    "work.delete": Operation("POST", "/works/{work_id}/delete", ("workspace_team",)),
    "work.restore": Operation("POST", "/works/{work_id}/restore", ("workspace_team",)),
    "author.get": Operation("GET", "/authors/{username}"),
    "author.avatar": Operation("GET", "/authors/{user_id}/avatar/{version}", output="file"),
    "account.nickname": Operation("PUT", "/auth/profile", payload=True),
    "account.avatar-upload": Operation("PUT", "/auth/profile/avatar", payload=True, binary=True),
    "account.avatar-remove": Operation("DELETE", "/auth/profile/avatar"),
    "account.password": Operation("POST", "/auth/password", payload=True),
    "account.email": Operation("PUT", "/auth/email", payload=True),
    "account.email-confirm": Operation("POST", "/auth/email/confirm", payload=True),
    "account.password-reset": Operation("POST", "/auth/password-reset", payload=True),
    "account.password-reset-confirm": Operation(
        "POST", "/auth/password-reset/confirm", payload=True
    ),
    "account.delete": Operation("POST", "/auth/account/delete", payload=True),
    "machine.link": Operation("GET", "/machines/links/{code}", ("workspace_team",)),
    "machine.link-approve": Operation(
        "POST", "/machines/links/{code}/approve", ("workspace_team",), payload=True
    ),
    "machine.add-connection": Operation(
        "POST", "/machines/connections", ("workspace_team",), payload=True
    ),
    "machine.update-connection": Operation(
        "PUT", "/machines/{machine_id}/connection", ("workspace_team",), payload=True
    ),
    "machine.get": Operation("GET", "/machines/{machine_id}", ("workspace_team",)),
    "machine.rename": Operation(
        "PATCH", "/machines/{machine_id}", ("workspace_team",), payload=True
    ),
    "machine.set-default": Operation("PUT", "/machines/{machine_id}/default", ("workspace_team",)),
    "machine.pause": Operation(
        "PUT", "/machines/{machine_id}/pause", ("workspace_team",), payload=True
    ),
    "machine.update": Operation("PUT", "/machines/{machine_id}/update", ("workspace_team",)),
    "machine.revoke": Operation("DELETE", "/machines/{machine_id}", ("workspace_team",)),
    "machine.delete": Operation("DELETE", "/machines/{machine_id}/record", ("workspace_team",)),
}
# END GENERATED API CONTRACT


class ClientError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def connection_url(value: str, *, allow_path: bool = False) -> str:
    address = urlsplit(value.strip())
    if (
        address.scheme not in {"https", "http"}
        or not address.hostname
        or address.username is not None
        or not allow_path
        and address.path not in {"", "/"}
        or address.query
        or address.fragment
        or any(char.isspace() for char in address.netloc)
    ):
        raise ClientError("请使用 ComfyShop 的 HTTP 或 HTTPS 站点地址")
    port = address.port
    host = address.hostname
    if ":" in host:
        host = f"[{host}]"
    if port is not None and port != (443 if address.scheme == "https" else 80):
        host = f"{host}:{port}"
    return f"{address.scheme}://{host}{address.path.rstrip('/')}"


def open_response(opener, request: Request):
    try:
        return opener.open(request, timeout=30)
    except HTTPError as error:
        with error:
            message = f"平台请求失败（HTTP {error.code}）"
            if error.headers.get_content_type() == "application/json":
                try:
                    detail = json.loads(error.read(8192))["detail"]
                    if isinstance(detail, str):
                        message = detail
                except (ValueError, KeyError, TypeError):
                    pass
        raise ClientError(message, error.code) from None
    except (URLError, TimeoutError, HTTPException):
        raise ClientError("无法连接 ComfyShop，请检查站点地址和网络") from None


class Client:
    def __init__(self, server: str, language: str | None = None):
        self.server = server
        self.language = language
        session_id = sha256(server.encode()).hexdigest()
        self.session_file = Path.home() / ".comfyshop" / "sessions" / f"{session_id}.cookies"
        self.cookies = LWPCookieJar(str(self.session_file))
        if self.session_file.is_file():
            self.cookies.load()
        self.opener = build_opener(NoRedirect(), HTTPCookieProcessor(self.cookies))

    def open(self, method: str, path: str, *, data=None, headers=None):
        request_headers = {"Origin": self.server}
        if self.language:
            request_headers["Accept-Language"] = self.language
        request = Request(
            self.server + "/api/v1" + path,
            data=data,
            method=method,
            headers=request_headers | (headers or {}),
        )
        return open_response(self.opener, request)

    def request(self, method: str, path: str, body=None, *, csrf: str | None = None) -> Any:
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode()
        if csrf is not None:
            headers["X-CSRF-Token"] = csrf
        with self.open(method, path, data=data, headers=headers) as response:
            if response.status == 204:
                return {}
            result = json.load(response)
            if not isinstance(result, (dict, list)):
                raise ClientError("平台响应无效")
            return result

    def upload(self, path: str, file: Path, csrf: str) -> Any:
        headers = {"Content-Type": "application/octet-stream", "X-CSRF-Token": csrf}
        with file.open("rb") as source:
            headers["Content-Length"] = str(os.fstat(source.fileno()).st_size)
            with self.open("PUT", path, data=source, headers=headers) as response:
                return json.load(response)

    def session(self):
        return self.request("GET", "/auth/session")

    def csrf(self) -> str:
        session = self.session()
        if not session["user"] or not session["csrfToken"]:
            raise ClientError("请先在终端运行 ComfyShop Skill 的 login 命令", 401)
        return session["csrfToken"]

    def login(self, username: str, password: str, *, register: bool = False):
        path = "/auth/register" if register else "/auth/login"
        session = self.request("POST", path, {"username": username, "password": password})
        if not session["user"] or not any(
            cookie.name == "comfyshop_session"
            and (not cookie.secure or self.server.startswith("https://"))
            for cookie in self.cookies
        ):
            raise ClientError("站点没有返回可用的登录会话")
        self.session_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=self.session_file.parent, delete=False) as output:
            temporary = Path(output.name)
        try:
            self.cookies.save(str(temporary))
            temporary.replace(self.session_file)
        finally:
            temporary.unlink(missing_ok=True)
        return session["user"]

    def logout(self):
        session = self.session()
        if session["user"]:
            self.request("POST", "/auth/logout", csrf=session["csrfToken"])
        self.session_file.unlink(missing_ok=True)

    def pages(self, path: str, **filters):
        cursor = None
        while True:
            page = self.request("GET", query(path, **filters, cursor=cursor, limit=100))
            yield from page["items"]
            cursor = page["nextCursor"]
            if not cursor:
                break


def query(path: str, **params) -> str:
    values = {key: value for key, value in params.items() if value is not None}
    return path + "?" + urlencode(values, doseq=True) if values else path


def identifier(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", value):
        raise ClientError("请使用平台返回的记录 ID")
    return value


def path_value(parameter: str, value: str) -> str:
    if parameter != "username":
        return identifier(value)
    if not re.fullmatch(r"[\w-]{2,32}", value):
        raise ClientError("请使用平台返回的账号名")
    return quote(value, safe="")


def path_parameters(operation: Operation) -> list[str]:
    return re.findall(r"\{([a-z_]+)\}", operation.path)


def list_operations() -> dict:
    return {
        "operations": [
            {
                "name": name,
                "method": operation.method,
                "path": operation.path,
                "ids": path_parameters(operation),
                "query": operation.filters,
                "requiresBody": operation.payload,
                "bodyFormat": ("file" if operation.binary else "json")
                if operation.payload
                else None,
                "output": operation.output,
            }
            for name, operation in OPERATIONS.items()
        ]
    }


@contextmanager
def new_output(destination: Path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            yield output
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def call_operation(client: Client, args: argparse.Namespace) -> Any:
    operation = OPERATIONS[args.operation]
    parameters = path_parameters(operation)
    if len(parameters) != len(args.ids):
        raise ClientError("所需位置参数为 " + ("、".join(parameters) or "无"))
    path = operation.path.format(
        **{name: path_value(name, value) for name, value in zip(parameters, args.ids, strict=True)}
    )
    filters: dict[str, list[str]] = {}
    for item in args.query:
        key, delimiter, value = item.partition("=")
        if (
            not delimiter
            or key not in operation.filters
            or (key in filters and key not in operation.repeatable_filters)
        ):
            raise ClientError(f"无效或重复的查询参数 {key}")
        filters.setdefault(key, []).append(value)
    path = query(path, **filters)

    if operation.payload != (args.body is not None):
        source = "文件" if operation.binary else "JSON文件"
        raise ClientError(
            f"此操作需要 --body {source}" if operation.payload else "此操作不接受 --body"
        )
    body = None
    if args.body and not operation.binary:
        body = json.loads(args.body.read_text(encoding="utf-8-sig"))
        if not isinstance(body, dict):
            raise ClientError("请求文件需要包含一个 JSON 对象")
    if operation.output == "file":
        if args.out is None:
            raise ClientError("请通过 --out 指定下载文件")
        with client.open("GET", path) as response:
            return save_download(response, args.out)

    csrf = client.csrf() if operation.method != "GET" else None
    with new_output(args.out) if args.out else nullcontext() as output:
        if operation.binary:
            assert args.body is not None and csrf is not None
            result = client.upload(path, args.body, csrf)
        else:
            result = client.request(operation.method, path, body, csrf=csrf)
        if args.operation == "workflow.import":
            explain_import_format(result)
        if operation.output == "graph":
            result = result["graph"]
        if output is not None:
            output.write(json_bytes(result))
    return {"path": str(args.out.resolve())} if args.out else result


def explain_import_format(workflow: dict) -> None:
    if workflow.get("format") == "ui":
        print("已保存编辑器格式。运行请从 ComfyUI 导出 API JSON，并上传新版本。", file=sys.stderr)


def configure_machine(client: Client, args: argparse.Namespace) -> dict:
    if args.command == "machine-create":
        path, body = "/machines", {"name": args.name}
    else:
        path, body = f"/machines/{identifier(args.machine_id)}/rotate", None
    config = {
        "serverUrl": connection_url(args.platform_url or client.server, allow_path=True),
        "comfyUrl": connection_url(args.comfy_url, allow_path=True),
    }
    csrf = client.csrf()
    issued = False
    try:
        with new_output(args.out) as output:
            result = client.request("POST", path, body, csrf=csrf)
            issued = True
            config["apiKey"] = result["apiKey"]
            output.write(json_bytes(config))
            output.flush()
            os.fsync(output.fileno())
    except (OSError, ValueError, KeyError, TypeError):
        if issued:
            raise ClientError("平台已签发密钥，配置保存失败。请先核对工作机状态") from None
        raise
    return {"machine": result["machine"], "path": str(args.out.resolve())}


def install(server: str, agent: str) -> Path:
    request = Request(server + ARCHIVE)
    with open_response(build_opener(NoRedirect()), request) as response:
        content = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(content) > MAX_ARCHIVE_BYTES:
        raise ClientError("Skill 安装包过大")

    parent = Path.home() / CLIENTS[agent] / "skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / "comfyshop"
    if target.is_symlink() or (target.exists() and not (target / "platform.json").is_file()):
        raise ClientError(f"已有 ComfyShop Skill，请先移走这个目录：{target}")
    with (
        ZipFile(BytesIO(content)) as archive,
        TemporaryDirectory(prefix=".comfyshop-", dir=parent.parent) as temporary,
    ):
        names = archive.namelist()
        files = {name.removeprefix("comfyshop/") for name in names if name.startswith("comfyshop/")}
        if (
            len(files) != len(names)
            or not SKILL_FILES <= files
            or any(
                not re.fullmatch(r"references/[a-z][a-z0-9-]*\.md", name)
                for name in files - SKILL_FILES
            )
        ):
            raise ClientError("Skill 安装包内容不完整")
        if sum(archive.getinfo(name).file_size for name in names) > MAX_ARCHIVE_BYTES:
            raise ClientError("Skill 安装包内容过大")
        staging = Path(temporary) / "install"
        for name in sorted(files):
            output = staging / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(f"comfyshop/{name}"))
        (staging / "platform.json").write_text(
            json.dumps({"server": server}) + "\n", encoding="utf-8"
        )
        previous = Path(temporary) / "previous"
        try:
            if target.exists():
                target.rename(previous)
            staging.rename(target)
        except (OSError, KeyboardInterrupt):
            if previous.exists() and not target.exists():
                previous.rename(target)
            raise
    return target


def interactive_login(client: Client, *, register: bool = False):
    session = client.session()
    if session["user"]:
        if register:
            raise ClientError("请先退出当前 Skill 会话，再注册新账号")
        return session["user"]
    if not sys.stdin.isatty():
        command = "register" if register else "login"
        raise ClientError(f"请在自己的终端运行 {command}，并在终端输入账号和密码")
    username = input(f"ComfyShop 账号（{client.server}）：").strip()
    with warnings.catch_warnings():
        warnings.simplefilter("error", GetPassWarning)
        password = getpass("密码：")
    return client.login(username, password, register=register)


def submit(client: Client, plan: Path, *, workspace_team: str | None = None) -> tuple[dict, int]:
    content = json.loads(plan.read_text(encoding="utf-8-sig"))
    tasks = content if isinstance(content, list) else [content]
    if not tasks or any(not isinstance(item, dict) for item in tasks):
        raise ClientError("任务文件需要包含一个对象或非空的任务对象列表")
    keys = [item.get("idempotencyKey") for item in tasks]
    if any(
        not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{16,64}", key) for key in keys
    ):
        raise ClientError("任务文件中的每套输入需要一个有效的 idempotencyKey")
    if len(set(keys)) != len(keys):
        raise ClientError("任务文件里的每套输入需要不同的 idempotencyKey")

    csrf = client.csrf()
    endpoint = query("/tasks", workspace_team=workspace_team)
    accepted = []
    for index, task in enumerate(tasks):
        try:
            accepted.append(client.request("POST", endpoint, task, csrf=csrf))
        except (ClientError, OSError, ValueError, HTTPException) as error:
            status = error.status if isinstance(error, ClientError) else None
            message = str(error) if isinstance(error, ClientError) else "平台响应未能确认"
            return {
                "tasks": accepted,
                "stoppedAt": {
                    "index": index,
                    "idempotencyKey": keys[index],
                    "httpStatus": status,
                    "error": message,
                },
                "remaining": len(tasks) - index - 1,
            }, 1
    return {"tasks": accepted}, 0


def results(client: Client, task_id: str, *, workspace_owner: str | None = None) -> dict:
    executions = []
    for execution in client.pages("/executions", task_id=task_id, workspace_owner=workspace_owner):
        artifacts = []
        for artifact in client.pages(
            "/artifacts", execution_id=execution["id"], workspace_owner=workspace_owner
        ):
            original = artifact["media"].get("video") or artifact["media"]["src"]
            artifacts.append(
                {
                    **artifact,
                    "url": client.server + original,
                }
            )
        executions.append(
            {"id": execution["id"], "index": execution["index"], "artifacts": artifacts}
        )
    return {"taskId": task_id, "executions": sorted(executions, key=lambda item: item["index"])}


def upload(client: Client, path: Path, asset_id: UUID, *, save_to_library: bool = False):
    endpoint = query(
        f"/assets/{asset_id}",
        filename=path.name,
        save_to_library="true" if save_to_library else None,
    )
    return client.upload(endpoint, path, client.csrf())


def save_download(response, destination: Path) -> dict:
    with new_output(destination) as output:
        copyfileobj(response, output)
        size = response.headers.get("Content-Length")
        if size is not None and output.tell() != int(size):
            raise ClientError("下载未完成")
    return {"path": str(destination.resolve())}


def download(client: Client, artifact_id: str, destination: Path) -> dict:
    endpoint = f"/artifacts/{quote(artifact_id, safe='')}/file"
    with client.open("GET", endpoint) as response:
        return save_download(response, destination)


def official_template(index: Path, name: str) -> tuple[str, dict]:
    groups = json.loads(index.read_text(encoding="utf-8-sig"))
    if not isinstance(groups, list):
        raise ClientError("请提供 ComfyUI 模板包的 templates/index.json")
    matches = [
        (group["title"], template)
        for group in groups
        if isinstance(group, dict)
        and isinstance(group.get("title"), str)
        and isinstance(group.get("templates"), list)
        for template in group["templates"]
        if isinstance(template, dict) and template.get("name") == name
    ]
    if not matches:
        raise ClientError(f"官方索引中没有模板「{name}」")
    if len(matches) > 1:
        raise ClientError(f"官方索引中有多个同名模板「{name}」")
    group, template = matches[0]
    category = OFFICIAL_TEMPLATE_CATEGORIES.get(group)
    if category is None:
        raise ClientError(f"模板「{name}」所在的官方分组「{group}」尚未支持")
    return category, template


class TemplateInput(NamedTuple):
    file: str
    revision: str
    node_id: str
    node_type: str
    kind: str


def official_inputs(template: dict, source_revision: str | None) -> list[TemplateInput]:
    if source_revision is not None and not COMMIT_SHA.fullmatch(source_revision):
        raise ClientError("--source-revision 需要完整的 40 位小写 Git 提交 SHA")
    name = template["name"]
    io = template.get("io", {})
    inputs = io.get("inputs", []) if isinstance(io, dict) else None
    if not isinstance(inputs, list):
        raise ClientError(f"模板「{name}」的素材索引无效")
    result = []
    for entry in inputs:
        if not isinstance(entry, dict):
            raise ClientError(f"模板「{name}」的素材记录无效")
        filename = entry.get("file")
        if (
            not isinstance(filename, str)
            or filename in {"", ".", ".."}
            or any(character in filename for character in "/\\\0")
        ):
            raise ClientError(f"模板「{name}」的素材文件名无效")
        revision = entry.get("sourceRevision")
        if revision is None:
            revision = source_revision
        if revision is None:
            raise ClientError(
                f"模板「{name}」的素材「{filename}」缺少固定的 sourceRevision。"
                "请用 --source-revision 指定索引来源提交"
            )
        if not isinstance(revision, str) or not COMMIT_SHA.fullmatch(revision):
            raise ClientError(f"模板「{name}」的素材「{filename}」的 sourceRevision 无效")
        node_id, node_type, kind = (
            entry.get("nodeId"),
            entry.get("nodeType"),
            entry.get("mediaType"),
        )
        if (
            type(node_id) not in {str, int}
            or not isinstance(node_type, str)
            or kind not in ("image", "video", "audio", "3d")
        ):
            raise ClientError(f"模板「{name}」的素材「{filename}」缺少可用的节点或媒体类型")
        result.append(TemplateInput(filename, revision, str(node_id), node_type, kind))
    return result


def template_field(template: str, material: TemplateInput, graph: dict, form: dict) -> str:
    candidates = []
    direct = []
    for field in form["fields"]:
        node_id = field["nodeId"]
        node = graph.get(node_id, {})
        if node.get("class_type") != material.node_type or field["kind"] != material.kind:
            continue
        value = node.get("inputs", {}).get(field["inputName"])
        if (
            isinstance(value, str)
            and value.removesuffix(" [input]").replace("\\", "/").split("/")[-1] == material.file
        ):
            if node_id == material.node_id:
                direct.append(field["id"])
            candidates.append(field["id"])
    matches = direct or candidates
    if len(matches) == 1:
        return matches[0]
    raise ClientError(
        f"模板「{template}」的素材「{material.file}」无法匹配节点 {material.node_id} 的表单字段"
    )


def prepare_template_materials(client: Client, args: argparse.Namespace) -> dict:
    _, template = official_template(args.index, args.template_name)
    name = template["name"]
    materials = official_inputs(template, args.source_revision)
    workflow_id = identifier(args.workflow_id)
    endpoint = f"/workflows/{workflow_id}"
    workflow = client.request("GET", query(endpoint, version_id=args.version))
    if workflow["format"] != "api":
        raise ClientError(f"模板「{name}」需先上传 ComfyUI 导出的 API JSON")
    version = workflow["versionId"]
    graph = client.request("GET", query(endpoint + "/graph", version_id=version))["graph"]
    form_path = query(endpoint + "/inputs", machine_id=args.machine_id, version_id=version)
    initial = client.request("GET", form_path)
    for material in materials:
        template_field(name, material, graph, initial)

    assets: dict[TemplateInput, str] = {}
    with TemporaryDirectory(prefix="comfyshop-template-") as temporary:
        fetched: dict[tuple[str, str], str] = {}
        source_opener = build_opener(NoRedirect())
        for material in materials:
            key = material.revision, material.file
            if key not in fetched:
                print(f"准备模板「{name}」的「{material.file}」", file=sys.stderr)
                folder = Path(temporary) / material.revision
                folder.mkdir(exist_ok=True)
                local = folder / material.file
                url = (
                    "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/"
                    f"{material.revision}/input/{quote(material.file, safe='')}"
                )
                try:
                    with open_response(source_opener, Request(url)) as response:
                        save_download(response, local)
                    asset = upload(client, local, uuid4())
                    if asset["media"]["kind"] != material.kind:
                        raise ClientError("素材类型与官方索引不符")
                    fetched[key] = asset["id"]
                except (ClientError, OSError, HTTPException) as error:
                    raise ClientError(
                        f"模板「{name}」的素材「{material.file}」准备失败。{error}"
                    ) from error
            assets[material] = fetched[key]

    current = client.request("GET", form_path)
    input_values = {
        template_field(name, material, graph, current): {"assetId": asset_id}
        for material, asset_id in assets.items()
    }
    if len(input_values) != len(assets):
        raise ClientError(f"模板「{name}」有多个素材对应同一个表单字段")
    return {
        "workflowId": workflow["id"],
        "versionId": version,
        "machineId": current["machineId"],
        "inputSchemaHash": current["schemaHash"],
        "inputValues": input_values,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="ComfyShop Skill")
    root.add_argument("--server", help="ComfyShop 的站点地址。安装后默认使用已配置的站点。")
    root.add_argument("--language", help="显示语言，例如 zh 或 en。省略时使用部署默认语言。")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("install", help="安装 Skill 并在交互式终端登录").add_argument(
        "client", choices=CLIENTS
    )
    commands.add_parser("login", help="在终端登录 ComfyShop")
    commands.add_parser("register", help="在终端注册 ComfyShop 账号")
    commands.add_parser("logout", help="退出当前 Skill 会话")
    commands.add_parser("account", help="检查当前会话")
    commands.add_parser("operations", help="查看业务操作和参数")
    call = commands.add_parser("call", help="执行指定业务操作")
    call.add_argument("operation", choices=OPERATIONS)
    call.add_argument("ids", nargs="*")
    call.add_argument("--query", action="append", default=[], metavar="KEY=VALUE")
    call.add_argument("--body", type=Path)
    call.add_argument("--out", type=Path)
    workflows = commands.add_parser("workflows", help="搜索工作流")
    workflows.add_argument("--scope", choices=["public", "mine", "favorites"], default="public")
    workflows.add_argument(
        "--category",
        choices=["all", *WORKFLOW_CATEGORIES],
    )
    workflows.add_argument("--search")
    workflows.add_argument("--inpaint-artifact", help="只查能对指定成品图局部重绘的工作流")
    workflows.add_argument("--sort", choices=["updated", "popular"])
    workflows.add_argument("--cursor")
    workflows.add_argument("--limit", type=int)
    workspace = workflows.add_mutually_exclusive_group()
    workspace.add_argument("--workspace-owner", help="已授权空间的所有者 ID")
    workspace.add_argument("--workspace-team", help="团队 ID")
    for name, help_text in (
        ("import-template", "用官方索引导入工作流及分类"),
        ("classify-template", "按官方索引校正已有工作流分类"),
    ):
        template = commands.add_parser(name, help=help_text)
        template.add_argument("index", type=Path)
        template.add_argument("template_name")
        if name == "import-template":
            template.add_argument("graph", type=Path)
        else:
            template.add_argument("workflow_id")
    inputs = commands.add_parser("template-inputs", help="下载并绑定官方模板的固定版本素材")
    inputs.add_argument("index", type=Path)
    inputs.add_argument("template_name")
    inputs.add_argument("workflow_id")
    inputs.add_argument("machine_id")
    inputs.add_argument("--version")
    inputs.add_argument("--source-revision", help="为未指定 sourceRevision 的素材提供完整提交 SHA")
    commands.add_parser("workflow-link", help="取得工作流分享地址").add_argument("workflow_id")
    commands.add_parser("machines", help="查看自己的工作机")
    for command, target, help_text in (
        ("machine-create", "name", "添加工作机并保存连接配置"),
        ("machine-rotate", "machine_id", "重置工作机密钥并保存新配置"),
    ):
        machine = commands.add_parser(command, help=help_text)
        machine.add_argument(target)
        machine.add_argument("--out", type=Path, required=True)
        machine.add_argument("--platform-url")
        machine.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    commands.add_parser("worker-bundle", help="下载工作机启动包").add_argument(
        "destination", type=Path
    )
    form = commands.add_parser("form", help="读取所选工作流版本的生成表单")
    form.add_argument("workflow_id")
    target = form.add_mutually_exclusive_group(required=True)
    target.add_argument("machine_id", nargs="?", help="当前空间的工作机 ID")
    target.add_argument("--service", action="store_true", help="使用平台托管工作流的输入表单")
    form.add_argument("--version")
    form.add_argument("--workspace-team", help="团队 ID")
    replay = form.add_mutually_exclusive_group()
    replay.add_argument("--from-execution")
    replay.add_argument("--from-work")
    submission = commands.add_parser("submit", help="提交包含幂等键的 JSON 任务文件")
    submission.add_argument("file", type=Path)
    submission.add_argument("--workspace-team", help="团队 ID")
    for command in ("progress", "results"):
        read_task = commands.add_parser(command)
        read_task.add_argument("task_id")
        read_task.add_argument("--workspace-owner", help="已授权空间的所有者 ID")
    asset = commands.add_parser("upload", help="上传私有参考素材")
    asset.add_argument("file", type=Path)
    asset.add_argument("--asset-id", type=UUID)
    asset.add_argument("--save-to-library", action="store_true", help="将素材存入个人资产库")
    artifact = commands.add_parser("download", help="下载成品原文件")
    artifact.add_argument("artifact_id")
    artifact.add_argument("destination", type=Path)
    return root


def run(args: argparse.Namespace) -> tuple[dict | list | None, int]:
    command = args.command
    if command == "operations":
        return list_operations(), 0

    server = args.server
    if not server:
        config = Path(__file__).resolve().parents[1] / "platform.json"
        if not config.is_file():
            raise ClientError("请先安装 ComfyShop Skill 或通过 --server 指定站点")
        server = json.loads(config.read_text(encoding="utf-8"))["server"]
    server = connection_url(server)
    if command == "install":
        target = install(server, args.client)
        print(f"已安装 ComfyShop Skill：{target}")
        if not sys.stdin.isatty():
            print("初次使用请在自己的终端运行 scripts/comfyshop.py 的 login 命令。")
            return None, 0
    if command == "worker-bundle":
        with open_response(
            build_opener(NoRedirect()), Request(server + WORKER_ARCHIVE)
        ) as response:
            return save_download(response, args.destination), 0

    client = Client(server, args.language)
    if command in {"install", "login", "register"}:
        user = interactive_login(client, register=command == "register")
        return {"server": server, "user": user}, 0
    if command == "account":
        return {"server": server, "user": client.session()["user"]}, 0
    if command == "logout":
        client.logout()
        return {"server": server, "user": None}, 0
    if command == "call":
        return call_operation(client, args), 0
    if command in {"machine-create", "machine-rotate"}:
        return configure_machine(client, args), 0
    if command == "workflows":
        endpoint = query(
            "/workflows",
            scope=args.scope,
            category=args.category,
            search=args.search,
            inpaint_artifact_id=args.inpaint_artifact,
            sort=args.sort,
            cursor=args.cursor,
            limit=args.limit,
            workspace_owner=args.workspace_owner,
            workspace_team=args.workspace_team,
        )
        return client.request("GET", endpoint), 0
    if command == "import-template":
        category, template = official_template(args.index, args.template_name)
        graph = json.loads(args.graph.read_text(encoding="utf-8-sig"))
        body = {
            "name": template.get("title") or args.template_name,
            "category": category,
            "graph": graph,
        }
        workflow = client.request("POST", "/workflows", body, csrf=client.csrf())
        explain_import_format(workflow)
        return workflow, 0
    if command == "classify-template":
        category, _ = official_template(args.index, args.template_name)
        endpoint = "/workflows/" + identifier(args.workflow_id)
        workflow = client.request("GET", endpoint)
        if workflow["category"] == category:
            return workflow, 0
        return client.request("PATCH", endpoint, {"category": category}, csrf=client.csrf()), 0
    if command == "template-inputs":
        return prepare_template_materials(client, args), 0
    if command == "workflow-link":
        workflow_id = identifier(args.workflow_id)
        workflow = client.request("GET", f"/workflows/{workflow_id}")
        return {
            "url": f"{server}/workflows/{workflow_id}",
            "published": workflow["published"],
        }, 0
    if command == "machines":
        return client.request("GET", "/machines"), 0
    if command == "form":
        workflow_id = quote(args.workflow_id, safe="")
        path = (
            OPERATIONS["workflow.service-inputs"].path.format(workflow_id=workflow_id)
            if args.service
            else f"/workflows/{workflow_id}/inputs"
        )
        endpoint = query(
            path,
            machine_id=args.machine_id,
            version_id=args.version,
            workspace_team=args.workspace_team,
            execution_id=args.from_execution,
            work_id=args.from_work,
        )
        return client.request("GET", endpoint), 0
    if command == "submit":
        return submit(client, args.file, workspace_team=args.workspace_team)
    if command == "progress":
        task_id = quote(args.task_id, safe="")
        endpoint = query(f"/tasks/{task_id}/progress", workspace_owner=args.workspace_owner)
        return client.request("GET", endpoint), 0
    if command == "results":
        return results(client, args.task_id, workspace_owner=args.workspace_owner), 0
    if command == "upload":
        return upload(
            client, args.file, args.asset_id or uuid4(), save_to_library=args.save_to_library
        ), 0
    if command == "download":
        return download(client, args.artifact_id, args.destination), 0
    raise ClientError("未知的 Skill 命令")


def main() -> int:
    try:
        output, status = run(parser().parse_args())
        if output is not None:
            print(json.dumps(output, ensure_ascii=False))
        return status
    except (
        ClientError,
        OSError,
        ValueError,
        KeyError,
        HTTPException,
        BadZipFile,
        GetPassWarning,
    ) as error:
        print(
            str(error) if isinstance(error, ClientError) else f"操作失败：{error}", file=sys.stderr
        )
        return 1
    except (KeyboardInterrupt, EOFError):
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
