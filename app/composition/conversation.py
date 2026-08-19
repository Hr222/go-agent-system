"""Conversation 写入能力的 Composition Root。"""

from sqlalchemy.orm import Session

from app.infrastructure.persistence.repositories.conversation_event_repository import (
    ConversationEventRepository,
)
from app.infrastructure.persistence.repositories.conversation_history_read_repository import (
    ConversationHistoryReadRepository,
)
from app.infrastructure.persistence.repositories.conversation_write_repository import (
    ConversationWriteRepository,
)
from app.modules.conversation.application import (
    CharacterCountContextMessageCostEstimator,
    ConversationContextBuilder,
    ConversationHistoryReadService,
    ConversationWriteService,
)


def build_conversation_write_repository(session: Session) -> ConversationWriteRepository:
    """根据外部注入的数据库会话组装 Conversation 写仓储。"""

    return ConversationWriteRepository(session)


def build_conversation_write_service(session: Session) -> ConversationWriteService:
    """组装 Conversation 写入应用服务及其具体持久化适配器。"""

    return ConversationWriteService(build_conversation_write_repository(session))


def build_conversation_history_read_repository(
    session: Session,
) -> ConversationHistoryReadRepository:
    """根据外部注入的数据库会话组装 Conversation 历史读仓储。"""

    return ConversationHistoryReadRepository(session)


def build_conversation_history_read_service(
    session: Session,
) -> ConversationHistoryReadService:
    """组装 Conversation 历史读取应用服务及其只读适配器。"""

    return ConversationHistoryReadService(build_conversation_history_read_repository(session))


def build_conversation_context_builder() -> ConversationContextBuilder:
    """组装使用默认字符成本计量的 Conversation 上下文构建服务。"""

    return ConversationContextBuilder(CharacterCountContextMessageCostEstimator())


def build_conversation_event_repository(session: Session) -> ConversationEventRepository:
    return ConversationEventRepository(session)
