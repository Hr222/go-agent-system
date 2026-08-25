from __future__ import annotations

import httpx
import pytest
from openai import APIStatusError, APITimeoutError
from pydantic import ValidationError

from app.infrastructure.llm.transient_retry import (
    LlmTransientRetryPolicy,
    classify_llm_failure,
)
from app.shared.config import Settings


def _configuration(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_retry_max_attempts": 2,
        "llm_retry_base_backoff_seconds": 1.0,
        "llm_retry_max_backoff_seconds": 8.0,
        "llm_retry_max_retry_after_seconds": 30.0,
        "llm_retry_total_backoff_budget_seconds": 30.0,
    }
    values.update(overrides)
    return Settings(**values)


def _status_error(status_code: int, *, retry_after: str | None = None) -> APIStatusError:
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    request = httpx.Request("POST", "https://provider.example.com/v1/chat/completions")
    response = httpx.Response(status_code, headers=headers, request=request)
    return APIStatusError("provider failure", response=response, body=None)


def _timeout_error() -> APITimeoutError:
    request = httpx.Request("POST", "https://provider.example.com/v1/chat/completions")
    return APITimeoutError(request=request)


@pytest.mark.parametrize(
    ("error", "retryable", "category"),
    [
        (_status_error(408), True, "http_408"),
        (_status_error(429), True, "http_429"),
        (_status_error(503), True, "http_503"),
        (_status_error(401), False, "http_401"),
        (_status_error(422), False, "http_422"),
        (_timeout_error(), True, "timeout"),
        (httpx.ConnectError("connection failed"), True, "connection"),
        (RuntimeError("unknown"), False, "unknown"),
    ],
)
def test_classify_llm_failure_only_retries_known_transient_failures(
    error: BaseException,
    retryable: bool,
    category: str,
) -> None:
    result = classify_llm_failure(error)

    assert result.retryable is retryable
    assert result.category == category


def test_retry_policy_retries_timeout_with_jittered_exponential_backoff() -> None:
    attempts = 0
    waits: list[float] = []
    policy = LlmTransientRetryPolicy(
        provider="glm",
        configuration=_configuration(),
        sleep_fn=waits.append,
        random_fn=lambda: 0.5,
        clock=lambda: 1.0,
    )

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _timeout_error()
        return "ok"

    assert policy.execute(operation) == "ok"
    assert attempts == 2
    assert waits == [1.125]


def test_retry_policy_prioritizes_retry_after_for_rate_limits() -> None:
    attempts = 0
    waits: list[float] = []
    policy = LlmTransientRetryPolicy(
        provider="deepseek",
        configuration=_configuration(llm_retry_max_retry_after_seconds=3.0),
        sleep_fn=waits.append,
        random_fn=lambda: 0.0,
        clock=lambda: 1.0,
    )

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _status_error(429, retry_after="7")
        return "ok"

    assert policy.execute(operation) == "ok"
    assert attempts == 2
    assert waits == [3.0]


def test_retry_policy_stops_before_request_when_backoff_budget_is_insufficient() -> None:
    attempts = 0
    waits: list[float] = []
    policy = LlmTransientRetryPolicy(
        provider="glm",
        configuration=_configuration(llm_retry_total_backoff_budget_seconds=0.5),
        sleep_fn=waits.append,
        clock=lambda: 1.0,
    )

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise _status_error(429, retry_after="1")

    with pytest.raises(APIStatusError):
        policy.execute(operation)

    assert attempts == 1
    assert waits == []


def test_retry_policy_does_not_retry_non_retryable_http_error() -> None:
    attempts = 0
    policy = LlmTransientRetryPolicy(
        provider="glm",
        configuration=_configuration(),
        sleep_fn=lambda delay: None,
        clock=lambda: 1.0,
    )

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise _status_error(401)

    with pytest.raises(APIStatusError):
        policy.execute(operation)

    assert attempts == 1


def test_retry_policy_logs_only_safe_failure_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_key = "sk-secret-key"
    prompt = "用户的私密问题"
    output = "模型私密输出"
    policy = LlmTransientRetryPolicy(
        provider="glm",
        configuration=_configuration(),
        sleep_fn=lambda delay: None,
        clock=lambda: 1.0,
    )

    with pytest.raises(APIStatusError):
        policy.execute(lambda: _raise(_status_error(401, retry_after=secret_key)))

    assert "provider=glm" in caplog.text
    assert secret_key not in caplog.text
    assert prompt not in caplog.text
    assert output not in caplog.text


def test_stream_retry_session_uses_injected_async_sleep() -> None:
    waits: list[float] = []

    async def record_sleep(delay: float) -> None:
        waits.append(delay)

    policy = LlmTransientRetryPolicy(
        provider="glm",
        configuration=_configuration(),
        async_sleep_fn=record_sleep,
        random_fn=lambda: 0.0,
        clock=lambda: 1.0,
    )

    async def scenario() -> bool:
        session = policy.new_session()
        return await session.retry_after_async_failure(_timeout_error(), attempt=1)

    import asyncio

    assert asyncio.run(scenario()) is True
    assert waits == [1.0]


def test_retry_settings_expose_bounded_policy_and_stream_first_activity_window() -> None:
    configuration = Settings(
        _env_file=None,
        llm_stream_first_token_timeout_seconds=5.0,
        llm_retry_max_attempts=3,
        llm_retry_base_backoff_seconds=1.0,
        llm_retry_max_backoff_seconds=4.0,
        llm_retry_max_retry_after_seconds=10.0,
        llm_retry_total_backoff_budget_seconds=7.0,
    )

    assert configuration.llm_retry_config.max_attempts == 3
    assert configuration.llm_retry_config.max_backoff_seconds == 4.0
    assert configuration.llm_stream_first_activity_timeout_seconds == 22.0


def test_retry_settings_reject_base_backoff_above_its_maximum() -> None:
    with pytest.raises(ValidationError, match="LLM_RETRY_BASE_BACKOFF_SECONDS"):
        Settings(
            _env_file=None,
            llm_retry_base_backoff_seconds=3.0,
            llm_retry_max_backoff_seconds=2.0,
        )


def _raise(error: BaseException) -> None:
    raise error
