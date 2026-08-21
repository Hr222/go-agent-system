from __future__ import annotations

from sqlalchemy import select

from app.composition.conversation import build_conversation_write_service
from app.composition.dialogue import build_basic_dialogue_runtime
from app.infrastructure.persistence.models.conversation import ConversationMessageRecord
from app.modules.dialogue.application import DialogueCommand
from app.modules.llm.contracts import ChatLlmResult
from tests.support.db_test_utils import SchemaHarness


class RecordingChatLlm:
    def __init__(self) -> None:
        self.requests = []

    def invoke(self, request):  # noqa: ANN001
        self.requests.append(request)
        return ChatLlmResult(
            content="数据库集成回答",
            model="dialogue-test",
            prompt_version="dialogue-basic-chat-v1",
            total_tokens=9,
        )


def test_dialogue_runtime_persists_user_and_assistant_messages() -> None:
    harness = SchemaHarness("dialogue_basic")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            conversation = build_conversation_write_service(session).create_conversation(
                owner_subject="user-1"
            )
            llm = RecordingChatLlm()
            runtime = build_basic_dialogue_runtime(session, llm)

            result = runtime.execute(
                DialogueCommand(
                    conversation_id=conversation.id,
                    message="数据库中的问题",
                )
            )

            records = list(
                session.scalars(
                    select(ConversationMessageRecord).order_by(
                        ConversationMessageRecord.sequence.asc()
                    )
                )
            )
            assert [record.role for record in records] == ["user", "assistant"]
            assert [record.content for record in records] == [
                "数据库中的问题",
                "数据库集成回答",
            ]
            assert result.user_message.sequence == 1
            assert result.assistant_message.sequence == 2
            assert result.conversation_id == conversation.id
            assert len(llm.requests) == 1
        finally:
            session.close()
    finally:
        harness.drop_schema()
