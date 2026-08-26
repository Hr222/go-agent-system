from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError

from app.infrastructure.llm import llm_client
from app.infrastructure.llm.llm_client import RagAnswerGenerator
from app.infrastructure.llm.request_governance import LlmRequestGovernor
from app.infrastructure.llm.transient_retry import LlmTransientRetryPolicy
from app.platform.knowledge.ports.read_port import KnowledgeSearchHit
from app.shared.config import Settings


class FakeCompletions:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="基于证据的回答。"))]
        )


class FlakyCompletions(FakeCompletions):
    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        self.attempts += 1
        if self.attempts == 1:
            request = httpx.Request("POST", "https://provider.example.com/v1/chat/completions")
            raise APITimeoutError(request=request)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="基于证据的回答。"))]
        )


class RecordingGovernor(LlmRequestGovernor):
    def __init__(self, configuration: Settings) -> None:
        super().__init__(configuration.llm_provider_config())
        self.attempt_count = 0

    @contextmanager
    def attempt(self):  # type: ignore[override]
        self.attempt_count += 1
        with super().attempt():
            yield


def _hit() -> KnowledgeSearchHit:
    return KnowledgeSearchHit(
        document_id=1,
        version_id=2,
        chunk_id=3,
        policy_name="测试制度",
        policy_category="测试分类",
        responsible_department=None,
        version_label="现行",
        section_title="第一条",
        section_path="第一条",
        page_no=1,
        chunk_text="测试证据。",
        score=1.0,
        rank=1,
        retrieval_source="hybrid",
    )


def test_rag_answer_generator_uses_selected_glm_profile_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = Settings(
        _env_file=None,
        zhipu_resource_chat_model="glm-resource-test",
        zhipu_resource_thinking="disabled",
    )
    monkeypatch.setattr(llm_client, "settings", configuration)
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    generator = RagAnswerGenerator(client=client)

    result = generator.answer(query="测试问题", hits=[_hit()])

    assert result.answer == "基于证据的回答。"
    assert completions.kwargs is not None
    assert completions.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_rag_answer_generator_retries_transient_completion_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = Settings(
        _env_file=None,
        zhipu_resource_chat_model="glm-resource-test",
        llm_retry_base_backoff_seconds=0.01,
    )
    monkeypatch.setattr(llm_client, "settings", configuration)
    completions = FlakyCompletions()
    waits: list[float] = []
    governor = RecordingGovernor(configuration)
    generator = RagAnswerGenerator(
        client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
        retry_policy=LlmTransientRetryPolicy(
            provider="glm",
            configuration=configuration,
            sleep_fn=waits.append,
            random_fn=lambda: 0.0,
            clock=lambda: 1.0,
        ),
        request_governor=governor,
    )

    result = generator.answer(query="测试问题", hits=[_hit()])

    assert result.answer == "基于证据的回答。"
    assert completions.attempts == 2
    assert governor.attempt_count == 2
    assert waits == [0.01]
