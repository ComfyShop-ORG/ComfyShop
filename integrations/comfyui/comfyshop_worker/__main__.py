"""独立工作机入口，解析 CLI 参数后启动与 ComfyUI 插件共用的 Runner。"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
import shutil

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from filelock import Timeout

from .launcher import Launcher, UpdateError
from .link import LinkError, load_config
from .release import UPDATE_KEY_FILE, Build
from .runner import Runner
from .update_control import CONTROL_ENV, UpdateControl


def main() -> int | None:
    parser = argparse.ArgumentParser(description="ComfyShop 工作机")
    parser.add_argument("--once", action="store_true", help="领取并执行一个任务后退出")
    parser.add_argument("--version", action="store_true", help="显示工作机程序版本")
    parser.add_argument("--launcher-uv", help=argparse.SUPPRESS)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent
    if args.version:
        build = Build.installed(source)
        print(f"ComfyShop 工作机 {build.version if build else '版本未知'}")
        return 0
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        config = load_config()
    except LinkError as error:
        parser.exit(1, f"{error}\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"无法加载工作机配置。{error}\n")
    except KeyboardInterrupt:
        parser.exit(1)
    try:
        trust = source / UPDATE_KEY_FILE
        if args.launcher_uv and trust.is_file():
            launcher = shutil.which(args.launcher_uv)
            if launcher is None:
                raise UpdateError("找不到安装新版依赖所需的 uv")
            key = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(trust.read_text(encoding="ascii"))
            )
            return asyncio.run(
                Launcher(config, source, key, str(Path(launcher).absolute())).run(once=args.once)
            )
        control_path = os.getenv(CONTROL_ENV)
        control = UpdateControl(Path(control_path)) if control_path else None
        return asyncio.run(Runner(config, control).run(once=args.once))
    except Timeout:
        parser.exit(1, "此配置的工作机已在运行。请先停止已有进程。\n")
    except (OSError, ValueError, UpdateError) as error:
        parser.exit(1, f"无法启动工作机。{error}\n")
    except KeyboardInterrupt:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
