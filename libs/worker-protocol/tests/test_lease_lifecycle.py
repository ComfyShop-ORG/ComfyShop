import asyncio

import pytest
from comfyshop_worker_protocol.platform import PlatformError
from comfyshop_worker_protocol.service import run_with_lease


def test_lease_loss_cancels_and_drains_the_active_execution():
    async def check():
        started = asyncio.Event()
        finished = asyncio.Event()

        async def work():
            started.set()
            try:
                await asyncio.Future()
            finally:
                finished.set()

        async def heartbeat():
            await started.wait()
            raise PlatformError(409, "lease expired")

        with pytest.raises(PlatformError, match="lease expired"):
            await run_with_lease(work(), heartbeat())
        assert finished.is_set()

    asyncio.run(check())


def test_committed_result_wins_over_a_simultaneous_final_heartbeat():
    async def work():
        return None

    async def heartbeat():
        raise PlatformError(409, "lease expired")

    asyncio.run(run_with_lease(work(), heartbeat()))
