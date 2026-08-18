from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.persistence.conversation_mapper import (
    conversation_from_record,
    conversation_to_record,
    message_from_record,
    message_to_record,
)
from app.infrastructure.persistence.models.conversation import (
    ConversationMessageRecord,
    ConversationRecord,
)
from app.modules.conversation.domain import Conversation, Message, MessageRole
from tests.support.db_test_utils import SchemaHarness

SQL_SCRIPT = (
    Path(__file__).resolve().parents[2] / "sql" / "007_conversation_model_storage.sql"
)


def test_domain_records_round_trip_through_orm_mapping() -> None:
    created_at = datetime(2026, 8, 18, 9, 30, tzinfo=timezone.utc)
    updated_at = datetime(2026, 8, 18, 9, 35, tzinfo=timezone.utc)
    conversation = Conversation(
        id=uuid4(),
        created_at=created_at,
        updated_at=updated_at,
    )
    message = Message(
        id=uuid4(),
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="已收到。",
        sequence=2,
        created_at=updated_at,
    )

    conversation_record = conversation_to_record(conversation)
    message_record = message_to_record(message)

    assert conversation_from_record(conversation_record) == conversation
    assert message_from_record(message_record) == message


def test_conversation_orm_metadata_registers_required_tables_and_constraints() -> None:
    conversation_table = ConversationRecord.__table__
    message_table = ConversationMessageRecord.__table__

    assert conversation_table.name == "conversation"
    assert set(conversation_table.c.keys()) == {"id", "created_at", "updated_at"}
    assert set(message_table.c.keys()) == {
        "id",
        "conversation_id",
        "role",
        "content",
        "sequence",
        "created_at",
    }
    assert next(iter(message_table.foreign_keys)).ondelete == "CASCADE"
    assert {
        constraint.name for constraint in message_table.constraints if constraint.name
    } >= {
        "chk_conversation_message_role",
        "chk_conversation_message_content_not_blank",
        "chk_conversation_message_sequence_positive",
        "uq_conversation_message_conversation_sequence",
    }


def test_conversation_sql_script_is_executable_and_idempotent() -> None:
    harness = SchemaHarness("conversation_sql")
    harness.create_schema()
    try:
        script = SQL_SCRIPT.read_text(encoding="utf-8")
        with harness.test_engine.begin() as connection:
            connection.exec_driver_sql(script)
            connection.exec_driver_sql(script)
            table_names = set(
                connection.execute(
                    text(
                        """
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = current_schema()
                          AND tablename IN ('conversation', 'conversation_message')
                        """
                    )
                ).scalars()
            )

        assert table_names == {"conversation", "conversation_message"}
        assert "CREATE TABLE IF NOT EXISTS conversation" in script
        assert "CREATE TABLE IF NOT EXISTS conversation_message" in script
        assert "ON DELETE CASCADE" in script
        assert "chk_conversation_message_role" in script
        assert "uq_conversation_message_conversation_sequence" in script
    finally:
        harness.drop_schema()


def _new_domain_conversation() -> Conversation:
    return Conversation(id=uuid4())


def _new_domain_message(
    conversation_id,  # noqa: ANN001
    *,
    role: MessageRole = MessageRole.USER,
    content: str = "你好",
    sequence: int = 1,
) -> Message:
    return Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sequence=sequence,
    )


def test_conversation_and_message_persist_restore_and_cascade_delete() -> None:
    harness = SchemaHarness("conversation_persist")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            conversation = _new_domain_conversation()
            message = _new_domain_message(conversation.id, sequence=1)
            session.add_all(
                [conversation_to_record(conversation), message_to_record(message)]
            )
            session.commit()

            restored_conversation = conversation_from_record(
                session.get(ConversationRecord, conversation.id)
            )
            restored_message = message_from_record(
                session.get(ConversationMessageRecord, message.id)
            )
            assert restored_conversation == conversation
            assert restored_message == message

            session.delete(session.get(ConversationRecord, conversation.id))
            session.commit()
            assert session.get(ConversationMessageRecord, message.id) is None
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_message_cannot_reference_missing_conversation() -> None:
    harness = SchemaHarness("conversation_fk")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            session.add(
                message_to_record(_new_domain_message(uuid4()))
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            assert session.query(ConversationMessageRecord).count() == 0
        finally:
            session.close()
    finally:
        harness.drop_schema()


@pytest.mark.parametrize(
    "record",
    [
        ConversationMessageRecord(
            id=uuid4(),
            conversation_id=uuid4(),
            role="tool",
            content="内容",
            sequence=1,
        ),
        ConversationMessageRecord(
            id=uuid4(),
            conversation_id=uuid4(),
            role="user",
            content="   ",
            sequence=1,
        ),
        ConversationMessageRecord(
            id=uuid4(),
            conversation_id=uuid4(),
            role="user",
            content="内容",
            sequence=0,
        ),
    ],
)
def test_message_database_constraints_reject_invalid_values(
    record: ConversationMessageRecord,
) -> None:
    harness = SchemaHarness("conversation_constraints")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            conversation = ConversationRecord(id=record.conversation_id)
            session.add(conversation)
            session.commit()
            session.add(record)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            assert session.get(ConversationMessageRecord, record.id) is None
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_message_sequence_is_unique_per_conversation_only() -> None:
    harness = SchemaHarness("conversation_sequence")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            first_conversation = ConversationRecord(id=uuid4())
            second_conversation = ConversationRecord(id=uuid4())
            session.add_all([first_conversation, second_conversation])
            session.commit()

            session.add(
                ConversationMessageRecord(
                    id=uuid4(),
                    conversation_id=first_conversation.id,
                    role="user",
                    content="第一条",
                    sequence=1,
                )
            )
            session.commit()

            session.add(
                ConversationMessageRecord(
                    id=uuid4(),
                    conversation_id=first_conversation.id,
                    role="assistant",
                    content="重复顺序",
                    sequence=1,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                ConversationMessageRecord(
                    id=uuid4(),
                    conversation_id=second_conversation.id,
                    role="user",
                    content="另一会话第一条",
                    sequence=1,
                )
            )
            session.commit()
            assert session.query(ConversationMessageRecord).count() == 2
        finally:
            session.close()
    finally:
        harness.drop_schema()
