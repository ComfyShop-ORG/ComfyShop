"""通过 HTTP 和 WebSocket 与本机 ComfyUI 通信，恢复已有 prompt 并读取成功历史。"""

import asyncio
import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlencode

import httpx
from comfyshop_worker_protocol import DEFAULT_MAX_ARTIFACT_BYTES, TaskStage
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .config import RunRecord
from .graph import WorkflowError


def history_outputs(history: dict) -> list[dict]:
    """把已明确成功的历史转换为有序文件描述，保留每份成品的节点和输出槽。

    执行报错、中断、成功未确认或没有可保存的媒体时抛出 `WorkflowError`。
    """
    status = history.get("status", {})
    messages = status.get("messages", [])
    for kind, data in messages:
        if kind in {"execution_error", "execution_interrupted"}:
            raise WorkflowError(str(data.get("exception_message") or "ComfyUI 执行中断")[:1800])
    if status.get("status_str") != "success" or not status.get("completed"):
        raise WorkflowError("ComfyUI 未确认执行成功")
    files = {}

    def collect(value, node_id, slot):
        if isinstance(value, dict):
            if isinstance(value.get("filename"), str) and value.get("type", "output") in {
                "output",
                "temp",
            }:
                suffix = Path(value["filename"]).suffix.lower()
                if suffix in {
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                    ".gif",
                    ".mp4",
                    ".webm",
                    ".mov",
                    ".flac",
                } or (suffix == ".glb" and value.get("type", "output") == "output"):
                    descriptor = {
                        key: value.get(key, "output" if key == "type" else "")
                        for key in ["filename", "subfolder", "type"]
                    }
                    descriptor["outputNodeId"] = str(node_id)
                    descriptor["outputSlot"] = slot
                    files[json.dumps(descriptor, sort_keys=True)] = descriptor
            else:
                for key in sorted(value):
                    collect(value[key], node_id, f"{slot}/{key}" if slot else str(key))
        elif isinstance(value, list):
            for child in value:
                collect(child, node_id, slot)

    for node_id, output in sorted(history.get("outputs", {}).items()):
        collect(output, node_id, "")
    if not files:
        raise WorkflowError("工作流未输出平台支持的图像、视频、FLAC 音频或 GLB 模型")
    return [{**descriptor, "outputIndex": index} for index, descriptor in enumerate(files.values())]


def completed_outputs(history: dict, record: RunRecord) -> list[dict]:
    files = history_outputs(history)
    if preview_id := record.get("promptPreviewNodeId"):
        preview = history.get("outputs", {}).get(preview_id, {}).get("text")
        if (
            isinstance(preview, list)
            and len(preview) == 1
            and isinstance(preview[0], str)
            and 0 < len(preview[0]) <= 65_536
        ):
            record["effectivePrompt"] = preview[0]
    return files


class _NodeProgress:
    """按 ComfyUI 的节点事件估算一次执行的完成比例。"""

    def __init__(self, node_count: int):
        self.node_count = max(node_count, 1)
        self.completed: set[str] = set()
        self.last_node: str | None = None

    def advance(self, kind: str | None, data: dict) -> float:
        """记入一条属于当前 prompt 的事件，返回 0–0.99 的比例。"""
        if kind == "execution_cached":
            self.completed.update(data.get("nodes", []))
        elif kind == "executing":
            if self.last_node:
                self.completed.add(self.last_node)
            self.last_node = data.get("node")
        fraction = len(self.completed)
        if kind == "progress" and data.get("max", 0) > 0:
            fraction += min(1, data.get("value", 0) / data["max"])
        return min(0.99, fraction / self.node_count)


class Comfy:
    """持有 ComfyUI HTTP 连接，并按 prompt ID 跟踪队列、事件和历史。"""

    def __init__(self, url: str, *, missing_grace_seconds: float = 15):
        self.url = url
        self.missing_grace_seconds = missing_grace_seconds
        self.client = httpx.AsyncClient(base_url=url + "/", timeout=httpx.Timeout(60, connect=10))

    async def close(self):
        await self.client.aclose()

    async def get(self, path: str):
        response = await self.client.get(path)
        response.raise_for_status()
        return response.json()

    async def inventory(self) -> tuple[dict, dict]:
        info, stats = await asyncio.gather(self.get("object_info"), self.get("system_stats"))
        device = ", ".join(d.get("name", "") for d in stats.get("devices", []))[:200]
        return info, {"device": device, "nodes": list(info)}

    async def idle(self) -> bool:
        queue = await self.get("queue")
        return not queue.get("queue_running") and not queue.get("queue_pending")

    async def stop(self, prompt_id: str) -> bool:
        """停止本工作机提交的 `prompt_id`，返回是否发出了停止请求。

        还在排队时把它从队列删除。只有它正在执行时才请求中断，其他来源的任务和
        队列里的其余条目保持不变。它已经结束或不在队列里时不做任何事。
        """
        queue = await self.get("queue")

        def listed(group: str) -> bool:
            return any(len(item) > 1 and item[1] == prompt_id for item in queue.get(group, []))

        if listed("queue_pending"):
            response = await self.client.post("queue", json={"delete": [prompt_id]})
        elif listed("queue_running"):
            response = await self.client.post("interrupt", json={"prompt_id": prompt_id})
        else:
            return False
        response.raise_for_status()
        return True

    async def upload_asset(self, task_id: str, asset: dict, path: Path) -> str:
        suffix = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "video/x-matroska": ".mkv",
            "audio/aac": ".aac",
            "audio/flac": ".flac",
            "audio/mp4": ".m4a",
            "audio/mpeg": ".mp3",
            "audio/ogg": ".ogg",
            "audio/wav": ".wav",
            "audio/webm": ".webm",
            "audio/x-matroska": ".mka",
            "model/gltf-binary": ".glb",
        }.get(asset["contentType"])
        if not suffix:
            raise WorkflowError("不支持的素材格式")
        with path.open("rb") as source:
            response = await self.client.post(
                "upload/image",
                data={"type": "input", "subfolder": "ComfyShop/" + task_id, "overwrite": "true"},
                files={"image": (asset["id"] + suffix, source, asset["contentType"])},
            )
        response.raise_for_status()
        result = response.json()
        return result["subfolder"].strip("/\\").replace("\\", "/") + "/" + result["name"]

    async def history(self, prompt_id: str) -> dict | None:
        return (await self.get("history/" + prompt_id)).get(prompt_id)

    async def known(self, prompt_id: str) -> bool:
        if await self.history(prompt_id):
            return True
        queue = await self.get("queue")
        return any(
            len(item) > 1 and item[1] == prompt_id
            for group in ["queue_running", "queue_pending"]
            for item in queue.get(group, [])
        )

    async def execute(
        self,
        graph: dict,
        record: RunRecord,
        save: Callable[[], None],
        progress: Callable[[float, str], None],
        *,
        report_stage: Callable[[TaskStage, str], None] | None = None,
        timeout_seconds: float = 3600,
    ) -> list[dict]:
        """提交或恢复一次执行，返回成功历史中的有序成品描述。

        `record` 保存 prompt、阶段和开始时间，`save` 持久化它。
        `progress` 接收 0–0.99 的节点进度和当前 prompt ID。限时从首次执行起计，
        超时时先停下这次提交的 prompt。超时、提交结果不明或 ComfyUI 报错时抛出
        `WorkflowError`。
        """
        if "startedAt" not in record:
            record["startedAt"] = time.time()
            save()
        remaining = timeout_seconds - (time.time() - record["startedAt"])
        try:
            if remaining <= 0:
                raise TimeoutError
            async with asyncio.timeout(remaining):
                return await self._execute(graph, record, save, progress, report_stage)
        except TimeoutError:
            await self._abandon(record)
            raise WorkflowError("执行已超过时间限制，请检查工作机后重新提交") from None

    async def _abandon(self, record: RunRecord) -> None:
        """超时放弃这次执行时停下自己提交的 prompt，不让它继续占用 GPU。

        只按 prompt ID 停止，共用这台 ComfyUI 的其他任务不受影响。停止失败时 prompt 会
        自行结束，工作机等 ComfyUI 空闲后再领取。
        """
        if record.get("phase") not in {"submitting", "submitted"}:
            return
        try:
            await self.stop(record["promptId"])
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError):
            pass

    async def _submit(self, graph: dict, record: RunRecord, save: Callable[[], None]) -> None:
        """向 ComfyUI 提交一次 prompt，并把阶段写入 `record`。

        先保存 submitting 再发送。回复丢失时只在队列或历史里能找到原 prompt 才继续，
        否则抛出 `WorkflowError`，不重复提交。
        """
        record["phase"] = "submitting"
        save()
        try:
            response = await self.client.post(
                "prompt",
                json={
                    "prompt": graph,
                    "client_id": record["clientId"],
                    "prompt_id": record["promptId"],
                },
            )
        except httpx.TransportError:
            if not await self.known(record["promptId"]):
                raise WorkflowError("ComfyUI 提交结果不明，已停止，未重复执行") from None
        else:
            if not response.is_success:
                try:
                    data = response.json()
                except ValueError:
                    raise WorkflowError(
                        f"ComfyUI 拒绝工作流（HTTP {response.status_code}）"
                    ) from None
                if response.status_code == 400 and isinstance(data, dict) and "node_errors" in data:
                    record["phase"] = "prepared"
                    save()
                raise WorkflowError(
                    "ComfyUI 拒绝工作流："
                    + json.dumps(data.get("node_errors") or data.get("error"), ensure_ascii=False)[
                        :1500
                    ]
                )
            record["promptId"] = response.json()["prompt_id"]
        record["phase"] = "submitted"
        save()

    async def _execute(
        self,
        graph: dict,
        record: RunRecord,
        save: Callable[[], None],
        progress: Callable[[float, str], None],
        report_stage: Callable[[TaskStage, str], None] | None,
    ) -> list[dict]:
        # Persisted 'submitting' means the HTTP reply may have been lost.
        if record["phase"] == "submitting":
            if not await self.known(record["promptId"]):
                raise WorkflowError("上次提交结果不明，已停止，未重复执行")
            record["phase"] = "submitted"
            save()
        ws_url = (
            self.url.replace("https://", "wss://").replace("http://", "ws://")
            + "/ws?"
            + urlencode({"clientId": record["clientId"]})
        )
        socket = None
        steps = _NodeProgress(len(graph))
        missing_since = None
        checked_at = float("-inf")
        while True:
            try:
                # 先连接 WebSocket 再提交，避免错过执行开始前后的事件。
                if socket is None:
                    socket = await connect(ws_url, max_size=8 * 1024 * 1024, open_timeout=10)
                    if record["phase"] == "prepared":
                        await self._submit(graph, record, save)
                    if report_stage and record["phase"] == "submitted":
                        report_stage(
                            "executing" if record.get("executionStarted") else "waiting_for_comfy",
                            record["promptId"],
                        )
                prompt_id = record["promptId"]
                history = await self.history(prompt_id)
                if history:
                    if socket:
                        await socket.close()
                        socket = None
                    return completed_outputs(history, record)
                now = time.monotonic()
                if now - checked_at >= min(3, self.missing_grace_seconds):
                    checked_at = now
                    if await self.known(prompt_id):
                        missing_since = None
                    else:
                        missing_since = now if missing_since is None else missing_since
                        if now - missing_since >= self.missing_grace_seconds:
                            raise WorkflowError("ComfyUI 队列和历史中已无此任务，未重复执行")
                try:
                    message = await asyncio.wait_for(socket.recv(), timeout=3)
                except TimeoutError:
                    continue
                if not isinstance(message, str):
                    continue
                event = json.loads(message)
                data = event.get("data", {})
                if data.get("prompt_id") != prompt_id:
                    continue
                kind = event.get("type")
                if kind in {"execution_error", "execution_interrupted"}:
                    raise WorkflowError(
                        str(data.get("exception_message") or "ComfyUI 执行中断")[:1800]
                    )
                if kind in {
                    "execution_start",
                    "execution_cached",
                    "executing",
                    "executed",
                    "progress",
                }:
                    record["executionStarted"] = True
                    progress(steps.advance(kind, data), prompt_id)
            except (WebSocketException, OSError, httpx.TransportError):
                if socket:
                    await socket.close()
                    socket = None
                if report_stage:
                    report_stage("reconnecting", record["promptId"])
                await asyncio.sleep(3)
            except BaseException:
                if socket:
                    await socket.close()
                raise

    async def download(
        self, descriptor: dict, path: Path, *, max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES
    ) -> str:
        checksum = hashlib.sha256()
        size = 0
        params = {key: descriptor[key] for key in ["filename", "subfolder", "type"]}
        async with self.client.stream("GET", "view", params=params) as response:
            response.raise_for_status()
            with path.open("wb") as output:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise WorkflowError("成品超过文件大小限制")
                    checksum.update(chunk)
                    await asyncio.to_thread(output.write, chunk)
        return checksum.hexdigest()
