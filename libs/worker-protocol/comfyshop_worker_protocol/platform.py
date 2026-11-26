"""访问平台的工作机 API，为领取、租约心跳和文件传输提供重试。"""

import asyncio
import hashlib
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any, Self

import httpx

from . import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    ERROR_CODE_HEADER,
    LEASE_HEADER,
    PROTOCOL_VERSION,
    RECOVERY_HEADER,
    TaskStage,
)
from .definition import PERSONAL
from .logging import logger


def artifact_byte_limit(job: dict[str, Any]) -> int:
    limit = job.get("maxArtifactBytes")
    return limit if type(limit) is int and limit > 0 else DEFAULT_MAX_ARTIFACT_BYTES


def task_event(
    sequence: int, stage: TaskStage, index: int, progress: int, prompt_id: str | None = None
) -> dict:
    return {
        "sequence": sequence,
        "stage": stage,
        "executionIndex": index,
        "progress": progress,
        "promptId": prompt_id,
    }


class PlatformError(Exception):
    """保留平台返回的 HTTP 状态码，供主循环处理停机、丢失租约或稍后重试。"""

    def __init__(self, status: int, detail: str, *, code: str | None = None):
        self.status = status
        self.code = code
        super().__init__(detail)


class Platform:
    """持有工作机 Bearer 密钥的客户端，任务请求另带当前租约。"""

    def __init__(
        self, server_url: str, api_key: str, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.client = httpx.AsyncClient(
            base_url=server_url.rstrip("/") + "/api/v1/worker/",
            headers={"Authorization": "Bearer " + api_key},
            timeout=httpx.Timeout(60, connect=10),
            follow_redirects=False,
            transport=transport,
        )

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def claim(
        self, claim_id: str, lease: str, *, service: str | None = None, adapters: Sequence[str] = ()
    ) -> dict | None:
        body: dict[str, Any] = {
            "protocolVersion": PROTOCOL_VERSION,
            "claimId": claim_id,
            "leaseSecret": lease,
        }
        path = "claim"
        if service is not None:
            path = f"services/{service}/claim"
            body["adapters"] = list(adapters)
        job = await self.request(path, body)
        if job:
            task = job["task"]
            logger.info(
                "已领取任务",
                worker_kind=service or PERSONAL.kind,
                task_id=task["id"],
                workflow_id=task.get("workflowId"),
                execution_count=task["executionCount"],
            )
        return job

    async def heartbeat(self, task_id: str, lease: str, event: dict) -> dict:
        result = await self.task_request(task_id, lease, "heartbeat", event)
        if not isinstance(result, dict):
            raise PlatformError(502, "平台心跳响应无效")
        logger.debug(
            "任务租约已续期",
            task_id=task_id,
            sequence=event["sequence"],
            stage=event["stage"],
            execution_index=event["executionIndex"],
            progress=event["progress"],
        )
        return result

    async def task_request(
        self, task_id: str, lease: str, path: str, body: dict | None = None, *, method: str = "POST"
    ) -> Any:
        return await self.request(f"tasks/{task_id}/{path}", body, lease=lease, method=method)

    async def upload_artifact(
        self,
        task_id: str,
        lease: str,
        client_id: str,
        file: Path,
        *,
        filename: str,
        sha256: str,
        execution_index: int,
        output_node_id: str,
        output_slot: str,
        output_index: int,
        recovering: bool = False,
    ) -> None:
        await self.request(
            f"tasks/{task_id}/artifacts/{client_id}",
            file=file,
            lease=lease,
            headers={RECOVERY_HEADER: "1"} if recovering else None,
            params={
                "filename": filename,
                "sha256": sha256,
                "execution_index": execution_index,
                "output_node_id": output_node_id,
                "output_slot": output_slot,
                "output_index": output_index,
            },
        )

        logger.debug(
            "平台成品回传响应",
            task_id=task_id,
            execution_index=execution_index,
            output_index=output_index,
            recovering=recovering,
        )

    async def request(
        self,
        path: str,
        body: dict | None = None,
        *,
        lease: str | None = None,
        file: Path | None = None,
        params: dict | None = None,
        method: str = "POST",
        headers: dict[str, str] | None = None,
    ):
        """请求相对 `path` 并返回响应 JSON。传入 `file` 时用 PUT 流式发送原始字节。

        临时网络错误和 5xx 最多尝试四次。最终 HTTP 失败或成功响应不是 JSON 时抛出
        `PlatformError`，网络重试耗尽时传播 `httpx.TransportError`。
        """
        for attempt in range(4):
            try:
                request_headers = dict(headers or {})
                if lease:
                    request_headers[LEASE_HEADER] = lease
                if file:
                    request_headers["Content-Type"] = "application/octet-stream"
                    request_headers["Content-Length"] = str(
                        (await asyncio.to_thread(file.stat)).st_size
                    )

                    async def chunks() -> AsyncIterator[bytes]:
                        with file.open("rb") as source:
                            while chunk := await asyncio.to_thread(source.read, 1024 * 1024):
                                yield chunk

                    response = await self.client.put(
                        path, content=chunks(), headers=request_headers, params=params
                    )
                else:
                    response = await self.client.request(
                        method, path, json=body, headers=request_headers
                    )
                if response.status_code >= 500 and attempt < 3:
                    logger.debug(
                        "平台请求稍后重试", http_status=response.status_code, attempt=attempt + 1
                    )
                    await asyncio.sleep(2**attempt)
                    continue
                if not response.is_success:
                    try:
                        payload = response.json()
                    except ValueError:
                        payload = None
                    detail = payload.get("detail") if isinstance(payload, dict) else None
                    detail = detail or "工作机接口请求失败"
                    raise PlatformError(
                        response.status_code,
                        str(detail),
                        code=response.headers.get(ERROR_CODE_HEADER),
                    )
                try:
                    return response.json()
                except ValueError:
                    # 例如反向代理返回的网页，按网关错误处理。
                    raise PlatformError(502, "平台响应无法解析") from None
            except httpx.TransportError as error:
                if attempt == 3:
                    raise
                logger.debug(
                    "平台连接稍后重试", error_type=type(error).__name__, attempt=attempt + 1
                )
                await asyncio.sleep(2**attempt)

    async def download_asset(self, task_id: str, asset: dict, path: Path, lease: str):
        """将任务绑定素材写到 `path`，核对长度和 SHA-256。校验失败为 `PlatformError(422)`。"""
        await self.download_verified(
            f"tasks/{task_id}/assets/{asset['id']}",
            path,
            asset["size"],
            asset["sha256"],
            headers={LEASE_HEADER: lease},
            label="素材",
        )

    async def download_verified(
        self,
        endpoint: str,
        path: Path,
        expected_size: int,
        sha256: str,
        *,
        headers: dict[str, str] | None = None,
        label: str = "文件",
    ) -> None:
        digest = hashlib.sha256()
        size = 0
        async with self.client.stream("GET", endpoint, headers=headers) as response:
            if not response.is_success:
                raise PlatformError(
                    response.status_code,
                    f"{label}下载失败",
                    code=response.headers.get(ERROR_CODE_HEADER),
                )
            with path.open("wb") as output:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    size += len(chunk)
                    if size > expected_size:
                        raise PlatformError(422, f"{label}大小不一致")
                    digest.update(chunk)
                    await asyncio.to_thread(output.write, chunk)
        if size != expected_size or digest.hexdigest() != sha256:
            raise PlatformError(422, f"{label}校验失败")
