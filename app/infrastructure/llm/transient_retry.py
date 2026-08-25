from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic, sleep
from typing import TypeVar

import httpx
from openai import APIConnectionError, APITimeoutError

from app.shared.config import LlmRetryConfig, Settings, settings
from app.shared.logging import get_logger

logger = get_logger("app.infrastructure.llm.transient_retry")

ResultT = TypeVar("ResultT")


@dataclass(frozen=True, slots=True)
class LlmFailureClassification:
    """上游失败的安全分类结果，不保留可能包含输入内容的异常文本。"""

    category: str
    retryable: bool
    status_code: int | None = None
    retry_after_seconds: float | None = None


def classify_llm_failure(error: BaseException) -> LlmFailureClassification:
    """仅识别已知的短暂上游故障；未知异常保守地不重试。"""

    status_code = _status_code(error)
    if status_code is not None:
        if status_code in (408, 429) or 500 <= status_code <= 599:
            return LlmFailureClassification(
                category=f"http_{status_code}",
                retryable=True,
                status_code=status_code,
                retry_after_seconds=(
                    _retry_after_seconds(error) if status_code == 429 else None
                ),
            )
        return LlmFailureClassification(
            category=f"http_{status_code}",
            retryable=False,
            status_code=status_code,
        )
    if isinstance(error, (APITimeoutError, httpx.TimeoutException, TimeoutError)):
        return LlmFailureClassification(category="timeout", retryable=True)
    if isinstance(
        error,
        (APIConnectionError, httpx.TransportError, ConnectionError, OSError),
    ):
        return LlmFailureClassification(category="connection", retryable=True)
    return LlmFailureClassification(category="unknown", retryable=False)


class LlmTransientRetryPolicy:
    """OpenAI-compatible LLM 的唯一应用级瞬态失败重试入口。"""

    def __init__(
        self,
        *,
        provider: str,
        configuration: Settings = settings,
        sleep_fn: Callable[[float], None] = sleep,
        async_sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_fn: Callable[[], float] = random.random,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._provider = provider
        self._config = configuration.llm_retry_config
        self._sleep = sleep_fn
        self._async_sleep = async_sleep_fn
        self._random = random_fn
        self._clock = clock

    def execute(self, operation: Callable[[], ResultT]) -> ResultT:
        """执行同步 Provider 调用，并只在可恢复失败后重试。"""

        session = self.new_session()
        for attempt in range(1, self._config.max_attempts + 1):
            try:
                return operation()
            except Exception as error:
                if not session.retry_after_failure(error, attempt=attempt):
                    raise
        raise RuntimeError("LLM 重试循环在未返回结果时结束。")

    @property
    def max_attempts(self) -> int:
        return self._config.max_attempts

    def new_session(self) -> "LlmTransientRetrySession":
        """为一项同步或流式 Provider 调用创建独立的重试预算。"""

        return LlmTransientRetrySession(
            provider=self._provider,
            config=self._config,
            sleep_fn=self._sleep,
            async_sleep_fn=self._async_sleep,
            random_fn=self._random,
            clock=self._clock,
        )


class LlmTransientRetrySession:
    """维护单次 LLM 调用的尝试次数与累计退避预算。"""

    def __init__(
        self,
        *,
        provider: str,
        config: LlmRetryConfig,
        sleep_fn: Callable[[float], None],
        async_sleep_fn: Callable[[float], Awaitable[None]],
        random_fn: Callable[[], float],
        clock: Callable[[], float],
    ) -> None:
        self._provider = provider
        self._config = config
        self._sleep = sleep_fn
        self._async_sleep = async_sleep_fn
        self._random = random_fn
        self._clock = clock
        self._started_at = clock()
        self._waited_seconds = 0.0

    def retry_after_failure(self, error: BaseException, *, attempt: int) -> bool:
        """决定并执行一次同步重试等待。"""

        delay = self._retry_delay(error, attempt=attempt)
        if delay is None:
            return False
        self._sleep(delay)
        self._waited_seconds += delay
        return True

    async def retry_after_async_failure(
        self,
        error: BaseException,
        *,
        attempt: int,
    ) -> bool:
        """决定并执行一次异步重试等待。"""

        delay = self._retry_delay(error, attempt=attempt)
        if delay is None:
            return False
        await self._async_sleep(delay)
        self._waited_seconds += delay
        return True

    def _retry_delay(self, error: BaseException, *, attempt: int) -> float | None:
        classification = classify_llm_failure(error)
        elapsed_ms = max(0.0, (self._clock() - self._started_at) * 1000)
        if not classification.retryable:
            _log_retry_stop(
                provider=self._provider,
                attempt=attempt,
                classification=classification,
                reason="non_retryable",
                waited_seconds=self._waited_seconds,
                elapsed_ms=elapsed_ms,
            )
            return None
        if attempt >= self._config.max_attempts:
            _log_retry_stop(
                provider=self._provider,
                attempt=attempt,
                classification=classification,
                reason="attempts_exhausted",
                waited_seconds=self._waited_seconds,
                elapsed_ms=elapsed_ms,
            )
            return None

        delay = self._delay_for(classification, attempt=attempt)
        if self._waited_seconds + delay > self._config.total_backoff_budget_seconds:
            _log_retry_stop(
                provider=self._provider,
                attempt=attempt,
                classification=classification,
                reason="backoff_budget_exhausted",
                waited_seconds=self._waited_seconds,
                elapsed_ms=elapsed_ms,
            )
            return None

        logger.info(
            "llm retry scheduled provider=%s attempt=%s category=%s status_code=%s "
            "delay_seconds=%.3f waited_seconds=%.3f elapsed_ms=%.1f",
            self._provider,
            attempt,
            classification.category,
            classification.status_code,
            delay,
            self._waited_seconds,
            elapsed_ms,
        )
        return delay

    def _delay_for(self, classification: LlmFailureClassification, *, attempt: int) -> float:
        if classification.retry_after_seconds is not None:
            return min(
                classification.retry_after_seconds,
                self._config.max_retry_after_seconds,
            )

        base_delay = min(
            self._config.max_backoff_seconds,
            self._config.base_backoff_seconds * (2 ** (attempt - 1)),
        )
        jitter = base_delay * max(0.0, min(1.0, self._random())) * 0.25
        return min(self._config.max_backoff_seconds, base_delay + jitter)


def _status_code(error: BaseException) -> int | None:
    value = getattr(error, "status_code", None)
    if isinstance(value, int):
        return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _retry_after_seconds(error: BaseException) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    value = getter("retry-after")
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def _log_retry_stop(
    *,
    provider: str,
    attempt: int,
    classification: LlmFailureClassification,
    reason: str,
    waited_seconds: float,
    elapsed_ms: float,
) -> None:
    logger.warning(
        "llm retry stopped provider=%s attempt=%s category=%s status_code=%s reason=%s "
        "waited_seconds=%.3f elapsed_ms=%.1f",
        provider,
        attempt,
        classification.category,
        classification.status_code,
        reason,
        waited_seconds,
        elapsed_ms,
    )


__all__ = [
    "LlmFailureClassification",
    "LlmTransientRetryPolicy",
    "LlmTransientRetrySession",
    "classify_llm_failure",
]
