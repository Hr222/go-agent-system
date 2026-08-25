from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from time import monotonic, sleep

from app.shared.config import LlmProviderConfig
from app.shared.logging import get_logger

logger = get_logger("app.infrastructure.llm.request_governance")

_ASYNC_SLOT_POLL_SECONDS = 0.05
_shared_governors_lock = threading.Lock()
_shared_governors: dict[LlmProviderConfig, "LlmRequestGovernor"] = {}


class LlmRequestGovernor:
    """当前进程内共享的 OpenAI-compatible Provider 请求治理器。"""

    def __init__(
        self,
        provider_config: LlmProviderConfig,
        *,
        clock: Callable[[], float] = monotonic,
        sleep_fn: Callable[[float], None] = sleep,
        async_sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._provider_config = provider_config
        self._config = provider_config.request_governance
        self._clock = clock
        self._sleep = sleep_fn
        self._async_sleep = async_sleep_fn
        self._token_lock = threading.Lock()
        self._tokens = float(self._config.burst)
        self._last_refill = clock()
        self._slots = threading.BoundedSemaphore(self._config.max_concurrency)

    @contextmanager
    def attempt(self) -> Iterator[None]:
        """为一次同步 Provider 请求取得并在退出时归还并发租约。"""

        self._acquire_slot_sync()
        try:
            self._acquire_token_sync()
            yield
        finally:
            self._slots.release()

    @asynccontextmanager
    async def async_attempt(self) -> AsyncIterator[None]:
        """为一次异步 Provider 请求取得可取消的并发租约。"""

        await self._acquire_slot_async()
        try:
            await self._acquire_token_async()
            yield
        finally:
            self._slots.release()

    def _acquire_slot_sync(self) -> None:
        started = self._clock()
        self._slots.acquire()
        self._log_wait("concurrency", started)

    async def _acquire_slot_async(self) -> None:
        started = self._clock()
        while not self._slots.acquire(blocking=False):
            await self._async_sleep(_ASYNC_SLOT_POLL_SECONDS)
        self._log_wait("concurrency", started)

    def _acquire_token_sync(self) -> None:
        started = self._clock()
        while True:
            delay = self._take_token_or_delay()
            if delay is None:
                self._log_wait("rate", started)
                return
            self._sleep(delay)

    async def _acquire_token_async(self) -> None:
        started = self._clock()
        while True:
            delay = self._take_token_or_delay()
            if delay is None:
                self._log_wait("rate", started)
                return
            await self._async_sleep(delay)

    def _take_token_or_delay(self) -> float | None:
        with self._token_lock:
            now = self._clock()
            elapsed = max(0.0, now - self._last_refill)
            self._tokens = min(
                float(self._config.burst),
                self._tokens
                + elapsed * (self._config.requests_per_minute / 60.0),
            )
            self._last_refill = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return None
            return (1.0 - self._tokens) / (self._config.requests_per_minute / 60.0)

    def _log_wait(self, stage: str, started: float) -> None:
        waited_ms = max(0.0, (self._clock() - started) * 1000)
        if waited_ms <= 0:
            return
        logger.info(
            "llm request governance wait provider=%s runtime_profile=%s stage=%s "
            "waited_ms=%.1f requests_per_minute=%.3f burst=%s max_concurrency=%s",
            self._provider_config.provider,
            self._provider_config.runtime_profile or "none",
            stage,
            waited_ms,
            self._config.requests_per_minute,
            self._config.burst,
            self._config.max_concurrency,
        )


def shared_request_governor(provider_config: LlmProviderConfig) -> LlmRequestGovernor:
    """返回同一有效 Provider 配置在本进程内共享的治理器。"""

    with _shared_governors_lock:
        governor = _shared_governors.get(provider_config)
        if governor is None:
            governor = LlmRequestGovernor(provider_config)
            _shared_governors[provider_config] = governor
        return governor
