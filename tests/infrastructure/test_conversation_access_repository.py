from __future__ import annotations

from uuid import uuid4

from app.infrastructure.persistence.repositories.conversation_access_repository import (
    ConversationAccessRepository,
)
from app.platform.conversation.domain import Conversation
from tests.support.db_test_utils import SchemaHarness


def test_repository_resolves_conversation_with_id_and_owner_subject() -> None:
    harness = SchemaHarness("conversation_access")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            repository = ConversationAccessRepository(session)
            owner_one = repository.save_conversation(
                Conversation(id=uuid4(), owner_subject="user-1")
            )
            owner_two = repository.save_conversation(
                Conversation(id=uuid4(), owner_subject="user-2")
            )

            assert repository.get_owned_conversation(
                conversation_id=owner_one.id,
                owner_subject="user-1",
            ) == owner_one
            assert repository.get_owned_conversation(
                conversation_id=owner_one.id,
                owner_subject="user-2",
            ) is None
            assert repository.get_owned_conversation(
                conversation_id=owner_two.id,
                owner_subject="user-1",
            ) is None
        finally:
            session.close()
    finally:
        harness.drop_schema()
