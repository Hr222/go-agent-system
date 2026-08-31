from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import create_engine, make_url, select

from app.composition import root as composition_root
from app.composition.conversation import build_conversation_history_read_service
from app.infrastructure.persistence.models.conversation import ConversationMessageRecord
from app.platform.conversation.application import (
    CharacterCountContextMessageCostEstimator,
    ConversationContextBuilder,
)
from app.platform.conversation.domain import ContextBudget, ContextPolicy, MessageRole
from app.platform.dialogue.application import (
    ConversationTurnCoordinator,
    StreamingConversationCommand,
    StreamingConversationRuntime,
    ThreadedStreamingConversationPersistence,
)
from app.platform.llm.contracts import ChatLlmStreamChunk
from app.platform.security.domain.principal import RequestPrincipal
from app.shared.config import settings
from tests.support.db_test_utils import SchemaHarness


class OneChunkStreamingLlm:
    def stream(self, request: object) -> AsyncIterator[ChatLlmStreamChunk]:
        del request

        async def chunks() -> AsyncIterator[ChatLlmStreamChunk]:
            yield ChatLlmStreamChunk(content="真实数据库回答")

        return chunks()


def _require_postgres() -> None:
    database_url = make_url(settings.database_url)
    engine = create_engine(
        settings.database_url,
        connect_args={"connect_timeout": 2},
        pool_pre_ping=True,
    )
    try:
        with engine.connect():
            return
    except Exception as error:  # noqa: BLE001 - test must explain unavailable infrastructure
        endpoint = f"{database_url.host or 'unknown'}:{database_url.port or 'default'}"
        pytest.skip(
            f"PostgreSQL 集成测试未运行：无法连接配置的数据库 {endpoint} "
            f"（{type(error).__name__}）。"
        )
    finally:
        engine.dispose()


def test_streaming_runtime_uses_independent_postgres_sessions(monkeypatch) -> None:  # noqa: ANN001
    _require_postgres()
    harness = SchemaHarness("streaming_conversation_postgres")
    harness.create_schema()
    try:
        monkeypatch.setattr(composition_root, "SessionLocal", harness.session_local)
        persistence = ThreadedStreamingConversationPersistence(
            composition_root._SessionScopedStreamingConversationPersistenceWorkerFactory()
        )
        runtime = StreamingConversationRuntime(
            conversation_persistence=persistence,
            context_builder=ConversationContextBuilder(
                CharacterCountContextMessageCostEstimator()
            ),
            llm=OneChunkStreamingLlm(),  # type: ignore[arg-type]
            conversation_turn_coordinator=ConversationTurnCoordinator(),
            context_policy=ContextPolicy(max_messages=20),
            context_budget=ContextBudget(max_cost=12_000),
        )

        async def scenario() -> None:
            stream = await runtime.execute(
                StreamingConversationCommand(
                    principal=RequestPrincipal(subject="user-1", authenticated=True),
                    message="真实数据库问题",
                )
            )
            [event async for event in stream]

        asyncio.run(scenario())

        session = harness.session_local()
        try:
            messages = session.scalars(
                select(ConversationMessageRecord).order_by(
                    ConversationMessageRecord.sequence.asc()
                )
            ).all()
            assert [record.role for record in messages] == [
                MessageRole.USER.value,
                MessageRole.ASSISTANT.value,
            ]
            assert [record.content for record in messages] == [
                "真实数据库问题",
                "真实数据库回答",
            ]
            assert build_conversation_history_read_service(session).read_history(
                conversation_id=messages[0].conversation_id,
                limit=20,
            ).messages[-1].sequence == 2
        finally:
            session.close()
    finally:
        harness.drop_schema()
