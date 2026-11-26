"""RunningHub execution adapter for the shared leased work-machine runner."""

import asyncio
import hashlib
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from comfyshop_worker_protocol import TaskStage
from comfyshop_worker_protocol.logging import logger, worker_logging
from comfyshop_worker_protocol.platform import Platform
from comfyshop_worker_protocol.service import ServiceRunner

from .provider import Hub, ProviderError, definition, url_image

OUTPUT_HOSTS = {
    "runninghub.cn",
    "runninghub.ai",
    "rh-images.xiaoyaoyou.com",
    "rh-images-switch-1252422369.cos.ap-guangzhou.myqcloud.com",
}


class Adapter:
    def __init__(self, http: httpx.AsyncClient, auth: dict):
        output_hosts = {
            host.strip().lower()
            for host in os.getenv("COMFYSHOP_RUNNINGHUB_OUTPUT_HOSTS", "").split(",")
            if host.strip()
        }
        self.hub = Hub(http, auth["scope"], auth["apiKey"])
        self.http, self.hosts = http, OUTPUT_HOSTS | output_hosts
        self.reference = ""
        self.values: dict[tuple[str, str], object] = {}
        self.seeds: list[list[dict]] = []

    async def prepare(self, job: dict, assets: dict[str, Path]) -> None:
        context = job["workerContext"]
        self.reference = context["reference"]
        graph = await self.hub.graph(self.reference)
        digest = hashlib.sha256(
            json.dumps(
                graph, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
            ).encode()
        ).hexdigest()
        if digest != context["graph_hash"]:
            raise ProviderError("云端工作流已变更，请重新导入并核对参数")
        uploaded = {}
        values = job["task"]["inputValues"]
        bindings = {(a["nodeId"], a["inputName"]): a for a in job["assets"]}
        for field in context["fields"]:
            if field["id"] not in values:
                continue
            node, name = field["nodeId"], field["name"]
            value = values[field["id"]]
            if data := bindings.get((node, name)):
                asset_id = data["id"]
                if asset_id not in uploaded:
                    uploaded[asset_id] = await self.hub.upload(
                        assets[asset_id], data["filename"], data["contentType"]
                    )
                source = uploaded[asset_id]
                value = (
                    source.get("download_url")
                    if url_image(graph[node]["class_type"], name)
                    else source["fileName"]
                )
                if not value:
                    raise ProviderError("未收到此素材节点需要的文件地址")
            elif field["kind"] == "integer":
                value = int(value)
            self.values[node, name] = value
        self.seeds = job["executionSeeds"]

    async def submit(self, index: int) -> str:
        values = self.values.copy()
        for seed in self.seeds[index]:
            values[seed["nodeId"], seed["inputName"]] = int(seed["value"])
        return await self.hub.submit(
            self.reference,
            [{"nodeId": n, "fieldName": f, "fieldValue": v} for (n, f), v in values.items()],
        )

    async def poll(self, remote_id: str) -> TaskStage | list:
        return await self.hub.outputs(remote_id)

    async def download(self, item: dict, path: Path, index: int) -> tuple[str, str]:
        url = item["fileUrl"]
        for _ in range(5):
            target = urlsplit(url)
            host = target.hostname or ""
            if (
                target.scheme != "https"
                or target.username
                or target.password
                or target.port not in (None, 443)
                or not any(
                    host == allowed or host.endswith("." + allowed) for allowed in self.hosts
                )
            ):
                raise ProviderError("成品地址不在允许的域名内")
            async with self.http.stream("GET", url, follow_redirects=False) as response:
                if response.is_redirect and "location" in response.headers:
                    url = urljoin(url, response.headers["location"])
                    continue
                if 400 <= response.status_code < 500 and response.status_code not in (408, 429):
                    raise ProviderError("RunningHub 成品下载失败")
                response.raise_for_status()
                size = 0
                with path.open("wb") as output:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        size += len(chunk)
                        if size > 1024**3:
                            raise ProviderError("成品超过文件大小限制")
                        await asyncio.to_thread(output.write, chunk)
                if not size:
                    raise ProviderError("云端成品为空")
                suffix = (
                    Path(target.path).suffix[:12]
                    or mimetypes.guess_extension(
                        response.headers.get("Content-Type", "").partition(";")[0]
                    )
                    or ""
                )
                return f"result-{index + 1}{suffix}", str(
                    item.get("nodeId") or definition.output_node
                )
        raise ProviderError("成品重定向次数过多")


async def serve() -> None:
    token = os.getenv("COMFYSHOP_WORKER_SERVICE_TOKENS__RUNNINGHUB")
    if not token:
        raise SystemExit("请配置 COMFYSHOP_WORKER_SERVICE_TOKENS__RUNNINGHUB")
    platform = Platform(
        os.environ.get("COMFYSHOP_SERVER_URL", "http://127.0.0.1:8688").rstrip("/"), token
    )
    try:
        async with httpx.AsyncClient(timeout=60) as http:
            await ServiceRunner(platform, definition, http).run()
    finally:
        await platform.close()


def main() -> None:
    try:
        with worker_logging(definition.kind):
            logger.info("RunningHub 工作机已启动")
            try:
                asyncio.run(serve())
            except KeyboardInterrupt:
                logger.info("RunningHub 工作机已停止")
    except ValueError as error:
        raise SystemExit(str(error)) from None
