"""独立工作机入口，解析 CLI 参数后启动与 ComfyUI 插件共用的 Runner。"""

import argparse
import asyncio
import logging

from filelock import Timeout

from .link import LinkError, load_config
from .runner import Runner


def main():
    parser = argparse.ArgumentParser(description="ComfyShop 工作机")
    parser.add_argument("--once", action="store_true", help="领取并执行一个任务后退出")
    args = parser.parse_args()
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
        asyncio.run(Runner(config).run(once=args.once))
    except Timeout:
        parser.exit(1, "此配置的工作机已在运行。请先停止已有进程。\n")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
