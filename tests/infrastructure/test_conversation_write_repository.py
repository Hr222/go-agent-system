from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.composition.conversation import build_conversation_write_service
from app.infrastructure.persistence.models.conversation import (
    ConversationEventRecord,
    ConversationMessageRecord,
    ConversationRecord,
)
from app.infrastructure.persistence.repositories.conversation_event_repository import (
    ConversationEventRepository,
)
from app.infrastructure.persistence.repositories.conversation_write_repository import (
    ConversationWriteRepository,
)
from app.modules.conversation.domain import ConversationEvent, MessageRole
from app.modules.conversation.errors import ConversationNotFoundError
from tests.support.db_test_utils import SchemaHarness


def test_repository_creates_and_appends_messages_in_order() -> None:
    harness = SchemaHarness("conversation_write")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            service = build_conversation_write_service(session)
            conversation = service.create_conversation(owner_subject="user-1")
            created_updated_at = conversation.updated_at

            first = service.append_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="  第一条  ",
            )
            second = service.append_message(
                conversation_id=conversation.id,
                role="assistant",
                content="第二条",
            )

            assert first.sequence == 1
            assert first.content == "  第一条  "
            assert second.sequence == 2
            assert second.role is MessageRole.ASSISTANT
            assert session.scalar(
                select(func.count(ConversationMessageRecord.id)).where(
                    ConversationMessageRecord.conversation_id == conversation.id
                )
            ) == 2

            persisted_conversation = session.get(ConversationRecord, conversation.id)
            assert persisted_conversation is not None
            assert persisted_conversation.topic_summary == "第一条"
            assert persisted_conversation.updated_at >= created_updated_at
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_manual_topic_summary_is_preserved_on_follow_up_messages() -> None:
    harness = SchemaHarness("conversation_topic_write")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            service = build_conversation_write_service(session)
            conversation = service.create_conversation(owner_subject="user-1")
            service.append_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="首条消息",
            )
            service.update_topic_summary(
                conversation_id=conversation.id,
                topic_summary="人工修正标题",
            )
            service.append_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="后续消息",
            )

            persisted = session.get(ConversationRecord, conversation.id)
            assert persisted is not None
            assert persisted.topic_summary == "人工修正标题"
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_repository_rejects_missing_conversation_without_message() -> None:
    harness = SchemaHarness("conversation_write_missing")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            repository = ConversationWriteRepository(session)
            with pytest.raises(ConversationNotFoundError, match="会话不存在"):
                repository.append_message(
                    conversation_id=uuid4(),
                    role=MessageRole.USER,
                    content="不会写入",
                )

            assert session.scalar(select(func.count(ConversationMessageRecord.id))) == 0
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_repository_rolls_back_when_flush_fails() -> None:
    harness = SchemaHarness("conversation_write_rollback")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            service = build_conversation_write_service(session)
            conversation = service.create_conversation(owner_subject="user-1")
            persisted_before = session.get(ConversationRecord, conversation.id)
            assert persisted_before is not None
            updated_before = persisted_before.updated_at

            repository = ConversationWriteRepository(session)
            with patch.object(session, "flush", side_effect=RuntimeError("模拟写入失败")):
                with pytest.raises(RuntimeError, match="模拟写入失败"):
                    repository.append_message(
                        conversation_id=conversation.id,
                        role=MessageRole.USER,
                        content="不会留下",
                    )

            session.expire_all()
            assert session.scalar(select(func.count(ConversationMessageRecord.id))) == 0
            persisted_after = session.get(ConversationRecord, conversation.id)
            assert persisted_after is not None
            assert persisted_after.updated_at == updated_before
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_repository_deletes_conversation_and_cascades_messages_and_events() -> None:
    harness = SchemaHarness("conversation_delete_cascade")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            service = build_conversation_write_service(session)
            conversation = service.create_conversation(owner_subject="user-1")
            service.append_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="待删除消息",
            )
            event = ConversationEvent(
                conversation_id=conversation.id,
                event_type="agent_call",
                call_id="delete-call",
                capability_code="agent.tender.generate_bid_skeleton",
                sequence=1,
                payload={"status": "requested"},
            )
            ConversationEventRepository(session).save_event(event)

            ConversationWriteRepository(session).delete_conversation(
                conversation_id=conversation.id,
            )

            session.expire_all()
            assert session.get(ConversationRecord, conversation.id) is None
            assert session.scalar(
                select(func.count(ConversationMessageRecord.id)).where(
                    ConversationMessageRecord.conversation_id == conversation.id
                )
            ) == 0
            assert session.scalar(
                select(func.count(ConversationEventRecord.id)).where(
                    ConversationEventRecord.conversation_id == conversation.id
                )
            ) == 0
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_repository_rolls_back_failed_conversation_delete() -> None:
    harness = SchemaHarness("conversation_delete_rollback")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            service = build_conversation_write_service(session)
            conversation = service.create_conversation(owner_subject="user-1")
            service.append_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="保留消息",
            )
            event = ConversationEvent(
                conversation_id=conversation.id,
                event_type="agent_result",
                call_id="rollback-call",
                capability_code="agent.tender.generate_bid_skeleton",
                sequence=1,
                payload={"status": "completed"},
            )
            ConversationEventRepository(session).save_event(event)

            repository = ConversationWriteRepository(session)
            with patch.object(session, "commit", side_effect=RuntimeError("模拟删除失败")):
                with pytest.raises(RuntimeError, match="模拟删除失败"):
                    repository.delete_conversation(conversation_id=conversation.id)

            session.expire_all()
            assert session.get(ConversationRecord, conversation.id) is not None
            assert session.scalar(
                select(func.count(ConversationMessageRecord.id)).where(
                    ConversationMessageRecord.conversation_id == conversation.id
                )
            ) == 1
            assert session.scalar(
                select(func.count(ConversationEventRecord.id)).where(
                    ConversationEventRecord.conversation_id == conversation.id
                )
            ) == 1
        finally:
            session.close()
    finally:
        harness.drop_schema()


def _append_in_thread(harness: SchemaHarness, conversation_id) -> int:  # noqa: ANN001
    session = harness.session_local()
    try:
        service = build_conversation_write_service(session)
        return service.append_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content="并发消息",
        ).sequence
    finally:
        session.close()


def test_concurrent_appends_use_unique_consecutive_sequences() -> None:
    harness = SchemaHarness("conversation_write_concurrent")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            conversation = build_conversation_write_service(session).create_conversation(
                owner_subject="user-1"
            )
        finally:
            session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(_append_in_thread, harness, conversation.id)
                for _ in range(2)
            ]
            sequences = sorted(future.result(timeout=30) for future in futures)

        assert sequences == [1, 2]
    finally:
        harness.drop_schema()
