"""Lease and result protocol for a service work machine. Only the adapter calls the provider."""

import asyncio
import hashlib
import secrets
import time
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

import httpx

from . import TaskStage
from .definition import ExecutionAdapter, SubmissionRejected, WorkerDefinition
from .logging import logger
from .platform import Platform, PlatformError, task_event


async def claim_service_job(
    platform: Platform, kind: str, adapters: Sequence[str]
) -> tuple[dict, str] | None:
    lease = secrets.token_urlsafe(36)
    job = await platform.claim(str(uuid4()), lease, service=kind, adapters=adapters)
    return (job, lease) if isinstance(job, dict) else None


async def renew_lease(interval: float, heartbeat: Callable[[], Awaitable[object]]) -> None:
    while True:
        await asyncio.sleep(interval)
        await heartbeat()


async def run_with_lease(
    work: Coroutine[Any, Any, None], renewal: Coroutine[Any, Any, None]
) -> None:
    execution = asyncio.create_task(work)
    heartbeat = asyncio.create_task(renewal)
    try:
        done, _ = await asyncio.wait((execution, heartbeat), return_when=asyncio.FIRST_COMPLETED)
        # The worker may already have committed the result when a final heartbeat loses the lease.
        await (execution if execution in done else heartbeat)
    finally:
        execution.cancel()
        heartbeat.cancel()
        await asyncio.gather(execution, heartbeat, return_exceptions=True)


class LeasedJob:
    def __init__(self, platform: Platform, job: dict, lease: str, interval: float):
        self.platform = platform
        self.job = job
        self.task_id = job["task"]["id"]
        self.lease = lease
        self.interval = interval
        self.sequence = job["eventSequence"]
        self.stage: TaskStage = "preflight"
        self.index = 0
        self.progress = job["task"]["progress"]
        self.retryable = False

    async def request(self, path: str, body: dict | None = None, **options: Any):
        return await self.platform.task_request(self.task_id, self.lease, path, body, **options)

    async def heartbeat(self, stage: TaskStage | None = None) -> None:
        if stage == self.stage:
            return
        self.stage = stage or self.stage
        self.sequence += 1
        await self.platform.heartbeat(
            self.task_id,
            self.lease,
            task_event(self.sequence, self.stage, self.index, self.progress),
        )

    async def renew(self) -> None:
        remaining = self.job["leaseExpiresAt"] / 1000 - time.time()
        await renew_lease(max(1.0, min(10.0, remaining / 3)), self.heartbeat)

    async def assets(self, root: Path) -> dict[str, Path]:
        paths = {}
        for asset in self.job["assets"]:
            asset_id = asset["id"]
            if asset_id not in paths:
                path = root / asset_id
                await self.platform.download_asset(self.task_id, asset, path, self.lease)
                paths[asset_id] = path
        return paths

    async def submit(self, adapter: ExecutionAdapter) -> str:
        base = f"executions/{self.index}/"
        if not await self.request(base + "reserve"):
            self.retryable = False
            raise ValueError("提交结果待核对，请查看云端任务记录")
        self.retryable = False
        remote_id = await adapter.submit(self.index)
        # Keep the accepted ID in memory if only the platform connection is interrupted.
        while True:
            try:
                await self.request(base + "start", {"promptId": remote_id})
                logger.info("云端已受理生成", execution_index=self.index, remote_id=remote_id)
                return remote_id
            except PlatformError as error:
                if error.status < 500 and error.status not in (408, 429):
                    raise
            except httpx.TransportError:
                pass
            await asyncio.sleep(self.interval)

    async def collect(self, adapter: ExecutionAdapter, remote_id: str, root: Path) -> None:
        while True:
            outputs = await adapter.poll(remote_id)
            if isinstance(outputs, list):
                break
            await self.heartbeat(outputs)
            await asyncio.sleep(self.interval)
        await self.heartbeat("uploading")
        receipts = []
        for position, item in enumerate(outputs):
            receipt = f"{self.index}-{position}"
            path = root / receipt
            filename, node = await adapter.download(item, path, position)
            with path.open("rb") as stream:
                checksum = await asyncio.to_thread(hashlib.file_digest, stream, "sha256")
            await self.platform.upload_artifact(
                self.task_id,
                self.lease,
                receipt,
                path,
                filename=filename,
                sha256=checksum.hexdigest(),
                execution_index=self.index,
                output_node_id=node,
                output_slot="outputs",
                output_index=position,
            )
            path.unlink()
            receipts.append(receipt)
        await self.request(f"executions/{self.index}/complete", {"clientIds": receipts})
        logger.info("执行已完成", execution_index=self.index, output_count=len(receipts))

    async def execute(self, definition: WorkerDefinition, http: httpx.AsyncClient) -> None:
        pending = [
            item for item in self.job["executions"] if item["status"] in {"queued", "running"}
        ]
        if not pending:
            await self.request("complete")
            return
        pending.sort(
            key=lambda item: (not item["promptId"], not item["submissionPending"], item["index"])
        )
        self.index = pending[0]["index"]
        if definition.executor is None:
            raise TypeError("ServiceRunner 需要工作机的执行适配器")
        try:
            auth = {}
            if definition.connection == "account":
                try:
                    auth = await self.request("connection", method="GET")
                except PlatformError as error:
                    if error.status in (409, 422):
                        raise ValueError("所选工作机的连接已更换或移除") from None
                    raise
            adapter = definition.executor(http, auth or {})
            with TemporaryDirectory(prefix="comfyshop-service-") as directory:
                root = Path(directory)
                prepared = False
                for execution in pending:
                    self.index = execution["index"]
                    remote_id = execution["promptId"]
                    self.retryable = not remote_id and not execution["submissionPending"]
                    if not remote_id:
                        if not self.retryable:
                            raise ValueError("提交结果待核对，请查看云端任务记录")
                        if not prepared:
                            await adapter.prepare(self.job, await self.assets(root))
                            prepared = True
                        remote_id = await self.submit(adapter)
                    await self.collect(adapter, remote_id, root)
                    self.progress = min(
                        99, 100 * (self.index + 1) // self.job["task"]["executionCount"]
                    )
        except (ValueError, PlatformError) as error:
            if isinstance(error, PlatformError) and error.status not in (400, 413, 415, 422):
                raise
            failure: dict = {"error": str(error)[:1000]}
            if self.retryable or isinstance(error, SubmissionRejected):
                failure["retryableExecutionIndex"] = self.index
            await self.request("fail", failure)
            logger.error("执行失败", execution_index=self.index, error_type=type(error).__name__)


class ServiceRunner:
    def __init__(
        self,
        platform: Platform,
        definition: WorkerDefinition,
        http: httpx.AsyncClient,
        interval: float = 3,
    ):
        self.platform = platform
        self.definition = definition
        self.http = http
        self.interval = interval

    async def run_once(self) -> bool:
        kind = self.definition.kind
        claim = await claim_service_job(self.platform, kind, self.definition.adapters or (kind,))
        if claim is None:
            return False
        job, lease = claim
        leased = LeasedJob(self.platform, job, lease, self.interval)
        with logger.contextualize(worker_kind=kind, task_id=leased.task_id):
            await run_with_lease(leased.execute(self.definition, self.http), leased.renew())
        return True

    async def run(self) -> None:
        while True:
            try:
                if await self.run_once():
                    continue
            except (httpx.HTTPError, PlatformError, OSError) as error:
                logger.warning("工作机连接中断，将重新领取", error_type=type(error).__name__)
            await asyncio.sleep(self.interval)
