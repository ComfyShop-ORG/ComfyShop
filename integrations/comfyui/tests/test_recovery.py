import asyncio
from uuid import uuid4

import httpx
import pytest

from comfyshop_worker.comfy import Comfy
from comfyshop_worker.config import Config, Journal
from comfyshop_worker.graph import WorkflowError
from comfyshop_worker.platform import PlatformError
from comfyshop_worker.runner import Runner


def test_rejected_key_stops_startup(monkeypatch, tmp_path, caplog):
    async def verify():
        api_key = "private-test-key"
        runner = Runner(Config("http://platform.test", "http://comfy.test", api_key, tmp_path))

        async def refresh_inventory():
            raise PlatformError(401, api_key)

        monkeypatch.setattr(runner, "refresh_inventory", refresh_inventory)
        await asyncio.wait_for(runner.run(), timeout=3)
        assert runner.platform.client.is_closed and runner.comfy.client.is_closed
        assert "下载新配置" in caplog.text
        assert api_key not in caplog.text

    asyncio.run(verify())


def test_expired_task_lease_allows_next_claim(monkeypatch, tmp_path):
    async def verify():
        runner = Runner(Config("http://platform.test", "http://comfy.test", "test-key", tmp_path))
        first_started = asyncio.Event()
        first_stopped = asyncio.Event()
        next_processed = asyncio.Event()
        claims = []
        machine_heartbeats = 0

        async def inventory():
            return {}, {}

        async def idle():
            if claims:
                assert first_stopped.is_set() and runner.journal.read() is None
            if len(claims) == 2:
                await asyncio.Future()
            return True

        async def request(path, body=None, **_options):
            nonlocal machine_heartbeats
            if path == "catalog":
                return {}
            if path == "heartbeat":
                machine_heartbeats += 1
                if machine_heartbeats > 1:
                    await first_started.wait()
                return {}
            if path == "claim":
                task_id = "expired" if not claims else "next"
                claims.append(body)
                return {"task": {"id": task_id, "executionCount": 1}}
            if path == "tasks/expired/heartbeat":
                raise PlatformError(409, "任务租约已失效")
            raise AssertionError(path)

        async def process():
            if runner.state["job"]["task"]["id"] == "expired":
                first_started.set()
                try:
                    await asyncio.Future()
                finally:
                    first_stopped.set()
            else:
                next_processed.set()

        monkeypatch.setattr(runner.comfy, "inventory", inventory)
        monkeypatch.setattr(runner.comfy, "idle", idle)
        monkeypatch.setattr(runner.platform, "request", request)
        monkeypatch.setattr(runner, "process", process)
        running = asyncio.create_task(runner.run())
        next_task = asyncio.create_task(next_processed.wait())
        try:
            done, _ = await asyncio.wait(
                {running, next_task}, timeout=3, return_when=asyncio.FIRST_COMPLETED
            )
            if running in done:
                await running
            assert next_task in done
            assert [claim["protocolVersion"] for claim in claims] == [3, 3]
            assert claims[0]["claimId"] != claims[1]["claimId"]
            assert claims[0]["leaseSecret"] != claims[1]["leaseSecret"]
        finally:
            running.cancel()
            next_task.cancel()
            await asyncio.gather(running, next_task, return_exceptions=True)

    asyncio.run(verify())


def test_restarted_worker_recognizes_already_committed_task(monkeypatch, tmp_path):
    journal = Journal(tmp_path)
    journal.save(
        {
            "leaseSecret": "persisted-lease",
            "job": {"task": {"id": "completed", "executionCount": 1}, "assets": [{"id": "asset"}]},
            "runs": {"0": {"phase": "submitted", "promptId": "persisted-prompt"}},
        }
    )

    async def verify():
        runner = Runner(Config("http://platform.test", "http://comfy.test", "test-key", tmp_path))
        reports = []

        async def inventory():
            return {}, {}

        async def request(path, body=None, **options):
            if path in {"catalog", "heartbeat"}:
                return {}
            assert path == "tasks/completed/heartbeat"
            assert options["lease"] == "persisted-lease"
            reports.append(body)
            return {"status": "succeeded"}

        async def unexpected(*_args, **_kwargs):
            raise AssertionError("completed tasks must not repeat transfer or inference")

        monkeypatch.setattr(runner.comfy, "inventory", inventory)
        monkeypatch.setattr(runner.comfy, "execute", unexpected)
        monkeypatch.setattr(runner.platform, "download_asset", unexpected)
        monkeypatch.setattr(runner.platform, "request", request)
        await asyncio.wait_for(runner.run(once=True), timeout=3)
        assert reports and all(report["executionIndex"] == 0 for report in reports)
        assert journal.read() is None

    asyncio.run(verify())


def test_connection_loss_keeps_the_claim_and_resumes_the_same_task(monkeypatch, tmp_path):
    async def verify():
        runner = Runner(Config("http://platform.test", "http://comfy.test", "test-key", tmp_path))
        claims = []
        attempts = []

        async def inventory():
            return {}, {}

        async def idle():
            return True

        async def request(path, body=None, **_options):
            if path == "claim":
                claims.append(body)
                return {"task": {"id": "kept", "executionCount": 1}}
            return {}

        async def process():
            attempts.append(runner.journal.read())
            if len(attempts) == 1:
                raise httpx.ConnectError("platform unreachable")

        async def no_wait(_seconds):
            return None

        monkeypatch.setattr(runner.comfy, "inventory", inventory)
        monkeypatch.setattr(runner.comfy, "idle", idle)
        monkeypatch.setattr(runner.platform, "request", request)
        monkeypatch.setattr(runner, "process", process)
        monkeypatch.setattr(runner, "heartbeats", lambda: asyncio.sleep(0))
        monkeypatch.setattr("comfyshop_worker.runner.asyncio.sleep", no_wait)
        await asyncio.wait_for(runner.run(once=True), timeout=3)
        assert len(claims) == 1
        assert [attempt["job"]["task"]["id"] for attempt in attempts] == ["kept", "kept"]
        assert attempts[0]["claimId"] == attempts[1]["claimId"]
        assert runner.journal.read() is None

    asyncio.run(verify())


def test_ambiguous_submission_is_never_automatically_resubmitted():
    async def verify():
        posts = []

        def handle(request):
            if request.method == "POST":
                posts.append(request)
            return httpx.Response(
                200,
                json={"queue_running": [], "queue_pending": []}
                if request.url.path == "/queue"
                else {},
            )

        comfy = Comfy("http://comfy")
        await comfy.client.aclose()
        comfy.client = httpx.AsyncClient(
            base_url="http://comfy/", transport=httpx.MockTransport(handle)
        )
        record = {"promptId": str(uuid4()), "clientId": str(uuid4()), "phase": "submitting"}
        try:
            with pytest.raises(WorkflowError, match="未重复执行"):
                await comfy.execute({}, record, lambda: None, lambda *_: None)
            assert posts == []
        finally:
            await comfy.close()

    asyncio.run(verify())


def test_lost_submit_response_resumes_history_without_second_inference(monkeypatch):
    async def verify():
        submitted = 0
        prompt_id = str(uuid4())

        class Socket:
            closed = False

            async def close(self):
                self.closed = True

        socket = Socket()

        async def connect(*_args, **_kwargs):
            return socket

        monkeypatch.setattr("comfyshop_worker.comfy.connect", connect)

        def handle(request):
            nonlocal submitted
            if request.method == "POST":
                submitted += 1
                raise httpx.ReadTimeout("reply lost", request=request)
            if request.url.path.startswith("/history/"):
                return httpx.Response(
                    200,
                    json={
                        prompt_id: {
                            "status": {"completed": True, "status_str": "success"},
                            "outputs": {
                                "save": {
                                    "images": [
                                        {"filename": "real.png", "type": "output", "subfolder": ""}
                                    ]
                                }
                            },
                        }
                    },
                )
            raise AssertionError(str(request.url))

        comfy = Comfy("http://comfy")
        await comfy.client.aclose()
        comfy.client = httpx.AsyncClient(
            base_url="http://comfy/", transport=httpx.MockTransport(handle)
        )
        record = {"promptId": prompt_id, "clientId": str(uuid4()), "phase": "prepared"}
        phases = []
        try:
            files = await comfy.execute(
                {}, record, lambda: phases.append(record["phase"]), lambda *_: None
            )
            assert submitted == 1
            assert files[0]["filename"] == "real.png"
            assert phases == ["prepared", "submitting", "submitted"]
            assert socket.closed
        finally:
            await comfy.close()

    asyncio.run(verify())


def test_missing_submitted_job_fails_without_resubmission(monkeypatch):
    async def verify():
        posts = []

        class Socket:
            closed = False

            async def close(self):
                self.closed = True

        socket = Socket()

        async def connect(*args, **kwargs):
            return socket

        monkeypatch.setattr("comfyshop_worker.comfy.connect", connect)

        def handle(request):
            if request.method == "POST":
                posts.append(request)
            return httpx.Response(200, json={"queue_running": [], "queue_pending": []})

        comfy = Comfy("http://comfy", missing_grace_seconds=0)
        await comfy.client.aclose()
        comfy.client = httpx.AsyncClient(
            base_url="http://comfy/", transport=httpx.MockTransport(handle)
        )
        record = {"promptId": "missing", "clientId": "client", "phase": "submitted"}
        try:
            with pytest.raises(WorkflowError, match="已无此任务"):
                await comfy.execute({}, record, lambda: None, lambda *_: None)
            assert not posts and socket.closed
        finally:
            await comfy.close()

    asyncio.run(verify())


def test_execution_deadline_survives_restart_and_bounds_waiting(monkeypatch):
    import time

    async def verify():
        comfy = Comfy("http://comfy")
        calls = []

        async def waiting(*args):
            calls.append(True)
            await asyncio.Future()

        monkeypatch.setattr(comfy, "_execute", waiting)
        try:
            record = {"startedAt": time.time() - 60}
            with pytest.raises(WorkflowError, match="时间限制"):
                await comfy.execute({}, record, lambda: None, lambda *_: None, timeout_seconds=1)
            assert not calls
            with pytest.raises(WorkflowError, match="时间限制"):
                await comfy.execute({}, {}, lambda: None, lambda *_: None, timeout_seconds=0.01)
            assert calls == [True]
        finally:
            await comfy.close()

    asyncio.run(verify())


def test_user_stop_interrupts_only_this_workers_prompt(monkeypatch, tmp_path):
    async def verify():
        runner = Runner(Config("http://platform.test", "http://comfy.test", "test-key", tmp_path))
        started = asyncio.Event()
        stopped: list[str] = []
        claims = []

        async def inventory():
            return {}, {}

        async def idle():
            if claims:
                await asyncio.Future()
            return True

        async def request(path, body=None, **_options):
            if path in {"catalog", "heartbeat"}:
                if path == "heartbeat" and claims:
                    await started.wait()
                return {}
            if path == "claim":
                claims.append(body)
                return {"task": {"id": "stopped", "executionCount": 1}}
            if path == "tasks/stopped/heartbeat":
                raise PlatformError(409, "任务已取消")
            raise AssertionError(path)

        async def process():
            runner.state["promptId"] = "prompt-of-this-worker"
            started.set()
            await asyncio.Future()

        async def stop(prompt_id):
            stopped.append(prompt_id)
            return True

        monkeypatch.setattr(runner.comfy, "inventory", inventory)
        monkeypatch.setattr(runner.comfy, "idle", idle)
        monkeypatch.setattr(runner.comfy, "stop", stop)
        monkeypatch.setattr(runner.platform, "request", request)
        monkeypatch.setattr(runner, "process", process)
        running = asyncio.create_task(runner.run())
        try:
            for _ in range(300):
                if stopped:
                    break
                await asyncio.sleep(0.01)
            assert stopped == ["prompt-of-this-worker"]
            assert runner.journal.read() is None
        finally:
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)

    asyncio.run(verify())


def test_stop_leaves_other_queue_entries_alone():
    async def verify():
        calls = []

        def handler(request):
            calls.append((request.method, request.url.path, request.content))
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "queue_running": [[1, "someone-else", {}]],
                        "queue_pending": [[2, "mine", {}]],
                    },
                )
            return httpx.Response(200, json={})

        comfy = Comfy("http://comfy.test")
        comfy.client = httpx.AsyncClient(
            base_url="http://comfy.test/", transport=httpx.MockTransport(handler)
        )
        try:
            assert await comfy.stop("mine") is True
            assert calls[-1][:2] == ("POST", "/queue") and b"mine" in calls[-1][2]
            assert await comfy.stop("finished-earlier") is False
            assert not any(path == "/interrupt" for _, path, _ in calls)
        finally:
            await comfy.close()

    asyncio.run(verify())


def test_persistent_errors_end_the_task_instead_of_retrying_forever(monkeypatch, tmp_path):
    from comfyshop_worker import runner as module

    runner = Runner(Config("http://platform.test", "http://comfy.test", "test-key", tmp_path))
    runner.state = {
        "claimId": "claim",
        "leaseSecret": "lease",
        "job": {"task": {"id": "stuck", "executionCount": 2}},
    }
    clock = [1000.0]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    assert [runner._retry_delay() for _ in range(6)] == [3, 6, 12, 24, 48, 60]
    assert "failure" not in runner.state
    # 推进到下一次执行时重新计时，只有同一次执行持续出错才放弃。
    clock[0] += module.RETRY_LIMIT_SECONDS
    runner.state["index"] = 1
    assert runner._retry_delay() == 3 and "failure" not in runner.state
    clock[0] += module.RETRY_LIMIT_SECONDS
    runner._retry_delay()
    assert "持续出错" in runner.state["failure"]
    assert runner.journal.read()["failure"] == runner.state["failure"]


def test_an_unexpected_error_fails_only_the_current_task(monkeypatch, tmp_path):
    runner = Runner(Config("http://platform.test", "http://comfy.test", "test-key", tmp_path))
    runner.state = {
        "claimId": "claim",
        "leaseSecret": "lease",
        "job": {"task": {"id": "broken", "executionCount": 1}},
    }
    reported = []

    async def process():
        raise KeyError("prompt_id")

    async def task_request(path, body=None):
        reported.append((path, body))

    monkeypatch.setattr(runner, "process", process)
    monkeypatch.setattr(runner, "_task_request", task_request)
    asyncio.run(runner._work())
    assert reported == [("fail", {"error": "工作机处理任务时出错（KeyError）"})]


def test_a_timed_out_execution_stops_only_its_own_prompt(monkeypatch):
    async def verify():
        comfy = Comfy("http://comfy")
        stopped = []

        async def submitted_then_stuck(_graph, record, *_args):
            record["phase"] = "submitted"
            await asyncio.Future()

        async def stop(prompt_id):
            stopped.append(prompt_id)
            return True

        monkeypatch.setattr(comfy, "_execute", submitted_then_stuck)
        monkeypatch.setattr(comfy, "stop", stop)
        try:
            record = {"promptId": "mine", "clientId": "client", "phase": "prepared"}
            with pytest.raises(WorkflowError, match="时间限制"):
                await comfy.execute({}, record, lambda: None, lambda *_: None, timeout_seconds=0.01)
            assert stopped == ["mine"]
            # 还没提交给 ComfyUI 的执行没有可停的 prompt。
            idle = {"promptId": "never-sent", "clientId": "client", "phase": "prepared"}
            with pytest.raises(WorkflowError, match="时间限制"):
                await comfy.execute({}, {**idle, "startedAt": 0}, lambda: None, lambda *_: None)
            assert stopped == ["mine"]
        finally:
            await comfy.close()

    asyncio.run(verify())


def test_a_platform_outage_mid_task_is_retried_not_failed(monkeypatch, tmp_path):
    runner = Runner(Config("http://platform.test", "http://comfy.test", "test-key", tmp_path))
    runner.state = {
        "claimId": "claim",
        "leaseSecret": "lease",
        "job": {"task": {"id": "busy", "executionCount": 1}},
    }
    reported = []

    async def process():
        raise PlatformError(502, "平台响应无法解析")

    async def task_request(path, body=None):
        reported.append(path)

    monkeypatch.setattr(runner, "process", process)
    monkeypatch.setattr(runner, "_task_request", task_request)
    # 平台重启时反向代理返回 502：保留记录等平台恢复，不把跑完的结果判为失败。
    assert asyncio.run(runner._cycle()).name == "RETRY"
    assert reported == [] and "failure" not in runner.state


def test_progress_restarts_the_retry_clock(monkeypatch, tmp_path):
    from comfyshop_worker import runner as module

    runner = Runner(Config("http://platform.test", "http://comfy.test", "test-key", tmp_path))
    runner.state = {
        "claimId": "claim",
        "leaseSecret": "lease",
        "job": {"task": {"id": "long", "executionCount": 1}},
    }
    clock = [1000.0]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    runner._retry_delay()
    runner._progressed()
    # 开头短暂断网一次，20 分钟后上传时再断一次，不算持续出错。
    clock[0] += 20 * 60
    assert runner._retry_delay() == 3
    assert "failure" not in runner.state


def test_generation_progress_restarts_the_retry_clock(monkeypatch, tmp_path):
    from comfyshop_worker import runner as module

    runner = Runner(Config("http://platform.test", "http://comfy.test", "test-key", tmp_path))
    runner.state = {
        "claimId": "claim",
        "leaseSecret": "lease",
        "job": {"task": {"id": "video", "executionCount": 1}},
    }
    clock = [1000.0]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    runner._retry_delay()
    # 重连后同一次生成继续向前走，20 分钟后再断一次，不算持续出错。
    runner.progress(40, "executing")
    clock[0] += 20 * 60
    assert runner._retry_delay() == 3
    assert "failure" not in runner.state
    # 进度没有向前时计时照旧，持续出错仍会放弃。
    runner.progress(40, "executing")
    clock[0] += module.RETRY_LIMIT_SECONDS
    runner._retry_delay()
    assert "持续出错" in runner.state["failure"]
