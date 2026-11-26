"""独立工作机入口，解析 CLI 参数后启动与 ComfyUI 插件共用的 Runner。"""

import argparse
import asyncio
import os
import shutil
import signal
import subprocess
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, NoReturn

from comfyshop_worker_protocol.definition import PERSONAL
from comfyshop_worker_protocol.logging import logger, worker_logging
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from filelock import Timeout

from .config import Config
from .launcher import Launcher, UpdateError
from .link import LinkError, load_config
from .release import UPDATE_KEY_FILE, Build
from .runner import Runner
from .service import LOG_DIRECTORY_ENV, SERVICE_ACTIONS, manage_service, service_launch
from .update_control import CONTROL_ENV, UpdateControl


async def _serve(action: Coroutine[Any, Any, int | None]) -> int | None:
    """Cleanly stop the worker child when a POSIX service manager sends SIGTERM."""
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    if os.name == "posix" and task is not None:
        loop.add_signal_handler(signal.SIGTERM, task.cancel, "SIGTERM")
    try:
        return await action
    except asyncio.CancelledError as error:
        if error.args == ("SIGTERM",):
            return None
        raise
    finally:
        if os.name == "posix":
            loop.remove_signal_handler(signal.SIGTERM)


def _uv_path(value: str) -> str:
    launcher = shutil.which(value)
    if launcher is None:
        raise UpdateError("找不到安装新版依赖所需的 uv")
    return str(Path(launcher).absolute())


def main() -> int | None:
    parser = argparse.ArgumentParser(description="ComfyShop 工作机")
    parser.add_argument("--once", action="store_true", help="领取并执行一个任务后退出")
    parser.add_argument("--version", action="store_true", help="显示工作机程序版本")
    parser.add_argument("--service", choices=SERVICE_ACTIONS, help="管理当前账号的后台工作机")
    parser.add_argument("--service-run", help=argparse.SUPPRESS)
    parser.add_argument("--service-logs", help=argparse.SUPPRESS)
    parser.add_argument("--launcher-uv", help=argparse.SUPPRESS)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent
    if args.version:
        build = Build.installed(source)
        print(f"ComfyShop 工作机 {build.version if build else '版本未知'}")
        return 0
    if args.service:
        try:
            file = Path(os.environ.get("COMFYSHOP_WORKER_CONFIG", source / "worker.json")).resolve()
            launch = None
            log_directory = None
            if args.service == "install":
                os.environ["COMFYSHOP_WORKER_CONFIG"] = str(file)
                config = Config.load()
                uv = _uv_path(args.launcher_uv) if args.launcher_uv else None
                launch = service_launch(file, source, config.state_dir, uv)
                log_directory = config.state_dir.resolve()
            result = manage_service(args.service, file, launch)
            if log_directory:
                print(f"工作机后台服务已安装。日志目录：{log_directory}")
            return result
        except (OSError, ValueError, UpdateError, subprocess.CalledProcessError) as error:
            parser.exit(1, f"无法管理工作机后台服务。{error}\n")
    if args.service_run:
        if not args.service_logs:
            parser.error("后台工作机需要日志目录")
        os.environ["COMFYSHOP_WORKER_CONFIG"] = args.service_run
        os.environ[LOG_DIRECTORY_ENV] = args.service_logs
        os.environ["COMFYSHOP_WORKER_STATE_DIR"] = args.service_logs
    logs = os.environ.get(LOG_DIRECTORY_ENV)
    trust = source / UPDATE_KEY_FILE
    signed_launcher = args.launcher_uv and trust.is_file()
    name = "launcher.log" if signed_launcher else "worker.log"
    try:
        with worker_logging(PERSONAL.kind, file=Path(logs) / name if logs else None):
            return _start(args, source, trust, bool(signed_launcher), logs, parser)
    except ValueError as error:
        parser.exit(1, f"{error}\n")


def _start(
    args: argparse.Namespace,
    source: Path,
    trust: Path,
    signed_launcher: bool,
    logs: str | None,
    parser: argparse.ArgumentParser,
) -> int | None:
    def fail(message: str) -> NoReturn:
        if logs:
            logger.error(message)
        parser.exit(1, message + "\n")

    try:
        config = Config.load() if logs else load_config()
    except LinkError as error:
        fail(str(error))
    except (OSError, ValueError) as error:
        fail(f"无法加载工作机配置。{error}")
    except KeyboardInterrupt:
        parser.exit(1)
    try:
        if signed_launcher:
            key = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(trust.read_text(encoding="ascii"))
            )
            return asyncio.run(
                _serve(
                    Launcher(config, source, key, _uv_path(args.launcher_uv)).run(once=args.once)
                )
            )
        control_path = os.getenv(CONTROL_ENV)
        control = UpdateControl(Path(control_path)) if control_path else None
        return asyncio.run(_serve(Runner(config, control).run(once=args.once)))
    except Timeout:
        fail("此配置的工作机已在运行。请先停止已有进程。")
    except (OSError, ValueError, UpdateError) as error:
        fail(f"无法启动工作机。{error}")
    except KeyboardInterrupt:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
