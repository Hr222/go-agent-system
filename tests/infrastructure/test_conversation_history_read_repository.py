from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.dialects import postgresql

from app.composition.conversation import (
    build_conversation_history_read_service,
    build_conversation_recent_message_read_service,
    build_conversation_write_service,
)
from app.infrastructure.persistence.models.conversation import (
    ConversationMessageRecord,
    ConversationRecord,
)
from app.platform.conversation.domain import MessageRole
from app.platform.conversation.errors import ConversationNotFoundError
from tests.support.db_test_utils import SchemaHarness


def _seed_conversation(harness: SchemaHarness, count: int) -> UUID:
    session = harness.session_local()
    try:
        service = build_conversation_write_service(session)
        conversation = service.create_conversation(owner_subject="user-1")
        for index in range(count):
            service.append_message(
                conversation_id=conversation.id,
                role=MessageRole.USER if index % 2 == 0 else MessageRole.ASSISTANT,
                content=f"消息 {index + 1}",
            )
        return conversation.id
    finally:
        session.close()


def test_history_read_restores_conversation_and_ordered_messages() -> None:
    harness = SchemaHarness("conversation_history")
    harness.create_schema()
    try:
        conversation_id = _seed_conversation(harness, 3)
        session = harness.session_local()
        try:
            page = build_conversation_history_read_service(session).read_history(
                conversation_id=conversation_id,
                limit=10,
            )

            assert page.conversation.id == conversation_id
            assert [message.sequence for message in page.messages] == [1, 2, 3]
            assert [message.content for message in page.messages] == [
                "消息 1",
                "消息 2",
                "消息 3",
            ]
            assert [message.role for message in page.messages] == [
                MessageRole.USER,
                MessageRole.ASSISTANT,
                MessageRole.USER,
            ]
            assert page.has_more is False
            assert page.next_after_sequence is None
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_history_read_distinguishes_empty_conversation() -> None:
    harness = SchemaHarness("conversation_history_empty")
    harness.create_schema()
    try:
        conversation_id = _seed_conversation(harness, 0)
        session = harness.session_local()
        try:
            page = build_conversation_history_read_service(session).read_history(
                conversation_id=conversation_id
            )
            assert page.conversation.id == conversation_id
            assert page.messages == ()
            assert page.has_more is False
            assert page.next_after_sequence is None
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_history_read_rejects_missing_conversation() -> None:
    harness = SchemaHarness("conversation_history_missing")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            with pytest.raises(ConversationNotFoundError, match="会话不存在"):
                build_conversation_history_read_service(session).read_history(
                    conversation_id=uuid4()
                )
            assert session.scalar(select(func.count(ConversationRecord.id))) == 0
            assert session.scalar(select(func.count(ConversationMessageRecord.id))) == 0
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_history_cursor_pages_have_no_duplicates_and_continue_after_append() -> None:
    harness = SchemaHarness("conversation_history_cursor")
    harness.create_schema()
    try:
        conversation_id = _seed_conversation(harness, 3)
        read_session = harness.session_local()
        try:
            read_service = build_conversation_history_read_service(read_session)
            first_page = read_service.read_history(
                conversation_id=conversation_id,
                limit=2,
            )
            assert [message.sequence for message in first_page.messages] == [1, 2]
            assert first_page.has_more is True
            assert first_page.next_after_sequence == 2

            second_page = read_service.read_history(
                conversation_id=conversation_id,
                limit=2,
                after_sequence=first_page.next_after_sequence,
            )
            assert [message.sequence for message in second_page.messages] == [3]
            assert second_page.has_more is False
            assert second_page.next_after_sequence is None
        finally:
            read_session.close()

        write_session = harness.session_local()
        try:
            build_conversation_write_service(write_session).append_message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content="消息 4",
            )
        finally:
            write_session.close()

        continued_session = harness.session_local()
        try:
            continued_page = build_conversation_history_read_service(
                continued_session
            ).read_history(
                conversation_id=conversation_id,
                limit=2,
                after_sequence=3,
            )
            assert [message.sequence for message in continued_page.messages] == [4]
            assert continued_page.messages[0].content == "消息 4"
        finally:
            continued_session.close()
    finally:
        harness.drop_schema()


def test_recent_message_read_returns_bounded_ordered_snapshot() -> None:
    harness = SchemaHarness("conversation_recent_window")
    harness.create_schema()
    try:
        conversation_id = _seed_conversation(harness, 5)
        session = harness.session_local()
        try:
            window = build_conversation_recent_message_read_service(session).read_recent_messages(
                conversation_id=conversation_id,
                through_sequence=4,
                limit=2,
            )

            assert window.conversation_id == conversation_id
            assert [message.sequence for message in window.messages] == [3, 4]
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_recent_message_read_returns_empty_window_before_first_message() -> None:
    harness = SchemaHarness("conversation_recent_window_empty")
    harness.create_schema()
    try:
        conversation_id = _seed_conversation(harness, 0)
        session = harness.session_local()
        try:
            window = build_conversation_recent_message_read_service(session).read_recent_messages(
                conversation_id=conversation_id,
                through_sequence=1,
                limit=20,
            )

            assert window.messages == ()
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_recent_message_query_can_use_existing_conversation_sequence_index() -> None:
    """验证最近窗口的过滤和倒序限制具备现有唯一索引的执行依据。"""

    harness = SchemaHarness("conversation_recent_explain")
    harness.create_schema()
    try:
        conversation_id = _seed_conversation(harness, 20)
        statement = (
            select(ConversationMessageRecord)
            .where(
                ConversationMessageRecord.conversation_id == conversation_id,
                ConversationMessageRecord.sequence <= 15,
            )
            .order_by(ConversationMessageRecord.sequence.desc())
            .limit(5)
        )
        compiled = statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        with harness.test_engine.begin() as connection:
            connection.execute(text("SET LOCAL enable_seqscan = off"))
            plan = connection.execute(
                text(f"EXPLAIN (FORMAT JSON) {compiled}")
            ).scalar_one()

        plan_text = str(plan)
        assert "uq_conversation_message_conversation_sequence" in plan_text
    finally:
        harness.drop_schema()
