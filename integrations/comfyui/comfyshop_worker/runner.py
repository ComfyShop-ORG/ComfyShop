"""工作机主循环，按本地恢复记录串联领取、执行、回传和失败报告。"""

import asyncio
import hashlib
import json
import secrets
import time
from collections.abc import Callable
from contextlib import suppress
from enum import Enum, auto
from pathlib import Path
from sys import platform as host_platform
from typing import Any, Literal, cast
from uuid import UUID, uuid4

import httpx
from comfyshop_worker_protocol import PROTOCOL_VERSION, RECOVERY_HEADER, TASK_CANCELLED, TaskStage
from comfyshop_worker_protocol.catalog import make_catalog
from comfyshop_worker_protocol.logging import logger
from comfyshop_worker_protocol.platform import (
    Platform,
    PlatformError,
    artifact_byte_limit,
    task_event,
)
from filelock import FileLock

from .comfy import Comfy, completed_outputs
from .config import Config, Journal, RecoveryRecord, RetryRecord, RunRecord, WorkerState, write_json
from .graph import WorkflowError, preflight, prepare_bound_graph
from .release import Build
from .update_control import UPDATE_EXIT, UpdateControl

# 同一执行序号上持续出现暂时性故障的时限，超过后放弃这份任务。
RETRY_LIMIT_SECONDS = 15 * 60


class _Cycle(Enum):
    """主循环一轮的结果，决定本地记录是保留还是清理。"""

    # ComfyUI 正忙于其他队列，稍后再领取。
    BUSY = auto()
    # 平台没有可领取的任务。
    EMPTY = auto()
    # 任务已有最终结果或租约已失效，清理本地记录。
    FINISHED = auto()
    # 暂时性故障，保留本地记录后重试。
    RETRY = auto()
    # 工作机密钥失效，结束主循环。
    STOP = auto()


class Runner:
    """用同一份任务日志协调平台租约和本机 ComfyUI prompt。"""

    def __init__(self, config: Config, control: UpdateControl | None = None):
        self.config = config
        self.control = control
        build = Build.installed(Path(__file__).resolve().parent.parent)
        if build is None:
            raise ValueError("无法读取工作机版本，请重新安装工作机")
        self.build = build
        self.update_id: str | None = None
        self.platform = Platform(config.server_url, config.api_key)
        self.comfy = Comfy(config.comfy_url)
        self.journal = Journal(config.state_dir)
        self.recovery_dir = config.state_dir / "recoveries"
        self.state: WorkerState | None = self.journal.read()
        self.capabilities: dict = {"protocolVersion": PROTOCOL_VERSION}
        self.comfy_status: Literal["idle", "busy", "unreachable"] | None = None
        self.startup_issue: (
            Literal["comfy_connection", "comfy_inventory", "platform_connection"] | None
        ) = None
        self.object_info: dict = {}
        self.active: asyncio.Task | None = None
        self.lease_lost = False
        # 用户在平台停止了当前任务，需要让 ComfyUI 停下对应的 prompt。
        self.stop_requested = False
        self.authorization_lost = False
        self.catalog_digest: str | None = None
        # 还没领到任务时连续出错的次数，用来逐次加长等待。
        self.idle_failures = 0

    async def refresh_inventory(self) -> None:
        self.object_info, self.capabilities = await self.comfy.inventory()
        self.capabilities["protocolVersion"] = PROTOCOL_VERSION
        catalog = make_catalog(self.object_info)
        digest = hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest()
        if digest != self.catalog_digest:
            await self.platform.request("catalog", catalog, method="PUT")
            self.catalog_digest = digest
        await self._machine_heartbeat()

    async def _machine_heartbeat(self) -> None:
        control = self.control
        operating_system = {"win32": "windows", "darwin": "macos", "linux": "linux"}.get(
            host_platform
        )
        failure = control.failed_update() if control and not control.trial else None
        response = await self.platform.request(
            "heartbeat",
            {
                **self.capabilities,
                "operatingSystem": operating_system,
                "comfyStatus": self.comfy_status,
                "startupIssue": self.startup_issue,
                "runtime": {
                    "version": self.build.version,
                    "build": self.build.build,
                    "canUpdate": control is not None,
                    "checking": bool(control and control.trial),
                    "failure": failure,
                },
            },
        )
        if not control or control.trial:
            return
        if failure:
            control.failure.unlink(missing_ok=True)
        pending = response.get("update") if isinstance(response, dict) else None
        self.update_id = None
        if isinstance(pending, dict) and pending.get("status") in {"pending", "updating"}:
            update_id = pending.get("id")
            if isinstance(update_id, str):
                with suppress(ValueError):
                    self.update_id = str(UUID(update_id))

    def _current(self) -> WorkerState:
        """返回正在处理的记录。只在已有领取凭据的步骤里调用。"""
        if self.state is None:
            raise RuntimeError("工作机当前没有任务记录")
        return self.state

    def _job(self) -> dict[str, Any]:
        """返回已领取的任务。只在 `_acquire` 确认领取之后调用。"""
        job = self._current().get("job")
        if job is None:
            raise RuntimeError("工作机尚未领取任务")
        return job

    def save(self) -> None:
        self.journal.save(self._current())

    def progress(self, value: int, stage: TaskStage, prompt_id: str | None = None) -> None:
        state = self._current()
        previous = state.get("progress", 0)
        state["progress"] = max(previous, min(99, value))
        if state["progress"] > previous:
            # 进度向前走了，之前的故障已经过去：一次长时间的生成里相隔很久的两次
            # 短暂故障不算持续出错。
            state.pop("retry", None)
        state["stage"] = stage
        if prompt_id:
            state["promptId"] = prompt_id
        self.save()

    async def _task_request(self, path: str, body: dict | None = None) -> Any:
        """用当前租约请求任务接口，`path` 相对于 `tasks/<任务 ID>/`。"""
        state = self._current()
        return await self.platform.task_request(
            self._job()["task"]["id"], state["leaseSecret"], path, body
        )

    async def report(self) -> dict[str, Any]:
        state = self._current()
        state["sequence"] = state.get("sequence", 0) + 1
        self.save()
        return await self.platform.heartbeat(
            self._job()["task"]["id"],
            state["leaseSecret"],
            task_event(
                state["sequence"],
                state.get("stage", "preflight"),
                state.get("index", 0),
                state.get("progress", 0),
                state.get("promptId"),
            ),
        )

    def _lose_authorization(self) -> None:
        self.authorization_lost = True
        if self.active:
            self.active.cancel()
        logger.error("工作机密钥已失效")

    async def _renew_lease(self) -> bool:
        """为正在处理的任务发送一次任务心跳。密钥失效时返回假。"""
        if not (self.state and self.state.get("job") and not self.state.get("finishing")):
            return True
        reported_state = self.state
        try:
            await self.report()
        except PlatformError as error:
            if error.status == 401:
                self._lose_authorization()
                return False
            if error.status in {404, 409}:
                if self.state is reported_state and self.active and self.active.cancel():
                    self.lease_lost = True
                    self.stop_requested = error.code == TASK_CANCELLED
                    logger.warning(
                        "任务已被停止" if self.stop_requested else "任务租约已失效，停止当前任务"
                    )
            else:
                logger.warning("任务心跳暂时失败", http_status=error.status)
        except httpx.TransportError:
            logger.warning("平台连接暂时中断")
        except Exception:
            logger.exception("任务心跳出错")
        return True

    async def _publish_health(self) -> bool:
        try:
            await self._machine_heartbeat()
        except PlatformError as error:
            if error.status == 401:
                self._lose_authorization()
                return False
            logger.warning("工作机心跳暂时失败", http_status=error.status)
        except httpx.TransportError:
            logger.warning("平台连接暂时中断")
        except Exception:
            logger.exception("工作机心跳出错")
        return True

    async def _comfy_idle(self) -> bool:
        """检查本机队列，同时记录独立于平台心跳的 ComfyUI 状态。"""
        try:
            async with asyncio.timeout(3):
                idle = await self.comfy.idle()
        except (TimeoutError, httpx.HTTPError, ValueError):
            self.comfy_status = "unreachable"
            raise
        self.comfy_status = "idle" if idle else "busy"
        return idle

    async def heartbeats(self) -> None:
        """每 10 秒发送机器心跳，并续期当前任务的租约。

        两者分开处理：机器心跳失败时，任务租约照常续期。
        """
        while True:
            if not await self._publish_health() or not await self._renew_lease():
                return
            if self.active and not self.active.done() and not self.lease_lost:
                with suppress(TimeoutError, httpx.HTTPError, ValueError):
                    await self._comfy_idle()
            await asyncio.sleep(10)

    async def _transfer_assets(self, job: dict[str, Any]) -> dict[str, str]:
        """把任务绑定的素材从平台传入 ComfyUI，返回素材 ID 到 ComfyUI 输入路径的映射。"""
        state = self._current()
        task_id = job["task"]["id"]
        uploaded = state.setdefault("uploadedAssets", {})
        for asset in job["assets"]:
            if asset["id"] in uploaded:
                continue
            path = self.config.state_dir / (asset["id"] + ".input")
            try:
                await self.platform.download_asset(task_id, asset, path, state["leaseSecret"])
                uploaded[asset["id"]] = await self.comfy.upload_asset(task_id, asset, path)
                self._progressed()
            finally:
                path.unlink(missing_ok=True)
        return uploaded

    async def _upload_outputs(
        self,
        task_id: str,
        lease: str,
        index: int,
        record: RunRecord,
        save: Callable[[], None],
        *,
        recovering: bool = False,
    ) -> list[str]:
        """逐个回传一次执行的成品，返回按输出顺序排列的回传编号。"""
        outputs = record.get("outputs", [])
        client_ids = []
        confirmed = record.setdefault("uploadedClientIds", [])
        max_bytes = artifact_byte_limit((self.state or {}).get("job", {}))
        for offset, descriptor in enumerate(outputs):
            # 编号由输出来源决定，断线重试时同一份成品沿用同一编号。
            identity = hashlib.sha256(json.dumps(descriptor, sort_keys=True).encode()).hexdigest()
            client_id = f"r{index}_{identity[:32]}"
            client_ids.append(client_id)
            if client_id in confirmed:
                continue
            path = self.config.state_dir / f"{task_id}-{client_id}.part"
            try:
                checksum = await self.comfy.download(descriptor, path, max_bytes=max_bytes)
                await self.platform.upload_artifact(
                    task_id,
                    lease,
                    client_id,
                    path,
                    filename=descriptor["filename"],
                    sha256=checksum,
                    execution_index=index,
                    output_node_id=descriptor["outputNodeId"],
                    output_slot=descriptor["outputSlot"],
                    output_index=descriptor["outputIndex"],
                    recovering=recovering,
                )
                confirmed.append(client_id)
                save()
            finally:
                path.unlink(missing_ok=True)
            logger.info(
                "已回传成品",
                task_id=task_id,
                execution_index=index,
                output_index=offset,
                output_count=len(outputs),
            )
        return client_ids

    async def _generate_outputs(
        self, index: int, uploaded: dict[str, str], record: RunRecord
    ) -> None:
        """执行或恢复原 prompt，记录成功历史以便独立重试回传。"""
        job = self._job()
        count = job["task"]["executionCount"]
        graph = prepare_bound_graph(
            job["graph"], job["executionSeeds"][index], job["assets"], uploaded
        )
        preflight(graph, self.object_info)
        if preview_node := job.get("promptPreviewNodeId"):
            record["promptPreviewNodeId"] = preview_node
        self.save()

        def report_stage(stage: TaskStage, prompt_id: str) -> None:
            self.progress(int(index / count * 90), stage, prompt_id)

        report_stage("connecting", record["promptId"])
        await self.report()
        outputs = await self.comfy.execute(
            graph,
            record,
            self.save,
            lambda fraction, prompt_id: self.progress(
                int((index + fraction) / count * 90), "executing", prompt_id
            ),
            report_stage=report_stage,
            timeout_seconds=self.config.execution_timeout_seconds,
        )
        record["outputs"] = outputs
        self._progressed()

    async def _run_execution(self, index: int, uploaded: dict[str, str]) -> None:
        """执行并回传第 `index` 次运行，平台确认清单后推进本机序号。"""
        state = self._current()
        task = self._job()["task"]
        count = task["executionCount"]
        record = state.setdefault("runs", {}).setdefault(
            str(index),
            {"promptId": str(uuid4()), "clientId": str(uuid4()), "phase": "prepared"},
        )
        if "outputs" not in record:
            await self._generate_outputs(index, uploaded, record)

        self.progress(int((index + 0.95) / count * 90), "uploading", record["promptId"])
        await self.report()
        await self._task_request(f"executions/{index}/start", {"promptId": record["promptId"]})
        client_ids = await self._upload_outputs(
            task["id"], state["leaseSecret"], index, record, self._progressed
        )
        manifest: dict[str, list[str] | str] = {"clientIds": client_ids}
        if effective_prompt := record.get("effectivePrompt"):
            manifest["effectivePrompt"] = effective_prompt
        await self._task_request(f"executions/{index}/complete", manifest)
        # 平台确认清单后才推进本机序号。断连重试时可根据原编号确认同一组结果。
        state["index"] = index + 1
        state.pop("promptId", None)
        record["phase"] = "done"
        record.pop("outputs", None)
        record.pop("uploadedClientIds", None)
        self._progressed()

    async def process(self) -> None:
        """从已领取的 `job` 和保存的执行序号继续，完成后向平台确认结果。

        工作流错误由主循环记录并回报。网络中断时保留执行记录，供重连后继续处理。
        """
        state = self._current()
        job = self._job()
        task_id = job["task"]["id"]
        count = job["task"]["executionCount"]
        uploaded: dict[str, str] | None = None
        if state.get("index", 0) < count:
            # The final manifest may have committed before the journal advanced.
            if state.get("runs") and (await self.report())["status"] == "succeeded":
                state["index"] = count
                logger.info("任务完成", task_id=task_id)
                return
            execution_seeds = job.get("executionSeeds")
            recovery_window = job.get("recoveryWindowSeconds")
            if (
                not isinstance(execution_seeds, list)
                or len(execution_seeds) != count
                or type(recovery_window) is not int
                or recovery_window <= 0
            ):
                raise WorkflowError("平台返回的任务数据不完整")
        for index in range(state.get("index", 0), count):
            record = state.get("runs", {}).get(str(index))
            if uploaded is None and (record is None or "outputs" not in record):
                await self.refresh_inventory()
                uploaded = await self._transfer_assets(job)
            with logger.contextualize(execution_index=index):
                await self._run_execution(index, uploaded or {})
        state["finishing"] = True
        self.save()
        await self._task_request("complete")
        logger.info("任务完成", task_id=task_id)

    def _remember_recovery(self) -> None:
        """保留未交付的原 prompt，供任务结算后核对或补传。"""
        state = self.state or {}
        job = state.get("job", {})
        window = job.get("recoveryWindowSeconds")
        index = state.get("index", 0)
        record = state.get("runs", {}).get(str(index))
        if type(window) is not int or window <= 0 or record is None:
            return
        task_id = str(UUID(job["task"]["id"]))
        pending = RecoveryRecord(
            taskId=task_id,
            leaseSecret=self._current()["leaseSecret"],
            index=index,
            expiresAt=time.time() + window,
            run=record,
        )
        self.recovery_dir.mkdir(exist_ok=True, mode=0o700)
        write_json(self.recovery_dir / f"{task_id}.json", pending)

    async def _recover(self, path: Path, pending: RecoveryRecord) -> bool:
        record = pending["run"]
        prompt_id = record["promptId"]
        if "outputs" not in record and record["phase"] != "prepared":
            history = await self.comfy.history(prompt_id)
            if not history:
                return False
            try:
                record["outputs"] = completed_outputs(history, record)
            except WorkflowError:
                # ComfyUI has a terminal history without a complete result.
                pass
        index = pending["index"]
        task_id = pending["taskId"]
        lease = pending["leaseSecret"]
        base = f"tasks/{task_id}/executions/{index}"
        body = {"promptId": prompt_id, "outcome": "outputs" if record.get("outputs") else "missing"}
        response = await self.platform.request(base + "/recovery", body, method="PUT", lease=lease)
        if not isinstance(response, dict):
            raise PlatformError(502, "平台补传响应无效")
        if response.get("action") == "done":
            return True
        if response.get("action") != "upload" or not isinstance(response.get("clientIds"), list):
            raise PlatformError(502, "平台补传响应无效")
        # The platform is authoritative even if an earlier receipt was lost.
        record["uploadedClientIds"] = response["clientIds"]

        def save() -> None:
            write_json(path, pending)

        save()
        try:
            client_ids = await self._upload_outputs(
                task_id, lease, index, record, save, recovering=True
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 404:
                raise
            body["outcome"] = "missing"
            await self.platform.request(base + "/recovery", body, method="PUT", lease=lease)
            return True
        manifest: dict[str, str | list[str]] = {"clientIds": client_ids}
        if effective_prompt := record.get("effectivePrompt"):
            manifest["effectivePrompt"] = effective_prompt
        await self.platform.request(
            base + "/complete", manifest, lease=lease, headers={RECOVERY_HEADER: "1"}
        )
        return True

    async def _recover_pending(self) -> None:
        for path in self.recovery_dir.glob("*.json"):
            try:
                pending = cast(RecoveryRecord, json.loads(path.read_text()))
                done = pending["expiresAt"] <= time.time() or await self._recover(path, pending)
            except PlatformError as error:
                done = error.status in {401, 404, 409}
                if not done:
                    logger.warning("执行补传稍后重试", http_status=error.status)
            except httpx.HTTPError:
                logger.warning("执行补传等待连接恢复")
                done = False
            except (KeyError, OSError, TypeError, ValueError):
                logger.exception("无法读取或保存待补传记录")
                done = False
            if done:
                path.unlink(missing_ok=True)

    async def _recovery_loop(self) -> None:
        while True:
            try:
                await self._recover_pending()
            except Exception:
                logger.exception("无法核对待补传的执行")
            await asyncio.sleep(10)

    async def _connect(self) -> bool:
        """等待 ComfyUI 和平台都可用并同步节点目录。密钥无效时返回假。"""
        # ComfyUI custom-node imports happen before its HTTP server is ready.
        while True:
            try:
                await self.refresh_inventory()
            except PlatformError as error:
                if error.status == 401:
                    logger.error("工作机密钥无效。请在平台重置密钥，下载新配置后重新启动。")
                    return False
                self.startup_issue = "platform_connection"
                logger.warning(
                    "平台连接失败，请核对 serverUrl 和工作机版本", http_status=error.status
                )
            except (httpx.TransportError, httpx.HTTPStatusError) as error:
                if error.request.url.path.endswith(("/object_info", "/system_stats")):
                    logger.warning("无法读取 ComfyUI 节点。请启动 ComfyUI 并核对 comfyUrl。")
                    self.comfy_status = "unreachable"
                    self.startup_issue = "comfy_connection"
                else:
                    self.startup_issue = "platform_connection"
                    logger.warning("无法连接平台。请核对 serverUrl 和工作机的网络连接。")
            except ValueError:
                self.comfy_status = "unreachable"
                self.startup_issue = "comfy_inventory"
                logger.warning("无法读取服务响应。请核对 serverUrl 和 comfyUrl。")
            else:
                self.startup_issue = None
                return True
            if not await self._publish_health():
                return False
            await asyncio.sleep(5)

    async def _acquire(self) -> _Cycle | None:
        """确保本地记录里有已领取的任务。已有任务返回 `None`，否则说明这一轮为何没有任务。

        领取编号和租约凭据先写入日志再发出请求，重启后重试的是同一次领取。
        """
        if not self.state:
            if not await self._comfy_idle():
                return _Cycle.BUSY
            self.state = {"claimId": str(uuid4()), "leaseSecret": secrets.token_urlsafe(32)}
            self.save()
        if not self.state.get("job"):
            job = await self.platform.claim(self.state["claimId"], self.state["leaseSecret"])
            if not job:
                self.state = None
                self.journal.clear()
                return _Cycle.EMPTY
            self.state["job"] = job
            self.save()
        return None

    async def _work(self) -> None:
        """处理已领取的任务。确定的失败写入日志并回报，暂时性故障向上传播以便重试。"""
        state = self._current()
        if not state.get("failure"):
            try:
                self.active = asyncio.create_task(self.process())
                await self.active
            except WorkflowError as error:
                logger.error("任务未完成", error_type=type(error).__name__)
                state["failure"] = str(error)[:2000]
                self.save()
            except PlatformError as error:
                # 平台暂时出错（5xx、代理返回的网页）交给主循环重试，受重试时限约束。
                if error.status in {401, 404, 409} or error.status >= 500:
                    raise
                state["failure"] = str(error)[:2000]
                self.save()
            except httpx.HTTPStatusError as error:
                if error.response.status_code >= 500:
                    raise
                state["failure"] = f"ComfyUI 请求失败 ({error.response.status_code})"
                self.save()
            except httpx.TransportError:
                raise
            except Exception as error:
                # 未预料的错误不重试同一份任务，避免反复消耗 GPU；工作机继续接下一单。
                logger.exception("处理任务时出错")
                state["failure"] = f"工作机处理任务时出错（{type(error).__name__}）"
                self.save()
        failure = state.get("failure")
        if failure:
            # 回报失败期间继续续租：回报重试较久时，租约过期会把真实原因换成「连接中断」。
            await self._task_request("fail", {"error": failure})

    async def _cycle(self) -> _Cycle:
        """领取并处理一个任务，把各类中断归为一种循环结果。"""
        try:
            waiting = await self._acquire()
            if waiting:
                return waiting
            with logger.contextualize(task_id=self._job()["task"]["id"]):
                await self._work()
        except asyncio.CancelledError:
            # Never issue ComfyUI's global interrupt on a shared machine.
            caller = asyncio.current_task()
            if caller and caller.cancelling():
                raise
            if self.authorization_lost:
                return _Cycle.STOP
            if not self.lease_lost:
                raise
        except (TimeoutError, httpx.TransportError):
            logger.warning("连接中断，保留执行记录后重连")
            return _Cycle.RETRY
        except httpx.HTTPStatusError as error:
            logger.warning("ComfyUI 请求失败，稍后重试", http_status=error.response.status_code)
            return _Cycle.RETRY
        except PlatformError as error:
            if error.status == 401:
                logger.error("工作机密钥已失效")
                return _Cycle.STOP
            if error.status not in {404, 409}:
                logger.warning(
                    "平台请求失败，稍后重试", http_status=error.status, error_code=error.code
                )
                return _Cycle.RETRY
            self.stop_requested = error.code == TASK_CANCELLED
            logger.warning(
                "任务已被停止" if self.stop_requested else "任务租约已失效，停止当前任务"
            )
        except Exception:
            logger.exception("工作机出错，稍后重试")
            return _Cycle.RETRY
        return _Cycle.FINISHED

    def _progressed(self) -> None:
        """保存已经确认的新进展，重试从头计时。

        生成过程中进度每向前一步，`progress` 同样清除重试记录。
        """
        self._current().pop("retry", None)
        self.save()

    def _retry_delay(self) -> float:
        """记录一次暂时性故障并返回等待秒数，等待按次数加倍，最长 60 秒。

        已领取的任务持续出错、期间没有任何进展超过 `RETRY_LIMIT_SECONDS` 时记为失败，下一轮
        回报平台并释放工作机。任务心跳期间租约一直有效，没有这个时限会无限重试。还没领到
        任务时（例如平台拒绝领取请求）同样逐次加倍等待。
        """
        state = self.state
        if not state or not state.get("job"):
            self.idle_failures += 1
            return min(60.0, self.config.poll_seconds * 2 ** (self.idle_failures - 1))
        index = state.get("index", 0)
        record = state.get("retry")
        if record is None or record["index"] != index:
            record = RetryRecord(since=time.time(), index=index, count=0)
        record["count"] += 1
        state["retry"] = record
        if not state.get("failure") and time.time() - record["since"] >= RETRY_LIMIT_SECONDS:
            logger.error("任务持续出错，停止重试")
            state["failure"] = "平台或 ComfyUI 持续出错，已停止重试，请检查工作机后重新提交"
        self.save()
        return min(60.0, 3.0 * 2 ** (record["count"] - 1))

    async def _stop_prompt(self) -> None:
        """用户停止任务后，让 ComfyUI 停下本工作机为它提交的 prompt。

        租约过期等其他情况不调用这里，共用同一台 ComfyUI 的其他任务不受影响。
        """
        prompt_id = (self.state or {}).get("promptId")
        if not prompt_id:
            return
        try:
            if await self.comfy.stop(prompt_id):
                logger.info("已停止 ComfyUI 中的任务", prompt_id=prompt_id)
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError):
            logger.warning("无法停止 ComfyUI 中的任务，它会自行结束")

    async def run(self, *, once: bool = False) -> int | None:
        """持有状态目录的独占锁并轮询平台。`once` 在一次领取及其处理结束后退出。

        目录已被另一个进程使用时抛出 `filelock.Timeout`。任务租约失效后清理本地跟踪，
        工作机密钥失效时结束主循环。
        """
        lock = FileLock(str(self.config.state_dir / "worker.lock"))
        lock.acquire(timeout=0)
        heartbeat = None
        recovery = None
        try:
            if not await self._connect():
                return
            if self.control and self.control.trial:
                await self.control.wait_for_activation()
                if not await self._connect():
                    return
            logger.info("工作机已连接", device=self.capabilities.get("device", ""))
            heartbeat = asyncio.create_task(self.heartbeats())
            if not once:
                recovery = asyncio.create_task(self._recovery_loop())
            while not self.authorization_lost:
                if not once and self.control and self.update_id and self.state is None:
                    self.control.request_update(self.update_id)
                    return UPDATE_EXIT
                outcome = await self._cycle()
                if outcome is _Cycle.STOP:
                    return
                if outcome is _Cycle.RETRY:
                    await asyncio.sleep(self._retry_delay())
                    continue
                self.idle_failures = 0
                if outcome is _Cycle.FINISHED:
                    if self.stop_requested:
                        await self._stop_prompt()
                    self._remember_recovery()
                    self.active = None
                    self.lease_lost = False
                    self.stop_requested = False
                    self.journal.clear()
                    self.state = None
                    if once:
                        return
                else:
                    if once and outcome is _Cycle.EMPTY:
                        return
                    await asyncio.sleep(self.config.poll_seconds)
        finally:
            for background in (heartbeat, recovery):
                if background:
                    background.cancel()
                    with suppress(asyncio.CancelledError):
                        await background
            await self.platform.close()
            await self.comfy.close()
            lock.release()
