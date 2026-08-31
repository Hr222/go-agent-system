"""Conversation 应用依赖的端口。"""

from app.platform.conversation.domain import MAX_TOPIC_SUMMARY_LENGTH
from app.platform.conversation.ports.access_port import ConversationAccessPort
from app.platform.conversation.ports.context_cost_port import ContextMessageCostEstimator
from app.platform.conversation.ports.event_port import (
    ConversationEventReadPort,
    ConversationEventWritePort,
)
from app.platform.conversation.ports.read_port import (
    DEFAULT_CONVERSATION_LIST_PAGE_SIZE,
    DEFAULT_HISTORY_PAGE_SIZE,
    DEFAULT_RECENT_MESSAGE_WINDOW_SIZE,
    MAX_CONVERSATION_LIST_PAGE_SIZE,
    MAX_HISTORY_PAGE_SIZE,
    MAX_RECENT_MESSAGE_WINDOW_SIZE,
    ConversationHistoryPage,
    ConversationListCursor,
    ConversationListReadPort,
    ConversationReadPort,
    ConversationRecentMessageReadPort,
    ConversationRecentMessageWindow,
    ConversationSummary,
    ConversationSummaryPage,
)
from app.platform.conversation.ports.topic_summary import ConversationTopicSummaryGenerator
from app.platform.conversation.ports.write_port import (
    DEFAULT_PINNED_CONVERSATION_LIMIT,
    ConversationWritePort,
)

__all__ = [
    "ConversationAccessPort",
    "ConversationListCursor",
    "ConversationListReadPort",
    "ConversationHistoryPage",
    "ConversationRecentMessageReadPort",
    "ConversationRecentMessageWindow",
    "ContextMessageCostEstimator",
    "ConversationEventReadPort",
    "ConversationEventWritePort",
    "ConversationReadPort",
    "ConversationSummary",
    "ConversationSummaryPage",
    "ConversationWritePort",
    "DEFAULT_PINNED_CONVERSATION_LIMIT",
    "ConversationTopicSummaryGenerator",
    "MAX_TOPIC_SUMMARY_LENGTH",
    "DEFAULT_CONVERSATION_LIST_PAGE_SIZE",
    "DEFAULT_HISTORY_PAGE_SIZE",
    "MAX_CONVERSATION_LIST_PAGE_SIZE",
    "MAX_HISTORY_PAGE_SIZE",
    "DEFAULT_RECENT_MESSAGE_WINDOW_SIZE",
    "MAX_RECENT_MESSAGE_WINDOW_SIZE",
]
