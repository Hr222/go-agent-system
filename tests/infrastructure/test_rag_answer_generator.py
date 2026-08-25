from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.infrastructure.llm import llm_client
from app.infrastructure.llm.llm_client import RagAnswerGenerator
from app.modules.knowledge.ports.read_port import KnowledgeSearchHit
from app.shared.config import Settings


class FakeCompletions:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="基于证据的回答。"))]
        )


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
