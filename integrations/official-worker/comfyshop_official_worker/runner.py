"""Run hosted jobs through the platform's execution and media endpoints."""

import asyncio
import hashlib
import mimetypes
import tempfile
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path

import httpx
from comfyshop_worker_protocol import TaskStage
from comfyshop_worker_protocol.definition import OFFICIAL
from comfyshop_worker_protocol.logging import logger
from comfyshop_worker_protocol.platform import (
    Platform,
    PlatformError,
    artifact_byte_limit,
    task_event,
)
from comfyshop_worker_protocol.service import claim_service_job, renew_lease, run_with_lease

from .atlas_cloud import (
    ADAPTER,
    MAX_INLINE_OUTPUT_BYTES,
    SUBMISSION_UNKNOWN,
    Atlas,
    AtlasSpec,
    InlineFormat,
    InlineOutput,
    RemoteOutput,
    RunError,
)
from .atlas_media import MediaEncoding, atlas_media_reference, bind_atlas_media

CHUNK_BYTES = 1024 * 1024
DEFAULT_MAX_CONCURRENCY = 4


async def _save(response: httpx.Response, path: Path, limit: int) -> tuple[int, str]:
    response.raise_for_status()
    hasher = hashlib.sha256()
    size = 0
    with path.open("wb") as output:
        async for chunk in response.aiter_bytes(CHUNK_BYTES):
            size += len(chunk)
            if size > limit:
                raise RunError("文件超过工作机允许的大小")
            hasher.update(chunk)
            await asyncio.to_thread(output.write, chunk)
    return size, hasher.hexdigest()


@dataclass
class Activity:
    sequence: int
    total: int
    completed: int
    failure: str | None
    last_index: int = 0
    stages: dict[int, TaskStage] = field(default_factory=dict)

    def heartbeat(self) -> dict:
        index, stage = next(iter(self.stages.items()), (self.last_index, "preflight"))
        uploading = sum(value == "uploading" for value in self.stages.values())
        self.sequence += 1
        return task_event(
            self.sequence,
            stage,
            index,
            min(99, (100 * self.completed + 70 * uploading) // self.total),
        )


def _log_worker_error(error: Exception) -> None:
    if isinstance(error, ExceptionGroup):
        for cause in error.exceptions:
            _log_worker_error(cause)
    elif isinstance(error, PlatformError):
        if error.status != 409:
            logger.warning("工作机请求失败，将重新领取", http_status=error.status)
    elif isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code != 409:
            logger.warning("工作机请求失败，将重新领取", http_status=error.response.status_code)
    else:
        logger.warning("工作机当前无法继续处理任务，将重新领取", error_type=type(error).__name__)


class Runner:
    def __init__(
        self,
        platform: Platform,
        atlas: Atlas,
        downloads: httpx.AsyncClient,
        *,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        if type(max_concurrency) is not int or max_concurrency < 1:
            raise ValueError("官方工作机最大并发生成次数必须为正整数")
        self.platform = platform
        self.atlas = atlas
        self.downloads = downloads
        self.max_concurrency = max_concurrency
        self._slots = asyncio.Semaphore(max_concurrency)

    async def run(self) -> None:
        async def process(job: dict, lease: str, first_slot: ExitStack) -> None:
            try:
                await self._run_job(job, lease, first_slot)
            except Exception as error:
                _log_worker_error(error)

        async with asyncio.TaskGroup() as jobs:
            while True:
                try:
                    claim = await self._claim()
                except (PlatformError, httpx.HTTPError, ValueError, OSError) as error:
                    _log_worker_error(error)
                    claim = None
                if claim is None:
                    await asyncio.sleep(2)
                    continue
                job, lease, first_slot = claim
                worker = jobs.create_task(process(job, lease, first_slot))
                worker.add_done_callback(lambda _, slot=first_slot: slot.close())

    async def run_once(self) -> bool:
        claim = await self._claim()
        if claim is None:
            return False
        job, lease, first_slot = claim
        with first_slot:
            await self._run_job(job, lease, first_slot)
        return True

    async def _claim(self) -> tuple[dict, str, ExitStack] | None:
        # 领取占用首个执行的名额。首个执行完成或领取中断时归还一次。
        await self._slots.acquire()
        with ExitStack() as slot:
            slot.callback(self._slots.release)
            claim = await claim_service_job(self.platform, OFFICIAL.kind, (ADAPTER,))
            if claim is None:
                return None
            job, lease = claim
            return job, lease, slot.pop_all()

    async def _run_job(self, job: dict, lease: str, first_slot: ExitStack) -> None:
        task = job["task"]
        task_id = task["id"]
        executions = job["executions"]
        activity = Activity(
            job["eventSequence"],
            len(executions),
            sum(e["status"] == "succeeded" for e in executions),
            task["error"],
            last_index=next((e["index"] for e in executions if e["status"] != "queued"), 0),
        )
        interval = max(2.0, min(20.0, (job["leaseExpiresAt"] - task["updated"]) / 3000))
        with logger.contextualize(task_id=task["id"]):
            await run_with_lease(
                self._execute(job, task_id, lease, activity, first_slot),
                renew_lease(
                    interval, lambda: self.platform.heartbeat(task_id, lease, activity.heartbeat())
                ),
            )

    async def _execute(
        self,
        job: dict,
        task_id: str,
        lease: str,
        activity: Activity,
        first_slot: ExitStack,
    ) -> None:
        try:
            spec = AtlasSpec.model_validate(job["graph"]["config"])
        except ValueError:
            await self._fail(task_id, lease, "官方工作流的执行配置无效")
            return
        pending = [e for e in job["executions"] if e["status"] in ("queued", "running")]
        # 接管后优先收回已有生成编号的成品。提交结果不明的执行留待核对。
        uncertain = next((e for e in pending if e["submissionPending"] and not e["promptId"]), None)
        if uncertain is not None:
            activity.failure = SUBMISSION_UNKNOWN
            activity.last_index = uncertain["index"]
        pending.sort(key=lambda e: not e["promptId"])

        async def generate(execution: dict) -> None:
            index = execution["index"]
            activity.last_index = index
            activity.stages[index] = "preflight"
            with logger.contextualize(execution_index=index):
                logger.info("开始处理官方执行", model=spec.model, output_kind=spec.operation)
                try:
                    with tempfile.TemporaryDirectory(prefix="comfyshop-official-") as directory:
                        await self._execution(
                            job, spec, execution, task_id, lease, activity, Path(directory)
                        )
                except RunError as error:
                    if activity.failure is None or not error.retryable:
                        activity.failure = str(error)
                    logger.warning(
                        "官方执行失败",
                        stage=activity.stages[index],
                        reason=str(error),
                        retryable=error.retryable,
                    )
                    await self.platform.task_request(
                        task_id,
                        lease,
                        f"executions/{index}/fail",
                        body={"error": str(error), "retryable": error.retryable},
                    )
                finally:
                    del activity.stages[index]

        async with asyncio.TaskGroup() as runs:
            for position, execution in enumerate(pending):
                if position == 0:
                    release = first_slot.close
                else:
                    await self._slots.acquire()
                    release = self._slots.release
                if activity.failure and not execution["promptId"]:
                    release()
                    break
                running = runs.create_task(generate(execution))
                running.add_done_callback(lambda _, release=release: release())
        if activity.failure:
            await self._fail(task_id, lease, activity.failure)
        elif not pending:
            await self.platform.task_request(task_id, lease, "complete")

    async def _execution(
        self,
        job: dict,
        spec: AtlasSpec,
        execution: dict,
        task_id: str,
        lease: str,
        activity: Activity,
        directory: Path,
    ) -> None:
        started = time.monotonic()
        index = execution["index"]
        path = f"executions/{index}"
        prediction = execution["promptId"]
        if not prediction and execution["submissionPending"]:
            raise RunError(SUBMISSION_UNKNOWN)
        values = job["task"]["inputValues"]
        payload = spec.payload(values)
        inline_format: InlineFormat | None = None
        if job["graph"].get("output_kind") == "text":
            inline_format = "text"
        elif payload.get("enable_base64_output") is True:
            if spec.operation == "image":
                inline_format = spec.base64_output_format
            elif spec.operation == "video":
                inline_format = "mp4"
            elif spec.operation == "audio":
                output_format = payload.get("format", "mp3")
                if output_format not in ("mp3", "wav", "pcm"):
                    raise RunError("此工作机无法解码所选的 Base64 音频格式", retryable=True)
                inline_format = output_format
        submitted = None
        if not prediction:
            file_number = count()

            async def reference(
                asset: dict,
                *,
                encoding: MediaEncoding,
                alpha_requirement: str | None = None,
                reject_png_alpha: bool = False,
            ) -> str:
                file = directory / f"input-{next(file_number)}"
                try:
                    await self.platform.download_asset(task_id, asset, file, lease)
                except PlatformError as error:
                    if error.status == 422:
                        raise RunError("素材校验失败", retryable=True) from error
                    raise
                logger.debug("素材校验通过", asset_id=asset["id"], size_bytes=asset["size"])
                with file.open("rb") as source:
                    return await atlas_media_reference(
                        self.atlas,
                        asset,
                        source,
                        encoding=encoding,
                        alpha_requirement=alpha_requirement,
                        reject_png_alpha=reject_png_alpha,
                    )

            await bind_atlas_media(spec, payload, values, job["assets"], reference)
            if activity.failure:
                return
            spec.validate_request_size(payload)
            if not await self.platform.task_request(task_id, lease, f"{path}/reserve"):
                raise RunError(SUBMISSION_UNKNOWN)
            activity.stages[index] = "executing"
            prediction, submitted = await self.atlas.submit(spec, payload)
            logger.info("Atlas Cloud 已受理生成", prediction_id=prediction)
            await self.platform.task_request(
                task_id, lease, f"{path}/start", body={"promptId": prediction}
            )
        else:
            logger.info("续查 Atlas Cloud 生成", prediction_id=prediction)
        activity.stages[index] = "executing"
        with logger.contextualize(prediction_id=prediction):
            additional_kinds = job["graph"].get("additional_output_kinds", [])
            outputs = await self.atlas.outputs(
                prediction,
                inline_format=inline_format,
                initial=submitted if payload.get("enable_sync_mode") is True else None,
                timeout_seconds=spec.prediction_timeout_seconds,
                prediction_endpoint=spec.prediction_endpoint,
                include_metadata="text" in additional_kinds,
                return_voice_result=spec.return_voice_result,
                include_thumbnail=spec.operation == "audio" and "image" in additional_kinds,
                include_draft_id=payload.get("draft") is True and "text" in additional_kinds,
            )
            activity.stages[index] = "uploading"
            logger.info("Atlas Cloud 已返回成品，开始回传", output_count=len(outputs))
            client_ids = []
            suffix = spec.audio_suffixes.get(str(payload.get(spec.audio_suffix_parameter))) or (
                ".pcm" if spec.operation == "audio" and payload.get("format") == "pcm" else ""
            )
            if spec.operation == "image" and payload.get("output_format") == "svg":
                suffix = ".svg"
            max_bytes = artifact_byte_limit(job)
            for output_index, output in enumerate(outputs):
                client_id = f"{index}-{output_index}"
                await self._upload_output(
                    output,
                    directory / client_id,
                    task_id,
                    lease,
                    index,
                    output_index,
                    max_bytes=max_bytes,
                    preferred_suffix=suffix,
                )
                client_ids.append(client_id)
            await self.platform.task_request(
                task_id, lease, f"{path}/complete", body={"clientIds": client_ids}
            )
            activity.completed += 1
            logger.info(
                "官方成品已入库",
                output_count=len(client_ids),
                elapsed_seconds=round(time.monotonic() - started, 2),
            )

    async def _upload_output(
        self,
        output: str | InlineOutput | RemoteOutput,
        path: Path,
        task_id: str,
        lease: str,
        index: int,
        output_index: int,
        *,
        max_bytes: int,
        preferred_suffix: str = "",
    ) -> None:
        filename = None
        if isinstance(output, InlineOutput):
            if len(output.content) > min(max_bytes, MAX_INLINE_OUTPUT_BYTES):
                raise RunError("文件超过工作机允许的大小")
            size = await asyncio.to_thread(path.write_bytes, output.content)
            digest = hashlib.sha256(output.content).hexdigest()
            suffix = output.suffix
        else:
            if isinstance(output, RemoteOutput):
                url = output.url
                filename = output.filename
            else:
                url = output
            async with self.downloads.stream("GET", url) as response:
                status = response.status_code
                logger.debug(
                    "Atlas Cloud 成品下载响应", output_index=output_index, http_status=status
                )
                if 400 <= status < 500 and status not in {408, 429}:
                    raise RunError(f"Atlas Cloud 成品下载失败（HTTP {status}）")
                size, digest = await _save(response, path, max_bytes)
                content_type = response.headers.get("content-type", "").split(";", 1)[0]
                suffix = preferred_suffix or mimetypes.guess_extension(content_type)
                if not suffix or suffix in {".bin", ".txt"}:
                    suffix = Path(response.url.path).suffix[:12]
        if not size:
            raise RunError("Atlas Cloud 返回的成品为空")
        try:
            await self.platform.upload_artifact(
                task_id,
                lease,
                path.name,
                path,
                filename=filename or f"result-{output_index + 1}{suffix}",
                sha256=digest,
                execution_index=index,
                output_node_id="official",
                output_slot="outputs",
                output_index=output_index,
            )
        except PlatformError as error:
            if error.status in {400, 413, 415, 422}:
                raise RunError("生成成品未通过文件校验") from error
            raise

    async def _fail(self, task_id: str, lease: str, error: str) -> None:
        logger.error("官方任务执行失败", reason=error)
        await self.platform.task_request(task_id, lease, "fail", body={"error": error})
