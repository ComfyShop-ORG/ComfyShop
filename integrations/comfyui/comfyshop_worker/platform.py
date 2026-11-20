"""访问平台的工作机 API，为领取、租约心跳和文件传输提供重试。"""

import asyncio
import hashlib
from pathlib import Path

import httpx


class PlatformError(Exception):
    """保留平台返回的 HTTP 状态码，供主循环处理停机、丢失租约或稍后重试。"""

    def __init__(self, status: int, detail: str):
        self.status = status
        super().__init__(detail)


class Platform:
    """持有工作机 Bearer 密钥的客户端，任务请求另带当前租约。"""

    def __init__(self, server_url: str, api_key: str):
        self.client = httpx.AsyncClient(
            base_url=server_url + "/api/v1/worker/",
            headers={"Authorization": "Bearer " + api_key},
            timeout=httpx.Timeout(60, connect=10),
            follow_redirects=False,
        )

    async def close(self):
        await self.client.aclose()

    async def request(
        self,
        path: str,
        body: dict | None = None,
        *,
        lease: str | None = None,
        file: Path | None = None,
        params: dict | None = None,
        method: str = "POST",
    ):
        """请求相对 `path` 并返回响应 JSON。传入 `file` 时用 PUT 流式发送原始字节。

        临时网络错误和 5xx 最多尝试四次。最终 HTTP 失败或成功响应不是 JSON 时抛出
        `PlatformError`，网络重试耗尽时传播 `httpx.TransportError`。
        """
        for attempt in range(4):
            try:
                headers = {"X-Task-Lease": lease} if lease else {}
                if file:
                    headers["Content-Type"] = "application/octet-stream"
                    headers["Content-Length"] = str(file.stat().st_size)

                    async def chunks():
                        with file.open("rb") as source:
                            while chunk := await asyncio.to_thread(source.read, 1024 * 1024):
                                yield chunk

                    response = await self.client.put(
                        path, content=chunks(), headers=headers, params=params
                    )
                else:
                    response = await self.client.request(method, path, json=body, headers=headers)
                if response.status_code >= 500 and attempt < 3:
                    await asyncio.sleep(2**attempt)
                    continue
                if not response.is_success:
                    try:
                        detail = response.json().get("detail", "工作机接口请求失败")
                    except ValueError:
                        detail = "工作机接口请求失败"
                    raise PlatformError(response.status_code, str(detail))
                try:
                    return response.json()
                except ValueError:
                    # 例如反向代理返回的网页，按网关错误处理。
                    raise PlatformError(502, "平台响应无法解析") from None
            except httpx.TransportError:
                if attempt == 3:
                    raise
                await asyncio.sleep(2**attempt)

    async def download_asset(self, task_id: str, asset: dict, path: Path, lease: str):
        """将任务绑定素材写到 `path`，核对长度和 SHA-256。校验失败为 `PlatformError(422)`。"""
        digest = hashlib.sha256()
        size = 0
        async with self.client.stream(
            "GET", f"tasks/{task_id}/assets/{asset['id']}", headers={"X-Task-Lease": lease}
        ) as response:
            if not response.is_success:
                raise PlatformError(response.status_code, "素材下载失败")
            with path.open("wb") as output:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    size += len(chunk)
                    if size > asset["size"]:
                        raise PlatformError(422, "素材大小不一致")
                    digest.update(chunk)
                    await asyncio.to_thread(output.write, chunk)
        if size != asset["size"] or digest.hexdigest() != asset["sha256"]:
            raise PlatformError(422, "素材校验失败")
