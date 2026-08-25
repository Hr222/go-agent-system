from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.llm.request_governance import LlmRequestGovernor
from app.shared.config import Settings


def _configuration(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "zhipu_resource_requests_per_minute": 60.0,
        "zhipu_resource_request_burst": 1,
        "zhipu_resource_request_max_concurrency": 1,
    }
    values.update(overrides)
    return Settings(**values)


def test_governor_allows_configured_burst_then_waits_for_refill() -> None:
    now = [0.0]
    waits: list[float] = []
    config = _configuration(zhipu_resource_request_burst=2)
    governor = LlmRequestGovernor(
        config.llm_provider_config(),
        clock=lambda: now[0],
        sleep_fn=lambda delay: (waits.append(delay), now.__setitem__(0, now[0] + delay)),
    )

    with governor.attempt():
        pass
    with governor.attempt():
        pass
    with governor.attempt():
        pass

    assert waits == [1.0]


def test_governor_releases_sync_slot_after_provider_failure() -> None:
    config = _configuration()
    governor = LlmRequestGovernor(config.llm_provider_config())

    with pytest.raises(RuntimeError):
        with governor.attempt():
            raise RuntimeError("provider failure")

    with governor.attempt():
        pass


def test_governor_async_wait_is_cancelled_without_leaking_slot() -> None:
    async def scenario() -> None:
        config = _configuration()
        governor = LlmRequestGovernor(
            config.llm_provider_config(),
            async_sleep_fn=lambda _delay: asyncio.sleep(0.01),
        )
        first_entered = asyncio.Event()
        release_first = asyncio.Event()

        async def first() -> None:
            async with governor.async_attempt():
                first_entered.set()
                await release_first.wait()

        first_task = asyncio.create_task(first())
        await first_entered.wait()
        waiting = asyncio.create_task(_hold_attempt(governor))
        await asyncio.sleep(0.02)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        release_first.set()
        await first_task

        async with governor.async_attempt():
            pass

    asyncio.run(scenario())


async def _hold_attempt(governor: LlmRequestGovernor) -> None:
    async with governor.async_attempt():
        await asyncio.sleep(1)
