"""三类工作机共用的 Loguru 输出和任务上下文。"""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

from loguru import logger as logger

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
FORMAT = "{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level: <8} | {message} | {extra}"


@contextmanager
def worker_logging(kind: str, *, file: Path | None = None, embedded: bool = False) -> Iterator[str]:
    level = os.environ.get("COMFYSHOP_WORKER_LOG_LEVEL", "").strip().upper() or "INFO"
    if level not in LEVELS:
        raise ValueError(f"COMFYSHOP_WORKER_LOG_LEVEL 支持 {', '.join(LEVELS)}")
    with logger.contextualize(worker_kind=kind):
        if embedded:
            # ComfyUI plugins share the host's Loguru instance. Respect custom handlers.
            try:
                logger.remove(0)
            except ValueError:
                pass
            else:
                logger.add(sys.stderr, filter=lambda record: "worker_kind" not in record["extra"])
        else:
            logger.remove()

        add = partial(
            logger.add, level=level, format=FORMAT, colorize=False, backtrace=False, diagnose=False
        )
        if file is None:
            sink = add(sys.stderr, filter=lambda r: r["extra"].get("worker_kind") == kind)
        else:
            sink = add(file, rotation=2 * 1024 * 1024, retention=2, encoding="utf-8")
        try:
            yield level
        finally:
            logger.remove(sink)
