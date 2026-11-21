"""启动器与子进程交换更新请求和首次启动确认。"""

import asyncio
import json
from pathlib import Path
from uuid import UUID

from .config import write_json

CONTROL_ENV = "COMFYSHOP_WORKER_UPDATE_CONTROL"
UPDATE_EXIT = 75
STARTUP_SECONDS = 60


class UpdateControl:
    def __init__(self, directory: Path):
        self.directory = directory
        trial = directory / "trial"
        self.target = trial.read_text(encoding="ascii") if trial.is_file() else None
        self.trial = self.target is not None
        self.ready = directory / "ready"
        self.current = directory.parent / "current.json"
        self.request = directory / "request.json"
        self.failure = directory.parent / "failure.json"

    def request_update(self, update_id: str) -> None:
        write_json(self.request, {"id": str(UUID(update_id))})

    def failed_update(self) -> dict | None:
        try:
            return json.loads(self.failure.read_bytes())
        except FileNotFoundError:
            return None

    async def wait_for_activation(self) -> None:
        self.ready.touch()
        async with asyncio.timeout(STARTUP_SECONDS):
            while (
                not self.current.is_file()
                or json.loads(self.current.read_bytes())["sha256"] != self.target
            ):
                await asyncio.sleep(0.1)
        self.trial = False
