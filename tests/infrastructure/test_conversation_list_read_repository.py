from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update

from app.composition.conversation import (
    build_conversation_list_read_service,
    build_conversation_write_service,
)
from app.infrastructure.persistence.models.conversation import ConversationRecord
from app.modules.conversation.domain import Conversation, MessageRole
from tests.support.db_test_utils import SchemaHarness

CONVERSATION_ONE = UUID("00000000-0000-0000-0000-000000000211")
CONVERSATION_TWO = UUID("00000000-0000-0000-0000-000000000212")
CONVERSATION_THREE = UUID("00000000-0000-0000-0000-000000000213")
OTHER_CONVERSATION = UUID("00000000-0000-0000-0000-000000000214")


def _seed(harness: SchemaHarness) -> None:
    session = harness.session_local()
    try:
        write = build_conversation_write_service(session)
        for conversation_id, owner in (
            (CONVERSATION_ONE, "owner-1"),
            (CONVERSATION_TWO, "owner-1"),
            (CONVERSATION_THREE, "owner-1"),
            (OTHER_CONVERSATION, "owner-2"),
        ):
            conversation = write.write_port.save_conversation(  # type: ignore[attr-defined]
                Conversation(
                    id=conversation_id,
                    owner_subject=owner,
                )
            )
            if conversation_id == CONVERSATION_ONE:
                write.append_message(
                    conversation_id=conversation.id,
                    role=MessageRole.USER,
                    content="不应出现在摘要列表中",
                )

        timestamps = {
            CONVERSATION_ONE: datetime(2025, 1, 3, tzinfo=timezone.utc),
            CONVERSATION_TWO: datetime(2025, 1, 2, tzinfo=timezone.utc),
            CONVERSATION_THREE: datetime(2025, 1, 2, tzinfo=timezone.utc),
            OTHER_CONVERSATION: datetime(2025, 1, 4, tzinfo=timezone.utc),
        }
        for conversation_id, updated_at in timestamps.items():
            session.execute(
                update(ConversationRecord)
                .where(ConversationRecord.id == conversation_id)
                .values(created_at=updated_at, updated_at=updated_at)
            )
        session.commit()
    finally:
        session.close()


def test_list_repository_filters_owner_orders_and_pages_stably() -> None:
    harness = SchemaHarness("conversation_list")
    harness.create_schema()
    try:
        _seed(harness)
        session = harness.session_local()
        try:
            service = build_conversation_list_read_service(session)
            first = service.list_owned(owner_subject="owner-1", limit=2)

            assert [item.id for item in first.conversations] == [
                CONVERSATION_ONE,
                CONVERSATION_THREE,
            ]
            assert first.has_more is True
            assert first.next_cursor is not None
            assert first.next_cursor.id == CONVERSATION_THREE

            second = service.list_owned(
                owner_subject="owner-1",
                limit=2,
                cursor=first.next_cursor,
            )
            assert [item.id for item in second.conversations] == [CONVERSATION_TWO]
            assert second.has_more is False
            assert second.next_cursor is None
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_list_repository_returns_empty_page_for_owner_without_conversations() -> None:
    harness = SchemaHarness("conversation_list_empty")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            page = build_conversation_list_read_service(session).list_owned(
                owner_subject="nobody"
            )
            assert page.conversations == ()
            assert page.has_more is False
            assert page.next_cursor is None
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_list_repository_places_pinned_conversations_first_and_pages_by_pin_group() -> None:
    harness = SchemaHarness("conversation_list_pinned")
    harness.create_schema()
    try:
        _seed(harness)
        session = harness.session_local()
        try:
            session.execute(
                update(ConversationRecord)
                .where(ConversationRecord.id == CONVERSATION_THREE)
                .values(is_pinned=True)
            )
            session.commit()
            service = build_conversation_list_read_service(session)
            first = service.list_owned(owner_subject="owner-1", limit=1)
            assert [item.id for item in first.conversations] == [CONVERSATION_THREE]
            assert first.conversations[0].is_pinned is True

            second = service.list_owned(
                owner_subject="owner-1",
                limit=2,
                cursor=first.next_cursor,
            )
            assert [item.id for item in second.conversations] == [
                CONVERSATION_ONE,
                CONVERSATION_TWO,
            ]
            assert all(item.is_pinned is False for item in second.conversations)
        finally:
            session.close()
    finally:
        harness.drop_schema()
