from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

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
from app.platform.conversation.domain import Conversation, ConversationEvent, MessageRole
from app.platform.conversation.errors import (
    ConversationNotFoundError,
    ConversationPinLimitExceededError,
)
from app.platform.conversation.ports import DEFAULT_PINNED_CONVERSATION_LIMIT
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


def test_repository_limits_pins_per_owner_without_updating_recent_activity() -> None:
    harness = SchemaHarness("conversation_pin_limit")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            repository = ConversationWriteRepository(session)
            owner_conversations = [
                repository.save_conversation(Conversation(owner_subject="owner-1"))
                for _ in range(DEFAULT_PINNED_CONVERSATION_LIMIT + 1)
            ]
            other_owner = repository.save_conversation(Conversation(owner_subject="owner-2"))
            original_updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            session.execute(
                update(ConversationRecord)
                .where(
                    ConversationRecord.id.in_(
                        [conversation.id for conversation in owner_conversations] + [other_owner.id]
                    )
                )
                .values(updated_at=original_updated_at)
            )
            session.commit()

            for conversation in owner_conversations[:DEFAULT_PINNED_CONVERSATION_LIMIT]:
                pinned = repository.update_pinned(
                    conversation_id=conversation.id,
                    owner_subject="owner-1",
                    is_pinned=True,
                )
                assert pinned.updated_at == original_updated_at

            repeated = repository.update_pinned(
                conversation_id=owner_conversations[0].id,
                owner_subject="owner-1",
                is_pinned=True,
            )
            assert repeated.updated_at == original_updated_at

            with pytest.raises(ConversationPinLimitExceededError, match="最多置顶"):
                repository.update_pinned(
                    conversation_id=owner_conversations[-1].id,
                    owner_subject="owner-1",
                    is_pinned=True,
                )

            unpinned = repository.update_pinned(
                conversation_id=owner_conversations[0].id,
                owner_subject="owner-1",
                is_pinned=False,
            )
            assert unpinned.updated_at == original_updated_at
            assert unpinned.is_pinned is False

            replacement = repository.update_pinned(
                conversation_id=owner_conversations[-1].id,
                owner_subject="owner-1",
                is_pinned=True,
            )
            assert replacement.updated_at == original_updated_at
            assert replacement.is_pinned is True

            other_pinned = repository.update_pinned(
                conversation_id=other_owner.id,
                owner_subject="owner-2",
                is_pinned=True,
            )
            assert other_pinned.is_pinned is True

            session.expire_all()
            assert session.scalar(
                select(func.count(ConversationRecord.id)).where(
                    ConversationRecord.owner_subject == "owner-1",
                    ConversationRecord.is_pinned.is_(True),
                )
            ) == DEFAULT_PINNED_CONVERSATION_LIMIT
        finally:
            session.close()
    finally:
        harness.drop_schema()


def _pin_for_owner_in_thread(
    harness: SchemaHarness,
    conversation_id,
    barrier: Barrier,
) -> bool:  # noqa: ANN001
    session = harness.session_local()
    try:
        barrier.wait(timeout=10)
        ConversationWriteRepository(session).update_pinned(
            conversation_id=conversation_id,
            owner_subject="owner-1",
            is_pinned=True,
        )
        return True
    except ConversationPinLimitExceededError:
        return False
    finally:
        session.close()


def test_concurrent_pins_cannot_exceed_the_owner_limit() -> None:
    harness = SchemaHarness("conversation_pin_concurrent")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            repository = ConversationWriteRepository(session)
            conversations = [
                repository.save_conversation(Conversation(owner_subject="owner-1"))
                for _ in range(DEFAULT_PINNED_CONVERSATION_LIMIT + 1)
            ]
            for conversation in conversations[: DEFAULT_PINNED_CONVERSATION_LIMIT - 1]:
                repository.update_pinned(
                    conversation_id=conversation.id,
                    owner_subject="owner-1",
                    is_pinned=True,
                )
        finally:
            session.close()

        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(
                executor.map(
                    lambda conversation: _pin_for_owner_in_thread(
                        harness,
                        conversation.id,
                        barrier,
                    ),
                    conversations[-2:],
                )
            )

        verification_session = harness.session_local()
        try:
            pinned_count = verification_session.scalar(
                select(func.count(ConversationRecord.id)).where(
                    ConversationRecord.owner_subject == "owner-1",
                    ConversationRecord.is_pinned.is_(True),
                )
            )
            assert sorted(outcomes) == [False, True]
            assert pinned_count == DEFAULT_PINNED_CONVERSATION_LIMIT
        finally:
            verification_session.close()
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
