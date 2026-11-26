"""Copy this directory to ComfyUI/custom_nodes/ComfyShop to enable auto-start."""

import asyncio
import os
import threading

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


def _start():
    from comfyshop_worker_protocol.definition import PERSONAL
    from comfyshop_worker_protocol.logging import logger, worker_logging

    from .comfyshop_worker.link import load_config
    from .comfyshop_worker.runner import Runner

    try:
        with worker_logging(PERSONAL.kind, embedded=True):
            try:
                asyncio.run(Runner(load_config(logger.warning)).run())
            except Exception:
                logger.exception("ComfyShop 工作机已停止")
    except ValueError as error:
        logger.error("无法配置工作机日志，{}", error)


if os.environ.get("COMFYSHOP_API_KEY") or os.environ.get("COMFYSHOP_WORKER_CONFIG"):
    threading.Thread(target=_start, name="ComfyShop", daemon=True).start()
