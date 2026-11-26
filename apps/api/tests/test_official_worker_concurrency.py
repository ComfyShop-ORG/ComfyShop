import asyncio
import json
import sys
from contextlib import asynccontextmanager, nullcontext

import httpx
import pytest
from official_test_support import asset, image_bytes, submit, worker_client
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_official_workflows import SEEDREAM, upload

from comfyshop_api.models import Execution, Task
from comfyshop_official_worker import __main__ as cli
from comfyshop_official_worker.atlas_cloud import (
    ATLAS_ROOT,
    SUBMISSION_UNKNOWN,
    Atlas,
    InlineOutput,
)
from comfyshop_official_worker.runner import Runner


@pytest.mark.parametrize("inline", [False, True])
def test_official_worker_enforces_the_claimed_artifact_limit(
    official, settings, monkeypatch, inline
):
    settings.max_artifact_bytes = 1024
    content = b"0" * (settings.max_artifact_bytes + 1)
    workflow = upload(official, SEEDREAM)
    reference = asset(official, image_bytes("white"))
    task = submit(official, workflow, {"prompt": "测试", "reference_1": {"assetId": reference}})

    def provider(request):
        if request.url.path.endswith("/uploadMedia"):
            return httpx.Response(200, json={"url": "https://cdn.example/reference.png"})
        assert request.method == "POST"
        return httpx.Response(200, json={"data": {"id": "result"}})

    async def outputs(*_, **_options):
        return [InlineOutput(content, ".png") if inline else "https://cdn.example/result.png"]

    async def run():
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=content))
            ) as downloads,
        ):
            worker = Runner(platform, Atlas(atlas), downloads)
            monkeypatch.setattr(worker.atlas, "outputs", outputs)
            assert await worker.run_once()

    asyncio.run(run())
    progress = official.get(f"/api/v1/tasks/{task['id']}/progress").raise_for_status().json()
    assert progress["status"] == "failed" and progress["error"] == "文件超过工作机允许的大小"


def test_official_worker_refills_a_free_slot_while_another_task_is_running(official, settings):
    settings.worker_lease_seconds = 10
    workflow = upload(official, SEEDREAM)
    reference = asset(official, image_bytes("white"))
    task_ids = {
        color: submit(official, workflow, {"prompt": color, "reference_1": {"assetId": reference}})[
            "id"
        ]
        for color in ("red", "blue", "green", "yellow")
    }

    def status(color):
        return (
            official.get(f"/api/v1/tasks/{task_ids[color]}/progress")
            .raise_for_status()
            .json()["status"]
        )

    async def run():
        polling = {color: asyncio.Event() for color in task_ids}
        release = {color: asyncio.Event() for color in task_ids}
        renewed = {task_id: asyncio.Event() for task_id in task_ids.values()}
        completed = {task_id: asyncio.Event() for task_id in task_ids.values()}
        submissions = []
        interrupted = set()

        async def provider(request):
            if request.url.path.endswith("/uploadMedia"):
                return httpx.Response(200, json={"url": "https://cdn.example/reference.png"})
            if request.method == "POST":
                color = json.loads(request.content)["prompt"]
                submissions.append(color)
                return httpx.Response(200, json={"data": {"id": color}})
            color = request.url.path.rsplit("/", 1)[-1]
            polling[color].set()
            try:
                await release[color].wait()
            except asyncio.CancelledError:
                interrupted.add(color)
                raise
            return httpx.Response(
                200,
                json={
                    "data": {"status": "completed", "outputs": [f"https://cdn.example/{color}.png"]}
                },
            )

        def download(request):
            color = request.url.path.removeprefix("/").removesuffix(".png")
            return httpx.Response(
                200, content=image_bytes(color), headers={"Content-Type": "image/png"}
            )

        async def track_response(response):
            path = response.request.url.path.split("/")
            if response.is_success and path[-1] == "heartbeat":
                renewed[path[-2]].set()
            if response.is_success and path[-1] == "complete":
                completed[path[-4]].set()

        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(download)) as downloads,
            asyncio.timeout(20),
        ):
            platform.client.event_hooks["response"].append(track_response)
            worker = asyncio.create_task(
                Runner(platform, Atlas(atlas), downloads, max_concurrency=2).run()
            )
            try:
                await asyncio.gather(polling["red"].wait(), polling["blue"].wait())
                await asyncio.gather(
                    renewed[task_ids["red"]].wait(), renewed[task_ids["blue"]].wait()
                )
                assert [status(color) for color in task_ids] == [
                    "running",
                    "running",
                    "queued",
                    "queued",
                ]
                official.post(f"/api/v1/tasks/{task_ids['blue']}/cancel").raise_for_status()
                await polling["green"].wait()
                assert [status(color) for color in task_ids] == [
                    "running",
                    "cancelled",
                    "running",
                    "queued",
                ]
                release["green"].set()
                await completed[task_ids["green"]].wait()
                await polling["yellow"].wait()
                assert status("red") == "running"
                release["red"].set()
                await completed[task_ids["red"]].wait()
            finally:
                worker.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await worker
        assert sorted(submissions) == sorted(task_ids)
        assert interrupted == {"blue", "yellow"}

    asyncio.run(run())
    for color in ("red", "green"):
        artifacts = official.get("/api/v1/artifacts", params={"task_id": task_ids[color]}).json()[
            "items"
        ]
        assert len(artifacts) == 1
        assert official.get(artifacts[0]["media"]["src"]).content == image_bytes(color)


@pytest.fixture
def submit_batch(official):
    workflow = upload(official, SEEDREAM)
    reference = asset(official, image_bytes("white"))

    def create(prompt, count):
        return submit(
            official,
            workflow,
            {"prompt": prompt, "reference_1": {"assetId": reference}},
            execution_count=count,
        )["id"]

    return create


def prediction_ids(official, task_id):
    with Session(official.app.state.engine) as db:
        return dict(
            db.execute(
                select(Execution.index, Execution.prompt_id).where(Execution.task_id == task_id)
            ).all()
        )


class BatchAtlas:
    """由测试逐个结束预测，平台端使用真实租约、执行行和媒体存储。"""

    def __init__(self):
        self.replies = {}
        self.polls = asyncio.Queue()
        self.completions = asyncio.Queue()
        self.failures = asyncio.Queue()
        self.heartbeats = asyncio.Queue()
        self.in_flight = 0
        self.peak = 0

    async def provider(self, request):
        if request.url.path.endswith("/uploadMedia"):
            return httpx.Response(200, json={"url": "https://cdn.example/reference.png"})
        if request.method == "POST":
            prompt = json.loads(request.content)["prompt"]
            prediction = f"{prompt}-{len(self.replies) + 1}"
            self.replies[prediction] = asyncio.get_running_loop().create_future()
            return httpx.Response(200, json={"data": {"id": prediction}})
        prediction = request.url.path.rsplit("/", 1)[-1]
        self.polls.put_nowait(prediction)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            status = await asyncio.shield(self.replies[prediction])
            return httpx.Response(
                200,
                json={
                    "data": {
                        "status": status,
                        "outputs": [f"https://cdn.example/{prediction}.png"],
                    }
                },
            )
        finally:
            self.in_flight -= 1

    def image(self, prediction):
        return image_bytes((int(prediction.rsplit("-", 1)[-1]), 0, 0))

    def download(self, request):
        prediction = request.url.path.strip("/").removesuffix(".png")
        return httpx.Response(
            200, content=self.image(prediction), headers={"Content-Type": "image/png"}
        )

    async def record(self, response):
        path = response.request.url.path.split("/")
        if response.is_success and path[-1] == "complete" and path[-3] == "executions":
            self.completions.put_nowait((path[-4], int(path[-2])))
        if response.is_success and path[-1] == "fail" and path[-3] == "executions":
            self.failures.put_nowait((path[-4], int(path[-2])))
        if response.is_success and path[-1] == "heartbeat":
            self.heartbeats.put_nowait((path[-2], json.loads(response.request.content)))

    @asynccontextmanager
    async def worker(self, official, limit):
        async with (
            worker_client(official) as platform,
            httpx.AsyncClient(
                base_url=ATLAS_ROOT, transport=httpx.MockTransport(self.provider)
            ) as atlas,
            httpx.AsyncClient(transport=httpx.MockTransport(self.download)) as downloads,
        ):
            platform.client.event_hooks["response"].append(self.record)
            yield Runner(platform, Atlas(atlas), downloads, max_concurrency=limit)


def test_batch_and_other_task_share_execution_capacity(official, settings, submit_batch):
    settings.worker_lease_seconds = 10
    batch, other = submit_batch("batch", 4), submit_batch("other", 1)
    model = BatchAtlas()

    async def run():
        async with asyncio.timeout(20), model.worker(official, 3) as worker:
            serving = asyncio.create_task(worker.run())
            try:
                first = [await model.polls.get() for _ in range(3)]
                assert sorted(p.split("-")[0] for p in first) == ["batch", "batch", "other"]
                ids = prediction_ids(official, batch)
                assert ids[2] is None and ids[3] is None
                model.replies[ids[1]].set_result("completed")
                assert await model.completions.get() == (batch, 1)
                assert (await model.polls.get()).startswith("batch-")
                while True:
                    task_id, heartbeat = await model.heartbeats.get()
                    if task_id == batch and heartbeat["progress"] > 0:
                        assert heartbeat["progress"] == 25 and heartbeat["executionIndex"] in (0, 2)
                        break
                model.replies[ids[0]].set_result("completed")
                assert await model.completions.get() == (batch, 0)
                assert (await model.polls.get()).startswith("batch-")
                ids = prediction_ids(official, batch)
                model.replies[ids[3]].set_result("completed")
                model.replies[ids[2]].set_result("completed")
                model.replies[prediction_ids(official, other)[0]].set_result("completed")
                assert {await model.completions.get() for _ in range(3)} == {
                    (batch, 3),
                    (batch, 2),
                    (other, 0),
                }
            finally:
                serving.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await serving

    asyncio.run(run())
    assert model.peak == 3 and len(model.replies) == 5
    for task_id in (batch, other):
        progress = official.get(f"/api/v1/tasks/{task_id}/progress").raise_for_status().json()
        assert progress["status"] == "succeeded" and progress["progress"] == 100
        ids = prediction_ids(official, task_id)
        runs = official.get("/api/v1/executions", params={"task_id": task_id}).json()["items"]
        assert len(runs) == len(ids)
        for item in runs:
            assert official.get(item["media"]["src"]).content == model.image(ids[item["index"]])


def test_parallel_failures_drain_submitted_siblings_and_preserve_retryability(
    official, submit_batch
):
    task_id = submit_batch("batch", 5)
    model = BatchAtlas()

    async def run():
        async with asyncio.timeout(15):
            async with model.worker(official, 3) as worker:
                task = asyncio.create_task(worker.run_once())
                for _ in range(3):
                    await model.polls.get()
                ids = prediction_ids(official, task_id)
                model.replies[ids[0]].set_result("failed")
                model.replies[ids[1]].set_result("failed")
                assert {await model.failures.get() for _ in range(2)} == {
                    (task_id, 0),
                    (task_id, 1),
                }
                progress = (
                    official.get(f"/api/v1/tasks/{task_id}/progress").raise_for_status().json()
                )
                assert progress["status"] == "running"
                assert [e["status"] for e in progress["executions"]] == [
                    "failed",
                    "failed",
                    "running",
                    "queued",
                    "queued",
                ]
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            with Session(official.app.state.engine) as db:
                db.get(Task, task_id).lease_expires_at = 0
                db.commit()
            async with model.worker(official, 3) as successor:
                task = asyncio.create_task(successor.run_once())
                assert await model.polls.get() == ids[2]
                model.replies[ids[2]].set_result("completed")
                assert await task

    asyncio.run(run())
    assert len(model.replies) == 3
    progress = official.get(f"/api/v1/tasks/{task_id}/progress").raise_for_status().json()
    assert progress["status"] == "failed"
    assert [(e["status"], e["recovery"]) for e in progress["executions"]] == [
        ("failed", "rerunnable"),
        ("failed", "rerunnable"),
        ("succeeded", None),
        ("failed", "rerunnable"),
        ("failed", "rerunnable"),
    ]


def test_parallel_lease_takeover_resumes_known_predictions_and_fences_unknown_submission(
    official, submit_batch
):
    task_id = submit_batch("batch", 5)
    model = BatchAtlas()

    async def run():
        async with asyncio.timeout(15):
            async with model.worker(official, 2) as first:
                task = asyncio.create_task(first.run_once())
                for _ in range(2):
                    await model.polls.get()
                ids = prediction_ids(official, task_id)
                model.replies[ids[1]].set_result("completed")
                assert await model.completions.get() == (task_id, 1)
                await model.polls.get()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            with Session(official.app.state.engine) as db:
                db.get(Task, task_id).lease_expires_at = 0
                db.scalar(
                    select(Execution).where(Execution.task_id == task_id, Execution.index == 3)
                ).submission_pending = True
                db.commit()
            async with model.worker(official, 1) as successor:
                task = asyncio.create_task(successor.run_once())
                ids = prediction_ids(official, task_id)
                for index in (0, 2):
                    assert await model.polls.get() == ids[index]
                    model.replies[ids[index]].set_result("completed")
                assert await task

    asyncio.run(run())
    assert len(model.replies) == 3
    progress = (
        official.get(f"/api/v1/tasks/{task_id}/progress?include_takeover_history=true")
        .raise_for_status()
        .json()
    )
    assert progress["status"] == "failed" and progress["error"] == SUBMISSION_UNKNOWN
    assert [wait["outcome"] for wait in progress["takeoverHistory"]["waits"]] == ["resumed"]
    assert [(e["status"], e["recovery"]) for e in progress["executions"]] == [
        ("succeeded", None),
        ("succeeded", None),
        ("succeeded", None),
        ("failed", "unverified"),
        ("failed", "rerunnable"),
    ]


def test_failed_batch_skips_model_submission_for_sibling_still_preparing_media(
    official, submit_batch
):
    task_id = submit_batch("batch", 3)
    model = BatchAtlas()

    async def run():
        preparing, resume = asyncio.Event(), asyncio.Event()
        uploads = 0
        provider = model.provider

        async def slow_upload(request):
            nonlocal uploads
            if request.url.path.endswith("/uploadMedia"):
                uploads += 1
                if uploads == 2:
                    preparing.set()
                    await resume.wait()
            return await provider(request)

        model.provider = slow_upload
        async with asyncio.timeout(15), model.worker(official, 2) as worker:
            task = asyncio.create_task(worker.run_once())
            await preparing.wait()
            prediction = await model.polls.get()
            model.replies[prediction].set_result("failed")
            assert (await model.failures.get())[0] == task_id
            resume.set()
            assert await task

    asyncio.run(run())
    assert len(model.replies) == 1
    progress = official.get(f"/api/v1/tasks/{task_id}/progress").raise_for_status().json()
    assert [e["recovery"] for e in progress["executions"]] == ["rerunnable"] * 3


@pytest.mark.parametrize(
    ("environment", "arguments", "expected"),
    [
        (None, [], 4),
        ("", [], 4),
        ("1", [], 1),
        ("2", ["--max-concurrency", "8"], 8),
        ("0", [], None),
        ("bad", [], None),
    ],
)
def test_official_worker_startup_concurrency(monkeypatch, environment, arguments, expected):
    observed = []

    async def observe(worker):
        observed.append(worker.max_concurrency)

    monkeypatch.setattr(Runner, "run", observe)
    monkeypatch.setattr(cli, "worker_logging", lambda kind: nullcontext("INFO"))
    monkeypatch.setattr(sys, "argv", ["comfyshop-official-worker", "run", *arguments])
    monkeypatch.setenv("COMFYSHOP_WORKER_SERVICE_TOKENS__OFFICIAL", "test-token")
    monkeypatch.setenv("ATLAS_CLOUD_API_KEY", "test-provider-key")
    if environment is None:
        monkeypatch.delenv("COMFYSHOP_OFFICIAL_WORKER_MAX_CONCURRENCY", raising=False)
    else:
        monkeypatch.setenv("COMFYSHOP_OFFICIAL_WORKER_MAX_CONCURRENCY", environment)
    if expected is None:
        with pytest.raises(SystemExit) as error:
            cli.main()
        assert error.value.code != 0 and not observed
    else:
        cli.main()
        assert observed == [expected]
