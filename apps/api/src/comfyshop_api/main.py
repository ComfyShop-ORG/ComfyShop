"""平台 API 入口，负责挂载路由、网页与后台维护。工作机进程负责运行 ComfyUI。"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from comfyshop_api.api.auth import router as auth_router
from comfyshop_api.api.health import router as health_router
from comfyshop_api.api.tasks import router as tasks_router
from comfyshop_api.api.workflows import router as workflows_router
from comfyshop_api.api.machines import router as machines_router
from comfyshop_api.api.worker import router as worker_router
from comfyshop_api.api.artifacts import router as artifacts_router
from comfyshop_api.api.assets import router as assets_router
from comfyshop_api.api.executions import router as executions_router
from comfyshop_api.api.works import router as works_router
from comfyshop_api.api.web import WebStaticFiles
from comfyshop_api.core.config import Settings, get_settings
from comfyshop_api.db import make_engine
from comfyshop_api.schemas import ErrorRead
from comfyshop_api.services.artifacts import expire_incomplete_artifacts
from comfyshop_api.services.machines import expire_leases
from comfyshop_api.services.assets import expire_unused_assets
from comfyshop_api.services.originals import (
    delete_pending_originals,
    release_uploads,
    retire_unreferenced_originals,
)
from comfyshop_media.errors import MediaError
from comfyshop_media.storage import StorageError
from comfyshop_api.security import expire_auth_attempts


def create_app(settings: Settings | None = None) -> FastAPI:
    """构造 FastAPI 应用。传入 `settings` 可让测试使用独立数据库及文件目录。

    返回的应用在启动时创建数据库引擎和维护循环，在关闭时结束维护并释放连接。
    静态目录存在 `index.html` 时，同一应用也提供网页。
    """
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = make_engine(settings.database_dsn)
        application.state.engine = engine
        stopped = asyncio.Event()

        def sweep() -> None:
            with Session(engine) as db:
                expire_leases(db)
                expire_unused_assets(db, settings)
                expire_incomplete_artifacts(db, settings)
                expire_auth_attempts(db)

        def sweep_staging() -> None:
            def recover(directory: Path) -> None:
                names = [p.name for p in directory.iterdir() if not p.name.startswith(".")]
                with Session(engine) as db:
                    release_uploads(db, names)

            settings.media_storage.prune_abandoned_staging(recover)

        def sweep_originals() -> None:
            with Session(engine) as db:
                retire_unreferenced_originals(db)
                delete_pending_originals(db, settings.media_storage)

        async def maintain(
            action: Callable[[], None], interval: int, label: str, *, immediate: bool = False
        ) -> None:
            while not stopped.is_set():
                if not immediate:
                    try:
                        await asyncio.wait_for(stopped.wait(), timeout=interval)
                        break
                    except TimeoutError:
                        pass
                immediate = False
                try:
                    await asyncio.to_thread(action)
                except (SQLAlchemyError, OSError):
                    logging.getLogger("comfyshop").exception("%s暂时失败", label)

        try:
            async with asyncio.TaskGroup() as background:
                background.create_task(maintain(sweep, 15, "后台维护", immediate=True))
                background.create_task(maintain(sweep_originals, 15, "原件回收"))
                background.create_task(maintain(sweep_staging, 60, "暂存文件回收"))
                background.create_task(
                    maintain(
                        lambda: settings.media_storage.prune_local_derivatives(),
                        60,
                        "本地派生缓存清理",
                    )
                )
                if settings.storage_backend == "s3":
                    background.create_task(
                        maintain(
                            lambda: settings.media_storage.prune_object_derivatives(),
                            60,
                            "对象存储派生缓存清理",
                        )
                    )
                try:
                    yield
                finally:
                    stopped.set()
        finally:
            engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.3.0",
        lifespan=lifespan,
        responses={code: {"model": ErrorRead} for code in [401, 403, 404, 409, 413, 422, 429]},
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(workflows_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(machines_router, prefix="/api/v1")
    app.include_router(worker_router, prefix="/api/v1")
    app.include_router(artifacts_router, prefix="/api/v1")
    app.include_router(assets_router, prefix="/api/v1")
    app.include_router(executions_router, prefix="/api/v1")
    app.include_router(works_router, prefix="/api/v1")

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, error: RequestValidationError):
        # Never echo submitted passwords or raw graph data in validation errors.
        fields = {str(part) for issue in error.errors() for part in issue["loc"]}
        detail = "输入内容无效"
        if "password" in fields:
            detail = "密码需为 8–128 位"
        elif "username" in fields:
            detail = "账号格式无效"
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(StorageError)
    async def storage_unavailable(_request: Request, error: StorageError) -> JSONResponse:
        logging.getLogger("comfyshop").warning("%s", error)
        return JSONResponse(status_code=503, content={"detail": "媒体存储暂时不可用"})

    @app.exception_handler(MediaError)
    async def invalid_media(_request: Request, error: MediaError) -> JSONResponse:
        status = {
            "invalid": 422,
            "missing": 404,
            "unavailable": 503,
            "too_large": 413,
            "range": 416,
            "range_syntax": 400,
        }[error.kind]
        return JSONResponse(status_code=status, content={"detail": str(error)})

    @app.middleware("http")
    async def private_responses(request: Request, call_next: RequestResponseEndpoint):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            # 接口默认不缓存。可缓存的响应（例如缩略图）自己声明并在每次使用前重新核对。
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def unknown_api(path: str):
        return JSONResponse(status_code=404, content={"detail": "接口不存在"})

    if settings.static_dir:
        downloads = settings.static_dir / "downloads"
        if downloads.is_dir():
            app.mount("/downloads", StaticFiles(directory=downloads), name="downloads")
        if (settings.static_dir / "index.html").is_file():
            app.mount(
                "/",
                WebStaticFiles(directory=settings.static_dir, public_url=settings.public_url),
                name="web",
            )
    return app


app = create_app()
