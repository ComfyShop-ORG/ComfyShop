"""Copy this directory to ComfyUI/custom_nodes/ComfyShop to enable auto-start."""

import asyncio
import logging
import os
import threading

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


def _start():
    from .comfyshop_worker.link import load_config
    from .comfyshop_worker.runner import Runner

    log = logging.getLogger("comfyshop")
    try:
        # 配置文件里没有密钥时，接入地址写进 ComfyUI 的日志，确认后自动开始工作。
        asyncio.run(Runner(load_config(log.warning)).run())
    except Exception:
        logging.getLogger("comfyshop").exception("ComfyShop 工作机已停止")


if os.environ.get("COMFYSHOP_API_KEY") or os.environ.get("COMFYSHOP_WORKER_CONFIG"):
    threading.Thread(target=_start, name="ComfyShop", daemon=True).start()
