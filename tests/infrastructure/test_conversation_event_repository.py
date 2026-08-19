from __future__ import annotations

from pathlib import Path

from app.infrastructure.persistence.models.conversation import (
    ConversationEventRecord,
    ConversationRecord,
)
from app.infrastructure.persistence.repositories.conversation_event_repository import (
    ConversationEventRepository,
)
from app.modules.conversation.domain import Conversation, ConversationEvent
from tests.support.db_test_utils import SchemaHarness


def test_event_sql_is_idempotent_and_repository_orders_by_sequence() -> None:
    harness = SchemaHarness("conversation_event")
    harness.create_schema()
    script = (
        Path(__file__).resolve().parents[2] / "sql" / "007_conversation_model_storage.sql"
    ).read_text(encoding="utf-8")
    event_script = (
        Path(__file__).resolve().parents[2] / "sql" / "008_conversation_event.sql"
    ).read_text(encoding="utf-8")
    try:
        with harness.test_engine.begin() as connection:
            connection.exec_driver_sql(script)
            connection.exec_driver_sql(event_script)
            connection.exec_driver_sql(event_script)
        session = harness.session_local()
        try:
            conversation = Conversation()
            session.add(ConversationRecord(id=conversation.id))
            session.commit()
            repository = ConversationEventRepository(session)
            event = ConversationEvent(
                conversation_id=conversation.id,
                event_type="agent_call",
                call_id="call-1",
                capability_code="agent.tender.generate_bid_skeleton",
                sequence=repository.next_event_sequence(conversation_id=conversation.id),
                payload={"status": "requested"},
            )
            repository.save_event(event)
            restored = repository.list_events(conversation_id=conversation.id, call_id="call-1")
            assert restored == (event,)
            assert session.query(ConversationEventRecord).count() == 1
        finally:
            session.close()
    finally:
        harness.drop_schema()
