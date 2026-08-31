"""Conversation 写入能力的 Composition Root。"""

from sqlalchemy.orm import Session

from app.infrastructure.persistence.repositories.conversation_access_repository import (
    ConversationAccessRepository,
)
from app.infrastructure.persistence.repositories.conversation_event_repository import (
    ConversationEventRepository,
)
from app.infrastructure.persistence.repositories.conversation_history_read_repository import (
    ConversationHistoryReadRepository,
)
from app.infrastructure.persistence.repositories.conversation_list_read_repository import (
    ConversationListReadRepository,
)
from app.infrastructure.persistence.repositories.conversation_write_repository import (
    ConversationWriteRepository,
)
from app.platform.conversation.application import (
    CharacterCountContextMessageCostEstimator,
    ConversationAccessService,
    ConversationContextBuilder,
    ConversationHistoryReadService,
    ConversationListReadService,
    ConversationManagementService,
    ConversationRecentMessageReadService,
    ConversationTopicSummaryUpdateService,
    ConversationWriteService,
    RuleBasedConversationTopicSummaryGenerator,
)


def build_conversation_write_repository(session: Session) -> ConversationWriteRepository:
    """根据外部注入的数据库会话组装 Conversation 写仓储。"""

    return ConversationWriteRepository(session)


def build_conversation_access_service(session: Session) -> ConversationAccessService:
    return ConversationAccessService(ConversationAccessRepository(session))


def build_conversation_write_service(session: Session) -> ConversationWriteService:
    """组装 Conversation 写入应用服务及其具体持久化适配器。"""

    return ConversationWriteService(
        build_conversation_write_repository(session),
        topic_summary_generator=RuleBasedConversationTopicSummaryGenerator(),
    )


def build_conversation_history_read_repository(
    session: Session,
) -> ConversationHistoryReadRepository:
    """根据外部注入的数据库会话组装 Conversation 历史读仓储。"""

    return ConversationHistoryReadRepository(session)


def build_conversation_topic_summary_update_service(
    session: Session,
) -> ConversationTopicSummaryUpdateService:
    return ConversationTopicSummaryUpdateService(
        access=build_conversation_access_service(session),
        writer=build_conversation_write_service(session),
    )


def build_conversation_management_service(session: Session) -> ConversationManagementService:
    return ConversationManagementService(
        access=build_conversation_access_service(session),
        writer=build_conversation_write_repository(session),
    )


def build_conversation_history_read_service(
    session: Session,
) -> ConversationHistoryReadService:
    """组装 Conversation 历史读取应用服务及其只读适配器。"""

    return ConversationHistoryReadService(build_conversation_history_read_repository(session))


def build_conversation_recent_message_read_service(
    session: Session,
) -> ConversationRecentMessageReadService:
    """组装用于上下文构建的有界最近消息读取服务。"""

    return ConversationRecentMessageReadService(build_conversation_history_read_repository(session))


def build_conversation_list_read_repository(session: Session) -> ConversationListReadRepository:
    """根据外部注入的数据库会话组装会话摘要只读仓储。"""

    return ConversationListReadRepository(session)


def build_conversation_list_read_service(
    session: Session,
) -> ConversationListReadService:
    """组装主体范围 Conversation 摘要列表应用服务。"""

    return ConversationListReadService(build_conversation_list_read_repository(session))


def build_conversation_context_builder() -> ConversationContextBuilder:
    """组装使用默认字符成本计量的 Conversation 上下文构建服务。"""

    return ConversationContextBuilder(CharacterCountContextMessageCostEstimator())


def build_conversation_event_repository(session: Session) -> ConversationEventRepository:
    return ConversationEventRepository(session)
